# 🧠 Beyin Çalışsın

TYT/AYT öğrencisinin deneme sınavlarında **yapamadığı sorulara** bakıp eksik kavramı teşhis eden ve
kaynak kitaplardaki **gerçek sorulardan** seviyeye uygun bir çalışma kâğıdı (PDF) hazırlayan yerel web
uygulaması.

"Beyin", uygulamanın çalıştığı bilgisayardaki **Claude Code**'dur. Arayüzde **🧠 Beyin Çalışsın**
butonuna basıldığında sunucu `claude -p` komutunu başlatır. Claude öğrencinin yanlış soru fotoğraflarını
ve deneme sonuçlarını inceler, soru bankasında arama yapar ve aday soruları önerir. Öğretmen
adaylar arasından seçim yapar, seçilen sorular tek tıkla PDF'e dönüşür.

> 📖 **Resimli kılavuz (neresi ne işe yarar):** [docs/KILAVUZ.md](docs/KILAVUZ.md) ·
> 🆕 **Yenilikler:** [GUNCELLEME.md](GUNCELLEME.md) · **Güncellemek için** Claude Code'a bu klasörde
> *"sistemi GitHub'dan güncelle"* demeniz yeterli; verileriniz korunur (ayrıntı: `CLAUDE.md`).
> Hızlı başlangıç: Python + Claude Code kurun, `claude` → `/login`, sonra `baslat.bat`'a çift tıklayın.

![Aday sorular](docs/img/2-adaylar.png)

```
Deneme sonuçları + yanlış soru fotoğrafları
        │
        ▼
 🧠 Claude Code (teşhis → konu → seviye)  ──►  soru bankası (kaynak PDF'lerden otomatik indeks)
        │
        ▼
 Aday sorular: Hatırlatıcı / öğretici → Pekiştirme → Zorlayıcı
        │  (öğretmen seçer, sıralar)
        ▼
 📄 A4 PDF: yapamadığı sorular + seçilen sorular + cevap anahtarı
```

## Özellikler

- **Otomatik soru bankası:** Kaynak PDF'lerdeki (MEB 3 Adım, 4/4, tarama testleri, çıkmış sorular) her
  soru kodla bulunur. Sayfası, kırpma kutusu, konusu, seviyesi (1./2./3. Adım, Test 1-4) ve ÖSYM etiketi
  kaydedilir. 40 kitaplık bir set yaklaşık 5 dakikada 33.000 soruya indekslenir.
- **Cevap anahtarı okuma:** Düzenli anahtarlar (3 Adım `1-C`, 4/4 tablo, tarama listesi) kodla okunur.
  Kalanları Claude anahtar sayfalarını görerek tamamlar. Çözümlü örneklerde `Cevap: X` doğrudan alınır.
- **Teşhis:** Claude yanlış soru fotoğraflarını açıp eksik beceriyi bulur. Örneğin "Fonksiyon" etiketli
  bir sorudan "ters fonksiyonda f⁻¹(a)=b ⇒ f(b)=a eksik" sonucunu çıkarır. Sonuç karnesi (PDF) varsa
  konu analizini de okur.
- **Seviyeli aday listesi:** Her eksik konu için önce çözümlü örnekler ve temel sorular, sonra pekiştirme,
  sonra zorlayıcı (3. Adım / ÖSYM) sorular gelir. İstenen sayının yaklaşık 2 katı aday gösterilir ve
  önerilenler işaretli gelir.
- **Kaliteli PDF:** Sorular kaynak PDF'ten vektör olarak alınır, yani bulanıklaşmaz. Orijinal soru
  numarası kapatılıp yenisi yazılır. Sona cevap anahtarı ve kaynak listesi eklenir.
- **Birleşik zorluk (1-5):** Her sorunun zorluğu dört katmanla hesaplanır:
  1. Kitap etiketi (1./2./3. Adım, Test 1-4, ÖSYM).
  2. **Claude puanı.** Beyin önerdiği her soruya puan verir; Kaynaklar sekmesindeki "⭐ Zorluk puanla" ile
     bir kitap toplu puanlanabilir.
  3. **Öğretmen geri bildirimi.** Kartlardaki Kolay / Uygun / Zor / ✕ Kullanma butonları. "Kullanma"
     denen soru bir daha önerilmez.
  4. **Öğrencinin sonucu.** Çıktılar sekmesindeki "📝 Sonuçları gir" ile her soru ✔ Yaptı / ✘ Yapamadı /
     Boş olarak işaretlenir. Beyin sonraki çalışmada `history` ile bu sonuçlara bakıp seviyeyi ayarlar.
- **Tekrar önleme:** Daha önce PDF'e konmuş sorular sonraki çalışmalarda önerilmez (Ayarlar'dan
  sıfırlanabilir).

## Gereksinimler

- Windows 10/11 (macOS/Linux'ta da çalışır; `baslat.bat` yerine `python -m app.server`)
- Python 3.10+ (`winget install -e --id Python.Python.3.12`)
- **Claude Code** kurulu ve oturum açılmış olmalı:
  ```
  irm https://claude.ai/install.ps1 | iex
  claude          # ilk çalıştırmada /login ile giriş yapın
  ```
  Claude masaüstü uygulamasıyla gelen `claude.exe` de otomatik bulunur. Ancak onun da terminalde bir kez
  `/login` ile oturum açması gerekir.

## Kurulum

```
git clone <bu-repo>
cd beyin-calissin
baslat.bat
```

`baslat.bat` eksik Python paketlerini kurar, `config.json` yoksa örnekten oluşturur ve tarayıcıda
`http://localhost:8765` adresini açar. İlk açılışta **Ayarlar** sekmesinden şunları girin:

| Ayar | Açıklama |
|---|---|
| Kaynak klasörleri | Soru kitabı PDF'lerinin bulunduğu klasörler (ör. `D:/Kaynaklar/MEB_TYT_Soru`) |
| Denemeler klasörü | Öğrencinin sınav klasörlerinin bulunduğu klasör |
| Claude Code yolu | Boş bırakılırsa otomatik bulunur |

Ardından **Kaynaklar → Yeni kitapları indeksle** butonuna basın.

### Kaynak dosya adları

İndeksleyici ders ve kitap türünü dosya adından anlar: `tyt_mat_3Adm.pdf`, `ayt_fizik_4_4.pdf`,
`tyt_bio_tarama.pdf`, `tyt_tarih_cikmis_Sorular.pdf`.
Ders kodları: `mat, fizik, kimya, bio, turkce, tarih, cografya, felsefe`.

### Denemeler klasörü

Her alt klasör bir sınavdır (ör. `D01_3D_2Eylül`). Sınav klasöründe şunlar bulunabilir:

- **Yapamadığı soruların fotoğrafları**, şu adlandırmayla:
  `<SınavKodu>_<Ders>_<Konu>_<Durum>_<SoruNo>_<DoğruCevap>.jpeg`
  Örnek: `D01_Mat_Fonksiyon_Yapamadı_10_E.jpeg`. Durum şunlardan biri olur: `Yanlış`, `Boş`, `Yapamadı`,
  `Zorlandı`. Ders kodları: `Mat, Geo, Fiz, Kim, Bio, Tur, Tar, Cog, Fel, Din`.
  Arayüzden yüklerken bu ad otomatik verilir.
- Deneme kitapçığı PDF'i (isteğe bağlı).
- `Sonuçlar/` klasöründeki karne PDF'i, **Sınavlar** sekmesinden sınava bağlanabilir.

## Kullanım

1. **Sınavlar:** Sınav ekleyin, fotoğrafları sürükleyip bırakın, sonuç PDF'ini seçin. İsterseniz
   "🧠 Sonucu analiz et" ile netleri ve zayıf konuları çıkarın.
2. **Beyin:** "Son 3/4/5" ile sınavları seçin (ya da tekil soruları işaretleyin). Dersleri, konu başına
   soru sayılarını ve varsa notunuzu girin, **🧠 Beyin Çalışsın** butonuna basın. Claude'un ne yaptığı
   canlı akar.
3. **Seçim:** Aday kartlarına tıklayarak seçin. Sağ alttaki sepetten sıralayın, rolleri değiştirin.
4. **📄 PDF Oluştur:** PDF yeni sekmede açılır. Tüm çıktılar **Çıktılar** sekmesinde saklanır.
5. **📝 Sonuçları gir:** Öğrenci kâğıdı çözünce Çıktılar sekmesinden hangi soruları yaptığını işaretleyin.
   Döngü böylece kapanır: sonraki beyin çalışması bu sonuçları dikkate alır.

## Mimari

| Dosya | Görev |
|---|---|
| `app/server.py` | FastAPI sunucusu, REST API |
| `app/static/` | Arayüz (tek sayfa, bağımlılıksız) |
| `app/indexer.py` | PDF → soru indeksi (PyMuPDF; sütun/numara tespiti, içindekilerden konu, ADIM/TEST seviyesi) |
| `app/keyparse.py` | Düzenli cevap anahtarlarını kelime konumlarından okur |
| `app/qbank.py` | Soru bankası arama/görsel/cevap CLI'ı: `python -m app.qbank --help` |
| `app/exams.py` | Sınav klasörleri, görsel adlandırma |
| `app/runner.py` | Claude Code'u headless başlatır (`--output-format stream-json`), akışı kaydeder |
| `app/pdfgen.py` | Vektör kırpımlarla A4 PDF |
| `brain/*.md` | Claude'a verilen görev talimatları (teşhis, cevap anahtarı, sınav analizi, zorluk puanlama) |
| `data/ratings.json`, `feedback.json`, `student_results.json` | Claude puanları, öğretmen geri bildirimi, öğrenci sonuçları |

Claude'un izinleri `app/runner.py` içindeki `ALLOWED_TOOLS` listesiyle sınırlıdır: dosya okuma/yazma
ve `python` komutları. Her çalışma `data/runs/<id>/` altında saklanır.

## Paylaşım paketi

`python -m app.pack D:/beyin-calissin-paylasim` komutu kod, veriler (`data/`), kaynak PDF'ler
(`kaynaklar/`) ve öğrenci klasörünü (`ogrenci/`) tek bir klasörde toplar. Ayarlar göreli yollarla
yazılır; paketi indiren kişide `baslat.bat` ile doğrudan çalışır. Başka bilgisayarda kaydedilmiş eski
mutlak yollar (ör. `D:/.../Denemeler/...`) klasör adına göre otomatik olarak yeniden eşlenir. Komutu
tekrar çalıştırmak paketi günceller; sadece değişen dosyalar kopyalanır.

## Gizlilik ve telif

- `config.json` ve `data/` (öğrenci verisi, indeks, çıktılar) **repoya girmez** (`.gitignore`).
- Kaynak kitap PDF'leri repoda yoktur; her kullanıcı kendi kaynaklarını gösterir.
- Claude çalışırken öğrencinin soru fotoğrafları ve sonuçları Anthropic'e gönderilir. Öğrenci/veli
  onayını göz önünde bulundurun.

## Sorun giderme

- **"Claude Code oturumu açık değil":** Terminalde `claude` çalıştırıp `/login` ile giriş yapın.
- **"Claude Code bulunamadı":** Ayarlar'a `claude.exe` yolunu yazın.
- **Soru kesimi hatalı:** Kitap farklı bir düzen kullanıyor olabilir. Kaynaklar sekmesinden
  "Hepsini yeniden indeksle" deneyin veya bir issue açın (sayfa görüntüsüyle).
