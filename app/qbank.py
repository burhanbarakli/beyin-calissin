"""Soru bankası: indeksleri okur, arar, soru görseli üretir.

Claude (beyin) bu modülü komut satırından kullanır:
    python -m app.qbank books
    python -m app.qbank topics  --subject mat --exam TYT
    python -m app.qbank search  --subject mat --exam TYT --topic "olasılık" [--text "zar"] [--level 1] [--limit 40]
    python -m app.qbank show    "<qid>" ["<qid>" ...]     -> PNG yolunu yazar (Read ile bakılabilir)
    python -m app.qbank keypages <book_id>                -> cevap anahtarı sayfalarını PNG yapar + metnini yazar
    python -m app.qbank setkeys  <book_id> <keys.json>    -> cevapları sorulara işler
    python -m app.qbank unanswered <book_id>              -> cevabı olmayan soru sayısı / örnekleri
    python -m app.qbank sections <book_id>                -> kitabın konu/seviye bölümleri ve soru sayıları
    python -m app.qbank pdftext <pdf> [--pages 1-3]       -> herhangi bir PDF'in metni
    python -m app.qbank pdfpng  <pdf> <sayfa> [--dpi 110] -> PDF sayfasını PNG yapar (Read ile bakılır)
    python -m app.qbank rate <ratings.json>               -> Claude zorluk puanlarını kaydeder (1-5)
    python -m app.qbank torate <book_id> [--limit 60]     -> puanlanmamış sorular
    python -m app.qbank history [--subject mat]           -> öğrencinin çalışma kâğıdı sonuçları
"""
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

import pymupdf

from . import config

CROP_DIR = config.CACHE_DIR / "crops"
KEY_DIR = config.CACHE_DIR / "keys"
CROP_DIR.mkdir(parents=True, exist_ok=True)
KEY_DIR.mkdir(parents=True, exist_ok=True)


def fold(s: str) -> str:
    """Türkçe karakterleri sadeleştirip küçük harfe çevirir (arama için)."""
    s = (s or "").replace("İ", "i").replace("I", "ı").lower()
    tr = str.maketrans("çğıöşüâîû", "cgiosuaiu")
    s = unicodedata.normalize("NFKD", s.translate(tr))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip()


# ------------------------------------------------------------------ veri
def _index_files():
    return sorted(config.INDEX_DIR.glob("*.json"))


def resolve_pdf(path: str) -> str:
    """Kitap PDF'ini önce ayarlardaki kaynak klasörlerinde dosya adıyla bul (paylaşılan/taşınan kurulum);
    bulunamazsa indeksteki yolu kullan."""
    name = Path(path).name.lower()
    for src in config.get()["sources"]:
        d = Path(src)
        if d.is_dir():
            for f in d.glob("*.pdf"):
                if f.name.lower() == name:
                    return str(f)
    return path


@lru_cache(maxsize=64)
def _load(path: str, mtime: float) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    d["book"]["path"] = resolve_pdf(d["book"].get("path", ""))
    return d


def load_book(book_id: str) -> dict:
    p = config.INDEX_DIR / f"{book_id}.json"
    return _load(str(p), p.stat().st_mtime)


def save_book(data: dict) -> None:
    p = config.INDEX_DIR / f"{data['book']['id']}.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def all_books() -> list[dict]:
    out = []
    rated = load_store("ratings")
    for p in _index_files():
        d = _load(str(p), p.stat().st_mtime)
        qs = d["questions"]
        out.append({
            **d["book"],
            "questions": len(qs),
            "answered": sum(1 for q in qs if q.get("answer")),
            "rated": sum(1 for q in qs if q["qid"] in rated),
            "key_pages": d.get("key_pages", []),
            "topics": len({q["topic"] for q in qs}),
        })
    return out


def book_of(qid: str) -> str:
    return qid.split("|", 1)[0]


def get_question(qid: str) -> dict | None:
    try:
        d = load_book(book_of(qid))
    except FileNotFoundError:
        return None
    for q in d["questions"]:
        if q["qid"] == qid:
            return {**q, "book": d["book"]}
    return None


def iter_questions(subject=None, exam=None, kind=None, book=None):
    for p in _index_files():
        d = _load(str(p), p.stat().st_mtime)
        b = d["book"]
        if subject and b["subject"] != subject:
            continue
        if exam and b["exam"].upper() != exam.upper():
            continue
        if kind and b["kind"] != kind:
            continue
        if book and b["id"] != book:
            continue
        for q in d["questions"]:
            yield b, q


def level_rank(book: dict, q: dict) -> int:
    """1 = temel/hatırlatıcı, 2 = orta/pekiştirme, 3 = zor/sınav düzeyi."""
    lv = q.get("level", "")
    if q.get("solved"):
        return 1  # çözümlü örnek: öğretici / hatırlatıcı
    m = re.match(r"(\d)\. Adım", lv)
    if m:
        return int(m.group(1))
    m = re.match(r"Test (\d+)", lv)
    if m:
        t = int(m.group(1))
        return 1 if t <= 1 else (2 if t <= 3 else 3)
    if q.get("osym") or book["kind"] == "cikmis":
        return 3
    if book["kind"] == "tarama":
        return 2
    return 2


# ------------------------------------------------------------------ zorluk: kitap + Claude + öğretmen + öğrenci
# data/ratings.json   {qid: {"claude": 1-5, "note": "..."}}
# data/feedback.json  {qid: {"teacher": "kolay"|"uygun"|"zor"|"kullanma"}}
# data/student_results.json {qid: {"result": "yapti"|"yapamadi"|"bos", "pdf": "...", "t": "..."}}
STORES = {"ratings": "ratings.json", "feedback": "feedback.json", "results": "student_results.json"}
BOOK_DIFF = {1: 2.0, 2: 3.0, 3: 4.0}   # kitap seviyesi → 1-5 ölçeği


def load_store(name: str) -> dict:
    p = config.DATA / STORES[name]
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_store(name: str, data: dict) -> None:
    (config.DATA / STORES[name]).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def update_store(name: str, patch: dict) -> dict:
    """patch = {qid: {...} | None}; None kaydı siler."""
    data = load_store(name)
    for qid, v in patch.items():
        if v is None:
            data.pop(qid, None)
        else:
            data[qid] = {**data.get(qid, {}), **v}
    save_store(name, data)
    return data


def difficulty(book: dict, q: dict, stores: dict | None = None) -> dict:
    """Birleşik zorluk (1-5) ve dayanakları.

    kitap seviyesi → (varsa) Claude puanı → öğretmen düzeltmesi (kolay −1 / zor +1) →
    öğrenci sonucu (yaptı −0,5 / yapamadı +0,5; bu öğrenciye göre).
    """
    stores = stores or {k: load_store(k) for k in STORES}
    qid = q["qid"]
    base = BOOK_DIFF[level_rank(book, q)]
    info = {"book": base}
    d = base
    r = stores["ratings"].get(qid)
    if r and r.get("claude"):
        d = float(r["claude"])
        info["claude"] = r["claude"]
    f = stores["feedback"].get(qid, {}).get("teacher")
    if f:
        info["teacher"] = f
        d += {"kolay": -1, "zor": 1}.get(f, 0)
    s = stores["results"].get(qid, {}).get("result")
    if s:
        info["student"] = s
        d += {"yapti": -0.5, "yapamadi": 0.5}.get(s, 0)
    d = max(1.0, min(5.0, d))
    info["value"] = round(d, 1)
    info["rank"] = 1 if d <= 2.4 else (2 if d <= 3.6 else 3)
    info["blocked"] = f == "kullanma"
    return info


def search(subject=None, exam=None, topic=None, text=None, level=None, kind=None, book=None,
           limit=40, only_answered=False, exclude=(), include_blocked=False):
    topic_terms = [fold(t) for t in re.split(r"[,|/]", topic or "") if t.strip()]
    text_terms = [fold(t) for t in re.split(r"[,|/]", text or "") if t.strip()]
    stores = {k: load_store(k) for k in STORES}
    res = []
    for b, q in iter_questions(subject, exam, kind, book):
        if q["qid"] in exclude:
            continue
        if only_answered and not q.get("answer"):
            continue
        diff = difficulty(b, q, stores)
        if diff["blocked"] and not include_blocked:
            continue
        rank = diff["rank"]
        if level and rank != int(level):
            continue
        ft = fold(q.get("topic", ""))
        fx = fold(q.get("text", ""))
        score = 0
        if topic_terms:
            hit = [t for t in topic_terms if t in ft]
            hit_txt = [t for t in topic_terms if t in fx]
            if not hit and not hit_txt:
                continue
            score += 10 * len(hit) + 2 * len(hit_txt)
        if text_terms:
            hit = [t for t in text_terms if t in fx]
            if not hit:
                continue
            score += 3 * len(hit)
        if q.get("answer"):
            score += 1
        if diff.get("teacher") == "uygun":
            score += 2
        res.append((score, b, q, diff))
    res.sort(key=lambda r: (-r[0], r[3]["value"], r[2]["qid"]))
    return [{
        "qid": q["qid"], "book": b["id"], "kind": b["kind_name"], "topic": q["topic"],
        "level": q.get("level", ""), "rank": diff["rank"], "difficulty": diff, "osym": q.get("osym", ""),
        "answer": q.get("answer", ""), "solved": q.get("solved", False), "text": q["text"][:220],
    } for score, b, q, diff in res[:limit]]


def diff_label(diff: dict) -> str:
    parts = [f"zorluk={diff['value']}/5"]
    if "claude" in diff:
        parts.append(f"claude {diff['claude']}")
    if diff.get("teacher"):
        parts.append(f"öğretmen: {diff['teacher']}")
    if diff.get("student"):
        parts.append({"yapti": "öğrenci YAPTI", "yapamadi": "öğrenci YAPAMADI", "bos": "öğrenci BOŞ"}[diff["student"]])
    return " ".join(parts)


def topics(subject=None, exam=None, kind=None):
    agg = {}
    for b, q in iter_questions(subject, exam, kind):
        key = (b["exam"], b["subject"], q["topic"] or "(konu yok)")
        a = agg.setdefault(key, {"exam": key[0], "subject": key[1], "topic": key[2], "count": 0,
                                 "r1": 0, "r2": 0, "r3": 0, "books": set()})
        a["count"] += 1
        a[f"r{level_rank(b, q)}"] += 1
        a["books"].add(b["kind_name"])
    out = []
    for a in agg.values():
        a["books"] = ", ".join(sorted(a["books"]))
        out.append(a)
    return sorted(out, key=lambda a: (a["exam"], a["subject"], a["topic"]))


# ------------------------------------------------------------------ görseller
_docs = {}


def _doc(path: str):
    if path not in _docs:
        _docs[path] = pymupdf.open(path)
    return _docs[path]


def crop_png(qid: str, dpi: int = 130) -> Path | None:
    q = get_question(qid)
    if not q:
        return None
    h = hashlib.md5(f"{qid}|{dpi}|{q['bbox']}".encode()).hexdigest()[:16]
    out = CROP_DIR / f"{h}.png"
    if not out.exists():
        page = _doc(q["book"]["path"])[q["page"] - 1]
        page.get_pixmap(dpi=dpi, clip=pymupdf.Rect(q["bbox"])).save(out)
    return out


def key_pages(book_id: str) -> list[dict]:
    d = load_book(book_id)
    doc = _doc(d["book"]["path"])
    out = []
    pages = d.get("key_pages", []) or list(range(max(1, doc.page_count - 7), doc.page_count + 1))
    for pno in pages:
        png = KEY_DIR / f"{book_id}_p{pno}.png"
        if not png.exists():
            doc[pno - 1].get_pixmap(dpi=110).save(png)
        out.append({"page": pno, "png": str(png), "text": doc[pno - 1].get_text()})
    return out


# ------------------------------------------------------------------ cevaplar
def _tkey(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", fold(s))


def match_topic(questions: list[dict], topic: str) -> list[dict]:
    """Konu adına en iyi uyan soruları döndürür: birebir > içerme > kelime örtüşmesi."""
    k = _tkey(topic)
    if not k:
        return questions
    exact = [q for q in questions if _tkey(q["topic"]) == k]
    if exact:
        return exact
    contain = [q for q in questions if _tkey(q["topic"]) and (k in _tkey(q["topic"]) or _tkey(q["topic"]) in k)]
    if contain:
        return contain
    words = set(fold(topic).split())
    best, best_score = [], 0.0
    for t in {q["topic"] for q in questions}:
        tw = set(fold(t).split())
        if not tw:
            continue
        score = len(words & tw) / len(words | tw)
        if score > best_score:
            best, best_score = [q for q in questions if q["topic"] == t], score
    return best if best_score >= 0.5 else []


def set_keys(book_id: str, keys: dict) -> dict:
    """keys = {"sections": [{"topic": "...", "level": "1. Adım" | "Test 2" | "", "answers": {"1": "C", ...}}]}

    Eşleşme: konu adı (sadeleştirilmiş, kısmi) + seviye + soru no.
    """
    d = load_book(book_id)
    d = json.loads(json.dumps(d))  # kopya
    qs = d["questions"]
    matched, unmatched_sections = 0, []
    for sec in keys.get("sections", []):
        st = fold(sec.get("topic", ""))
        sl = (sec.get("level") or "").strip()
        answers = {str(k).strip(): str(v).strip().upper()[:1] for k, v in sec.get("answers", {}).items()}
        cand = [q for q in qs if (not sl or q.get("level", "") == sl)]
        if st:
            cand = match_topic(cand, sec.get("topic", ""))
        n_before = matched
        # aynı konu+seviyede aynı no birden fazla ise sayfa sırasına göre ilkini al
        used = set()
        for q in sorted(cand, key=lambda q: (q["page"], q["bbox"][0], q["bbox"][1])):
            a = answers.get(str(q["n"]))
            if a and a in "ABCDE" and (q["n"] not in used):
                q["answer"] = a
                used.add(q["n"])
                matched += 1
        if matched == n_before:
            unmatched_sections.append(f"{sec.get('topic')} / {sl}")
    d["answers_filled"] = True
    save_book(d)
    total = len(qs)
    answered = sum(1 for q in qs if q.get("answer"))
    return {"matched_now": matched, "answered": answered, "total": total, "unmatched_sections": unmatched_sections}


# ------------------------------------------------------------------ CLI
def _print(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m app.qbank")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("books")
    t = sub.add_parser("topics")
    t.add_argument("--subject"); t.add_argument("--exam"); t.add_argument("--kind")
    s = sub.add_parser("search")
    for a in ("--subject", "--exam", "--topic", "--text", "--level", "--kind", "--book"):
        s.add_argument(a)
    s.add_argument("--limit", type=int, default=40)
    s.add_argument("--answered", action="store_true", help="sadece cevabı bilinenler")
    sh = sub.add_parser("show"); sh.add_argument("qids", nargs="+")
    kp = sub.add_parser("keypages"); kp.add_argument("book")
    sk = sub.add_parser("setkeys"); sk.add_argument("book"); sk.add_argument("file")
    un = sub.add_parser("unanswered"); un.add_argument("book")
    se = sub.add_parser("sections"); se.add_argument("book")
    pt = sub.add_parser("pdftext"); pt.add_argument("pdf"); pt.add_argument("--pages", default="")
    pp = sub.add_parser("pdfpng"); pp.add_argument("pdf"); pp.add_argument("page", type=int)
    pp.add_argument("--dpi", type=int, default=110)
    ra = sub.add_parser("rate", help='zorluk puanı kaydet: [{"qid","difficulty":1-5,"note"}]'); ra.add_argument("file")
    tr = sub.add_parser("torate", help="kitabın puanlanmamış soruları"); tr.add_argument("book")
    tr.add_argument("--limit", type=int, default=60)
    hi = sub.add_parser("history", help="öğrencinin çalışma kâğıdı sonuçları (konu bazında)"); hi.add_argument("--subject")
    a = ap.parse_args(argv)

    if a.cmd == "books":
        for b in all_books():
            print(f"{b['id']:30} {b['exam']} {b['subject_name']:10} {b['kind_name']:8} soru={b['questions']:4} "
                  f"cevaplı={b['answered']:4} konu={b['topics']} | {b['path']}")
    elif a.cmd == "topics":
        for x in topics(a.subject, a.exam, a.kind):
            print(f"{x['exam']} {x['subject']:8} | {x['topic'][:60]:60} | {x['count']:3} soru "
                  f"(temel {x['r1']}, orta {x['r2']}, zor {x['r3']}) [{x['books']}]")
    elif a.cmd == "search":
        for r in search(a.subject, a.exam, a.topic, a.text, a.level, a.kind, a.book, a.limit, a.answered):
            print(f"{r['qid']} | {r['kind']} | {r['topic'][:40]} | {r['level'] or '-'} | seviye={r['rank']} "
                  f"{diff_label(r['difficulty'])} | {r['osym'] or ''} | cevap={r['answer'] or '?'}"
                  f"{' | ÇÖZÜMLÜ ÖRNEK' if r['solved'] else ''}\n    {r['text'][:200]}")
    elif a.cmd == "rate":
        items = json.loads(Path(a.file).read_text(encoding="utf-8"))
        items = items.get("ratings", items) if isinstance(items, dict) else items
        patch, bad = {}, []
        for it in items:
            try:
                v = int(it["difficulty"])
            except (KeyError, TypeError, ValueError):
                bad.append(it.get("qid"))
                continue
            if 1 <= v <= 5 and get_question(it["qid"]):
                patch[it["qid"]] = {"claude": v, "note": str(it.get("note", ""))[:200]}
            else:
                bad.append(it.get("qid"))
        update_store("ratings", patch)
        print(f"{len(patch)} puan kaydedildi" + (f"; geçersiz: {bad[:10]}" if bad else ""))
    elif a.cmd == "torate":
        rated = load_store("ratings")
        d = load_book(a.book)
        todo = [q for q in d["questions"] if q["qid"] not in rated]
        print(f"# {len(todo)} / {len(d['questions'])} soru puansız. İlk {a.limit}:")
        for q in todo[:a.limit]:
            print(f"{q['qid']} | {q['topic'][:40]} | {q.get('level') or '-'} | cevap={q.get('answer') or '?'}"
                  f"{' | ÇÖZÜMLÜ' if q.get('solved') else ''}\n    {q['text'][:350]}")
    elif a.cmd == "history":
        res = load_store("results")
        agg = {}
        for qid, r in res.items():
            q = get_question(qid)
            if not q or (a.subject and q["book"]["subject"] != a.subject):
                continue
            k = (q["book"]["subject"], q["topic"])
            g = agg.setdefault(k, {"yapti": 0, "yapamadi": 0, "bos": 0, "qids": []})
            g[r["result"]] = g.get(r["result"], 0) + 1
            g["qids"].append(f"{qid}:{r['result']}")
        if not agg:
            print("Öğrencinin çalışma kâğıdı sonucu henüz girilmemiş.")
        for (subj, tp), g in sorted(agg.items()):
            print(f"{subj} | {tp} | yaptı {g['yapti']} · yapamadı {g['yapamadi']} · boş {g['bos']}")
            print("    " + ", ".join(g["qids"][:12]))
    elif a.cmd == "show":
        for qid in a.qids:
            p = crop_png(qid)
            print(f"{qid} -> {p}" if p else f"{qid} -> BULUNAMADI")
    elif a.cmd == "keypages":
        for k in key_pages(a.book):
            print(f"=== sayfa {k['page']}  görsel: {k['png']}\n{k['text'][:6000]}\n")
    elif a.cmd == "setkeys":
        keys = json.loads(Path(a.file).read_text(encoding="utf-8"))
        _print(set_keys(a.book, keys))
    elif a.cmd == "unanswered":
        d = load_book(a.book)
        miss = [q for q in d["questions"] if not q.get("answer")]
        print(f"{len(miss)} / {len(d['questions'])} sorunun cevabı yok")
        from collections import Counter
        for (tp, lv), n in Counter((q["topic"], q["level"]) for q in miss).most_common(40):
            print(f"  {n:3}  {tp} / {lv}")

    elif a.cmd == "sections":
        d = load_book(a.book)
        secs = {}
        for q in d["questions"]:
            k = (q["topic"], q["level"])
            s_ = secs.setdefault(k, {"n": 0, "max": 0, "pages": set(), "answered": 0})
            s_["n"] += 1
            s_["max"] = max(s_["max"], q["n"])
            s_["pages"].add(q["page"])
            s_["answered"] += bool(q.get("answer"))
        for (tp, lv), s_ in secs.items():
            print(f"{tp} | {lv or '-'} | {s_['n']} soru (en büyük no {s_['max']}) | cevaplı {s_['answered']} "
                  f"| sayfa {min(s_['pages'])}-{max(s_['pages'])}")
    elif a.cmd == "pdftext":
        doc = pymupdf.open(a.pdf)
        pages = range(doc.page_count)
        if a.pages:
            lo, _, hi = a.pages.partition("-")
            pages = range(int(lo) - 1, int(hi or lo))
        for i in pages:
            print(f"=== sayfa {i + 1}\n{doc[i].get_text()}")
    elif a.cmd == "pdfpng":
        doc = pymupdf.open(a.pdf)
        h = hashlib.md5(f"{a.pdf}|{a.page}|{a.dpi}".encode()).hexdigest()[:12]
        out = config.CACHE_DIR / f"page_{h}.png"
        doc[a.page - 1].get_pixmap(dpi=a.dpi).save(out)
        print(out)


if __name__ == "__main__":
    main()
