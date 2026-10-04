# Güncelleme Notları

En yeni sürüm en üstte. Kurulu sürüm `VERSION` dosyasında ve arayüzde başlığın yanında yazar.

> **Claude için:** Kullanıcı sistemi güncellediğinde, onun kurulu sürümünden yeni olan bölümleri ona
> kısaca ve Türkçe özetle. Her bölümdeki **"Yapmanız gereken"** satırını mutlaka söyle.
> Güncellemenin nasıl yapılacağı `CLAUDE.md` içindeki "Güncelleme" bölümündedir.

---

## 1.2.0 · 4 Ekim 2026 · Derin analiz

**Yeni**
- **🔬 Derin analiz:** Beyin panelinde, butonun üstünde yeni bir kutu. İşaretlenirse *soru analisti* ajanı devreye girer:
  - Öğrencinin her yanlış sorusunu baştan çözüp **adım düzeyinde teşhis** koyar: kopma noktası, hata türü (kavram/işlem/okuma/süre), kök neden.
  - Seçilen her adayı da çözerek **denetler**: cevap doğru mu, kesim tam mı, hedef beceriyi ölçüyor mu. Geçenler **✓ denetlendi** rozetiyle görünür.
  - Daha yavaş ve maliyeti normal modun yaklaşık 2-3 katı. Önerilen kullanım: Sonnet + derin analiz, bir deneme için yaklaşık 1-2 $.
- Beynin canlı akışında artık tek bir "Bitti" satırı var (toplam süre ve maliyet).

**Yapmanız gereken:** Güncellemeden sonra siyah pencereyi kapatıp `baslat.bat`'ı yeniden açın.

---

## 1.1.0 · 4 Ekim 2026 · Hızlı yükleme ve model seçimi

**Yeni**
- **Hızlı fotoğraf yükleme (Sınavlar sekmesi):** Sadece durum seçilir:
  - **Yapamadı / Yanlış / Doğru-Tereddütlü**. Fotoğraflar toplu olarak sürüklenip bırakılır, yükleme kendiliğinden başlar.
  - Ders, konu, soru no ve cevap **isteğe bağlı**; beyin bunları fotoğraftan kendisi bulur.
  - **Doğru yapılan soruları yüklemeye gerek yok.**
  - Beyin durumları önceliklendirir: Yapamadı > Yanlış > Doğru-Tereddütlü. Eski "Zorlandı" etiketli fotoğraflar "Tereddütlü" sayılır.
- **Model seçimi:** Beyin panelinde Opus (en iyi) / Sonnet (dengeli) / Haiku (en ucuz). Kalıcı varsayılan Ayarlar'da.
- **Silme:** Çıktılar sekmesinde PDF'ler ve beyin çalışmaları tek tek ya da toplu silinebilir. Silinen PDF'teki sorular tekrar önerilebilir hâle gelir.

**Düzeltmeler**
- PDF'in hep eski seçilen sorularla çıkması düzeltildi. Artık her beyin çalışmasının kendi seçimi var; sepeti boşaltma (🗑) butonu eklendi.
- Claude masaüstü uygulaması güncellenince "Claude Code bulunamadı" hatası çıkıyordu; düzeltildi.

**Yapmanız gereken:** `baslat.bat`'ı yeniden açın. Sağ üstte yeşil **"Claude Code bulundu"** yazısını kontrol edin.

---

## 1.0.0 · 30 Eylül 2026 · İlk sürüm

- Yerel web uygulaması (`baslat.bat` → `http://localhost:8765`).
- MEB kaynaklarından 33.000 soruluk bank, cevap anahtarları, birleşik zorluk (kitap + Claude puanı + öğretmen + öğrenci).
- Beyin: yanlış soru fotoğraflarından teşhis, seviyeli aday listesi, PDF çalışma kâğıdı.
- Öğretmen geri bildirimi (Kolay / Uygun / Zor / ✕ Kullanma) ve öğrenci sonuç girişi.
- Resimli kılavuz: `docs/KILAVUZ.md`.
