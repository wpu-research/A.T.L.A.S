# Context Handoff — 2026-06-13e (§V-C Faz 3: render %75'te, 1 worker stalled)

## Aktif İş
ATLAS IEEE Access makalesi, §V-C (Table 4). Branch: main.
Faz 0,1,2 TAMAM (bkz. continue-2026-06-13d.md). Faz 3 (toplu render+metrik) sürüyor.

## Durum
- `compute_metrics.py` yazıldı ve lip-vertex extraction (`public/human.glb`, head_lod0,
  400 vertex, 14 kanal) doğrulandı.
- `run_eval.py --stage mfa` TAMAM (50/50 TextGrid, `paper/eval_work/mfa_out/`)
- `run_eval.py --stage schedules` TAMAM (300/300 JSON, `paper/eval_work/schedules/`,
  ~108MB, ~3.5 saat sürdü — TSYNC ailesi için causal Whisper simülasyonu)
- `run_eval.py --stage render --workers 4` ÇALIŞIYOR (arka plan, pid 454088,
  log: `/tmp/render_log.txt`). 07:53'te başladı.
  - **225/300 video tamam** (3 worker kendi 75'lik chunk'ını bitirdi).
  - **4. worker'ın 75 işi KALDI ve ~14:36'dan beri (≈3.5 saat) STALLED görünüyor**
    (chromium_headless_shell süreci 454165 hâlâ yaşıyor ama CPU kullanımı ~0,
    yeni dosya yazmıyor).
  - Hiçbir utterance'ın 6 koşulu birden tam değil (job sırası round-robin
    uid×cond olduğu için hepsi sona doğru tamamlanacaktı).

## Sıradaki Adım
1. **Stalled worker'ı teşhis et / yeniden başlat:**
   - `pgrep -af "run_eval|chromium_headless_shell"` ile süreçleri incele
   - Muhtemelen `pid 454088` ve ilgili worker sürecini `kill` et (225 video
     korunur, `stage_render` resumable — `out_mp4.exists()` kontrolü var)
   - `KMP_DUPLICATE_LIB_OK=TRUE python3 paper/tools/render/run_eval.py
     --audio paper/eval_audio --work paper/eval_work --stage render --workers 4`
     yeniden çalıştır — sadece eksik 75 (uid,cond) job'ı işleyecek
   - Düşün: belki `--workers 1` veya `2` ile yeniden başlatmak takılan worker'ı
     atlatır (round-robin dağılım farklı olur); ya da tek workerla kalan 75'i
     bitirmek de kabul edilebilir (yavaş ama garanti).
2. Render 300/300 olunca: `run_eval.py --stage syncnet`
   - SyncNet `/tmp/syncnet_python`'da mı kontrol et (ephemeral olabilir,
     silinmişse `download_model.sh` ile yeniden kur — modelin path'i
     SYNCNET_DIR sabiti run_eval.py'de)
3. `compute_metrics.py --audio paper/eval_audio --work paper/eval_work
   --model public/human.glb` çalıştır (render gerektirmez, schedules+mfa_out
   yeterli — bu paralelde de denenebilir, render'ı beklemeden!)
4. results.json (syncnet) + metrics.json (LVD/timing/lag) birleşince:
   Table 4 oluştur, §V-C metnini yaz, Abstract/Contribution/Conclusion
   placeholder'larını doldur (§V-C `[MOCK]` etiketlerini kaldır)
5. §V-B'ye ses toplama metodolojisini (Gemini Live batch generation) dürüstçe yaz

## Açık Sorular
- Stalled worker'ın kök nedeni belirsiz — uzun bir utterance (çok frame) mi,
  yoksa chromium/playwright hata mı verdi sessizce? Log'da hata yok
  (`/tmp/render_log.txt` son satır task09_tsync-coart done=75, o da worker 2'nin
  son işiymiş — yani worker 2 BİTTİ, başka bir worker (0,1, veya 3) takılı).
  Yeniden başlatınca log'u izlemek lazım.
- n=50 mi yeterli olacak yoksa stalled worker hiç bitmezse n=43-46 ile mi
  devam edilecek — kullanıcı n=40'ın kabul edilebilir olduğunu söyledi
  (40-50 aralığının alt sınırı).

## Önemli Bağlam
- TÜM SONUÇLAR GERÇEK ÖLÇÜM — fabrikasyon YASAK.
- 6 koşul: AMP, RATE, TSYNC, TSYNC-dur, TSYNC-coart, MFA (TSYNC ailesi = bizim
  sistemimiz, AMP/RATE/MFA = baseline/oracle referanslar).
- Render: SwiftShader CPU ZORUNLU (~250-320ms/frame), GPU yolları hepsi
  başarısız (bu sandboxed/Wayland ortamda). Bu makinede ~30-37 video/saat hız.
- run_eval.py 4 stage: mfa(✅) → schedules(✅) → render(%75) → syncnet(yapılmadı)
- compute_metrics.py render'a bağımlı DEĞİL — şimdi paralelde çalıştırılabilir.

## İlgili Dosyalar
- `paper/tools/render/run_eval.py` — batch driver (SYNCNET_DIR=/tmp/syncnet_python sabiti)
- `paper/tools/render/compute_metrics.py` — LVD/timing/lag (YENİ, TEST EDİLMEDİ end-to-end)
- `paper/eval_work/videos/` — 225/300 mp4
- `paper/eval_work/schedules/` — 300/300 json (108MB)
- `paper/eval_work/mfa_out/spk/*.TextGrid` — 50/50
- `/tmp/render_log.txt` — render stage log
- `paper/ATLAS_IEEE_Access_Draft.md` — sadece §V-C `[MOCK]` kaldı
