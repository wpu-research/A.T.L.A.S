# Context Handoff — 2026-06-13 (V-D Layer-wise Validation — debugging saga)

## Amaç
§V-D Table 5'in `[MOCK]` satırlarını gerçek ölçümle değiştirmek. GRID korpusu **diğer PC'de**
(`C:\Users\wpu-ai\Desktop\Atlas_Journal\grid_corpus`, Windows, conda env `mfa`).
İş akışı: script burada (Linux) yazılıyor → kullanıcı diğer PC'ye **manuel kopyalıyor**
(düz `Atlas_Journal\grid_layer_validation.py` olarak, paper\tools altında değil) → sonuçları
chat'e yapıştırıyor.

## Tamamlananlar

1. **`paper/tools/grid_layer_validation.py` yazıldı** — alt komutlar:
   - `prepare-mfa`: GRID .align → MFA korpusu (.lab + wav symlink/copy)
   - `layer1 [--model tiny|base|small]`: Whisper word boundary MAE (start/mid/end ayrı) + WER
   - `layer2 [--with-asr] [--model ...]`: Eq.4 λ-prior vs uniform fonem orta nokta MAE
     (MFA TextGrid'e karşı; MFA'nın phone sequence'i sabit alınır, G2P kullanılmaz —
     Eq.4'ün "bilinen diziyi zamana bölme" işini izole eder)
   - `report`: Table 5 markdown
   - `normalize_wer_tokens()`: GRID "c four" ↔ Whisper "c4" birleşik token sorunu için
     (sayı-kelime→rakam + harf+rakam split). WER normalize token'larla; boundary MAE
     orijinal token'larla (uydurma timestamp yok, sadece kapsam düşer).
   - `trim_leading_silence()`: RMS-eşikli baş-sessizlik kırpma; **sustained onset**
     (5 ardışık frame ≥ %10×max RMS) — tek-frame tıkırtılara dayanıklı. Lokal sentetik
     testlerle doğrulandı (click'li: 0.620s ✓, temiz: 0.620s ✓, sadece-sessizlik: 0.0 ✓).

2. **Diğer PC'de tamamlanan adımlar:**
   - MFA kuruldu (conda env `mfa`), `english_us_arpa` acoustic+dictionary indirildi
   - `prepare-mfa`: 6000 utterance (s29-s34) hazırlandı
   - `mfa align` 80 saniyede bitti → `mfa_out\` TextGrid'ler hazır
   - ÖNEMLİ: Windows'ta `$env:KMP_DUPLICATE_LIB_OK="TRUE"` şart (MFA/ctranslate2 OpenMP çakışması)

3. **Layer-1 ölçüm sonuçları (tiny, 6000 utt, s29-s34):**
   - Tur 1 (normalizasyonsuz): WER %48.2 → tokenizasyon artefaktı tespit edildi
   - Tur 2 (normalize): **WER %23.8** (gerçek; "bin"→"been" homofonları dahil; tahmin
     bandım %10-25 idi, üst sınırda)
   - Boundary MAE: start=326, mid=345, end=368 ms — üçü de yüksek
   - İşaretli teşhis: **mean=-325ms, median=-360ms, %94 ERKEN** → sistematik kayma, gürültü değil
   - HYP-REF karşılaştırması: Whisper tüm kelimeleri ~baş-sessizlik süresi kadar erkene
     kaydırıyor; span'ler birebir uyumlu (göreli dizilim İYİ)

## Çözüm Denemeleri (hepsi başarısız — sayılar hiç değişmedi)
1. `vad_filter=True` (Silero) → etkisiz (default speech_pad_ms=400 GRID'in 0.2-0.95s
   sessizliğini kırpmıyor)
2. Manuel trim v1 (tek frame > %5×max) → tek-frame click'ler onset'i 0'a çekti
3. Manuel trim v2 (sustained 5×frame > %10×max) → offset'ler HÂLÂ ~0.00
   (bbaj1a'da 0.01 — yeni sürüm çalışıyor ama onset baştan bulunuyor; baş kısımda
   sürekli enerji var, muhtemelen NEFES)

## ŞU ANKİ DURUM — kritik bekleyen test
**Yeni hipotez: Whisper masum olabilir — GRID wav'ları ile .align dosyaları birbirine
göre kaymış olabilir** (audio farklı kaynaktan/kırpmadan geliyorsa korpus-içi tutarsızlık).
Hakem testi kullanıcıya gönderildi (chat'teki son mesaj): **MFA TextGrid 'words' tier'ı
vs GRID .align kelime başlangıçları** — 50 utterance, işaretli istatistik.
- MFA da ~-325ms kayıksa → korpus verisi kaymış; referansı .align yerine MFA yaparız
  (fonem referansı zaten MFA). Layer-1 word boundary MAE'yi MFA'ya karşı ölçeriz.
- MFA .align ile uyuşuyorsa (±30ms) → kayma gerçekten Whisper'ın; trim'e devam
  (mutlak eşik dene) veya bias-düzeltilmiş MAE raporla.

## Sıradaki Adımlar (test sonucuna göre)
1. MFA-vs-ALIGN sonucunu değerlendir → referans kararı ver
2. layer1'i tiny + base ile final çalıştır (`--out layer1_tiny.json` / `layer1_base.json`)
3. `layer2 --with-asr` çalıştır → λ-prior vs uniform + composed satırlar
4. `report` → Table 5
5. Makale güncellemeleri:
   - Table 5 gerçek sayılarla, gerçek n ile
   - §V-D metni: "λ priors fit on s1-s28" → "fixed design priors (Eq.4), validated on
     held-out s29-s34" (priors corpus'tan fit EDİLMEDİ — layer23_bench.py DUR_PRIOR sabitleri)
   - Satır 184: "[23] ms [MOCK — measure]" → gerçek Layer-2 MAE
   - WER %23.8 + tiny zafiyeti dürüstçe; V-E'deki "tiny yetersiz" bulgusuyla tutarlı
   - **Yeni bulgu §IV-B'ye**: canlı Layer-1'de VAD/onset-hizalama ZORUNLU bileşen
     (baş-sessizlik saat kayması lip-sync'i bozar) — bu debugging'den çıkan gerçek katkı
   - DRAFT STATUS NOTICE'dan V-D'yi çıkar
6. Sonra §V-C (SyncNet/LSE-C/D/LVD) — ayrı büyük iş paketi, henüz başlanmadı

## Önemli Bağlam Notları
- Beklenti kalibrasyonu (kullanıcıya söylendi): iddia için word boundary MAE 20-45ms
  gerekiyordu; tiny için gerçekçi 80-200ms; WER ideal %3-8, tiny+GRID gerçekçi %10-25.
- Whisper tiny'nin göreli kelime dizilimi iyi — kayma çözülürse MAE ciddi düşebilir.
- `/tmp/grid_test/` (lokal) SAHTE fixture — gerçek GRID değil (enerji onset'i align'la
  uyuşmuyor, Whisper hiçbir şey tanımıyor, s1/s29 align'ları birebir aynı). Lokal teşhiste
  KULLANMA.
- Lokalde faster-whisper kurulu; sentetik testler çalışıyor.
- SCI yayın değerlendirmesi (kullanıcıya verildi): §V-C dolmadan gönderilemez; V-D gerçek
  sayıları mock'tan kötü olsa da dürüst çerçeveleme + model-boyutu karşılaştırmasıyla
  savunulabilir. "Training-free speech-to-viseme kütüphanesi çekirdeği" olarak open-source
  paketleme fikri konuşuldu (makale sonrası iş).

## İlgili Dosyalar
- `/home/wpu/Downloads/Projects/Atlas/paper/ATLAS_IEEE_Access_Draft.md`
- `/home/wpu/Downloads/Projects/Atlas/paper/tools/grid_layer_validation.py` (ana script)
- Diğer PC: `C:\Users\wpu-ai\Desktop\Atlas_Journal\` — grid_corpus, mfa_corpus, mfa_out,
  grid_layer_validation.py (manuel kopya), layer1_results.json (eski turlar)
