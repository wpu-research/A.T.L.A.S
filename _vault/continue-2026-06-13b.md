# Context Handoff — 2026-06-13b (V-D TAMAMLANDI — gerçek veri makaleye işlendi)

## Bu oturumda tamamlanan (devamı: continue-2026-06-13a.md'deki debugging'in çözümü)

### Kök neden bulundu ve çözüldü
- MFA-vs-ALIGN hakem testi (`check-align` alt komutu): MFA da .align'a göre **-362ms (SD 165)**
  kayık → **korpusun audio edisyonu ile .align dosyaları birbiriyle tutarsız** (wav'larda
  konuşma ~0.04s'de başlıyor, .align 0.2-0.95s baş sessizliği varsayıyor). Whisper masumdu.
- Çözüm: tüm zaman referansları **MFA'ya** çevrildi (`layer1 --mfa-out`, layer2'de
  `parse_textgrid_tier(tg,'words')`). Trim artık no-op ama genellik için duruyor.

### Final ölçümler (6000 utt, s29-s34, MFA referans)
**Layer-1 tiny:** WER %24.6, start MAE 69(68), mid 53(35), end 73(55), matched 18666/36000
**Layer-1 base:** WER %18.0, start MAE 90(61), mid 87(54), end 101(76), matched 19939/36000
  → İLGİNÇ BULGU: base WER'i düşürüyor ama timestamp'i İYİLEŞTİRMİYOR (90 vs 69) —
  attention-derived timestamp sınırı, model ölçeği çözmüyor.
**Layer-2 (101,265 fonem):** GT words + λ priors **18.5(16.0)ms**, uniform 20.1(19.6)ms
  → λ avantajı GRID'de MARJİNAL (%8) — mock'taki "yarıya indirir" iddiası kaldırıldı,
  "kısa kelimelerde uniform zaten near-optimal, uzun kelimelerde avantaj open question" yazıldı.
**Composed (55,502 fonem):** 64.8(53.9)ms → recognizer-dominated (18.5→64.8, word-start
  MAE 69'u izliyor). ±45ms sınırının ÜSTÜNDE — dürüstçe yazıldı.

### Makale güncellemeleri (hepsi yapıldı)
- **Table 5** gerçek sayılarla (n=6000; 101,265/55,502 fonem) + 3 gözlemli discussion paragrafı
- **§V-D metni**: MFA referans + .align tutarsızlık notu + λ "fixed design constants, not
  fitted" + WER normalizasyon açıklaması (callsign "c4" sorunu)
- **Satır ~180**: "[design values, to be fit]" → "fixed design priors... not fitted to any corpus"
- **Satır ~184**: "[23] ms [MOCK]" → "18 ms given reference word boundaries, rising to 65 ms
  end-to-end (Section V-D)"
- **§IV-B**: yeni paragraf — Whisper onset-anchoring/leading-silence saat kayması bulgusu,
  "Layer 1 requires explicit onset handling" (debugging'den çıkan gerçek katkı)
- **Abstract**: V-D sonuç cümlesi eklendi (18ms / ±45ms bound / 65ms composed)
- **Contribution 5**: yeniden yazıldı — V-D + V-E + V-F üçlüsü
- **Conclusion**: V-D cümlesi eklendi, placeholder sadece V-C'ye daraltıldı
- **Limitations**: "Seventh" eklendi (composed 65ms > 45ms bound; çare daha iyi boundary
  estimation, daha büyük model değil); "Fourth" (λ priors) gerçek bulguyla yeniden yazıldı
- **Future Work**: streaming boundary refinement (CTC tabanlı) eklendi
- **§V başı + DRAFT NOTICE**: "yalnızca V-C mock kaldı" durumuna güncellendi
- **V-F**: "prior-fitting" ifadeleri "Layer-2 validation/sanity checks" olarak düzeltildi

### Script son durumu (`paper/tools/grid_layer_validation.py`)
- `layer1 --mfa-out mfa_out` (MFA referans), `--model tiny/base/small`
- `check-align` alt komutu (korpus tutarlılık teşhisi)
- Windows cp1252 fix: `sys.stdout.reconfigure(encoding='utf-8')` main()'de
- `report` çıktısı utf-8 ile yazılıyor
- Sonuç JSON'ları diğer PC'de: layer1_tiny.json, layer1_base.json, layer2_results.json

## KALAN İŞLER
1. **§V-C (Table 4, SyncNet LSE-C/D, LVD, lag) — SON MOCK bölüm.** Gerektirdikleri:
   - N=100 canlı utterance toplama + 6 koşul render (AMP/RATE/TSYNC/TSYNC−dur/TSYNC−coart/MFA)
   - SyncNet pretrained + **sanity check önce yapılmalı** (VRM stilize yüzde çalışıyor mu,
     ±200ms shift ayrımı) — başarısızsa Table 4 LVD+lag+timing ile yeniden kurgulanır
   - Layer 1-3'ün render hattına entegrasyonu gerekiyor (şu an standalone)
2. Abstract satır 15 sonundaki `[PLACEHOLDER]` (SyncNet raporlama cümlesi) — V-C ile çözülür
3. Contribution 4'teki `[PLACEHOLDER — to be measured]` — V-C ile çözülür
4. Küçükler: §III'teki tool-routing placeholder (satır ~120), referans [6] verify,
   ref [27] verify, Appendix repo URL, satır 164 "[design values... finalize]", §VI-A
   "[verify against real data]"
5. `build_paper_docx.py` ile docx yeniden üretilmeli (yeni sonuçlarla)

## Önemli notlar
- V-C'ye başlarken İLK iş SyncNet sanity check (en riskli ön-koşul, erken test et)
- Mock Table 4'ün timing err. kolonundaki 23/41ms değerleri eski mock V-D'ye bağlıydı;
  V-C ölçülünce gerçek composed (65ms) ile tutarlılık kontrol edilmeli
- GRID korpusu + MFA çıktıları diğer PC'de duruyor (silinmesin — V-C'nin MFA-oracle
  koşulu için de gerekebilir)
