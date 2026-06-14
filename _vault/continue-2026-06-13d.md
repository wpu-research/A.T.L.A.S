# Context Handoff — 2026-06-13d (§V-C Faz 2 tamamlandı, Faz 3'e geçiş)

## Aktif İş
ATLAS IEEE Access makalesi, §V-C (Table 4: SyncNet/LSE-C/D/LVD/lag/timing). Branch: main.
Faz 0 (SyncNet sanity ✅) ve Faz 1 (6 koşul üreteci ✅) tamamlandı (bkz. continue-2026-06-13c.md).

## Durum
**Faz 2 TAMAMLANDI ✅** — Kullanıcı 3 karar verdi (AskUserQuestion):
1. N=40-50 utterance
2. Sadece İngilizce (Türkçe yok)
3. Ses toplama: Gemini Live API ile batch üretim (aynı model/ses/persona, canlı mikrofon DEĞİL)

Bu kararlara göre:
- **`paper/tools/render/collect_audio.py`** yazıldı ve test edildi. 5 görev tipi
  (qa/task/chat/howto/summary) × 10 prompt = 50 utterance. Gemini Live
  (`gemini-2.5-flash-native-audio-latest`, voice "Charon", aynı main.py config'i)
  ile bağlanıp metin prompt gönderiyor, modelin native-audio çıkışını (24kHz PCM)
  + kendi output_transcription'ını kaydediyor.
- **TAMAMLANDI**: `paper/eval_audio/` → 50/50 utterance, manifest.json,
  toplam ~778s (~13 dk) ses. Tüm wav+txt dosyaları mevcut, doğrulandı.
- **`paper/tools/render/run_eval.py`** yazıldı (henüz TEST EDİLMEDİ) — 4 stage:
  mfa → schedules → render → syncnet. Resumable, `--workers N` ile paralel render.

## Sıradaki Adım
1. **`compute_metrics.py` yazılmalı** (run_eval.py'nin docstring'inde referans var ama dosya YOK):
   - LVD: pygltflib ile human.glb morph-delta tabanlı dudak bölgesi vertex mesafeleri
     (vertex set TBD — head_lod0 mesh, dudak çevresi morph'larından etkilenen vertexler)
   - Timing error: schedule midpoint'leri vs MFA TextGrid fonem zamanları
   - Lag: JawOpen vs ses zarfı çapraz korelasyonu
   - Şema: schedules + results.json'dan tüketecek (render gerektirmez)
2. **`run_eval.py --audio paper/eval_audio --work paper/eval_work --workers 4` çalıştırılmalı**
   - Maliyet tahmini: ~250-320ms/frame (SwiftShader CPU) × ~75-190 frame × 6 koşul × 50
     utterance ≈ ÇOK SAATLİK İŞ. Arka planda (background task) başlatılmalı.
   - Önce `--stage mfa` ve `--stage schedules` hızlı test edilebilir (render'dan önce).
   - SyncNet `/tmp/syncnet_python`'da — kalıcı yere taşınması önerildi ama henüz yapılmadı
     (run_eval.py şu an SYNCNET_DIR = /tmp/syncnet_python sabit; /tmp kalıcı olmayabilir,
     eğer silinmişse download_model.sh ile yeniden kurulmalı).
3. Sonuçlar (results.json + compute_metrics çıktısı) elde edilince:
   - Faz 4: Table 4 oluştur, §V-C metnini yaz
   - Abstract/Contribution 4/Conclusion'daki §V-C placeholder'larını gerçek sayılarla doldur
   - §V-B'ye ses toplama metodolojisini DÜRÜSTÇE yaz (Gemini Live batch generation,
     canlı mikrofon kaydı değil — aynı model/ses/persona)

## Açık Sorular
- Mini-pilot'taki (en0, n=1) tuhaf sıralama (AMP en iyi LSE-D/C skorladı, MFA/TSYNC'den
  daha iyi — beklenenin tersi) henüz analiz edilmedi/tartışılmadı. N=50 sonuçları
  çıkınca tekrar bakılmalı; n=1 gürültüsü olası açıklama. BLOCKER değil ama not edilmeli.
- SyncNet `/tmp/syncnet_python` kalıcı değil — taşınmalı mı yoksa /tmp hayatta mı kontrol
  edilmeli önce.
- compute_metrics.py'deki "dudak bölgesi vertex set" tanımı henüz yapılmadı (human.glb
  head_lod0, 144012 vertex, 51 morph — hangi vertexler LVD için kullanılacak?).

## Önemli Bağlam
- TÜM SONUÇLAR GERÇEK ÖLÇÜM OLMALI — fabrikasyon YASAK (taslak uyarısı: "Submitting
  fabricated data constitutes research misconduct").
- §V-D tamamen bitti, commit `82d103b` push'landı. Sadece §V-C kaldı.
- 6 koşul: AMP, RATE (deployed), TSYNC (full pipeline), TSYNC-dur (uniform duration
  ablation), TSYNC-coart (nearest-phoneme step, kernel yok), MFA (non-causal oracle).
- Render: playwright + chromium + SwiftShader ZORUNLU
  (`--use-angle=swiftshader --enable-unsafe-swiftshader`). GPU yolları hepsi başarısız
  (Vulkan bayrağı boş beyaz kare üretiyor — sessiz tuzak).
- Avatar: `public/human.glb`, 51 ARKit morph, jawOpen morph'lu mesh = head_lod0 (144012 vert).
- MFA lokal kurulu (conda env "mfa"), english_us_arpa model+dictionary indirildi.

## İlgili Dosyalar
- `paper/ATLAS_IEEE_Access_Draft.md` — sadece §V-C `[MOCK]` kaldı (DRAFT STATUS NOTICE'da işaretli)
- `paper/tools/render/collect_audio.py` — TAMAMLANDI, 50/50 ses üretildi
- `paper/eval_audio/` — manifest.json + 50× (.wav, .txt), 778s toplam
- `paper/tools/render/make_conditions.py` — 6 koşul üreteci (Faz 1, TAMAMLANDI)
- `paper/tools/render/render_video.py`, `render_page.html` — render altyapısı (Faz 0, TAMAMLANDI)
- `paper/tools/render/run_eval.py` — yazıldı, TEST EDİLMEDİ, compute_metrics.py'yi referans
  alıyor ama o dosya henüz YOK
- `paper/tools/render/compute_metrics.py` — HENÜZ YAZILMADI (sıradaki öncelik)
- `paper/tools/grid_layer_validation.py` — §V-D aracı (TextGrid parse fonksiyonları
  make_conditions.py'de mfa_timed_phonemes için reuse ediliyor)
