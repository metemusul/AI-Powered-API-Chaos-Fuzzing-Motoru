"""
target_api.py
-------------
Hedef (Kurban) FastAPI Uygulaması.

Bu API, bilerek bırakılmış güvenlik açıkları içerir:
  - Negatif yaş kontrolü eksikliği (ValueError)
  - Çok uzun string'lerde bellek/overflow hatası
  - Geçersiz tip dönüşümleri (eval injection)
  - SQL Injection benzeri string interpolasyonu
  - XSS payload'larında log injection

Bu dosya doğrudan çalıştırılabilir veya main.py tarafından subprocess ile başlatılır.
"""

import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

# ---------------------------------------------------------------------------
# Logging yapılandırması
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("target_api")

# ---------------------------------------------------------------------------
# FastAPI Uygulaması
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Chaos Target API",
    description="Kasıtlı zafiyetler barındıran örnek API (fuzzing hedefi)",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Request Şeması (Pydantic Model)
# ---------------------------------------------------------------------------
class UserRegistration(BaseModel):
    username: str
    age: int
    email: str
    bio: Optional[str] = ""
    score: Optional[float] = 0.0
    metadata: Optional[dict] = {}


# ---------------------------------------------------------------------------
# Yardımcı: Bilerek zafiyetli iç fonksiyonlar
# ---------------------------------------------------------------------------

def _validate_age(age: int) -> str:
    """
    ZAFİYET 1: Negatif yaş kontrolü yok.
    Negatif değer geldiğinde matematiksel işlem ValueError fırlatır.
    """
    # Kasıtlı olarak negatif kontrol yapılmıyor
    result = 100 // age  # age=0 → ZeroDivisionError, age<0 → beklenmedik sonuç
    return f"Kalan yıllar: {result}"


def _process_bio(bio: str) -> str:
    """
    ZAFİYET 2: Aşırı uzun bio string'lerde RAM taşması simülasyonu.
    10_000 karakterden uzun bio gelirse kasıtlı exception fırlatılır.
    """
    if len(bio) > 10_000:
        raise MemoryError(f"Bio alanı çok uzun: {len(bio)} karakter (max 10,000)")

    # ZAFİYET 3: Eval injection – metadata içindeki 'formula' alanı doğrudan eval edilir
    return bio.strip()


def _build_sql_query(username: str) -> str:
    """
    ZAFİYET 4: SQL Injection – string format ile sorgu oluşturma.
    Gerçek DB yok ama pattern injection simüle edilir.
    """
    # Kasıtlı olarak parametrik sorgu kullanılmıyor
    query = f"SELECT * FROM users WHERE username = '{username}'"
    logger.info("Oluşturulan sorgu: %s", query)
    return query


def _eval_formula(metadata: dict) -> str:
    """
    ZAFİYET 5: Eval injection – metadata['formula'] varsa doğrudan eval edilir.
    """
    if "formula" in metadata:
        formula = metadata["formula"]
        try:
            result = eval(formula)  # noqa: S307 – kasıtlı güvensiz eval
            return f"Formula sonucu: {result}"
        except Exception as exc:
            raise RuntimeError(f"Formula değerlendirme hatası: {exc}") from exc
    return "Formula yok"


# ---------------------------------------------------------------------------
# Endpoint: /register
# ---------------------------------------------------------------------------
@app.post("/register", status_code=201)
async def register_user(payload: UserRegistration):
    """
    Kullanıcı kayıt endpoint'i.
    Bilerek bırakılmış zafiyetler içerir – fuzzing hedefidir.
    """
    logger.info("Yeni kayıt isteği alındı: username=%s, age=%s", payload.username, payload.age)

    try:
        # Zafiyetli işlem 1: Yaş doğrulama
        age_result = _validate_age(payload.age)

        # Zafiyetli işlem 2: Bio işleme
        bio_result = _process_bio(payload.bio or "")

        # Zafiyetli işlem 3: SQL sorgusu oluşturma
        sql_query = _build_sql_query(payload.username)

        # Zafiyetli işlem 4: Metadata formula eval
        formula_result = _eval_formula(payload.metadata or {})

        # Score overflow kontrolü yok
        if payload.score and payload.score > 1e308:
            raise OverflowError("Score değeri float sınırlarını aşıyor")

        response_data = {
            "status": "success",
            "message": f"Kullanıcı '{payload.username}' başarıyla kaydedildi.",
            "age_info": age_result,
            "bio_length": len(bio_result),
            "sql_debug": sql_query,
            "formula_debug": formula_result,
        }
        logger.info("Kayıt başarılı: %s", payload.username)
        return response_data

    except ZeroDivisionError as exc:
        logger.error("ZeroDivisionError: %s", exc)
        raise HTTPException(status_code=500, detail=f"Sıfıra bölme hatası: {exc}") from exc

    except MemoryError as exc:
        logger.error("MemoryError: %s", exc)
        raise HTTPException(status_code=500, detail=f"Bellek hatası: {exc}") from exc

    except RuntimeError as exc:
        logger.error("RuntimeError (eval injection?): %s", exc)
        raise HTTPException(status_code=500, detail=f"Çalışma zamanı hatası: {exc}") from exc

    except OverflowError as exc:
        logger.error("OverflowError: %s", exc)
        raise HTTPException(status_code=500, detail=f"Taşma hatası: {exc}") from exc

    except Exception as exc:
        logger.critical("Beklenmeyen hata: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Beklenmeyen iç hata: {exc}") from exc


# ---------------------------------------------------------------------------
# Sağlık Kontrolü Endpoint'i
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """API'nin ayakta olup olmadığını kontrol eder."""
    return {"status": "alive", "service": "Chaos Target API"}


# ---------------------------------------------------------------------------
# Doğrudan çalıştırma
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "target_api:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )
