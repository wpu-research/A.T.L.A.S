# Context Handoff — 2026-06-12 (devam — V-E + §VI kaldırma)

## Bu oturumda tamamlanan
1. **§V-E (Latency/CPU) artık GERÇEK veri içeriyor.**
   - `paper/tools/layer23_bench.py` — Layer 2/3 (G2P+Eq.4-5 süre tahmini, Eq.6-7 kernel
     synthesis) standalone implementasyon + benchmark. Sonuç: L_syn P95=0.070ms,
     L_g2p P95=0.042ms, CPU yükü %0.29 (one core). Sonuçlar: `paper/tools/layer23_bench_results.md`
   - `paper/tools/layer1_bench.py` — Layer 1 (streaming word-timestamp ASR) faster-whisper
     "tiny" int8 ile, W=3.2s/h=320ms/g=400ms tasarım değerleriyle simüle edildi.
     Audio: `paper/tools/layer1_audio/*.wav` (espeak-ng ile EN+TR, 10 cümle).
     Sonuç: EN emission lag P95=214ms (Δ≈215ms pratik), TR emission lag P95=4915ms
     (Δ≈4.9s — pratik DEĞİL, "tiny" model TR'de yavaş ve kararsız).
   - Bu **dil asimetrisi** gerçek bir bulgu olarak işlendi — Limitations'a (yeni §VI-B)
     eklendi, Future Work'e (§VI-C) "TR için base/small model benchmark" eklendi.
   - Table 6 tamamen yeniden yazıldı (gerçek sayılarla), §IV-E güncellendi.

2. **§VI (Perceptual Study, N=24, MOCK) tamamen kaldırıldı.**
   - Eski §VII Discussion → yeni §VI, eski §VIII Conclusion → yeni §VII.
   - Tüm "Section VI/VII/VIII" çapraz referansları güncellendi (satır 150, 217, 277,
     301, 303, 328, 356 ve civarı).
   - Contributions madde 5, Abstract, Conclusion, DRAFT STATUS NOTICE, TOC (satır 35)
     güncellendi — artık perceptual study yerine §V-E/§V-F'ye ve dil asimetrisine atıf var.

## Sıradaki Adım (kalan en büyük açık iş)
- **§V-C (Synchronization Results, SyncNet/LSE-C/D/LVD) ve §V-D (GRID Layer-wise
  validation, Tablo 5) hâlâ `[MOCK]`** — bunlar bu oturumda ele alınmadı.
- Bunlar için gerçek ölçüm: render edilmiş video + SyncNet (V-C), GRID üzerinde
  Whisper word boundary + MFA phoneme timing (V-D). Ayrı, büyük bir iş paketi.
- DRAFT STATUS NOTICE artık bunu doğru yansıtıyor: "Sections V-C and V-D remain MOCK".

## Önemli Bağlam
- TranscriptionSync (Layer 1-3) kod tabanında (`main.py`) DEPLOY EDİLMİŞ DEĞİL —
  sadece RATE varyantı (§IV-F) gerçekten çalışıyor. Bu oturumda yazılan Layer1-3
  implementasyonları **standalone modüller** (`paper/tools/layer1_bench.py`,
  `layer23_bench.py`) — makalede "component-wise implemented and benchmarked,
  full live integration is future work" olarak çerçevelendi (dürtüce, fabrication
  riski yok).
- `paper/tools/layer1_audio/` içindeki wav dosyaları repoya commit edilebilir
  (espeak-ng ile lokal üretildi, küçük dosyalar) — henüz git'e eklenmedi.

## İlgili Dosyalar
- `/home/wpu/Downloads/Projects/Atlas/paper/ATLAS_IEEE_Access_Draft.md`
- `/home/wpu/Downloads/Projects/Atlas/paper/tools/layer23_bench.py` (+ _results.md)
- `/home/wpu/Downloads/Projects/Atlas/paper/tools/layer1_bench.py`
- `/home/wpu/Downloads/Projects/Atlas/paper/tools/layer1_audio/*.wav`
