"""
main.py
-------
Uygulamanin giris noktasi.

Akis:
  1. .env dosyasindan GROQ_API_KEY yuklenir.
  2. target_api.py subprocess ile arka planda baslatilir.
  3. API'nin ayaga kalkmasi beklenir.
  4. FuzzerAgent, Groq LLM kullanarak yikici payload'lar uretir.
  5. ChaosEngine payload'lari hedef API'ye gonderir.
  6. Sonuclar analiz edilir ve bug_report.md uretilir.
  7. Arka plan API sureci temiz sekilde kapatilir.
"""

import io
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Logging – Root logger yapilandirmasi (tum moduller bu formati kullanir)
# ---------------------------------------------------------------------------
# Force UTF-8 on stdout to avoid cp1254 UnicodeEncodeError on Windows
_utf8_stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(_utf8_stdout),
        logging.FileHandler("chaos_run.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

# ---------------------------------------------------------------------------
# Proje kök dizinini Python path'e ekle
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# .env yükleme
# ---------------------------------------------------------------------------
env_path = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=env_path)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

TARGET_HOST = "127.0.0.1"
TARGET_PORT = 8000
TARGET_URL = f"http://{TARGET_HOST}:{TARGET_PORT}"


# ---------------------------------------------------------------------------
# Yardımcı: Target API'yi subprocess ile başlat
# ---------------------------------------------------------------------------
def start_target_api() -> subprocess.Popen:
    """
    target_api.py'yi arka planda subprocess ile başlatır.

    Returns:
        subprocess.Popen nesnesi
    """
    logger.info("[SETUP] Target API baslatiliyor (subprocess)...")
    target_script = str(PROJECT_ROOT / "target_api.py")

    try:
        process = subprocess.Popen(
            [sys.executable, target_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        logger.info("[OK] Target API sureci baslatildi. PID: %d", process.pid)
        return process

    except Exception as exc:
        logger.critical("Target API başlatılamadı: %s", exc, exc_info=True)
        sys.exit(1)


def stop_target_api(process: subprocess.Popen) -> None:
    """
    Arka plan API sürecini temiz şekilde sonlandırır.

    Args:
        process: Kapatılacak Popen süreci
    """
    logger.info("[STOP] Target API kapatiliyor (PID: %d)...", process.pid)
    try:
        process.terminate()
        try:
            process.wait(timeout=5)
            logger.info("[OK] Target API sureci duzgun kapatildi.")
        except subprocess.TimeoutExpired:
            logger.warning("Surec yanit vermedi, zorla kapatiliyor (kill)...")
            process.kill()
            process.wait()
            logger.info("[KILL] Target API sureci kill ile kapatildi.")
    except Exception as exc:
        logger.error("API kapatma sırasında hata: %s", exc)


# ---------------------------------------------------------------------------
# Ana orkestrasyon fonksiyonu
# ---------------------------------------------------------------------------
def main() -> int:
    """
    Tüm fuzzing sürecini yönetir.

    Returns:
        Çıkış kodu (0: başarı, 1: hata)
    """
    logger.info("=" * 60)
    logger.info("  [*] AI-Powered API Chaos & Fuzzing Motoru")
    logger.info("  Groq Llama-3.3 + LangChain + FastAPI")
    logger.info("=" * 60)

    # ── Ön Kontroller ─────────────────────────────────────────────────
    if not GROQ_API_KEY:
        logger.critical(
            "GROQ_API_KEY bulunamadi! .env dosyasini kontrol edin: %s", env_path
        )
        return 1

    logger.info("[OK] GROQ_API_KEY yuklendi. (ilk 8 karakter: %s...)", GROQ_API_KEY[:8])

    # ── Target API'yi Başlat ───────────────────────────────────────────
    api_process = start_target_api()
    # Uvicorn'un başlaması için kısa bekleme
    time.sleep(2)

    exit_code = 0
    try:
        # ── ChaosEngine'i Başlat ───────────────────────────────────────
        # Import burada yapılır — import hatası main'de yakalanabilsin
        from chaos_engine import ChaosEngine
        from fuzzer_agent import FuzzerAgent

        engine = ChaosEngine(target_url=TARGET_URL)

        # API'nin hazır olmasını bekle
        if not engine.wait_for_api(max_wait=30):
            logger.error("Hedef API baslatılamadı. Fuzzing iptal ediliyor.")
            return 1

        # Payload Uretimi (LLM)
        logger.info("[LLM] FuzzerAgent baslatiliyor...")
        agent = FuzzerAgent(groq_api_key=GROQ_API_KEY)

        logger.info("[LLM] Yikici payload'lar uretiliyor...")
        payloads = agent.generate_payloads()
        logger.info("[LLM] Toplam %d payload uretildi.", len(payloads))

        # Fuzzing Calistir
        logger.info("[FUZZ] Fuzzing basliyor...")
        session = engine.run(payloads)

        # Bug Report Uret
        report_path = engine.generate_bug_report(session)

        # Ozet
        logger.info("=" * 60)
        logger.info("  [DONE] FUZZING OTURUMU TAMAMLANDI")
        logger.info("  Gonderilen Payload  : %d", session.total_sent)
        logger.info("  Crash (HTTP 500)    : %d", session.total_crashes)
        logger.info("  Baglanti Hatalari   : %d", session.total_errors)
        logger.info("  Crash Orani         : %.1f%%", session.crash_rate)
        logger.info("  Toplam Sure         : %.1f saniye", session.duration_seconds)
        logger.info("  Bug Report          : %s", report_path.resolve())
        logger.info("  Log Dosyasi         : chaos_run.log")
        logger.info("=" * 60)

        if session.total_crashes > 0:
            logger.warning(
                "[!!!] %d adet HTTP 500 (crash) tespit edildi! Detaylar icin bug_report.md inceleniyor.",
                session.total_crashes,
            )
        else:
            logger.info("[OK] Hicbir crash tespit edilmedi.")

    except KeyboardInterrupt:
        logger.info("[INTERRUPT] Kullanici tarafindan iptal edildi (Ctrl+C).")
        exit_code = 130

    except Exception as exc:
        logger.critical("Beklenmeyen kritik hata: %s", exc, exc_info=True)
        exit_code = 1

    finally:
        # ── API Sürecini Temiz Kapat ───────────────────────────────────
        stop_target_api(api_process)

    return exit_code


# ---------------------------------------------------------------------------
# Giriş Noktası
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
