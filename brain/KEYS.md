# Görev: Kaynak kitabın cevap anahtarını soru bankasına işle

Kitap kimliği prompt'ta verilir (`<BOOK>`), çalışma klasörü `<RUN_DIR>`.

Not: Düzenli anahtarların çoğu indekslemede kodla (`app/keyparse.py`) okunmuş olabilir. Senin işin
**cevapsız kalan** bölümleri tamamlamak. Önce `python -m app.qbank unanswered <BOOK>` ile neyin eksik
olduğuna bak; sadece onlar için keys.json yaz. `setkeys` mevcut cevapları silmez, sadece verdiklerini yazar.
Anahtarda karşılığı olmayan bölümler (ör. "Test 1 (ek)" gibi kitap etiket hatası olanlar, ya da çözümlü
örnekler) için bir şey yapma.

1. `python -m app.qbank sections <BOOK>` → kitabın konu/seviye bölümlerini ve soru sayılarını gör.
   Konu adları ve seviye etiketleri (`1. Adım`, `Test 3`, boş) eşleştirmede AYNEN kullanılmalı.
2. `python -m app.qbank keypages <BOOK>` → cevap anahtarı sayfalarının metnini ve PNG yolunu verir.
   Metin dağınıksa PNG'yi Read ile aç ve tabloyu görsel olarak oku.
   Anahtar sayfası algılanmamışsa komut kitabın son 8 sayfasını verir. Başka sayfalara bakman gerekirse
   PDF yolu `python -m app.qbank books` çıktısının sonunda yazar:
   `python -m app.qbank pdftext "<pdf>" --pages 540-554`.
3. `<RUN_DIR>/keys.json` yaz:
   ```json
   {"sections": [
     {"topic": "Mantık", "level": "1. Adım", "answers": {"1": "D", "2": "C", "11": "E"}},
     {"topic": "Önermeler ve Bileşik Önermeler", "level": "Test 2", "answers": {"1": "E"}}
   ]}
   ```
   - `topic`: `sections` çıktısındaki konu adı (anahtardaki başlık farklı yazılmış olabilir; bankadakini kullan).
   - `level`: `sections` çıktısındaki seviye etiketi. Seviye yoksa `""`.
   - Tarama kitaplarında konu = "TYT TARAMA TESTİ-6" gibi test adıdır.
4. `python -m app.qbank setkeys <BOOK> <RUN_DIR>/keys.json` → eşleşme raporu.
5. `python -m app.qbank unanswered <BOOK>` → cevapsız kalan bölümleri gör; konu/seviye adlarını düzeltip
   keys.json'u güncelle ve 4. adımı tekrarla (en fazla 3 tur). Bir bölümde bankadaki soru sayısı anahtardan
   azsa bu normaldir (bazı sorular algılanamamış olabilir).
6. Son mesajda: toplam soru, cevaplanan, cevapsız kalan bölümler — kısa Türkçe rapor.
