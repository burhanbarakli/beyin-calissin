"""Paylaşılan soru bankası: repodaki `bank/` klasörü ↔ kişisel `data/` klasörü.

`bank/` repoya girer (herkese açık): soru indeksi, okunmuş cevaplar, Claude zorluk puanları.
Kişisel yollar ve öğrenci verisi içermez; kitap yolu yalnızca dosya adıdır ve çalışırken
`config.json`daki kaynak klasörlerinde dosya adıyla bulunur (qbank.resolve_pdf).

    python -m app.bank export   # data/ → bank/  (paylaşmadan önce)
    python -m app.bank seed     # bank/ → data/  (ilk açılışta otomatik)
"""
import json
import shutil
import sys
from pathlib import Path

from . import config

BANK = config.ROOT / "bank"
SHARED_STORES = ("ratings.json", "answer_overrides.json")


def _dump(obj, path: Path) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def export(log=print) -> None:
    (BANK / "index").mkdir(parents=True, exist_ok=True)
    for old in (BANK / "index").glob("*.json"):
        old.unlink()
    n = 0
    for p in sorted(config.INDEX_DIR.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        d["book"]["path"] = Path(d["book"]["path"]).name   # kişisel yol yok, sadece dosya adı
        _dump(d, BANK / "index" / p.name)
        n += len(d["questions"])
    for name in SHARED_STORES:
        src = config.DATA / name
        if src.exists():
            _dump(json.loads(src.read_text(encoding="utf-8")), BANK / name)
    log(f"bank/ güncellendi: {len(list((BANK / 'index').glob('*.json')))} kitap, {n} soru")


def seed(log=print) -> bool:
    """data/ boşsa bank/'tan doldurur; puan/cevap depolarında eksik olanları ekler."""
    if not (BANK / "index").is_dir():
        return False
    changed = False
    if not any(config.INDEX_DIR.glob("*.json")):
        for p in (BANK / "index").glob("*.json"):
            shutil.copy2(p, config.INDEX_DIR / p.name)
        log("Soru bankası repodaki hazır indeksten yüklendi (bank/index).")
        changed = True
    for name in SHARED_STORES:
        src = BANK / name
        if not src.exists():
            continue
        dst = config.DATA / name
        mine = json.loads(dst.read_text(encoding="utf-8")) if dst.exists() else {}
        theirs = json.loads(src.read_text(encoding="utf-8"))
        add = {k: v for k, v in theirs.items() if k not in mine}
        if add:
            mine.update(add)
            dst.write_text(json.dumps(mine, ensure_ascii=False, indent=1), encoding="utf-8")
            changed = True
    return changed


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "export":
        export()
    elif cmd == "seed":
        print("yüklendi" if seed() else "değişiklik yok")
    else:
        print(__doc__)
