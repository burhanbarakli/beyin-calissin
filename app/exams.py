"""Öğrencinin sınavları: exams_dir altındaki her görsel/PDF içeren klasör bir sınavdır.

Görsel adlandırma kuralı (sağdan okunur, konu adında '_' olabilir):
    <SınavKodu>_<Ders>_<Konu>_<Durum>_<SoruNo>_<DoğruCevap>.jpeg
    örn: D01_Mat_Fonksiyon_Yapamadı_10_E.jpeg

Klasöre isteğe bağlı exam.json konur:
    {"name": "...", "date": "2026-09-02", "type": "TYT", "result_pdf": "D:/.../Sonuçlar/deneme1_karne.pdf"}
Claude analizi sonrası analysis.json yazılır.
"""
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from . import config

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
SUBJECT_CODES = {
    "mat": "mat", "geo": "mat", "fiz": "fizik", "kim": "kimya", "bio": "bio", "biy": "bio",
    "tur": "turkce", "trk": "turkce", "tar": "tarih", "cog": "cografya", "fel": "felsefe",
    "din": "din", "edb": "turkce",
}
SUBJECT_NAMES = {
    "mat": "Matematik", "fizik": "Fizik", "kimya": "Kimya", "bio": "Biyoloji", "turkce": "Türkçe",
    "tarih": "Tarih", "cografya": "Coğrafya", "felsefe": "Felsefe", "din": "Din Kültürü",
}
STATUS_NORM = {"yanlış": "Yanlış", "yanlis": "Yanlış", "boş": "Boş", "bos": "Boş", "yapamadı": "Yapamadı",
               "yapamadi": "Yapamadı", "zorlandı": "Zorlandı", "zorlandi": "Zorlandı"}
MONTHS = {"ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "mayis": 5, "haziran": 6,
          "temmuz": 7, "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9, "ekim": 10, "kasım": 11,
          "kasim": 11, "aralık": 12, "aralik": 12}
SKIP_DIRS = {"sonuçlar", "sonuclar"}


def root() -> Path:
    return Path(config.get()["exams_dir"])


def parse_image_name(name: str) -> dict:
    stem = Path(name).stem
    parts = stem.split("_")
    info = {"file": name, "code": "", "subject": "", "subject_name": "", "topic": "", "status": "",
            "no": None, "answer": ""}
    if len(parts) >= 6:
        code, subj, *topic, status, no, ans = parts
        info.update(code=code, topic=" ".join(topic), status=STATUS_NORM.get(status.lower(), status),
                    answer=ans.upper()[:1])
        info["no"] = int(no) if no.isdigit() else None
        s = SUBJECT_CODES.get(subj.lower()[:3], subj.lower())
        info["subject"] = s
        info["subject_name"] = "Geometri" if subj.lower().startswith("geo") else SUBJECT_NAMES.get(s, subj)
    return info


def guess_date(folder: str, year: int) -> str:
    m = re.search(r"(\d{1,2})\s*([A-Za-zÇĞİÖŞÜçğıöşü]+)", folder.split("_", 2)[-1])
    if m and m.group(2).lower() in MONTHS:
        try:
            return datetime(year, MONTHS[m.group(2).lower()], int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""


def exam_id(folder: Path) -> str:
    return folder.relative_to(root()).as_posix()


def folder_of(eid: str) -> Path:
    p = (root() / eid).resolve()
    if root().resolve() not in p.parents and p != root().resolve():
        raise ValueError("geçersiz sınav yolu")
    return p


def load_exam(folder: Path) -> dict:
    meta_p = folder / "exam.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    images, pdfs = [], []
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() in IMG_EXT:
            info = parse_image_name(f.name)
            info["path"] = str(f)
            images.append(info)
        elif f.suffix.lower() == ".pdf":
            pdfs.append(str(f))
    analysis_p = folder / "analysis.json"
    analysis = json.loads(analysis_p.read_text(encoding="utf-8")) if analysis_p.exists() else None
    year = int(meta.get("year") or datetime.now().year)
    eid = exam_id(folder)
    type_guess = meta.get("type") or ("AYT" if "ayt" in folder.name.lower() else "TYT")
    return {
        "id": eid,
        "folder": str(folder),
        "name": meta.get("name") or folder.name,
        "date": meta.get("date") or guess_date(folder.name, year),
        "type": type_guess,
        "group": eid.split("/")[0] if "/" in eid else "Genel Denemeler",
        "result_pdf": config.remap(meta.get("result_pdf", "")),
        "booklet_pdfs": [p for p in pdfs if p != config.remap(meta.get("result_pdf", ""))],
        "images": images,
        "analysis": analysis,
        "notes": meta.get("notes", ""),
    }


def list_exams() -> list[dict]:
    r = root()
    if not r.is_dir():
        return []
    out = []
    for folder in sorted(p for p in r.rglob("*") if p.is_dir()):
        if any(part.lower() in SKIP_DIRS or part.startswith(".") for part in folder.relative_to(r).parts):
            continue
        files = [f for f in folder.iterdir() if f.is_file()]
        has = any(f.suffix.lower() in IMG_EXT | {".pdf"} for f in files) or (folder / "exam.json").exists()
        if has:
            out.append(load_exam(folder))
    out.sort(key=lambda e: (e["date"] or "0000", e["id"]), reverse=True)
    return out


def result_pdfs() -> list[str]:
    r = root()
    out = []
    for d in r.iterdir() if r.is_dir() else []:
        if d.is_dir() and d.name.lower() in SKIP_DIRS:
            out += [str(p) for p in sorted(d.glob("*.pdf"))]
    return out


def save_meta(eid: str, patch: dict) -> dict:
    folder = folder_of(eid)
    meta_p = folder / "exam.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    meta.update({k: v for k, v in patch.items() if k in {"name", "date", "type", "result_pdf", "notes", "year"}})
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_exam(folder)


def create_exam(folder_name: str, meta: dict) -> dict:
    safe = re.sub(r'[<>:"/\\|?*]', "_", folder_name).strip()
    folder = root() / safe
    folder.mkdir(parents=True, exist_ok=True)
    return save_meta(exam_id(folder), meta)


def add_image(eid: str, filename: str, data: bytes, subject_code: str, topic: str, status: str,
              no: str, answer: str) -> dict:
    folder = folder_of(eid)
    ext = Path(filename).suffix.lower() or ".jpeg"
    code = folder.name.split("_")[0]
    topic = re.sub(r"[^\wçğıöşüÇĞİÖŞÜ]+", "", topic.title()) or "Konu"
    name = f"{code}_{subject_code}_{topic}_{status}_{no}_{answer.upper()[:1] or 'X'}{ext}"
    target = folder / name
    i = 2
    while target.exists():
        target = folder / f"{Path(name).stem}-{i}{ext}"
        i += 1
    target.write_bytes(data)
    return parse_image_name(target.name) | {"path": str(target)}


def add_file(eid: str, filename: str, data: bytes) -> str:
    folder = folder_of(eid)
    target = folder / Path(filename).name
    target.write_bytes(data)
    return str(target)


def delete_image(path: str) -> None:
    p = Path(path).resolve()
    if root().resolve() not in p.parents or p.suffix.lower() not in IMG_EXT:
        raise ValueError("geçersiz dosya")
    trash = root() / ".silinenler"
    trash.mkdir(exist_ok=True)
    shutil.move(str(p), trash / p.name)
