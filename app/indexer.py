"""Kaynak PDF'lerden soru indeksi çıkarır (yapay zekâ kullanmadan, hızlı).

Her soru için: kitap, sayfa, kırpma kutusu (bbox), soru no, konu, seviye (ADIM/TEST), metin özeti.
Cevaplar sonradan Claude tarafından cevap anahtarı sayfalarından doldurulur (brain/KEYS.md).
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf

from . import config

SUBJECTS = {
    "mat": "Matematik", "fizik": "Fizik", "kimya": "Kimya", "bio": "Biyoloji",
    "turkce": "Türkçe", "tarih": "Tarih", "cografya": "Coğrafya", "felsefe": "Felsefe",
    "geo": "Geometri", "din": "Din Kültürü", "edebiyat": "Edebiyat",
}
KINDS = {
    "3adm": ("3 Adım", "Konu testleri 1-2-3. adım (kolay→zor)"),
    "4_4": ("4/4", "Konu testleri, TEST 1-4"),
    "tarama": ("Tarama", "Karma tarama testleri"),
    "cikmis": ("Çıkmış", "ÖSYM çıkmış sorular"),
}

TP_FLAGS = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
QNUM_RE = re.compile(r"^\s*(\d{1,2})\s*[.)]\s*(.*)$")
PAGE_NUM_RE = re.compile(r"^\s*(\d{1,3})\s*$")
TOC_RE = re.compile(r"^(.*?)[\s.…·]{4,}\s*(\d{1,3})\s*$")
ADIM_RE = re.compile(r"([123])\s*\.\s*ADIM", re.I)
TEST_RE = re.compile(r"(?:^|\n)\s*(\d{1,2})\s*\.?\s*\n?\s*TEST\b|TEST\s*[-:]?\s*(\d{1,2})\b", re.I)
KEY_RE = re.compile(r"CEVAP\s+ANAHTAR", re.I)
YEAR_RE = re.compile(r"\b(20[12]\d)\s*[-–]?\s*(TYT|AYT|YGS|LYS|MSÜ|ÖSYM)\b")


def fix_text(s: str) -> str:
    """Bazı PDF'lerde (çıkmış sorular) font kodlaması 29 karakter kaydırılmış: '7XUIDQ' -> 'Turfan'."""
    if "\n" in s:
        return "\n".join(fix_text(x) for x in s.split("\n"))
    if any(ord(c) < 0x20 and c not in "\t\r" for c in s):
        return "".join(chr(ord(c) + 29) if 0x03 <= ord(c) <= 0x5D else c for c in s)
    return s


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", fix_text(s))
    s = s.replace("­", "")
    return re.sub(r"\s+", " ", s).strip()


def book_meta(path: Path) -> dict:
    stem = path.stem
    low = stem.lower().replace("ı", "i")
    m = re.match(r"(tyt|ayt)_([a-zçğıöşü]+)_(.+)$", low)
    exam, subject, kind = ("?", "karma", "diger")
    if m:
        exam, subject, rest = m.group(1).upper(), m.group(2), m.group(3)
        if "3adm" in rest:
            kind = "3adm"
        elif "4_4" in rest:
            kind = "4_4"
        elif "tarama" in rest:
            kind = "tarama"
        elif "cikmis" in rest:
            kind = "cikmis"
        else:
            kind = rest
    return {
        "id": stem,
        "path": str(path),
        "exam": exam,
        "subject": subject,
        "subject_name": SUBJECTS.get(subject, subject.title()),
        "kind": kind,
        "kind_name": KINDS.get(kind, (kind, ""))[0],
    }


# ---------------------------------------------------------------- İçindekiler
def parse_toc(doc) -> list[tuple[int, str]]:
    """İÇİNDEKİLER sayfalarından (basılı_sayfa, başlık) listesi."""
    entries = []
    in_toc = False
    for i in range(min(10, doc.page_count)):
        text = doc[i].get_text()
        is_toc = "İÇİNDEKİLER" in text.upper() or "ICINDEKILER" in text.upper()
        if not is_toc:
            if in_toc and len(re.findall(r"\.{6,}", text)) >= 3:
                pass  # içindekiler devam sayfası
            elif in_toc:
                break
            else:
                continue
        in_toc = True
        lines = [norm(x) for x in text.split("\n")]
        # "1." satırı ile başlığı birleştir, başlık ile sayfa no ayrı satırlarda olabilir
        buf = ""
        for ln in lines:
            if not ln:
                continue
            if re.fullmatch(r"\d{1,2}\.", ln):
                continue
            cand = (buf + " " + ln).strip() if buf else ln
            m = TOC_RE.match(cand)
            if m and m.group(1).strip(" .") and not m.group(1).strip().isdigit():
                entries.append((int(m.group(2)), clean_title(m.group(1))))
                buf = ""
            elif re.search(r"\.{4,}\s*$", ln) or re.search(r"\.{4,}", ln):
                buf = cand
            elif PAGE_NUM_RE.match(ln) and buf:
                entries.append((int(ln), clean_title(buf)))
                buf = ""
            else:
                buf = "" if len(cand) > 160 else cand
    # tekrarları at, sayfaya göre sırala
    seen, out = set(), []
    for p, t in sorted(entries):
        if (p, t) not in seen and len(t) > 2:
            seen.add((p, t))
            # kitaptaki dizgi hatası: "Veri - 1" iki kez yazılmışsa ikincisi "Veri - 2" olur
            if out and out[-1][1] == t:
                m = re.search(r"(\d+)\s*$", t)
                t = t[:m.start()] + str(int(m.group(1)) + 1) if m else t + " (2)"
            out.append((p, t))
    return out


def clean_title(t: str) -> str:
    t = re.sub(r"(?i)^İÇİNDEKİLER\s*", "", norm(t)).strip(" .…·")
    return re.sub(r"^\d{1,2}\s*[.)]\s*", "", t)


def printed_page_number(page) -> int | None:
    h = page.rect.height
    for b in page.get_text("blocks"):
        x0, y0, x1, y1, txt = b[:5]
        if (y1 < h * 0.09 or y0 > h * 0.91) and PAGE_NUM_RE.match(txt.strip()):
            return int(txt.strip())
    return None


def page_offset(doc) -> int:
    """pdf_index - basılı_sayfa farkı (çoğunluk oyu)."""
    votes = {}
    for i in range(0, doc.page_count, max(1, doc.page_count // 40)):
        n = printed_page_number(doc[i])
        if n is not None:
            votes[i - n] = votes.get(i - n, 0) + 1
    return max(votes, key=votes.get) if votes else 0


# ---------------------------------------------------------------- Soru tespiti
def detect_questions(page, tp=None) -> list[dict]:
    W, H = page.rect.width, page.rect.height
    mid = W / 2
    top_limit, bottom_limit = H * 0.05, H * 0.93
    tp = tp or page.get_textpage(flags=TP_FLAGS)
    d = page.get_text("dict", textpage=tp)
    lines = []
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            spans = [s for s in ln["spans"] if s["text"].strip()]
            if not spans:
                continue
            lines.append((ln["bbox"], spans))

    cands = []
    for bbox, spans in lines:
        first = spans[0]
        txt = fix_text(first["text"])
        if len(spans) > 1 and re.fullmatch(r"\s*\d{1,2}\s*", txt):
            txt += fix_text(spans[1]["text"])
        m = QNUM_RE.match(txt)
        if not m:
            continue
        n = int(m.group(1))
        if n == 0 or n > 60:
            continue
        x0, y0 = first["bbox"][0], first["bbox"][1]
        if y0 < top_limit or y0 > bottom_limit:
            continue
        bold = bool(first["flags"] & 16) or "bold" in first["font"].lower() or "black" in first["font"].lower()
        # "1. ADIM", "2020 TYT" vb. yanlış pozitifleri ele
        rest = norm(" ".join(s["text"] for s in spans))
        if re.search(r"ADIM|TEST|BÖLÜM|ÜNİTE", rest, re.I) and len(rest) < 20:
            continue
        # numaranın ("12.") kapladığı alan: PDF'te orijinal numarayı kapatıp yenisini yazmak için
        if len(spans) > 1 and re.fullmatch(r"\s*\d{1,2}\s*", fix_text(first["text"])):
            nx1 = spans[1]["bbox"][2]
        else:
            fx0, fx1 = first["bbox"][0], first["bbox"][2]
            ftxt = first["text"]
            numlen = len(re.match(r"\s*\d{1,2}\s*[.)]", fix_text(ftxt)).group(0))
            nx1 = fx0 + (fx1 - fx0) * numlen / max(1, len(ftxt))
        num = [round(x0, 1), round(y0, 1), round(nx1 + 1, 1), round(first["bbox"][3], 1)]
        cands.append({"n": n, "x0": x0, "y0": y0, "bold": bold, "col": 0 if x0 < mid - 10 else 1, "num": num})

    if not cands:
        return []
    # her sütunda soru numaraları sol kenara hizalıdır: en soldaki x0'a yakın olanları al
    result = []
    two_col = any(c["col"] == 1 for c in cands)
    for col in (0, 1):
        cc = [c for c in cands if c["col"] == col]
        if not cc:
            continue
        # sol hizayı kalın numaralardan bul; kalın olmayanları sadece tam hizalıysa kabul et
        bolds = [c for c in cc if c["bold"]]
        if bolds and len(bolds) >= max(1, len(cc) // 3):
            left = min(c["x0"] for c in bolds)
            cc = [c for c in cc if (c["bold"] and c["x0"] - left < 14) or abs(c["x0"] - left) < 3]
        else:
            left = min(c["x0"] for c in cc)
            cc = [c for c in cc if c["x0"] - left < 14]
        cc.sort(key=lambda c: c["y0"])
        # artan numara dizisi
        seq, last = [], -1
        for c in cc:
            if c["n"] > last:
                seq.append(c)
                last = c["n"]
        for c in seq:
            c["left"] = left
        result += seq

    # sütun sınırları
    items = page_items(page)
    out = []
    for c in result:
        if two_col:
            cx0 = c["left"] - 6
            cx1 = mid - 4 if c["col"] == 0 else W - 20
            if c["col"] == 1:
                cx0 = max(mid - 4, c["left"] - 6)
        else:
            cx0, cx1 = c["left"] - 6, W - 20
        same = [o for o in result if o["col"] == c["col"] and o["y0"] > c["y0"] + 2]
        y_end = min([o["y0"] for o in same], default=bottom_limit) - 3
        clip = pymupdf.Rect(cx0, c["y0"] - 4, cx1, y_end)
        # içeriğe sıkıştır
        tight = content_rect(items, clip)
        if tight is None:  # taranmış sayfa (tam sayfa görsel + görünmez metin): sütun parçasını olduğu gibi al
            tight = clip
        if tight.height < 12:
            continue
        rect = pymupdf.Rect(clip.x0, tight.y0 - 3, clip.x1, tight.y1 + 4)
        text = lines_text(lines, rect)
        above = lines_text(lines, pymupdf.Rect(cx0, c["y0"] - 26, cx1, c["y0"] - 1))
        out.append({"n": c["n"], "col": c["col"], "bbox": [round(v, 1) for v in rect], "num": c["num"],
                    "text": text, "above": above})
    out.sort(key=lambda q: (q["col"], q["bbox"][1]))
    return out


def lines_text(lines, rect) -> str:
    """Merkezi rect içinde kalan satırların metni (textpage ile clip çalışmadığı için elle)."""
    out = []
    for (x0, y0, x1, y1), spans in lines:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if rect.x0 <= cx <= rect.x1 and rect.y0 <= cy <= rect.y1:
            out.append((round(y0), x0, " ".join(s["text"] for s in spans)))
    out.sort()
    return norm(" ".join(t for _, _, t in out))


def page_items(page) -> list:
    """Sayfadaki tüm çizilen öğelerin (metin, görsel, vektör) kutuları — tek seferde."""
    items = []
    try:
        for kind, rect in page.get_bboxlog():
            if kind.startswith("ignore"):
                continue
            items.append(pymupdf.Rect(rect))
    except Exception:
        for b in page.get_text("blocks"):
            items.append(pymupdf.Rect(b[:4]))
    return items


def content_rect(items, clip):
    r = None
    for it in items:
        br = it & clip
        if br.is_empty or (br.width < 1.5 and br.height < 1.5):
            continue
        # arka plan / sayfa genişliğindeki çerçeveleri sayma
        if it.width > clip.width * 1.2 or it.height > clip.height * 1.5:
            continue
        r = br if r is None else r | br
    return r


# ---------------------------------------------------------------- Kitap indeksi
def page_level(text: str, kind: str) -> str:
    m = ADIM_RE.search(text)
    if m:
        return f"{m.group(1)}. Adım"
    m = TEST_RE.search(text)
    if m:
        return f"Test {m.group(1) or m.group(2)}"
    return ""


SOLVED_RE = re.compile(r"Çözüm\s*:", re.I)
SOLVED_ANS_RE = re.compile(r"Cevap\s*:\s*([A-E])\b")


def solved_answer(text: str) -> str:
    """Çözümlü örnek sorularda kırpımın içindeki 'Cevap: X'."""
    if SOLVED_RE.search(text):
        m = SOLVED_ANS_RE.search(text)
        if m:
            return m.group(1)
    return ""


ANS_PAT = re.compile(r"\b\d{1,2}\s*[-.)]\s*[A-E]\b")


def looks_like_key(text: str) -> bool:
    single = sum(1 for ln in text.split("\n") if ln.strip() in ("A", "B", "C", "D", "E"))
    return len(ANS_PAT.findall(text)) >= 12 or single >= 25


def index_book(path: Path, progress=None) -> dict:
    meta = book_meta(path)
    doc = pymupdf.open(path)
    toc = parse_toc(doc)
    n = doc.page_count
    pages = []  # (index, level, questions)
    key_pages = []
    for i in range(n):
        page = doc[i]
        tp = page.get_textpage(flags=TP_FLAGS)
        text = fix_text(page.get_text(textpage=tp))
        if progress and i % 20 == 0:
            progress(i, n)
        if i > 3 and (KEY_RE.search(text) and (i >= n * 0.75 or looks_like_key(text))):
            key_pages.append(i + 1)
            continue
        if i < 2:
            continue
        pages.append((i, page_level(text[:400], meta["kind"]), detect_questions(page, tp)))
    # "CEVAP ANAHTARI" kapak sayfası olabilir: ardından gelen cevap desenli sayfaları da ekle
    if key_pages:
        nxt = key_pages[-1]
        while nxt < n and looks_like_key(fix_text(doc[nxt].get_text())):
            key_pages.append(nxt + 1)
            nxt += 1
        pages = [p for p in pages if p[0] + 1 not in key_pages]
    if not key_pages:  # etiketsiz cevap anahtarı: son sayfalarda cevap deseni ara
        for i in range(max(0, n - 12), n):
            if looks_like_key(fix_text(doc[i].get_text())):
                key_pages.append(i + 1)
        pages = [p for p in pages if p[0] + 1 not in key_pages]

    def topic_for(i, offset):
        printed, topic = i - offset, ""
        for p, t in toc:
            if p <= printed:
                topic = t
        return topic

    # sayfa kayması: oylanan değer ile 0'ı dene, daha çok soruya konu verebileni seç
    offset = page_offset(doc)
    if toc:
        def missing(off):
            return sum(len(qs) for i, _, qs in pages if not topic_for(i, off))
        offset = min({offset, 0}, key=missing)

    questions, qid_seen = [], set()
    last_raw_topic, last_level, last_n = None, "", 0
    topic_bump, ek = 0, 0

    def lvl_num(lv):
        m = re.search(r"\d+", lv or "")
        return int(m.group(0)) if m else 0

    for i, page_lv, qs in pages:
        raw_topic = topic_for(i, offset)
        if raw_topic != last_raw_topic:
            last_level, last_n, topic_bump, ek = "", 0, 0, 0
        # 3 Adım: seviye 3'ten 1'e döndü ama konu aynı → içindekilerde atlanmış yeni konu
        if page_lv and last_level and "Adım" in page_lv and lvl_num(page_lv) < lvl_num(last_level):
            topic_bump += 1
            last_n = 0
        # seviye yazmayan sayfa önceki sayfanın seviyesini devralır (aynı konu içinde)
        level = page_lv or last_level
        if level != last_level:
            last_n, ek = 0, 0
        # aynı etiket içinde numara başa döndü → kitapta etiket hatası; ayrı "(ek)" bölüm
        if qs and last_n and qs[0]["n"] < last_n and level == last_level:
            ek += 1
        last_raw_topic, last_level = raw_topic, level
        if qs:
            last_n = max(q["n"] for q in qs)
        topic = raw_topic
        if topic_bump:
            m = re.search(r"(\d+)\s*$", topic)
            topic = topic[:m.start()] + str(int(m.group(1)) + topic_bump) if m else f"{topic} - {topic_bump + 1}"
        if ek:
            level = f"{level} (ek{ek if ek > 1 else ''})"
        for q in qs:
            year = YEAR_RE.search(q.get("above", "")) or YEAR_RE.search(q["text"][:40])
            if not year and meta["kind"] == "cikmis":
                year = YEAR_RE.search(q["text"])
            qid = f"{meta['id']}|p{i + 1}|q{q['n']}"
            if qid in qid_seen:
                qid += f"c{q['col']}"
            qid_seen.add(qid)
            questions.append({
                "qid": qid,
                "page": i + 1,
                "n": q["n"],
                "bbox": q["bbox"],
                "num": q["num"],
                "topic": topic,
                "level": level,
                "osym": f"{year.group(1)} {year.group(2)}" if year else "",
                "text": q["text"][:600],
                "answer": solved_answer(q["text"]),
                "solved": bool(SOLVED_RE.search(q["text"])),
            })
    return {
        "book": meta,
        "pages": n,
        "offset": offset,
        "toc": toc,
        "key_pages": key_pages,
        "questions": questions,
        "answers_filled": False,
    }


def index_path(book_id: str) -> Path:
    return config.INDEX_DIR / f"{book_id}.json"


def list_source_pdfs() -> list[Path]:
    out = []
    for src in config.get()["sources"]:
        p = Path(src)
        if p.is_dir():
            out += sorted(x for x in p.glob("*.pdf"))
    return out


def run(paths=None, force=False, log=print):
    paths = paths or list_source_pdfs()
    for p in paths:
        meta = book_meta(p)
        out = index_path(meta["id"])
        if out.exists() and not force:
            log(f"atlandı (var): {meta['id']}")
            continue
        log(f"indeksleniyor: {meta['id']}")
        data = index_book(p)
        # önceki cevapları koru
        if out.exists():
            old = json.loads(out.read_text(encoding="utf-8"))
            ans = {q["qid"]: q.get("answer", "") for q in old.get("questions", [])}
            for q in data["questions"]:
                q["answer"] = ans.get(q["qid"]) or q["answer"]
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"  {len(data['questions'])} soru, cevap anahtarı sayfaları: {data['key_pages'][:12]}")
        # düzenli cevap anahtarlarını kodla oku (kalanlar için arayüzden Claude çalıştırılır)
        if data["key_pages"]:
            from . import keyparse, qbank
            try:
                keys = keyparse.parse_book(str(p), data["key_pages"])
                if keys["sections"]:
                    r = qbank.set_keys(meta["id"], keys)
                    log(f"  cevap anahtarı: {r['answered']}/{r['total']} soru cevaplandı")
            except Exception as e:  # noqa: BLE001
                log(f"  cevap anahtarı okunamadı: {e}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run([Path(a) for a in args] or None, force="--force" in sys.argv)
