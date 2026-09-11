# 🧊 MesoTech Cooling

[![Live Demo](https://img.shields.io/badge/Demo-Canlıda-brightgreen?style=for-the-badge&logo=render)](https://mesotech-cooling.onrender.com/)

🚀 **Canlı Kontrol Paneli:** [https://mesotech-cooling.onrender.com/](https://mesotech-cooling.onrender.com/)


**IoT tabanlı, kapalı devre akıllı soğutma sistemi** — distilasyon üniteleri gibi
sürekli soğutma ihtiyacı olan laboratuvar/endüstriyel cihazlar için şebeke suyu
tüketimini sıfırlamayı ve chiller sistemlerine göre daha düşük enerjiyle
çalışmayı hedefleyen bir kontrol yazılımı.

Sistem, giriş/çıkış su sıcaklıklarını ve akış hızını gerçek zamanlı okuyup PID
tabanlı bir algoritmayla pompa/fan hızını optimize eder; kural tabanlı fizik
kontrolleri + istatistiksel anomali tespiti (Isolation Forest / RobustZ) ile
arızaları erken yakalar ve web tabanlı bir panelden izlenebilir/yönetilebilir.

> Bu proje TEKNOFEST **Sıfır Atık ve Döngüsel Ekonomi Yarışması** kapsamında
> geliştirilmiştir (Takım: MezoTech).

---

## ✨ Özellikler

- **Kapalı devre kontrol:** PID tabanlı pompa/fan hız optimizasyonu, ortam
  sıcaklığı ve ΔT'ye göre kazanç (gain) seçimi.
- **Güvenlik katmanı:** Kural tabanlı fizik kontrolleri (aşırı sıcaklık, düşük
  akış/tıkanıklık, yüksek akış/kaçak, düşük su seviyesi) tespit edildiğinde
  sistemi otomatik güvenli moda (`emergency_stop`) alır.
- **Anomali tespiti:** Sadece normal örneklerle eğitilen Isolation Forest
  (scikit-learn varsa) veya RobustZ (yoksa) modeli ile model tabanlı sapma
  uyarısı; fizik kuralı + model onayı birlikte değerlendirilir.
- **Donanım soyutlaması:** `config.MODE` ile `SIMULATION` (bu repo, GPIO
  gerektirmez) veya `HARDWARE` (Raspberry Pi + DS18B20 + debimetre + PWM
  motor sürücü) arasında geçiş.
- **Web paneli:** Flask varsa Flask, yoksa standart kütüphane HTTP sunucusu
  üzerinden REST API + canlı dashboard (`/`).
- **Manuel/otomatik mod, hedef sıcaklık ayarı, arıza simülasyonu** (kirli
  serpantin, tıkanıklık, sensör arızası) test/demo amaçlı.

---

## 🏗️ Mimari

```
┌─────────────────────┐
│   plant_sim.py       │  ← MODE=SIMULATION iken sanal termal model
│   (veya gerçek        │     (Pi yokken dashboard'un canlı kalması için)
│   sensörler)          │
└─────────┬────────────┘
          │ sıcaklık / akış / seviye
          ▼
┌─────────────────────┐      ┌──────────────────────┐
│ sensor_manager.py    │─────▶│ anomaly_detector.py   │
│ (sensör okuma katmanı)│      │ (fizik kuralları +    │
└─────────┬────────────┘      │  IsolationForest/     │
          │                   │  RobustZ)              │
          ▼                   └──────────┬────────────┘
┌─────────────────────┐                   │ anomaliler
│ pump_controller.py    │                   ▼
│ (PID tabanlı hibrit   │          ┌──────────────────┐
│  pompa/fan kontrolü)  │          │  main.py           │
└─────────┬────────────┘◀─────────│  kontrol döngüsü + │
          │ pompa/fan hızı         │  HTTP/REST sunucu  │
          ▼                       └─────────┬─────────┘
┌─────────────────────┐                     │
│  hardware.py          │                     ▼
│  (GPIO/PWM soyutlama, │           ┌──────────────────┐
│   RPi yoksa no-op)    │           │ templates/         │
└─────────────────────┘           │ dashboard.html     │
                                    │ (canlı web paneli) │
                                    └──────────────────┘
```

---

## 📦 Kurulum

```bash
git clone https://github.com/<kullanici-adi>/mesotech-cooling.git
cd mesotech-cooling

python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
python3 main.py
```

Tarayıcıdan: **http://localhost:5000**

Varsayılan olarak `config.py` içinde `MODE = "SIMULATION"` tanımlıdır; bu
modda gerçek donanım gerekmez, `plant_sim.py` sanal bir termal model
üzerinden çalışır.

### Raspberry Pi üzerinde gerçek donanımla çalıştırma

1. `config.py` içinde `MODE = "HARDWARE"` yapın.
2. 1-Wire arayüzünü açın (`raspi-config` → Interface Options → 1-Wire).
3. `requirements.txt` içinde yorum satırı olan Raspberry Pi'ye özel
   paketlerin (`RPi.GPIO`, `w1thermsensor`, `scikit-learn`) yorumunu kaldırıp
   kurun.
4. DS18B20 sensör ID'lerini biliyorsanız `config.py`'de `TEMP_IN_ID` /
   `TEMP_OUT_ID` alanlarına girin (boş bırakılırsa ilk bulunan sensörler
   sırayla atanır — birden fazla sensör varsa risklidir, ID girilmesi önerilir).

---

## ⚙️ Yapılandırma (`config.py`)

| Ayar | Açıklama |
|---|---|
| `MODE` | `"SIMULATION"` veya `"HARDWARE"` |
| `PID_KP / KI / KD` | Temel PID kazançları (yüksek ΔT/ortam sıcaklığında otomatik daha agresif kazançlara geçilir, bkz. `pump_controller._select_gains`) |
| `PID_SETPOINT_TOUT` | Hedef çıkış suyu sıcaklığı (°C) |
| `ANOMALY_THRESHOLDS` | Akış, sıcaklık, ΔT, su seviyesi güvenlik eşikleri |
| `CRITICAL_KEYWORDS` | Bu kelimelerden biri anomali mesajında geçerse sistem otomatik güvenli moda geçer |
| `UPDATE_INTERVAL` | Kontrol döngüsü periyodu (saniye) |

---

## 🌐 REST API

| Yöntem | Uç nokta | Açıklama |
|---|---|---|
| GET | `/` | Canlı web paneli |
| GET | `/api/system/status` | Anlık sıcaklık, akış, pompa/fan, tasarruf verileri, anomaliler |
| GET | `/api/system/stats` | Model istatistikleri, sistem durumu, çalışma süresi |
| POST | `/api/system/control` | Aksiyon gönderme (aşağıya bakın) |

`POST /api/system/control` gövdesi örnekleri:

```jsonc
{ "action": "emergency_stop" }
{ "action": "reset_system" }
{ "action": "set_target_delta", "value": 24.0 }
{ "action": "set_manual_mode", "enabled": true, "speed": 60 }
{ "action": "set_manual_speed", "speed": 45 }
{ "action": "set_fault", "value": "blockage" }   // none | dirty | blockage | sensor
```

---

## 📁 Proje Yapısı

```
mesotech-cooling/
├── main.py                # HTTP sunucu + kontrol döngüsü
├── config.py               # Merkezi ayarlar
├── hardware.py              # GPIO/PWM soyutlaması (no-op fallback)
├── sensor_manager.py        # Sıcaklık + debi okuma katmanı
├── plant_sim.py              # Donanımsız test için sanal termal model
├── pump_controller.py        # PID tabanlı hibrit pompa/fan kontrolü
├── anomaly_detector.py       # Fizik kuralları + IsolationForest/RobustZ
├── templates/
│   └── dashboard.html         # Canlı web paneli
├── requirements.txt
└── DUZELTMELER.md             # Bilinen düzeltmelerin kaydı (bkz. aşağı)
```



## 👥 Takım

| İsim | Rol |
|---|---|
| Ahmet Selman Mızraklıdağ | Donanım |
| İsmail Açar | Yazılım Geliştirme ve Yapay Zeka |
| Dr. Öğr. Üyesi M. Hadi Süzer | Donanım Geliştirme ve Akademik Danışmanlık |
| Prof. Dr. Oktay KESKİN   | Proje Koordinasyonu/ İş Geliştirme |

---
