# 🤖 AI-Powered API Chaos & Fuzzing Motoru

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.2+-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![Groq](https://img.shields.io/badge/Groq_API-Llama--3.3-F55036?style=for-the-badge&logo=groq&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**LLM Tabanlı Otonom API Güvenlik & Dayanıklılık Test Aracı**

*Groq Llama-3.3 zekasıyla hedef API'nizi kırmak için tasarlandı.*

</div>

---

## 🎯 Amaç ve Arka Plan

Bu proje, REST API'lerini **otonom olarak** analiz eden, **LLM (Large Language Model)** kullanarak akıllı saldırı payload'ları üreten ve API'yi çökerttiğinde profesyonel bir hata raporu hazırlayan uçtan uca bir **API Chaos & Fuzzing** aracıdır.

Geleneksel fuzzer'ların aksine bu araç:
- 🧠 **Groq Llama-3.3-70b-versatile** kullanarak API şemasını *anlayarak* yaratıcı edge-case'ler üretir
- 💥 SQL Injection, XSS, Eval Injection, Overflow ve tip karışıklığı gibi güvenlik tehditlerini test eder
- 📝 Her crash için otomatik olarak profesyonel **Markdown Bug Report** üretir
- 🔄 Tamamen otonom çalışır — insan müdahalesine gerek yoktur

---

## 🏗️ Proje Mimarisi

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                  │
│                    (Orkestrasyon Katmanı)                        │
│  subprocess.Popen ──► target_api.py (FastAPI, :8000)            │
│       │                                                          │
│       ▼                                                          │
│  FuzzerAgent ──► Groq API ──► Llama-3.3-70b-versatile          │
│       │          (LangChain)      ▼                              │
│       │                   Yıkıcı JSON Payload'lar               │
│       ▼                                                          │
│  ChaosEngine ──► POST /register ──► Target API                  │
│       │              (requests)         │                        │
│       │                          ┌──────┴──────┐                │
│       │                          │ HTTP 500?   │                 │
│       │                          │  (Crash!)   │                 │
│       │                          └──────┬──────┘                │
│       ▼                                 ▼                        │
│  bug_report.md ◄──────── Crash Analizi & Raporlama             │
└─────────────────────────────────────────────────────────────────┘
```

### İletişim Döngüsü

1. **main.py** → target_api.py'yi `subprocess.Popen` ile arka planda başlatır
2. **FuzzerAgent** → Groq Llama-3.3'e API şemasını gönderir, yıkıcı payload listesi alır
3. **ChaosEngine** → Her payload'ı `POST /register` endpoint'ine `requests` ile gönderir
4. HTTP yanıt kodu `500` ise → crash kaydedilir, detaylar analiz edilir
5. Tüm oturum tamamlandığında → `bug_report.md` otomatik üretilir
6. **main.py** → API sürecini `process.terminate()` ile temiz kapatır

---

## 📁 Dosya Yapısı

```
.
├── target_api.py      # 🎯 Kurban API (Kasıtlı zafiyetli FastAPI uygulaması)
├── fuzzer_agent.py    # 🧠 LLM tabanlı payload üretici (LangChain + Groq)
├── chaos_engine.py    # ⚡ Orkestratör (HTTP gönderici + Bug Report üretici)
├── main.py            # 🚀 Giriş noktası (subprocess + tam otomasyon)
├── requirements.txt   # 📦 Python bağımlılıkları
├── .env               # 🔑 API anahtarları (git'e ekleme!)
├── bug_report.md      # 📝 Otomatik oluşturulan hata raporu (çalıştırma sonrası)
├── chaos_run.log      # 📋 Detaylı log dosyası (çalıştırma sonrası)
└── README.md          # 📖 Bu dosya
```

---

## 🚀 Kurulum ve Kullanım

### Ön Koşullar

- Python 3.11+
- [Groq API anahtarı](https://console.groq.com) (ücretsiz)

### 1. Depoyu Klonla

```bash
git clone https://github.com/kullanici/api-chaos-fuzzer.git
cd "Day 3 AI-Powered API Chaos & Fuzzing Motoru"
```

### 2. Sanal Ortam Oluştur ve Aktif Et

```bash
# Oluştur
python -m venv .venv

# Aktif et (Windows)
.venv\Scripts\activate

# Aktif et (Linux/macOS)
source .venv/bin/activate
```

### 3. Bağımlılıkları Yükle

```bash
pip install -r requirements.txt
```

### 4. API Anahtarını Yapılandır

```bash
# .env dosyası oluştur
echo "GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx" > .env
```

Veya doğrudan `.env` dosyasını düzenle:

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 5. Testi Başlat

```bash
python main.py
```

### 6. Sonuçları İncele

```bash
# Otomatik üretilen bug report
cat bug_report.md

# Detaylı log
cat chaos_run.log
```

---

## 🔍 Kullanılan Zafiyetler (Eğitim Amaçlı)

| Zafiyet | Alan | Tetikleyici | HTTP Sonucu |
|---------|------|------------|-------------|
| ZeroDivisionError | `age` | `age = 0` | 500 |
| MemoryError | `bio` | `len(bio) > 10.000` | 500 |
| Eval Injection (RCE) | `metadata.formula` | `{"formula": "..."}` | 500 |
| OverflowError | `score` | `score > 1e308` | 500 |
| SQL Injection (log) | `username` | `' OR 1=1; --` | Simülasyon |
| Type Confusion | Tümü | Yanlış tipler | 422 / 500 |

> ⚠️ **Uyarı**: Bu API yalnızca **eğitim ve güvenlik araştırması** amacıyla tasarlanmıştır. Gerçek üretim ortamlarında kullanmayın.

---

## 🛡️ Güvenli Mimari İlkeleri (Öğrenim Hedefleri)

Bu proje aşağıdaki güvenlik prensiplerini öğretmek için karşı-örnek içerir:

- ❌ `eval()` kullanmayın → ✅ `ast.literal_eval()` veya beyaz liste
- ❌ f-string SQL sorgusu → ✅ Prepared statements / ORM
- ❌ Sınırsız string girişi → ✅ Pydantic `Field(max_length=...)`
- ❌ Negatif/sıfır sayı → ✅ `Field(gt=0)` kısıtı
- ❌ İç hata detayı → ✅ Genel hata mesajı (bilgi sızıntısını önle)

---

## 🧪 Örnek Bug Report Çıktısı

Başarılı bir fuzzing çalıştırmasından sonra `bug_report.md` şu bilgileri içerir:

- 📊 Yönetici Özeti (crash oranı, risk seviyesi)
- 🚨 Tespit edilen her güvenlik açığının kategori ve detayları
- 💥 Crash'e neden olan tam JSON payload
- 📋 Tüm test sonuçlarının tablosu
- 🛡️ Öncelikli güvenlik düzeltme önerileri

---

## 📦 Kullanılan Teknolojiler

| Teknoloji | Kullanım |
|-----------|---------|
| **FastAPI** | Hedef (kurban) API sunucusu |
| **Uvicorn** | ASGI web sunucusu |
| **LangChain** | LLM orchestration framework |
| **Groq API** | Llama-3.3-70b-versatile LLM servisi |
| **Pydantic v2** | Request/Response doğrulama |
| **requests** | HTTP istemci (fuzzing istekleri) |
| **python-dotenv** | Ortam değişkeni yönetimi |

---

## 🤝 Katkı

Bu proje eğitim amaçlıdır. PR ve issue'lar memnuniyetle karşılanır.

---

## 📜 Lisans

```
MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

<div align="center">

Made with ❤️ for **API Security & Resilience Testing**

*"Break it before attackers do."*

</div>
