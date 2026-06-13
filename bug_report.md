# 🐛 AI-Powered API Chaos & Fuzzing — Bug Report

> **Oluşturma Tarihi:** 2026-06-13 20:16:21  
> **Hedef API:** `http://127.0.0.1:8000`  
> **Fuzzing Engine:** LangChain + Groq Llama-3.3-70b-versatile  

---

## 📊 Yönetici Özeti

| Metrik | Değer |
|--------|-------|
| Toplam Gönderilen Payload | **15** |
| Crash Sayısı (HTTP 500) | **3** |
| Bağlantı/İstek Hataları | **4** |
| Crash Oranı | **20.0%** |
| Toplam Test Süresi | **37.7 saniye** |
| Risk Seviyesi | **🟡 ORTA** |

---

## 🚨 Bulunan Güvenlik Açıkları / Crash'ler

### 🟠 ZeroDivisionError (Sıfıra Bölme)

**Etkilenen Payload Sayısı:** 1

#### Payload #1

**Gönderilen Payload:**
```json
{
  "username": "test",
  "age": 0,
  "email": "t@t.com"
}
```

**HTTP Durum Kodu:** `500`  
**Yanıt Süresi:** `4.7ms`  
**Hata Detayı:** `Sıfıra bölme hatası: integer division or modulo by zero`  

---

### 🟠 MemoryError (Bellek Taşması)

**Etkilenen Payload Sayısı:** 1

#### Payload #3

**Gönderilen Payload:**
```json
{
  "username": "test",
  "age": 25,
  "email": "t@t.com",
  "bio": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
  ... (kısaltıldı)
```

**HTTP Durum Kodu:** `500`  
**Yanıt Süresi:** `3.2ms`  
**Hata Detayı:** `Bellek hatası: Bio alanı çok uzun: 10001 karakter (max 10,000)`  

---

### 🔴 Eval Injection / RCE Riski

**Etkilenen Payload Sayısı:** 1

#### Payload #12

**Gönderilen Payload:**
```json
{
  "username": "test",
  "age": 25,
  "email": "t@t.com",
  "metadata": {
    "formula": "1/0",
    "nested": {
      "formula": "exit()"
    }
  }
}
```

**HTTP Durum Kodu:** `500`  
**Yanıt Süresi:** `2.1ms`  
**Hata Detayı:** `Çalışma zamanı hatası: Formula değerlendirme hatası: division by zero`  

---

## 📋 Tüm Test Sonuçları

| # | HTTP Durum | Süre (ms) | Sonuç | Hata Özeti |
|---|-----------|-----------|-------|-----------|
| 1 | `500` | 4.7 | 💥 | Sıfıra bölme hatası: integer division or modulo by zero |
| 2 | `201` | 2.3 | ✅ | - |
| 3 | `500` | 3.2 | 💥 | Bellek hatası: Bio alanı çok uzun: 10001 karakter (max 10,00 |
| 4 | `201` | 21.5 | ✅ | - |
| 5 | `201` | 2.0 | ✅ | - |
| 6 | `201` | 2.0 | ✅ | - |
| 7 | `ERR` | 0.5 | ❓ | RequestException: Out of range float values are not JSON com |
| 8 | `422` | 2.2 | ⚠️ | - |
| 9 | `422` | 2.0 | ⚠️ | - |
| 10 | `201` | 2.1 | ✅ | - |
| 11 | `201` | 2.0 | ✅ | - |
| 12 | `500` | 2.1 | 💥 | Çalışma zamanı hatası: Formula değerlendirme hatası: divisio |
| 13 | `ERR` | 10003.1 | ❓ | RequestTimeout |
| 14 | `ERR` | 10017.4 | ❓ | RequestTimeout |
| 15 | `ERR` | 10023.8 | ❓ | RequestTimeout |

---

## 🛡️ Güvenlik Önerileri

### Kritik Düzeltmeler

1. **ZeroDivisionError**: `age` değeri için `age > 0` doğrulaması zorunlu kılınmalı.
2. **Eval Injection (RCE)**: `eval()` kullanımı tamamen kaldırılmalı. Formüller için `ast.literal_eval()` veya beyaz liste kullanılmalı.
3. **MemoryError**: `bio` alanı için maksimum uzunluk Pydantic `Field(max_length=10000)` ile sınırlandırılmalı.
4. **OverflowError**: `score` alanı için `Field(le=1e308)` sınırı eklenmeli.
5. **SQL Injection**: Parametre tabanlı sorgular (prepared statements) kullanılmalı. Hiçbir kullanıcı girdisi doğrudan sorguya eklenmemeli.

### Genel Güvenlik Pratikleri

- Input sanitization tüm endpoint'lerde zorunlu olmalı.
- Rate limiting eklenmelidir (örn: slowapi).
- Hata mesajları iç stack trace içermemeli (information disclosure).
- Tüm giriş alanları için tip ve aralık doğrulaması Pydantic validator ile yapılmalı.
- Security headers (CORS, CSP) yapılandırılmalı.

---

## 🤖 Test Aracı Hakkında

Bu rapor **AI-Powered API Chaos & Fuzzing Motoru** tarafından otomatik olarak üretilmiştir.

| Bileşen | Versiyon/Model |
|---------|---------------|
| LLM | Groq Llama-3.3-70b-versatile |
| Framework | LangChain + FastAPI |
| Test Türü | Black-box Fuzzing + Edge-case Generation |

> *Bu rapor yalnızca eğitim ve güvenlik araştırması amacıyla üretilmiştir.*
