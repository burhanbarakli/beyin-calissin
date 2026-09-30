# Görev: Deneme sonucunu çözümle

Girdi: `<RUN_DIR>/task.json` → `exam` (klasör, görseller, `result_pdf`, `booklet_pdfs`).

1. `result_pdf` varsa `python -m app.qbank pdftext "<result_pdf>"` ile oku. Tipik yapı: ders netleri tablosu
   ve "Konu Analizi" (No, Konu, DC = doğru cevap, ÖC = öğrenci cevabı, SO = + / - / boş).
   ÖC boş → **Boş**, ÖC ≠ DC → **Yanlış**. "İPTAL" sorularını atla.
2. Görseller (`images[]`) varsa hepsini Read ile aç; her birinin konusunu ve eksik beceriyi 1 cümleyle yaz.
3. `<RUN_DIR>/analysis.json` yaz:

```json
{
  "exam_name": "X YAYINLARI TYT DENEME 1", "date": "2026-10-01", "type": "TYT",
  "nets": {"Türkçe": {"d": 30, "y": 6, "b": 4, "net": 28.5}, "Matematik": {"d": 12, "y": 4, "b": 24, "net": 11.0}},
  "total_net": 70.5,
  "missed": [
    {"subject": "mat", "section": "Matematik", "no": 3, "topic": "Sayı Kümeleri", "correct": "D", "given": "B", "status": "Yanlış"}
  ],
  "images": [{"file": "D01_Mat_Fonksiyon_Yapamadı_10_E.jpeg", "skill": "ters fonksiyon tanımı"}],
  "weak_topics": [
    {"subject": "mat", "topic": "Denklem ve Eşitsizlikler", "missed": 11, "total": 16, "note": "çoğu boş — süre/temel eksik"}
  ],
  "comment": "2-4 cümlelik Türkçe genel değerlendirme."
}
```

`subject` kodları: mat (geometri dahil), fizik, kimya, bio, turkce, tarih, cografya, felsefe, din.
`weak_topics` en zayıftan başlayarak sıralı olsun. Son mesajda kısa özet ver.
