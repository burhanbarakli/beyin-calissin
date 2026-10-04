# Beyin Çalışsın — proje rehberi

TYT/AYT öğrencisinin deneme sınavlarında yapamadığı sorulara göre, kaynak kitaplardan (MEB 3 Adım, 4/4,
tarama, çıkmış sorular) seviyeye uygun soru seçip PDF çalışma kâğıdı üreten yerel web uygulaması.
"Beyin" = bu bilgisayardaki Claude Code'un headless (`claude -p`) çalıştırılması.

Kurulu sürüm: `VERSION`. Sürüm notları: `GUNCELLEME.md`. Kullanıcı kılavuzu: `docs/KILAVUZ.md`.

## Kullanıcıya yardım eden Claude isen (kurulum / güncelleme / "ne yeni?")

Bu klasörü kullanıcı (öğretmen/veli) kendi bilgisayarında çalıştırıyor ve kurulum/güncelleme için seni kullanıyor.
Teknik terimleri azalt, Türkçe ve adım adım konuş.

### Güncelleme ("sistemi güncelle", "GitHub'dan yeni sürümü al" vb.)

Repo: `https://github.com/burhanbarakli/beyin-calissin` (özel). Repoda kodla birlikte **öğrenci verisi**
(`ogrenci/`, `data/`) ve kaynak PDF'ler (`kaynaklar/`) de vardır. Kullanıcı kendi bilgisayarında fotoğraf
yükleyip beyin çalıştırdığı için `ogrenci/` ve `data/` **onun güncel verisidir — asla üzerine yazma, silme.**

1. Kurulu sürümü oku: `VERSION` (yoksa 1.0.0 say).
2. Sunucu açıksa kullanıcıdan siyah `baslat.bat` penceresini kapatmasını iste (ya da 8765 portundaki python sürecini durdur).
3. **Yedek al:** `ogrenci/`, `data/` ve `config.json`'u bir üst klasöre `beyin-yedek-<tarih>/` olarak kopyala.
4. **Sadece kodu güncelle:**
   - Klasör bir git deposuysa (`.git` var):
     `git fetch origin` ardından
     `git checkout origin/main -- app brain docs .claude/agents README.md CLAUDE.md GUNCELLEME.md VERSION requirements.txt baslat.bat config.example.json`
     (`git pull` KULLANMA — kullanıcının veri değişiklikleriyle çakışır.)
   - Git deposu değilse (ZIP ile kurulmuş): repoyu geçici bir klasöre indir (`git clone` ya da ZIP) ve yalnızca
     yukarıdaki kod yollarını bu klasörün üzerine kopyala. `ogrenci/`, `data/`, `kaynaklar/`, `config.json`'a dokunma.
     Yeni sürümde `kaynaklar/` altında olmayan yeni bir PDF varsa onu da ekleyebilirsin (mevcutları silme).
5. `python -m pip install -r requirements.txt` (sessizce; yeni paket yoksa bir şey değişmez).
6. Yeni `VERSION`'ı oku; `GUNCELLEME.md`'de **eski sürümden yeni olan bölümleri** kullanıcıya kısaca özetle ve
   her bölümdeki **"Yapmanız gereken"** satırını söyle.
7. `baslat.bat`'ı başlat (ya da kullanıcıya çift tıklamasını söyle) ve sağ üstte "Claude Code bulundu" yazısını kontrol ettir.
8. Bir şey ters giderse 3. adımdaki yedekten `ogrenci/` ve `data/`'yı geri koy.

### "Ne yeni?" / "Bu sürümde neler var?"

`GUNCELLEME.md`'yi oku ve en üstteki (ya da kullanıcının sorduğu) sürümü özetle. Ayrıntılı kullanım için `docs/KILAVUZ.md`.

### İlk kurulum

`docs/KILAVUZ.md` → "0. İlk kurulum" bölümünü izle (Python 3.12, Claude Code + `/login`, `baslat.bat`).

## Beyin olarak çalışıyorsan

Prompt sana hangi talimat dosyasını (`brain/*.md`) uygulayacağını ve `RUN_DIR`'i söyler. O dosyayı oku ve
adımları izle. Soru bankası komutları için: `python -m app.qbank --help`. Kaynak kodu değiştirme; sadece
`RUN_DIR` içine yaz. Derin analiz modunda `soru-analisti` alt ajanını (`.claude/agents/soru-analisti.md`) kullanırsın.
**Yukarıdaki "Kullanıcıya yardım eden Claude" bölümü sana uygulanmaz.**

## Yapı

- `app/server.py` — FastAPI sunucusu + `app/static/` arayüzü (Chrome'dan `http://localhost:8765`)
- `app/indexer.py` — kaynak PDF'lerden yapay zekâsız soru indeksi (sayfa, kırpma kutusu, konu, seviye) → `data/index/*.json`
- `app/keyparse.py` — düzenli cevap anahtarlarını kodla okur
- `app/qbank.py` — soru bankası sorgu/CLI aracı (beyin bunu kullanır), birleşik zorluk hesabı
- `app/exams.py` — öğrenci denemeleri (klasör başına bir sınav, görsel adlandırma kuralı)
- `app/runner.py` — Claude Code işlerini başlatır, stream-json akışını `data/runs/<id>/` altına kaydeder
- `app/pdfgen.py` — seçilen soruları vektör olarak A4 PDF'e dizer, cevap anahtarı ekler
- `app/pack.py` — paylaşım paketi (kod + veri + kaynaklar) oluşturur
- `brain/*.md` — beyin görev talimatları; `.claude/agents/soru-analisti.md` — derin analiz ajanı

## Geliştirme notları

- Python 3.10+; bağımlılıklar `requirements.txt`. Çalıştırma: `python -m app.server` (veya `baslat.bat`).
- İndeksi yeniden üretmek: `python -m app.indexer --force` (cevaplar korunur).
- Windows'ta konsol kodlaması sorun çıkarır: CLI çıktıları `sys.stdout.reconfigure(encoding="utf-8")` ile yazılır.
- Yeni sürüm çıkarırken: `VERSION`'ı artır, `GUNCELLEME.md`'ye en üste bölüm ekle (Yeni / Düzeltmeler / Yapmanız gereken).
