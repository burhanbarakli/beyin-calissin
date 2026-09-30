"""Uygulama ayarları: config.json dosyasından okunur (yoksa config.example.json)."""
import glob
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
INDEX_DIR = DATA / "index"
RUNS_DIR = DATA / "runs"
OUTPUT_DIR = DATA / "outputs"
CACHE_DIR = DATA / "cache"

for _d in (INDEX_DIR, RUNS_DIR, OUTPUT_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _load() -> dict:
    for name in ("config.json", "config.example.json"):
        p = ROOT / name
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _abs(p: str) -> str:
    """Göreli yollar (ör. "kaynaklar/MEB_TYT_Soru") programın klasörüne göre çözülür."""
    if not p:
        return p
    path = Path(p)
    return str(path if path.is_absolute() else (ROOT / path).resolve()).replace("\\", "/")


def get() -> dict:
    cfg = _load()
    cfg.setdefault("student_name", "Öğrenci")
    cfg.setdefault("sources", [])
    cfg.setdefault("exams_dir", "")
    cfg.setdefault("port", 8765)
    cfg.setdefault("claude_path", "")
    cfg.setdefault("claude_model", "")
    cfg["sources"] = [_abs(s) for s in cfg["sources"]]
    cfg["exams_dir"] = _abs(cfg["exams_dir"])
    return cfg


def remap(path: str) -> str:
    """Başka bilgisayarda kaydedilmiş mutlak yolu bu bilgisayara uyarlar.

    Ör. "D:/Alper_irfanhoca/Denemeler/D01/x.jpeg" → "<exams_dir>/D01/x.jpeg"
    (yolun içinde kök klasörün adı — "Denemeler", "MEB_TYT_Soru" — aranır).
    """
    if not path:
        return path
    cfg = get()
    roots = [r for r in [cfg["exams_dir"], *cfg["sources"]] if r]
    try:
        rp = Path(path).resolve()
        if any(Path(r).resolve() in rp.parents for r in roots) and rp.exists():
            return path  # zaten bu kurulumun klasörlerinde
    except OSError:
        pass
    parts = Path(path.replace("\\", "/")).parts
    for root in roots:
        if not root:
            continue
        name = Path(root).name.lower()
        for i, part in enumerate(parts):
            if part.lower() == name:
                cand = Path(root, *parts[i + 1:])
                if cand.exists():
                    return str(cand).replace("\\", "/")
    return path  # eşlenemedi: olduğu gibi (varsa kullanılır)


def save(cfg: dict) -> None:
    (ROOT / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def find_claude() -> str | None:
    """Claude Code çalıştırılabilirini bulur: config > PATH > Claude masaüstü uygulaması."""
    cfg = get()
    if cfg.get("claude_path") and Path(cfg["claude_path"]).exists():
        return cfg["claude_path"]
    for name in ("claude", "claude.exe", "claude.cmd"):
        p = shutil.which(name)
        if p:
            return p
    candidates = []
    for base in (os.environ.get("APPDATA", ""), os.environ.get("LOCALAPPDATA", "")):
        if base:
            candidates += glob.glob(os.path.join(base, "Claude", "claude-code", "*", "claude.exe"))
    # Microsoft Store (MSIX) kurulumu: dosyalar paketin sanal klasöründedir, paket dışından sadece burada görünür
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        candidates += glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude",
                                             "claude-code", "*", "claude.exe"))
    home = Path.home()
    candidates += [str(home / ".local" / "bin" / "claude.exe"), str(home / ".claude" / "local" / "claude.exe")]
    candidates = [c for c in candidates if Path(c).exists()]
    if not candidates:
        return None

    def ver(p):
        try:
            return tuple(int(x) for x in Path(p).parent.name.split("."))
        except ValueError:
            return (0,)

    return sorted(candidates, key=ver)[-1]
