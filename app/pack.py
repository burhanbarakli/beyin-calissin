"""Paylaşım paketi: kod + veriler + kaynak PDF'ler + öğrenci klasörü → tek klasör (özel GitHub reposu için).

    python -m app.pack [hedef]          (varsayılan: D:/beyin-calissin-paylasim)

Hedefte oluşan yapı:
    app/ brain/ docs/ README.md ...     kod ve kılavuz
    data/                               indeks, cevaplar, puanlar, beyin çalışmaları, PDF çıktıları, sonuçlar
    kaynaklar/<klasör>/*.pdf            config'teki kaynak klasörlerinin PDF'leri
    ogrenci/<klasör>/                   denemeler klasörü (fotoğraflar, karneler)
    config.json                         göreli yollarla — indiren kişide aynen çalışır
Tekrar çalıştırmak güvenlidir: yalnızca değişen dosyalar kopyalanır, kaynakta silinenler hedeften de silinir.
"""
import json
import shutil
import sys
from pathlib import Path

from . import config

CODE = ["app", "brain", "docs", "README.md", "CLAUDE.md", "requirements.txt", "baslat.bat",
        "config.example.json", ".gitattributes"]
SKIP_NAMES = {"__pycache__", ".silinenler", "cache", "index_log.txt"}

GITIGNORE = """__pycache__/
*.pyc
data/cache/
.claude/
"""


def mirror(src: Path, dst: Path, pattern: str = "**/*", stats=None) -> None:
    stats = stats if stats is not None else {"copied": 0, "removed": 0}
    wanted = set()
    for f in src.glob(pattern):
        if not f.is_file() or any(p in SKIP_NAMES for p in f.relative_to(src).parts):
            continue
        rel = f.relative_to(src)
        wanted.add(rel)
        t = dst / rel
        if t.exists() and t.stat().st_size == f.stat().st_size and t.stat().st_mtime >= f.stat().st_mtime - 1:
            continue
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, t)
        stats["copied"] += 1
    if dst.exists():
        for t in dst.glob("**/*"):
            if t.is_file() and t.relative_to(dst) not in wanted:
                t.unlink()
                stats["removed"] += 1
    return stats


def pack(target: Path, log=print) -> None:
    cfg = config.get()
    target.mkdir(parents=True, exist_ok=True)
    stats = {"copied": 0, "removed": 0}
    for name in CODE:
        s = config.ROOT / name
        if s.is_dir():
            mirror(s, target / name, stats=stats)
        elif s.exists():
            t = target / name
            if not t.exists() or t.read_bytes() != s.read_bytes():
                shutil.copy2(s, t)
                stats["copied"] += 1
    log("kod kopyalandı")
    mirror(config.DATA, target / "data", stats=stats)
    log("data/ kopyalandı")
    src_rel = []
    for s in cfg["sources"]:
        s = Path(s)
        if s.is_dir():
            mirror(s, target / "kaynaklar" / s.name, pattern="*.pdf", stats=stats)
            src_rel.append(f"kaynaklar/{s.name}")
    log(f"kaynak PDF'ler kopyalandı: {src_rel}")
    ex = Path(cfg["exams_dir"])
    ex_rel = ""
    if ex.is_dir():
        mirror(ex, target / "ogrenci" / ex.name, stats=stats)
        ex_rel = f"ogrenci/{ex.name}"
        log(f"öğrenci klasörü kopyalandı: {ex_rel}")
    raw = config._load()
    (target / "config.json").write_text(json.dumps({
        "student_name": raw.get("student_name", "Öğrenci"),
        "sources": src_rel,
        "exams_dir": ex_rel,
        "port": raw.get("port", 8765),
        "claude_path": "",
        "claude_model": raw.get("claude_model", ""),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (target / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    size = sum(f.stat().st_size for f in target.glob("**/*") if f.is_file() and ".git" not in f.parts)
    log(f"Paket hazır: {target}  ({size / 1e6:.0f} MB; {stats['copied']} dosya kopyalandı, {stats['removed']} silindi)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    pack(Path(sys.argv[1] if len(sys.argv) > 1 else "D:/beyin-calissin-paylasim"))
