"""
chaos_engine.py
---------------
Orkestratör: Fuzzer payload'larını hedef API'ye gönderir,
HTTP 500 hatalarını yakalar ve Markdown formatında Bug Report üretir.

Sorumluluklar:
  - FuzzerAgent'ten payload'ları alır
  - requests ile POST /register endpoint'ine gönderir
  - Her yanıtı loglar
  - 500 hataları analiz eder
  - bug_report.md dosyası üretir
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from requests.exceptions import ConnectionError, RequestException, Timeout

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("chaos_engine")

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT = 10          # saniye
DEFAULT_RETRY_WAIT = 0.5      # saniye (istekler arası bekleme)
REPORT_FILE = Path("bug_report.md")


# ---------------------------------------------------------------------------
# Veri sınıfları
# ---------------------------------------------------------------------------
@dataclass
class TestResult:
    """Tek bir fuzzing test sonucunu temsil eder."""
    payload_index: int
    payload: dict[str, Any]
    status_code: int | None
    response_body: str
    duration_ms: float
    is_crash: bool
    error_detail: str = ""
    exception: str = ""


@dataclass
class FuzzingSession:
    """Tüm fuzzing oturumunun özetini tutar."""
    target_url: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    results: list[TestResult] = field(default_factory=list)
    total_sent: int = 0
    total_crashes: int = 0
    total_errors: int = 0

    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def crash_rate(self) -> float:
        if self.total_sent == 0:
            return 0.0
        return (self.total_crashes / self.total_sent) * 100


# ---------------------------------------------------------------------------
# Chaos Engine
# ---------------------------------------------------------------------------
class ChaosEngine:
    """
    Fuzzer payload'larını hedef API'ye gönderen ve sonuçları raporlayan orkestratör.
    """

    def __init__(
        self,
        target_url: str = "http://127.0.0.1:8000",
        timeout: int = DEFAULT_TIMEOUT,
        retry_wait: float = DEFAULT_RETRY_WAIT,
        report_path: Path = REPORT_FILE,
    ):
        """
        Args:
            target_url: Hedef API'nin base URL'i
            timeout: Her istek için timeout (saniye)
            retry_wait: İstekler arası bekleme süresi (saniye)
            report_path: Bug report çıktı yolu
        """
        self.target_url = target_url.rstrip("/")
        self.endpoint = f"{self.target_url}/register"
        self.timeout = timeout
        self.retry_wait = retry_wait
        self.report_path = report_path
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        logger.info("ChaosEngine başlatıldı: target=%s", self.endpoint)

    def wait_for_api(self, max_wait: int = 30) -> bool:
        """
        Hedef API'nin ayağa kalkmasını bekler.

        Args:
            max_wait: Maksimum bekleme süresi (saniye)

        Returns:
            API hazır ise True, timeout ise False
        """
        health_url = f"{self.target_url}/health"
        logger.info("[ChaosEngine] API bekleniyor: %s", health_url)

        for attempt in range(max_wait):
            try:
                resp = self.session.get(health_url, timeout=3)
                if resp.status_code == 200:
                    logger.info("[OK] Hedef API hazir. (%.1f saniyede)", attempt + 1)
                    return True
            except (ConnectionError, Timeout):
                pass

            time.sleep(1)
            if attempt % 5 == 0 and attempt > 0:
                logger.info("[...] API bekleniyor... (%d/%d)", attempt, max_wait)

        logger.error("[FAIL] API %d saniye icinde ayaga kalkmadi.", max_wait)
        return False

    def send_payload(self, payload: dict[str, Any], index: int) -> TestResult:
        """
        Tek bir payload'ı hedef API'ye gönderir.

        Args:
            payload: Gönderilecek JSON payload
            index: Payload sıra numarası

        Returns:
            TestResult nesnesi
        """
        logger.info(
            "[SEND] Payload #%d gonderiliyor: %s",
            index,
            json.dumps(payload, ensure_ascii=True)[:120],
        )

        start = time.perf_counter()
        status_code = None
        response_body = ""
        is_crash = False
        error_detail = ""
        exception_str = ""

        try:
            response = self.session.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            status_code = response.status_code
            response_body = response.text[:2000]  # max 2000 char

            if status_code == 500:
                is_crash = True
                try:
                    error_detail = response.json().get("detail", response_body)
                except Exception:
                    error_detail = response_body

                logger.warning(
                    "[CRASH!] Payload #%d -> HTTP 500 | Detay: %s",
                    index,
                    str(error_detail)[:200],
                )
            elif status_code == 422:
                logger.info("[WARN] Payload #%d -> HTTP 422 (Validation Error)", index)
            elif status_code == 201:
                logger.info("[OK] Payload #%d -> HTTP 201 (Basarili)", index)
            else:
                logger.info("[INFO] Payload #%d -> HTTP %d", index, status_code)

        except Timeout:
            elapsed_ms = (time.perf_counter() - start) * 1000
            exception_str = "RequestTimeout"
            logger.warning("[TIMEOUT] Payload #%d -> Timeout (%d s)", index, self.timeout)

        except ConnectionError as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            exception_str = f"ConnectionError: {exc}"
            logger.error("[CONN ERR] Payload #%d -> Baglanti hatasi: %s", index, exc)

        except RequestException as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            exception_str = f"RequestException: {exc}"
            logger.error("[REQ ERR] Payload #%d -> Istek hatasi: %s", index, exc)

        return TestResult(
            payload_index=index,
            payload=payload,
            status_code=status_code,
            response_body=response_body,
            duration_ms=elapsed_ms,
            is_crash=is_crash,
            error_detail=str(error_detail),
            exception=exception_str,
        )

    def run(self, payloads: list[dict[str, Any]]) -> FuzzingSession:
        """
        Tüm payload'ları sırayla gönderir ve oturum özetini döndürür.

        Args:
            payloads: Fuzzer'ın ürettiği payload listesi

        Returns:
            FuzzingSession özet nesnesi
        """
        session = FuzzingSession(target_url=self.target_url)
        logger.info("[START] Fuzzing oturumu basladi. Toplam payload: %d", len(payloads))

        for idx, payload in enumerate(payloads, start=1):
            result = self.send_payload(payload, idx)
            session.results.append(result)
            session.total_sent += 1

            if result.is_crash:
                session.total_crashes += 1
            if result.exception:
                session.total_errors += 1

            # İstekler arası kısa bekleme (rate limit ve log okunabilirliği)
            time.sleep(self.retry_wait)

        session.end_time = datetime.now()
        logger.info(
            "[DONE] Fuzzing tamamlandi. Gonderilen: %d | Crash: %d | Hata: %d | Sure: %.1fs",
            session.total_sent,
            session.total_crashes,
            session.total_errors,
            session.duration_seconds,
        )
        return session

    def generate_bug_report(self, session: FuzzingSession) -> Path:
        """
        Fuzzing oturumunun sonuçlarından Markdown Bug Report üretir.

        Args:
            session: Tamamlanmış FuzzingSession

        Returns:
            Oluşturulan rapor dosyasının Path'i
        """
        logger.info("[REPORT] Bug Report olusturuluyor: %s", self.report_path)
        crashes = [r for r in session.results if r.is_crash]

        lines: list[str] = []

        # ── Başlık ──────────────────────────────────────────────────────────
        lines += [
            "# 🐛 AI-Powered API Chaos & Fuzzing — Bug Report",
            "",
            f"> **Oluşturma Tarihi:** {session.start_time.strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"> **Hedef API:** `{session.target_url}`  ",
            f"> **Fuzzing Engine:** LangChain + Groq Llama-3.3-70b-versatile  ",
            "",
            "---",
            "",
        ]

        # ── Yönetici Özeti ───────────────────────────────────────────────────
        lines += [
            "## 📊 Yönetici Özeti",
            "",
            "| Metrik | Değer |",
            "|--------|-------|",
            f"| Toplam Gönderilen Payload | **{session.total_sent}** |",
            f"| Crash Sayısı (HTTP 500) | **{session.total_crashes}** |",
            f"| Bağlantı/İstek Hataları | **{session.total_errors}** |",
            f"| Crash Oranı | **{session.crash_rate:.1f}%** |",
            f"| Toplam Test Süresi | **{session.duration_seconds:.1f} saniye** |",
            f"| Risk Seviyesi | **{'🔴 KRİTİK' if session.crash_rate > 50 else '🟠 YÜKSEK' if session.crash_rate > 20 else '🟡 ORTA'}** |",
            "",
            "---",
            "",
        ]

        # ── Bulunan Güvenlik Açıkları ─────────────────────────────────────
        if crashes:
            lines += [
                "## 🚨 Bulunan Güvenlik Açıkları / Crash'ler",
                "",
            ]

            vuln_categories: dict[str, list[TestResult]] = {}
            for crash in crashes:
                detail = crash.error_detail.lower()
                if "sıfıra bölme" in detail or "zerodivision" in detail:
                    cat = "ZeroDivisionError (Sıfıra Bölme)"
                elif "bellek" in detail or "memory" in detail:
                    cat = "MemoryError (Bellek Taşması)"
                elif "eval" in detail or "formula" in detail or "çalışma zamanı" in detail:
                    cat = "Eval Injection / RCE Riski"
                elif "taşma" in detail or "overflow" in detail:
                    cat = "OverflowError (Sayısal Taşma)"
                else:
                    cat = "Diğer / Genel İç Hata"

                vuln_categories.setdefault(cat, []).append(crash)

            for category, cat_crashes in vuln_categories.items():
                severity_icon = "🔴" if "injection" in category.lower() or "rce" in category.lower() else "🟠"
                lines += [
                    f"### {severity_icon} {category}",
                    "",
                    f"**Etkilenen Payload Sayısı:** {len(cat_crashes)}",
                    "",
                ]

                for crash in cat_crashes:
                    payload_json = json.dumps(
                        crash.payload, ensure_ascii=False, indent=2
                    )
                    # Uzun string'leri kısalt
                    if len(payload_json) > 800:
                        payload_json = payload_json[:800] + "\n  ... (kısaltıldı)"

                    lines += [
                        f"#### Payload #{crash.payload_index}",
                        "",
                        "**Gönderilen Payload:**",
                        "```json",
                        payload_json,
                        "```",
                        "",
                        f"**HTTP Durum Kodu:** `{crash.status_code}`  ",
                        f"**Yanıt Süresi:** `{crash.duration_ms:.1f}ms`  ",
                        f"**Hata Detayı:** `{crash.error_detail[:300]}`  ",
                        "",
                    ]

                lines.append("---")
                lines.append("")
        else:
            lines += [
                "## ✅ Crash Bulunamadı",
                "",
                "Fuzzing sırasında HTTP 500 hatası tetiklenemedi.",
                "",
                "---",
                "",
            ]

        # ── Tüm Test Sonuçları ─────────────────────────────────────────────
        lines += [
            "## 📋 Tüm Test Sonuçları",
            "",
            "| # | HTTP Durum | Süre (ms) | Sonuç | Hata Özeti |",
            "|---|-----------|-----------|-------|-----------|",
        ]

        for r in session.results:
            status_emoji = {
                201: "✅",
                422: "⚠️",
                500: "💥",
            }.get(r.status_code, "❓")

            detail_short = (r.error_detail or r.exception or "-")[:60]
            lines.append(
                f"| {r.payload_index} | `{r.status_code or 'ERR'}` "
                f"| {r.duration_ms:.1f} "
                f"| {status_emoji} "
                f"| {detail_short} |"
            )

        lines += [
            "",
            "---",
            "",
        ]

        # ── Öneriler ────────────────────────────────────────────────────────
        lines += [
            "## 🛡️ Güvenlik Önerileri",
            "",
            "### Kritik Düzeltmeler",
            "",
            "1. **ZeroDivisionError**: `age` değeri için `age > 0` doğrulaması zorunlu kılınmalı.",
            "2. **Eval Injection (RCE)**: `eval()` kullanımı tamamen kaldırılmalı. "
            "Formüller için `ast.literal_eval()` veya beyaz liste kullanılmalı.",
            "3. **MemoryError**: `bio` alanı için maksimum uzunluk Pydantic `Field(max_length=10000)` "
            "ile sınırlandırılmalı.",
            "4. **OverflowError**: `score` alanı için `Field(le=1e308)` sınırı eklenmeli.",
            "5. **SQL Injection**: Parametre tabanlı sorgular (prepared statements) kullanılmalı. "
            "Hiçbir kullanıcı girdisi doğrudan sorguya eklenmemeli.",
            "",
            "### Genel Güvenlik Pratikleri",
            "",
            "- Input sanitization tüm endpoint'lerde zorunlu olmalı.",
            "- Rate limiting eklenmelidir (örn: slowapi).",
            "- Hata mesajları iç stack trace içermemeli (information disclosure).",
            "- Tüm giriş alanları için tip ve aralık doğrulaması Pydantic validator ile yapılmalı.",
            "- Security headers (CORS, CSP) yapılandırılmalı.",
            "",
            "---",
            "",
        ]

        # ── Araç Bilgisi ─────────────────────────────────────────────────────
        lines += [
            "## 🤖 Test Aracı Hakkında",
            "",
            "Bu rapor **AI-Powered API Chaos & Fuzzing Motoru** tarafından otomatik olarak üretilmiştir.",
            "",
            "| Bileşen | Versiyon/Model |",
            "|---------|---------------|",
            "| LLM | Groq Llama-3.3-70b-versatile |",
            "| Framework | LangChain + FastAPI |",
            "| Test Türü | Black-box Fuzzing + Edge-case Generation |",
            "",
            "> *Bu rapor yalnızca eğitim ve güvenlik araştırması amacıyla üretilmiştir.*",
            "",
        ]

        # ── Dosyaya Yaz ────────────────────────────────────────────────────
        report_content = "\n".join(lines)
        try:
            self.report_path.write_text(report_content, encoding="utf-8")
            logger.info("[SAVED] Bug Report kaydedildi: %s", self.report_path.resolve())
        except OSError as exc:
            logger.error("Bug Report yazılamadı: %s", exc)

        return self.report_path
