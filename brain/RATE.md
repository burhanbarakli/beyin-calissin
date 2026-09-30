# Görev: Kitaptaki soruların zorluğunu puanla (1-5)

Kitap `<BOOK>`, en fazla `<LIMIT>` soru, çalışma klasörü `<RUN_DIR>`.

Ölçek (TYT/AYT öğrencisi gözüyle):
- **1** tek adımlı tanım / hatırlatma
- **2** temel uygulama, tek kavram
- **3** TYT ortalaması; iki kavram ya da iki adım
- **4** çok adımlı, yorum veya dikkat gerektiren
- **5** ÖSYM'nin en zor soruları düzeyi

1. `python -m app.qbank torate <BOOK> --limit <LIMIT>` → puansız soruların metinleri.
2. Metinden karar ver. Şekil/grafik ağırlıklı ya da metni bozuk (matematik sembolleri dağınık) sorularda
   `python -m app.qbank show "<qid>"` ile PNG üretip Read ile bak. Hepsine bakma, sadece gerekenlere.
   Kitabın seviye etiketi (1./2./3. Adım, Test n) ipucudur ama bağlayıcı değildir.
3. `<RUN_DIR>/ratings.json` yaz: `[{"qid": "...", "difficulty": 3, "note": "iki adım, oran kurma"}]`
4. `python -m app.qbank rate <RUN_DIR>/ratings.json` ile kaydet.
5. Son mesajda: kaç soru puanlandı, puan dağılımı (1..5 kaç tane), kitabın genel zorluğu hakkında 1-2 cümle.
