# Beyin Çalışsın — proje rehberi

TYT/AYT öğrencisinin deneme sınavlarında yapamadığı sorulara göre, kaynak kitaplardan (MEB 3 Adım, 4/4,
tarama, çıkmış sorular) seviyeye uygun soru seçip PDF çalışma kâğıdı üreten yerel web uygulaması.
"Beyin" = bu bilgisayardaki Claude Code'un headless (`claude -p`) çalıştırılması.

## Yapı

- `app/server.py` — FastAPI sunucusu + `app/static/` arayüzü (Chrome'dan `http://localhost:8765`)
- `app/indexer.py` — kaynak PDF'lerden yapay zekâsız soru indeksi (sayfa, kırpma kutusu, konu, seviye) → `data/index/*.json`
- `app/qbank.py` — soru bankası sorgu/CLI aracı (beyin bunu kullanır)
- `app/exams.py` — öğrenci denemeleri (klasör başına bir sınav, görsel adlandırma kuralı)
- `app/runner.py` — Claude Code işlerini başlatır, stream-json akışını `data/runs/<id>/` altına kaydeder
- `app/pdfgen.py` — seçilen soruları vektör olarak A4 PDF'e dizer, cevap anahtarı ekler
- `brain/BRAIN.md`, `brain/KEYS.md`, `brain/EXAM.md` — beyin görev talimatları

## Beyin olarak çalışıyorsan

Prompt sana hangi talimat dosyasını (`brain/*.md`) uygulayacağını ve `RUN_DIR`'i söyler. O dosyayı oku ve
adımları izle. Soru bankası komutları için: `python -m app.qbank --help`. Kaynak kodu değiştirme; sadece
`RUN_DIR` içine yaz.

## Geliştirme notları

- Python 3.10+; bağımlılıklar `requirements.txt`. Çalıştırma: `python -m app.server` (veya `baslat.bat`).
- İndeksi yeniden üretmek: `python -m app.indexer --force` (cevaplar korunur).
- Windows'ta konsol kodlaması sorun çıkarır: CLI çıktıları `sys.stdout.reconfigure(encoding="utf-8")` ile yazılır.
- `config.json` ve `data/` kişiseldir, repoya girmez.
