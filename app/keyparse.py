"""Düzenli cevap anahtarlarını kelime konumlarından okur (yapay zekâsız).

Desteklenen iki düzen:
  A) "1. ADIM" satırları ve "1-C 2-D ..." belirteçleri (3 Adım kitapları)
  B) "1. TEST" satırları, üstte 1..20 numara başlığı, hücrelerde tek harf (4/4 kitapları)
Konu başlığı: belirteç olmayan, harf içeren, sol kenardan başlayan satır.
Çıktı qbank.set_keys ile uyumlu: {"sections": [{"topic", "level", "answers": {no: harf}}]}
Düzen tanınmazsa boş döner; o zaman Claude (brain/KEYS.md) devreye girer.
"""
import re
import sys
from collections import defaultdict

import pymupdf

LABEL_RE = re.compile(r"^(\d)\.?$")
PAIR_RE = re.compile(r"^(\d{1,2})\s*[-–.]\s*([A-E])?$")
LETTER_RE = re.compile(r"^[A-E]$")


def _lines(words, tol=3.5):
    """Kelimeleri y'ye göre satırlara grupla."""
    rows = []
    for w in sorted(words, key=lambda w: (w[1], w[0])):
        if rows and abs(rows[-1][0] - w[1]) <= tol:
            rows[-1][1].append(w)
        else:
            rows.append([w[1], [w]])
    return [(y, sorted(ws, key=lambda w: w[0])) for y, ws in rows]


def parse_page(page) -> list[dict]:
    words = [(w[0], (w[1] + w[3]) / 2, w[2], w[4].strip()) for w in page.get_text("words") if w[4].strip()]
    lines = _lines(words)
    labels, headings, headers = [], [], []
    for y, ws in lines:
        texts = [w[3] for w in ws]
        joined = " ".join(texts)
        # satır etiketi: "1." + "ADIM"/"TEST"
        is_label = False
        for i in range(len(ws) - 1):
            if LABEL_RE.match(ws[i][3]) and ws[i + 1][3].upper() in ("ADIM", "TEST") and ws[i][0] < page.rect.width * 0.25:
                labels.append({"y": y, "level": f"{ws[i][3].rstrip('.')}. Adım" if ws[i + 1][3].upper() == "ADIM"
                               else f"Test {ws[i][3].rstrip('.')}", "x1": ws[i + 1][2]})
                is_label = True
        if is_label or any(t.upper() in ("ADIM", "TEST") for t in texts[:3]):
            continue
        # numara başlığı satırı (düzen B): çoğu kelime sayı
        nums = [w for w in ws if w[3].isdigit() and 1 <= int(w[3]) <= 40]
        if len(nums) >= 6 and len(nums) >= 0.8 * len(ws):
            headers.append({"y": y, "cols": [((w[0] + w[2]) / 2, int(w[3])) for w in nums]})
            continue
        if re.search(r"CEVAP\s+ANAHTAR", joined, re.I) or re.search(r"ADIM|TEST", joined) and len(joined) < 12:
            continue
        if any((PAIR_RE.match(t) and PAIR_RE.match(t).group(2)) or LETTER_RE.match(t) for t in texts[:2]):
            continue
        if re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3,}", joined) and ws[0][0] < page.rect.width * 0.3 and not joined.isdigit():
            headings.append({"y": y, "text": re.sub(r"^\d{1,2}\s*[.)]\s*", "", joined)})

    if not labels:
        return parse_sequential(page)
    sections = defaultdict(dict)  # (topic, level) -> {no: letter}

    def topic_at(y):
        cand = [h for h in headings if h["y"] < y]
        return cand[-1]["text"] if cand else ""

    def label_at(y):
        best = min(labels, key=lambda l: abs(l["y"] - y))
        return best if abs(best["y"] - y) <= 12 else None

    for y, ws in lines:
        i = 0
        while i < len(ws):
            x0, yy, x1, t = ws[i]
            lab = label_at(yy)
            if not lab or x0 <= lab["x1"]:
                i += 1
                continue
            m = PAIR_RE.match(t)
            if m:
                no, letter = int(m.group(1)), m.group(2)
                if not letter and i + 1 < len(ws) and LETTER_RE.match(ws[i + 1][3]):
                    letter = ws[i + 1][3]
                    i += 1
                if letter:
                    sections[(topic_at(lab["y"]), lab["level"])][str(no)] = letter
            elif LETTER_RE.match(t):
                hdr = [h for h in headers if h["y"] < lab["y"]]
                if hdr:
                    cols = hdr[-1]["cols"]
                    cx = (x0 + x1) / 2
                    xc, no = min(cols, key=lambda c: abs(c[0] - cx))
                    if abs(xc - cx) < 12:
                        sections[(topic_at(lab["y"]), lab["level"])][str(no)] = t
            i += 1
    return [{"topic": tp, "level": lv, "answers": ans} for (tp, lv), ans in sections.items() if ans]


SEQ_RE = re.compile(r"^(\d{1,2})\s*[.)\-–]\s*([A-E])$")


def parse_sequential(page) -> list[dict]:
    """Düzen C (tarama): 'TYT TARAMA TESTİ-1' başlığı, altında '1. E' satırları; metin akış sırasıyla."""
    secs, topic, cur = [], "", {}
    for ln in page.get_text().split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        m = SEQ_RE.match(ln)
        if m:
            cur[m.group(1)] = m.group(2)
        elif re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3,}", ln) and not re.search(r"CEVAP\s+ANAHTAR", ln, re.I):
            if cur:
                secs.append({"topic": topic, "level": "", "answers": cur})
            topic, cur = ln, {}
    if cur:
        secs.append({"topic": topic, "level": "", "answers": cur})
    return [s for s in secs if len(s["answers"]) >= 3]


def parse_book(pdf_path: str, pages: list[int]) -> dict:
    doc = pymupdf.open(pdf_path)
    secs = []
    for p in pages:
        secs += parse_page(doc[p - 1])
    return {"sections": secs}


if __name__ == "__main__":
    import json
    sys.stdout.reconfigure(encoding="utf-8")
    from . import qbank
    book = sys.argv[1]
    d = qbank.load_book(book)
    res = parse_book(d["book"]["path"], d["key_pages"])
    print(json.dumps(res, ensure_ascii=False)[:1500])
    if "--apply" in sys.argv:
        print(qbank.set_keys(book, res))
