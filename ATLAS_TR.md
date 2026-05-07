# A.T.L.A.S — Özerk Görev-Öğrenen Yapay Zeka Sistemi

> Gerçek zamanlı sesli etkileşim, 3D avatar ve tam bilgisayar kontrolü sunan kişisel yapay zeka asistanı.

---

## Proje Genel Bakış

A.T.L.A.S (Autonomous Task-Learning AI System), Google Gemini 2.5 Flash Native Audio modeli üzerine inşa edilmiş, doğal dil komutlarıyla bilgisayarınızı, dosyalarınızı, tarayıcınızı, oyun platformlarınızı ve çok daha fazlasını yönetmenizi sağlayan bir masaüstü yapay zeka asistanıdır. Mikrofondan aldığı sesi gerçek zamanlı olarak işler, araçları otomatik olarak seçip çalıştırır ve yanıtı ses olarak geri iletir. Tarayıcı tabanlı 3D avatar arayüzü ile görsel bir deneyim sunar.

**Temel Özellikler:**

- Sıfır gecikme hedefli gerçek zamanlı ses girişi ve çıkışı
- 19 yerleşik araçla tam bilgisayar otomasyon kapasitesi
- VRoid VRM modelleri ile 3D avatar ve dudak senkronizasyonu
- JSON tabanlı kalıcı uzun süreli hafıza
- Çok adımlı karmaşık görevler için otonom ajan motoru
- Türkçe dahil çok dil desteği — yanıtlar kullanıcının diline göre verilir

---

## Sistem Mimarisi

```
┌─────────────────────────────────────────────────────────────────┐
│                        A.T.L.A.S                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Mikrofon (16 kHz)                                             │
│        │                                                         │
│        ▼                                                         │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │           Google Gemini 2.5 Flash Native Audio           │  │
│   │                   (Live API / Canlı Oturum)              │  │
│   └────────────────────────┬─────────────────────────────────┘  │
│                            │                                      │
│               ┌────────────┴──────────────┐                      │
│               │                           │                      │
│         Araç Çağrısı               Ses Yanıtı (24 kHz)          │
│               │                           │                      │
│               ▼                           ▼                      │
│   ┌────────────────────┐     ┌───────────────────────────────┐  │
│   │   Tool Router      │     │     sounddevice Oynatma       │  │
│   │   (main.py)        │     │           │                   │  │
│   └────────┬───────────┘     │   Genlik Zarfı (_jaw_smooth)  │  │
│            │                 │           │                   │  │
│   ┌────────▼───────────┐     │   Transkripsiyon → Viseme     │  │
│   │    actions/        │     │   (14 kanallı ARKit)          │  │
│   │  (19 araç modülü)  │     └──────────────┬────────────────┘  │
│   └────────────────────┘                    │                    │
│                                             ▼                    │
│                                   WebSocket (port 7862)          │
│                                             │                    │
│                                             ▼                    │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │        Tarayıcı Arayüzü (HTTP port 7861)                │   │
│   │     avatar.html  →  Three.js + @pixiv/three-vrm         │   │
│   │     52 ARKit Blendshape · Duygu · Otomatik Göz Kırpma  │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│   ┌──────────────────────┐   ┌──────────────────────────────┐   │
│   │   memory/            │   │   agent/                     │   │
│   │   long_term.json     │   │   planner + executor         │   │
│   │   (kalıcı hafıza)    │   │   (çok adımlı otomasyon)     │   │
│   └──────────────────────┘   └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Ses İşleme Hattı

```
Mikrofon (16 kHz)
        │
        ▼
Gemini Live API  ──────────────────────────────────────────────┐
        │                                                        │
        │                                         Ses Yanıtı (24 kHz)
        ▼                                                        │
  Araç Yönlendirici                               sounddevice oynatma
        │                                                        │
        ▼                                         Genlik zarfı (_jaw_smooth)
  actions/ modülleri                                             │
                                          Metin transkripsiyon → Viseme thread
                                                                 │
                                          14 kanallı ARKit blendshape dizisi
                                                                 │
                                          WebSocket mesajı → Tarayıcı
                                                                 │
                                          Three.js VRM ağı → Gerçek zamanlı
                                                             dudak senkronizasyonu
```

---

## Yetenekler

### 1. Uygulama Açma — `open_app`

Bilgisayardaki herhangi bir uygulama, program veya web sitesini açar.

| Parametre | Tür | Açıklama |
|-----------|-----|----------|
| `app_name` | string | Uygulama adı (ör. `"Spotify"`, `"Chrome"`, `"WhatsApp"`) |

**Örnek komutlar:**
- "Spotify'ı aç"
- "Chrome'u başlat"
- "Hesap makinesini aç"

---

### 2. Web Araması — `web_search`

Web'de arama yapar; standart arama ve karşılaştırma modlarını destekler.

| Parametre | Tür | Açıklama |
|-----------|-----|----------|
| `query` | string | Arama sorgusu |
| `mode` | string | `search` (varsayılan) veya `compare` |
| `items` | array | Karşılaştırılacak öğe listesi |
| `aspect` | string | `price`, `specs`, veya `reviews` |

**Örnek komutlar:**
- "Python'un en iyi özelliklerini ara"
- "iPhone 15 ile Galaxy S24'ü fiyat açısından karşılaştır"

---

### 3. Hava Durumu — `weather_report`

Herhangi bir şehir için anlık hava durumu bilgisi getirir.

| Parametre | Tür | Açıklama |
|-----------|-----|----------|
| `city` | string | Şehir adı |

**Örnek komutlar:**
- "İstanbul'un hava durumunu söyle"
- "Ankara'da bugün hava nasıl?"

---

### 4. Mesaj Gönderme — `send_message`

WhatsApp, Telegram ve diğer platformlar üzerinden mesaj gönderir.

| Parametre | Tür | Açıklama |
|-----------|-----|----------|
| `receiver` | string | Alıcı kişi adı |
| `message_text` | string | Gönderilecek mesaj |
| `platform` | string | `WhatsApp`, `Telegram`, vb. |

**Örnek komutlar:**
- "Ahmet'e WhatsApp'tan 'Toplantı saat 3'te' mesajı gönder"

---

### 5. Hatırlatıcı — `reminder`

Windows Görev Zamanlayıcı kullanarak zamanlı hatırlatıcılar ayarlar.

| Parametre | Tür | Açıklama |
|-----------|-----|----------|
| `date` | string | Tarih (YYYY-MM-DD) |
| `time` | string | Saat (HH:MM, 24 saatlik) |
| `message` | string | Hatırlatıcı metni |

**Örnek komutlar:**
- "Yarın saat 14:30'da ilaç almayı hatırlat"

---

### 6. YouTube Kontrolü — `youtube_video`

YouTube'u sesli komutla oynatır, duraklatır, özetler ve trend videoları getirir.

| Eylem | Açıklama |
|-------|----------|
| `play` | Arama yaparak video oynatır |
| `pause` | Oynatmayı duraklatır |
| `resume` | Devam ettirir |
| `stop` / `close` | Durdurur ve kapatır |
| `summarize` | Video içeriğini özetler |
| `get_info` | Video bilgilerini getirir |
| `trending` | Trend videoları listeler (ülke koduyla, ör. `TR`) |

**Örnek komutlar:**
- "YouTube'da Lo-Fi müzik çal"
- "Bu videonun özetini çıkar"
- "Türkiye'deki trend videoları göster"

---

### 7. Ekran ve Kamera Analizi — `screen_process`

Ekran görüntüsü veya web kamerası görüntüsü alır ve yapay zeka ile analiz eder.

| Parametre | Tür | Açıklama |
|-----------|-----|----------|
| `angle` | string | `screen` (ekran) veya `camera` (web kamerası) |
| `text` | string | Görüntü hakkında soru veya talimat |

**Örnek komutlar:**
- "Ekranımda ne var?"
- "Kameradan bak, ne görüyorsun?"
- "Bu formdaki hataları bul"

---

### 8. Bilgisayar Ayarları — `computer_settings`

İşletim sistemi düzeyinde tüm tek komutlu kontrolü yönetir.

| Eylem kategorisi | Örnekler |
|------------------|----------|
| Ses | Ses aç, ses kapat, ses düzeyini %50'ye ayarla |
| Ekran parlaklığı | Parlaklığı artır, %70'e ayarla |
| Pencere yönetimi | Pencereyi küçült, büyüt, kaydır |
| Güç | Bilgisayarı kapat, yeniden başlat, ekranı kilitle |
| Karanlık mod | Karanlık modu aç/kapat |
| Wi-Fi | Wi-Fi'yı aç/kapat |
| Klavye kısayolları | Ctrl+C, Alt+Tab, vb. |
| Ekran görüntüsü | Ekran görüntüsü al |
| Sekme yönetimi | Yeni sekme aç, sekmeyi kapat |
| Zoom | Sayfayı büyüt/küçült |

---

### 9. Tarayıcı Kontrolü — `browser_control`

Tam web tarayıcı otomasyonu — birden fazla tarayıcı aynı anda çalıştırılabilir.

**Desteklenen tarayıcılar:** Chrome, Edge, Firefox, Opera, Opera GX, Brave, Vivaldi

| Eylem | Açıklama |
|-------|----------|
| `go_to` | URL'ye gider |
| `search` | Web araması yapar |
| `click` | Elemana tıklar |
| `type` | Metin yazar |
| `scroll` | Sayfayı kaydırır |
| `fill_form` | Form doldurur |
| `smart_click` | Doğal dil tanımıyla tıklar |
| `smart_type` | Doğal dil tanımıyla yazar |
| `screenshot` | Tarayıcı ekran görüntüsü alır |
| `new_tab` / `close_tab` | Sekme yönetimi |
| `switch` | Tarayıcılar arası geçiş |

**Örnek komutlar:**
- "Edge'de GitHub'ı aç"
- "Chrome'da Google'da Python öğren'i ara"
- "Bu sayfadaki 'Giriş Yap' butonuna tıkla"

---

### 10. Dosya Yönetimi — `file_controller`

Dosya ve klasör işlemlerinin tamamını yönetir.

| Eylem | Açıklama |
|-------|----------|
| `list` | Dizin içeriğini listeler |
| `create_file` | Yeni dosya oluşturur |
| `create_folder` | Yeni klasör oluşturur |
| `delete` | Dosya/klasör siler |
| `move` / `copy` | Taşır veya kopyalar |
| `rename` | Yeniden adlandırır |
| `read` | Dosya içeriğini okur |
| `write` | Dosyaya yazar |
| `find` | Ada veya uzantıya göre arar |
| `disk_usage` | Disk kullanım bilgisi getirir |
| `organize_desktop` | Masaüstünü düzenler |

**Kısayol yollar:** `desktop`, `downloads`, `documents`, `home`

---

### 11. Masaüstü Kontrolü — `desktop_control`

Masaüstü duvar kağıdı değiştirme, düzenleme ve istatistik.

| Eylem | Açıklama |
|-------|----------|
| `wallpaper` | Dosya yolundan duvar kağıdı ayarlar |
| `wallpaper_url` | URL'den duvar kağıdı ayarlar |
| `organize` | Türe veya tarihe göre düzenler |
| `clean` | Masaüstünü temizler |
| `list` | Masaüstü öğelerini listeler |
| `stats` | Masaüstü istatistiklerini gösterir |

---

### 12. Kod Yardımcısı — `code_helper`

Her programlama dilinde kod yazar, düzenler, açıklar ve çalıştırır.

| Eylem | Açıklama |
|-------|----------|
| `write` | Yeni kod dosyası oluşturur |
| `edit` | Mevcut dosyayı düzenler |
| `explain` | Kodu açıklar |
| `run` | Kodu çalıştırır |
| `build` | Projeyi derler/paketler |
| `auto` | En uygun eylemi otomatik seçer |

---

### 13. Geliştirici Ajanı — `dev_agent`

Sıfırdan tam çok dosyalı projeler oluşturur: planlama, dosya yazma, bağımlılık kurma, VSCode'u açma ve hata düzeltme.

**Örnek komutlar:**
- "Flask ile REST API oluştur"
- "Tkinter ile hesap makinesi yap"

---

### 14. Ajan Görevi — `agent_task`

Birden fazla araç gerektiren karmaşık çok adımlı görevleri yürütür.

**Örnek komutlar:**
- "Yapay zeka trendlerini araştır ve bir dosyaya kaydet"
- "İndirmeler klasöründeki dosyaları düzenle ve rapor oluştur"

---

### 15. Bilgisayar Kontrolü — `computer_control`

PyAutoGUI üzerinden doğrudan fare ve klavye kontrolü.

| Eylem | Açıklama |
|-------|----------|
| `type` / `smart_type` | Metin yazar |
| `click` / `double_click` / `right_click` | Tıklama |
| `hotkey` | Kısayol tuşu uygular |
| `scroll` | Kaydırır |
| `move` | Fareyi taşır |
| `screenshot` | Ekran görüntüsü alır |
| `screen_find` | Ekranda öğe bulur |
| `screen_click` | Bulunan öğeye tıklar |

---

### 16. Oyun Güncelleyici — `game_updater`

Steam ve Epic Games için tüm oyun yönetimini üstlenir.

| Eylem | Açıklama |
|-------|----------|
| `update` | Oyunları günceller |
| `install` | Oyun yükler |
| `list` | Kurulu oyunları listeler |
| `download_status` | İndirme durumunu kontrol eder |
| `schedule` | Güncellemeyi zamanlar |

**Örnek komutlar:**
- "Steam oyunlarımı güncelle"
- "CS2'yi yükle"
- "Gece 3'te tüm oyunları güncelle, bitince bilgisayarı kapat"

---

### 17. Uçuş Bulucu — `flight_finder`

Google Flights'ta arama yaparak en iyi uçuş seçeneklerini sesli olarak sunar.

| Parametre | Tür | Açıklama |
|-----------|-----|----------|
| `origin` | string | Kalkış şehri veya havalimanı kodu |
| `destination` | string | Varış şehri veya havalimanı kodu |
| `date` | string | Kalkış tarihi (herhangi bir format) |
| `return_date` | string | Dönüş tarihi (gidiş-dönüş için) |
| `passengers` | integer | Yolcu sayısı (varsayılan: 1) |
| `cabin` | string | `economy`, `premium`, `business`, `first` |
| `save` | boolean | Sonuçları Not Defteri'ne kaydet |

---

### 18. Hafıza Kaydetme — `save_memory`

Kullanıcı hakkındaki önemli bilgileri kalıcı olarak uzun süreli hafızaya kaydeder.

**Hafıza kategorileri:**

| Kategori | İçerik |
|----------|--------|
| `identity` | İsim, yaş, meslek gibi kimlik bilgileri |
| `preferences` | Tercihler ve beğeniler |
| `projects` | Devam eden projeler |
| `relationships` | Kişi ilişkileri |
| `wishes` | İstekler ve hedefler |
| `notes` | Genel notlar |

**Teknik detaylar:**
- Depolama: `memory/long_term.json`
- Maksimum değer uzunluğu: 380 karakter
- Toplam hafıza limiti: 2200 karakter
- Thread-safe kilit mekanizması

---

### 19. Asistanı Kapat — `shutdown_jarvis`

A.T.L.A.S oturumunu güvenli şekilde sonlandırır. Her dilde çalışır ("kapat", "güle güle", "bye", "exit").

---

## Avatar Sistemi

### Genel Bakış

A.T.L.A.S'ın 3D avatar sistemi, VRoid Studio ile üretilmiş VRM modelleri kullanır ve tarayıcıda Three.js + @pixiv/three-vrm ile render edilir. Avatar, konuşma sırasında gerçek zamanlı dudak senkronizasyonu, duygu ifadeleri ve doğal boşta animasyonlar sergiler.

### Avatar Arayüzüne Erişim

```
http://localhost:7861/avatar.html
```

### VRM Modelleri

| Dosya | Açıklama |
|-------|----------|
| `public/vroid_male.vrm` | Erkek VRoid modeli |
| `public/vroid_female.vrm` | Kadın VRoid modeli |

### Foneme → ARKit Viseme Eşleşmesi

25 fonem sınıfı 14 ARKit yüz kanalına eşlenir:

| Fonem grubu | Örnekler | Başlıca etkilenen kanallar |
|-------------|----------|---------------------------|
| Ünlüler | a, e, i, o, u | `JawOpen`, `MouthFunnel`, `MouthPucker` |
| Çift dudaklılar | m, b, p | `MouthClose`, `MouthShrugUpper` |
| Labiodental | f, v | `MouthUpperUpLeft/Right` |
| Sibilantlar | s, z | `MouthStretchLeft/Right` |
| Yuvarlaklar | w, r | `MouthPucker`, `MouthFunnel` |
| Alveolarlar | l, t, d, n | `MouthLowerDownLeft/Right` |
| Frikatifler | h, j, k, g | `JawOpen` |

### Ses Tabanlı Çene Hareketi

Dil transkripsiyon beklenirken genlik zarfı (`_jaw_smooth`) ses çıkışından doğrudan çene hareketi üretir; lipsync aksamadan devam eder.

### Duygu Sistemi

Konuşma metni analiz edilerek 6 duygu durumu tespit edilir ve üst yüz ifadeleri buna göre güncellenir:

| Duygu | Tetikleyici anahtar kelimeler |
|-------|-------------------------------|
| `happy` | great, perfect, harika, süper, bravo |
| `thinking` | searching, let me, bakıyorum, hmm |
| `concerned` | error, sorry, maalesef, üzgün |
| `surprised` | wow, really, inanılmaz |
| `listening` | tell me, dinliyorum, anlat |
| `neutral` | (varsayılan) |

**Kural:** Konuşma sırasında yalnızca üst yüz ifadeleri (kaşlar, göz kapakları) değişir; lipsync sırasında alt yüz bağımsız çalışır.

### Boşta Animasyonlar

- Otomatik göz kırpma
- Nefes alma (göğüs/omuz salınımı)
- Baş sallama

### İfade Test Paneli

`avatar.html` içinde 70 ifadeyi manuel olarak test edebileceğiniz bir panel bulunur.

---

## Kurulum

### Gereksinimler

| Gereksinim | Sürüm / Detay |
|------------|---------------|
| Python | 3.12+ |
| İşletim Sistemi | Windows 10/11 (önerilen) |
| Tarayıcı | Chrome / Chromium (önerilen) |
| Gemini API Anahtarı | Ücretsiz — [aistudio.google.com](https://aistudio.google.com) |
| Mikrofon | Herhangi bir mikrofon |

### Adım Adım Kurulum

**1. Depoyu klonlayın:**

```bash
git clone https://github.com/your-username/atlas.git
cd atlas
```

**2. Bağımlılıkları yükleyin:**

```bash
python setup.py
```

Bu komut hem Python paketlerini hem de Playwright tarayıcılarını yükler.

Manuel kurulum tercih ederseniz:

```bash
pip install -r requirements.txt
playwright install
```

**3. API anahtarını yapılandırın:**

`config/api_keys.json` dosyasını oluşturun:

```json
{
    "gemini_api_key": "BURAYA_API_ANAHTARINIZI_YAZIN"
}
```

Ücretsiz API anahtarı için: [https://aistudio.google.com](https://aistudio.google.com)

**4. Asistanı başlatın:**

```bash
python main.py
```

Tarayıcı otomatik olarak açılır: `http://localhost:7861`

### Python Bağımlılıkları

```
sounddevice          # Gerçek zamanlı ses girişi/çıkışı
google-genai         # Gemini Live API istemcisi
google-generativeai  # Gemini SDK
playwright           # Tarayıcı otomasyonu
pyautogui            # Fare ve klavye kontrolü
numpy                # Ses tamponu işleme
mss                  # Ekran yakalama
Pillow               # Görüntü işleme
psutil               # Süreç/sistem bilgisi
pyperclip            # Pano yönetimi
pygetwindow          # Pencere yönetimi
opencv-python        # Görüntü analizi
comtypes             # Windows COM arayüzü
pycaw                # Windows ses kontrolü
win10toast           # Windows bildirim toast'ları
send2trash           # Geri dönüşüm kutusu silme
youtube-transcript-api  # YouTube altyazı/transkript
pywinauto            # Windows UI otomasyonu
pyaudio              # Ses akışı
websockets           # WebSocket sunucusu
```

---

## Kullanım

### Başlatma

```bash
python main.py
```

Başlatıldığında konsol şunu gösterir:

```
=======================================================
  A.T.L.A.S  →  http://localhost:7861
=======================================================
```

Tarayıcı otomatik açılır. Arayüz hazır olduğunda mikrofonunuzdan konuşmaya başlayın.

### Arayüz Seçenekleri

| URL | Arayüz | Açıklama |
|-----|--------|----------|
| `http://localhost:7861` | Metin UI (atlas.html) | Klasik metin tabanlı arayüz |
| `http://localhost:7861/avatar.html` | 3D Avatar UI | VRM avatar ile görsel arayüz |

### WebSocket Mesaj Formatları

Tarayıcı `ws://localhost:7862` adresine bağlanır.

**Durum güncelleme:**
```json
{ "type": "state", "value": "LISTENING" }
```

**Günlük mesajı:**
```json
{ "type": "log", "text": "Araç çağrısı: web_search" }
```

**Lipsync verisi:**
```json
{
    "type": "lipsync",
    "blendshapes": {
        "JawOpen": 0.6,
        "MouthStretchLeft": 0.3,
        "MouthStretchRight": 0.3
    }
}
```

### Ses Ayarları (main.py)

| Sabit | Değer | Açıklama |
|-------|-------|----------|
| `SEND_SAMPLE_RATE` | 16000 Hz | Mikrofon örnekleme hızı |
| `RECEIVE_SAMPLE_RATE` | 24000 Hz | Ses çıkış örnekleme hızı |
| `IN_CHUNK` | 1024 örnek | Mikrofon tamponu (~64 ms) |
| `OUT_CHUNK` | 8192 örnek | Ses çıkış tamponu (~340 ms) |

### Örnek Sesli Komutlar

```
"Spotify'ı aç"
"İstanbul'un hava durumunu söyle"
"Ahmet'e Telegram'dan 'Geç kalacağım' mesajı gönder"
"Yarın saat 9'da toplantı hatırlatıcısı kur"
"YouTube'da relaxing music çal"
"Ekranımda ne var?"
"Chrome'da github.com'u aç"
"Masaüstümü düzenle"
"Steam oyunlarımı güncelle"
"İstanbul'dan Londra'ya 15 Haziran uçuşu bul"
"Flask ile basit bir web sunucusu yaz"
"Ses düzeyini %50'ye ayarla"
"Bilgisayarı kapat"
```

---

## Dosya Yapısı

```
Atlas/
├── main.py                    # Ana giriş noktası: Gemini Live oturumu,
│                              #   ses hattı, araç yönlendirici, lipsync
├── ui.py                      # Tarayıcı arayüzü: HTTP (7861) + WebSocket (7862)
├── setup.py                   # Kurulum betiği
├── requirements.txt           # Python bağımlılıkları
│
├── core/
│   └── prompt.txt             # Sistem kimliği ve yürütme kuralları
│
├── actions/                   # Araç uygulamaları (her biri bağımsız modül)
│   ├── browser_control.py     # Playwright tarayıcı otomasyonu
│   ├── code_helper.py         # Kod yazma, çalıştırma, açıklama
│   ├── computer_control.py    # PyAutoGUI fare/klavye kontrolü
│   ├── computer_settings.py   # Windows OS ayarları
│   ├── desktop.py             # Masaüstü duvar kağıdı ve düzenleme
│   ├── dev_agent.py           # Sıfırdan proje oluşturucu
│   ├── file_controller.py     # Dosya/klasör yönetimi
│   ├── flight_finder.py       # Google Flights arama
│   ├── game_updater.py        # Steam/Epic Games yönetimi
│   ├── open_app.py            # Uygulama başlatıcı
│   ├── reminder.py            # Windows Görev Zamanlayıcı entegrasyonu
│   ├── screen_processor.py    # Ekran/kamera yakalama ve analizi
│   ├── send_message.py        # WhatsApp/Telegram mesajlaşma
│   ├── weather_report.py      # Hava durumu servisi
│   ├── web_search.py          # DuckDuckGo web araması
│   └── youtube_video.py       # YouTube oynatma ve analizi
│
├── agent/                     # Çok adımlı otonom ajan motoru
│   ├── planner.py             # Gemini tabanlı görev planlayıcı (maks. 5 adım)
│   ├── executor.py            # Adım yürütücü
│   ├── task_queue.py          # Görev kuyruğu yönetimi
│   └── error_handler.py       # Hata kurtarma
│
├── memory/                    # Uzun süreli hafıza sistemi
│   ├── memory_manager.py      # Yükleme/güncelleme/biçimlendirme
│   └── long_term.json         # Kalıcı kullanıcı verileri
│
├── lipsync/
│   └── client.py              # audio2lipsync istemcisi (port 8765)
│
├── web/                       # Tarayıcı ön yüzü
│   ├── atlas.html             # Klasik metin arayüzü
│   ├── avatar.html            # 3D avatar arayüzü
│   └── avatar_renderer.js     # Three.js + VRM oluşturucu
│
├── public/                    # /public/ yolundan sunulan avatar modelleri
│   ├── vroid_male.vrm         # Erkek VRoid modeli
│   └── vroid_female.vrm       # Kadın VRoid modeli
│
├── models/                    # Animasyon klipleri
│
└── config/
    └── api_keys.json          # Gemini API anahtarı yapılandırması
```

---

## Sorun Giderme

### Ses algılanmıyor

- `sounddevice` kurulu ve mikrofonunuz işletim sistemi düzeyinde varsayılan giriş olarak ayarlanmış olmalıdır.
- `main.py` içindeki `CHANNELS = 1` ve `SEND_SAMPLE_RATE = 16000` değerlerinin mikrofon donanımınızla uyumlu olduğunu doğrulayın.

### Tarayıcı açılmıyor

- `http://localhost:7861` adresine elle gidin.
- Güvenlik duvarı veya antivirüs yazılımının port 7861 veya 7862'yi engellemediğini kontrol edin.

### API hatası

- `config/api_keys.json` dosyasının doğru biçimde oluşturulduğunu doğrulayın.
- [aistudio.google.com](https://aistudio.google.com) üzerinden API anahtarınızın aktif olduğunu kontrol edin.

### Playwright kurulum hatası

```bash
playwright install chromium
```

---

## Lisans

Bu proje eğitim ve araştırma amaçlıdır.
