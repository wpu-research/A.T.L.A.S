# Context Handoff — 2026-06-13c (§V-C Faz 0: SyncNet sanity check GEÇTİ)

## Önceki durum
- §V-D tamamlandı, makaleye işlendi, commit `82d103b` push'landı (bkz. continue-2026-06-13b.md)
- §V-C planı yapıldı: Faz 0 (SyncNet sanity) → Faz 1 (koşul üreteçleri) → Faz 2 (N ses toplama)
  → Faz 3 (toplu render + metrikler) → Faz 4 (Table 4 + metin)

## Faz 0 — TAMAMLANDI, KAPI GEÇİLDİ ✅

### Kurulan altyapı (`paper/tools/render/`)
1. **`render_page.html`** — deterministik offline avatar renderer (three.js CDN importmap,
   GLTFLoader, kare kare: `setMorphs()` + `renderNow()`, lerp YOK — frame-accurate).
   Yüz framing: jawOpen morph'u olan mesh'in bbox'ı.
2. **`render_video.py`** — playwright headless chromium sürücüsü + ffmpeg mux.
   - KRİTİK: `--use-angle=swiftshader --enable-unsafe-swiftshader` bayrakları şart
     (headless'ta WebGL yoksa "setMorphs is not a function" şeklinde patlar)
   - Repo kökünden HTTP server açar (model `/public/human.glb` fetch'i için)
   - `--shift-ms ±N`: ses kaydırma (sanity check için)
   - Kanal adı eşleme: 'JawOpen' (paper/pipeline) → 'jawOpen' (GLB morph adı)
3. **`make_blendshapes.py`** — wav → TSYNC 60fps blendshape JSON (layer23_bench modülleri +
   faster-whisper "small" full-utterance). Faz 0 için nedensellik simülasyonu YOK
   (sanity check'e gerek yoktu); gerçek V-C TSYNC koşulu streaming simülasyonu kullanacak.

### Avatar modeli kararı
- **`public/human.glb`** = üretim avatarı, 51 ARKit morph target (jawOpen, mouthClose...).
  vroid_male.vrm DEĞİL (VRoid morph adları ARKit değil). Model dokusuz (kil görünümü)
  ama S3FD yüzü %100 tespit ediyor.

### SyncNet kurulumu
- `/tmp/syncnet_python` (joonson/syncnet_python) — `download_model.sh` ile syncnet_v2.model
  + sfd_face.pth indirildi. NOT: /tmp'de — kalıcı yere klonlanmalı (yeniden kurulum gerekebilir).
- Base anaconda env'de scipy 1.13→1.17 yükseltildi (numpy 2.2 uyumu; gensim uyarısı zararsız).
- `run_pipeline.py` için `--min_track 40` şart (kısa kliplerde default 100 track üretmiyor)
  ve `--overwrite` (yoksa eski çıktıyla sessizce devam ediyor, skor üretmiyor).

### Sanity check sonuçları (espeak 3.2s klipleri, 25fps)
| Klip | Koşul | AV offset (frame) | Beklenen |
|---|---|---|---|
| en0 | senkron | +1 (+40ms) | 0 |
| en0 | ses +200ms | -4 | -5 |
| en0 | ses -200ms | +6 | +5 |
| en1 | senkron | 0 | 0 |
| en2 | senkron | -8 | (gerçek pipeline kayması) |
| en2 | ses +200ms | **-13** | -8-5=**-13 BİREBİR** ✓ |

- SyncNet kaydırmalara ±1 frame hassasiyetle LİNEER yanıt veriyor → ölçüm aleti olarak geçerli.
- en2'deki -8: SyncNet hatası değil, o klipte whisper-small'un espeak sesindeki timestamp
  kayması (SyncNet bunu doğru yakaladı). DERS: gerçek değerlendirmede espeak DEĞİL,
  gerçek konuşma sesi kullanılacak.
- Mutlak LSE-D ~11.3-12.2 (insan videosu normu ~6-8'den yüksek — kil yüz, beklenen),
  LSE-C ~1.6-2.2. Koşullar-arası GÖRELİ karşılaştırma anlamlı; makaledeki kalibrasyon
  notu bu gözlemle yazılacak.

## Faz 1 — TAMAMLANDI ✅ (`make_conditions.py`)

Tüm 6 koşul üretiliyor: `python3 make_conditions.py --wav X.wav --lang en
[--transcript "..."] [--textgrid X.TextGrid] --outdir DIR [--conditions ...]`
- AMP: RMS zarf (95-pct normalize, asimetrik attack/release) → JawOpen≤0.55
- RATE: main.py `_viseme_worker`'ın birebir portu (13 char/s, _VISEME tablosu kopya,
  amp=min(1.4,env*2.2) ölçekleme, frame'e dönüştürülmüş EMA α)
- TSYNC: NEDENSEL streaming Layer-1 simülasyonu (`streaming_word_triples`: W=3.2/h=0.32/
  g=0.40, idealized real-time hop, deterministik) → Eq.4-5 → Eq.6-7
- TSYNC−dur (uniform), TSYNC−coart (nearest-phoneme step), MFA (TextGrid phones→kernel)
- en0 doğrulandı: 6 koşul üretildi, JawOpen/MouthClose istatistikleri makul ve ayrışık

### MFA artık LOKAL kurulu
- `conda run -n mfa mfa align <corpus> english_us_arpa english_us_arpa <out> --clean`
- corpus formatı: spk/utt.wav + spk/utt.lab

### Render performans bulguları (önemli)
- ~250-320ms/frame, SwiftShader CPU (GPU yolu YOK: Vulkan bayrağı 3ms ama BOŞ BEYAZ kare
  üretiyor — tuzak!; headed/egl/angle-gl hepsi WebGL context fail, Wayland oturumu)
- Maliyet vertex-bound: human.glb 4 mesh, head_lod0=144k vertex × 51 morph; gövde yok,
  çözünürlük düşürmek az kazandırıyor (640x480: 252ms, 320x240: 160ms)
- renderBatch (sayfa içi toplu render + dataURL) eklendi ama kazanç sınırlı çıktı
- Faz 3 planı: 4 paralel chromium worker → 600 video ≈ 2.5-3 saat (gece koşusu)

## ŞU AN ÇALIŞAN (arka plan): mini-pilot
en0 × 6 koşul render + SyncNet skorları → sıralama mantıklı mı (MFA en iyi, AMP en kötü
beklenir). Çıktı: /tmp/pilot_*.mp4, sonuçlar background task b4mhf1zrc.

## Sıradaki Adımlar
1. Mini-pilot sonuçlarını değerlendir (koşul sıralaması)
2. SyncNet'i kalıcı yere taşı (/tmp'de!) — örn. ~/tools/syncnet_python; model+weights
   yeniden indirilebilir (download_model.sh)
3. Faz 2 kararları (KULLANICIYLA): N (100 vs küçük), TR dahil mi, canlı Atlas ses kaydı nasıl
4. Faz 3: toplu render driver'ı (paralel worker, tek browser çok video) + metrik scriptleri
   (LVD: pygltflib morph delta, lag: çapraz korelasyon, timing: schedule vs MFA)

## Komut hatırlatmaları
```bash
# schedule üret
python3 paper/tools/render/make_blendshapes.py --wav X.wav --lang en --out X.json
# render
python3 paper/tools/render/render_video.py --schedule X.json --wav X.wav --out X.mp4 [--shift-ms 200]
# syncnet (cd /tmp/syncnet_python)
python3 run_pipeline.py --videofile X.mp4 --reference REF --data_dir OUT --min_track 40 --overwrite
python3 run_syncnet.py --videofile X.mp4 --reference REF --data_dir OUT
```
