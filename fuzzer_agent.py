"""
fuzzer_agent.py
---------------
LangChain + Groq (Llama-3.3) tabanlı Fuzzer Ajanı.

Bu modül:
  - Hedef API şemasını (UserRegistration Pydantic modeli) analiz eder
  - Groq LLM kullanarak yaratıcı, yıkıcı JSON payload'ları üretir
  - SQL Injection, XSS, overflow, negatif sayı, geçersiz tip gibi
    edge-case saldırı vektörlerini kapsar
"""

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("fuzzer_agent")

# ---------------------------------------------------------------------------
# Hedef API Şeması – Fuzzer bu şemayı temel alır
# ---------------------------------------------------------------------------
TARGET_SCHEMA = """
API Endpoint: POST /register
Content-Type: application/json

Beklenen JSON Şeması:
{
  "username": string (zorunlu),
  "age":      integer (zorunlu),
  "email":    string (zorunlu),
  "bio":      string (isteğe bağlı, varsayılan: ""),
  "score":    float  (isteğe bağlı, varsayılan: 0.0),
  "metadata": object (isteğe bağlı, varsayılan: {})
}

Bilinen İç Zafiyetler (test hedefleri):
1. age=0 → ZeroDivisionError (500)
2. age negatif → beklenmedik matematiksel sonuç
3. bio uzunluğu > 10.000 karakter → MemoryError (500)
4. metadata içinde 'formula' anahtarı → eval() injection → RCE / Runtime Error (500)
5. username içinde SQL özel karakterler → SQL Injection simülasyonu (log poisoning)
6. score değeri aşırı büyük → OverflowError (500)
7. Geçersiz tip gönderilmesi → Pydantic doğrulama hatası (422)
"""

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
Sen bir kıdemli API güvenlik uzmanı ve kötü niyetli fuzzer ajanısın.
Görevin: verilen API şemasını analiz ederek API'yi çökertecek (HTTP 500 döndürtecek)
en yaratıcı ve yıkıcı JSON payload'larını üretmek.

KURALLAR:
- Her payload bir Python dict gibi JSON formatında olmalı.
- Ürettiğin tüm payload'ları TEK bir JSON array içinde döndür.
- Yorum satırı, açıklama veya markdown bloğu KULLANMA – sadece saf JSON çıktısı ver.
- Şemadaki tüm alanları hedef al.
- En az 10, en fazla 15 farklı payload üret.
- Her payload farklı bir saldırı vektörünü temsil etmeli:
    * SQL Injection (username, email)
    * XSS payload (bio, username)
    * Sıfır/negatif yaş (age)
    * Çok büyük sayı (score, age)
    * Çok uzun string (bio > 10000 karakter)
    * Eval/formula injection (metadata.formula)
    * Null/None değerler (zorunlu alanlarda)
    * Unicode/emoji/özel karakter karmaşası
    * Yanlış tipler (string yerine number vb.)
    * Nested/deep object injection (metadata)
    * Empty string zorunlu alanlarda
    * Çok büyük integer overflow
    * Boolean injection
    * Array injection (scalar beklenirken)
"""


# ---------------------------------------------------------------------------
# Fuzzer Ajanı Sınıfı
# ---------------------------------------------------------------------------
class FuzzerAgent:
    """
    Groq LLM kullanarak hedef API için yıkıcı JSON payload'ları üretir.
    """

    def __init__(self, groq_api_key: str, model: str = "llama-3.3-70b-versatile"):
        """
        Args:
            groq_api_key: Groq API anahtarı
            model: Kullanılacak Groq modeli
        """
        self.model_name = model
        self.llm = ChatGroq(
            api_key=groq_api_key,
            model=model,
            temperature=0.9,       # Yüksek yaratıcılık
            max_tokens=4096,
        )
        logger.info("FuzzerAgent başlatıldı: model=%s", model)

    def generate_payloads(self) -> list[dict[str, Any]]:
        """
        LLM'e hedef API şemasını göndererek yıkıcı payload listesi üretir.

        Returns:
            Üretilen JSON payload'larının listesi
        """
        logger.info("LLM'den fuzzing payload'ları isteniyor...")

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Aşağıdaki API şeması için yıkıcı fuzzing payload'ları üret:\n\n"
                    f"{TARGET_SCHEMA}\n\n"
                    "ÖNEMLI: Sadece JSON array döndür. Başka hiçbir metin ekleme."
                )
            ),
        ]

        try:
            response = self.llm.invoke(messages)
            raw_content: str = response.content
            logger.debug("LLM ham yanıtı:\n%s", raw_content)

            payloads = self._parse_llm_response(raw_content)
            logger.info("LLM %d adet payload üretti.", len(payloads))
            return payloads

        except Exception as exc:
            logger.error("LLM payload üretiminde hata: %s", exc, exc_info=True)
            # Fallback: Elle yazılmış temel payload'lar
            logger.warning("Fallback payload'lar kullanılıyor.")
            return self._fallback_payloads()

    def _parse_llm_response(self, raw: str) -> list[dict[str, Any]]:
        """
        LLM çıktısından JSON array çıkarır.

        Args:
            raw: LLM'den gelen ham metin

        Returns:
            Parsed payload listesi
        """
        # Markdown kod bloğu varsa temizle
        cleaned = re.sub(r"```(?:json)?", "", raw).strip()
        cleaned = cleaned.rstrip("`").strip()

        # İlk '[' ile son ']' arasını çıkar
        start = cleaned.find("[")
        end = cleaned.rfind("]")

        if start == -1 or end == -1:
            logger.warning("JSON array bulunamadı, ham metin parse deneniyor.")
            raise ValueError("LLM çıktısında geçerli JSON array yok.")

        json_str = cleaned[start : end + 1]

        try:
            payloads = json.loads(json_str)
            if not isinstance(payloads, list):
                raise ValueError("JSON çıktısı list değil.")
            return payloads
        except json.JSONDecodeError as exc:
            logger.error("JSON parse hatası: %s", exc)
            logger.debug("Parse edilemeyen string:\n%s", json_str[:500])
            raise

    def _fallback_payloads(self) -> list[dict[str, Any]]:
        """
        LLM başarısız olursa kullanılacak elle yazılmış fallback payload'lar.

        Returns:
            Temel fuzzing payload listesi
        """
        long_bio = "A" * 10_001  # MemoryError tetikler

        return [
            # 1. Sıfır yaş → ZeroDivisionError
            {"username": "test", "age": 0, "email": "t@t.com"},
            # 2. Negatif yaş
            {"username": "test", "age": -999, "email": "t@t.com"},
            # 3. Çok uzun bio → MemoryError
            {"username": "test", "age": 25, "email": "t@t.com", "bio": long_bio},
            # 4. Formula eval injection
            {
                "username": "test",
                "age": 25,
                "email": "t@t.com",
                "metadata": {"formula": "__import__('os').system('id')"},
            },
            # 5. SQL Injection
            {
                "username": "' OR '1'='1'; DROP TABLE users; --",
                "age": 25,
                "email": "sql@inject.com",
            },
            # 6. XSS payload
            {
                "username": "<script>alert('XSS')</script>",
                "age": 25,
                "email": "xss@test.com",
                "bio": "<img src=x onerror=alert(1)>",
            },
            # 7. Çok büyük score → OverflowError
            {"username": "test", "age": 25, "email": "t@t.com", "score": 1e309},
            # 8. String yerine integer (type confusion)
            {"username": 12345, "age": "twenty", "email": "t@t.com"},
            # 9. Null değerler zorunlu alanlarda
            {"username": None, "age": None, "email": None},
            # 10. Çok büyük integer overflow
            {
                "username": "test",
                "age": 99999999999999999999999,
                "email": "t@t.com",
            },
            # 11. Boş string zorunlu alanlarda
            {"username": "", "age": 25, "email": ""},
            # 12. Nested injection metadata
            {
                "username": "test",
                "age": 25,
                "email": "t@t.com",
                "metadata": {"formula": "1/0", "nested": {"formula": "exit()"}},
            },
            # 13. Unicode/emoji karmaşası
            {
                "username": "😈💀🔥" * 100,
                "age": 25,
                "email": "unicode@💀.com",
                "bio": "\x00\x1f\x7f" * 50,
            },
            # 14. Boolean injection
            {"username": True, "age": False, "email": True},
            # 15. Array injection (scalar beklenirken)
            {
                "username": ["admin", "root"],
                "age": [1, 2, 3],
                "email": {"key": "value"},
            },
        ]
