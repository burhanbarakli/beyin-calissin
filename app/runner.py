"""Claude Code işleri: bu bilgisayardaki `claude` CLI'ını headless (-p) başlatır, akışı kaydeder.

Her iş data/runs/<id>/ altında tutulur:
    job.json        durum, tür, parametreler
    prompt.md       Claude'a verilen görev
    events.jsonl    stream-json ham olaylar
    feed.jsonl      arayüz için sadeleştirilmiş akış
    (iş türüne göre) candidates.json, keys.json, analysis.json ...
"""
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from . import config

ALLOWED_TOOLS = [
    "Read", "Glob", "Grep", "Write", "Edit", "TodoWrite",
    "Bash(python:*)", "Bash(python -m app.qbank:*)", "Bash(ls:*)", "Bash(cat:*)",
    "PowerShell(python:*)",
]

_procs: dict[str, subprocess.Popen] = {}
_lock = threading.Lock()


def run_dir(rid: str) -> Path:
    return config.RUNS_DIR / rid


def read_job(rid: str) -> dict:
    return json.loads((run_dir(rid) / "job.json").read_text(encoding="utf-8"))


def write_job(rid: str, job: dict) -> None:
    (run_dir(rid) / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")


def update_job(rid: str, **kw) -> dict:
    with _lock:
        job = read_job(rid)
        job.update(kw)
        write_job(rid, job)
        return job


def list_jobs(kind: str | None = None, limit: int = 50) -> list[dict]:
    out = []
    for d in sorted(config.RUNS_DIR.iterdir(), reverse=True):
        jf = d / "job.json"
        if jf.exists():
            try:
                j = json.loads(jf.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if kind and j.get("kind") != kind:
                continue
            out.append(j)
        if len(out) >= limit:
            break
    return out


def _feed(rid: str, typ: str, text: str) -> None:
    with open(run_dir(rid) / "feed.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.time(), "type": typ, "text": text}, ensure_ascii=False) + "\n")


def read_feed(rid: str, since: int = 0) -> list[dict]:
    p = run_dir(rid) / "feed.jsonl"
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    return [json.loads(x) for x in lines[since:] if x.strip()]


def _summarize_tool(name: str, inp: dict) -> str:
    if name == "Bash" or name == "PowerShell":
        return f"$ {inp.get('command', '')[:300]}"
    if name in ("Read", "Write", "Edit"):
        p = inp.get("file_path", "")
        return f"{name}: {Path(p).name if p else ''}"
    if name in ("Glob", "Grep"):
        return f"{name}: {inp.get('pattern', '')}"
    if name == "TodoWrite":
        todos = inp.get("todos", [])
        return "Plan: " + " · ".join(f"{'✓' if t.get('status') == 'completed' else '•'} {t.get('content', '')}" for t in todos)
    return f"{name}"


def _handle_event(rid: str, ev: dict) -> None:
    t = ev.get("type")
    if t == "system" and ev.get("subtype") == "init":
        _feed(rid, "info", f"Claude başladı (model: {ev.get('model', '?')})")
    elif t == "assistant":
        for block in ev.get("message", {}).get("content", []):
            if block.get("type") == "text" and block.get("text", "").strip():
                txt = block["text"].strip()
                if "Not logged in" in txt or "/login" in txt:
                    _feed(rid, "error", "Claude Code oturumu açık değil. Bir terminalde `claude` çalıştırıp /login "
                                        "ile giriş yapın (bir kez yeterli), sonra tekrar deneyin.")
                    continue
                _feed(rid, "text", txt)
            elif block.get("type") == "tool_use":
                _feed(rid, "tool", _summarize_tool(block.get("name", ""), block.get("input", {})))
    elif t == "user":
        for block in ev.get("message", {}).get("content", []) if isinstance(ev.get("message", {}).get("content"), list) else []:
            if block.get("type") == "tool_result" and block.get("is_error"):
                c = block.get("content")
                txt = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
                _feed(rid, "error", txt[:400])
    elif t == "result":
        cost = ev.get("total_cost_usd")
        dur = ev.get("duration_ms", 0) / 1000
        _feed(rid, "done" if not ev.get("is_error") else "error",
              f"Bitti — {dur:.0f} sn" + (f", ~${cost:.2f}" if cost else ""))
        update_job(rid, result_text=(ev.get("result") or "")[:4000], cost_usd=cost, duration_s=dur)


def start(kind: str, title: str, prompt: str, params: dict | None = None, on_finish=None,
          files: dict | None = None, model: str = "") -> str:
    """prompt içindeki <RUN_DIR> çalışma klasörüyle değiştirilir; files = {ad: json-nesnesi} önceden yazılır."""
    claude = config.find_claude()
    rid = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + kind + "-" + uuid.uuid4().hex[:4]
    d = run_dir(rid)
    d.mkdir(parents=True)
    rel = d.relative_to(config.ROOT).as_posix()
    prompt = prompt.replace("<RUN_DIR>", rel)
    for name, obj in (files or {}).items():
        (d / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "prompt.md").write_text(prompt, encoding="utf-8")
    job = {"id": rid, "kind": kind, "title": title, "params": params or {}, "status": "running",
           "created": datetime.now().isoformat(timespec="seconds"), "run_dir": str(d)}
    write_job(rid, job)
    if not claude:
        update_job(rid, status="error")
        _feed(rid, "error", "Claude Code bulunamadı. Ayarlar'dan claude.exe yolunu girin.")
        return rid

    cfg = config.get()
    args = [claude, "-p", prompt, "--output-format", "stream-json", "--verbose",
            "--permission-mode", "acceptEdits", "--allowedTools", *ALLOWED_TOOLS]
    model = model or cfg.get("claude_model", "")
    if model:
        args += ["--model", model]
    env = os.environ.copy()
    pydir = str(Path(sys.executable).parent)
    env["PATH"] = pydir + os.pathsep + str(Path(pydir) / "Scripts") + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["BEYIN_RUN_DIR"] = str(d)

    def worker():
        _feed(rid, "info", "Beyin çalışıyor…")
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            proc = subprocess.Popen(args, cwd=str(config.ROOT), env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, creationflags=flags)
            _procs[rid] = proc
            update_job(rid, pid=proc.pid)
            with open(d / "events.jsonl", "wb") as raw:
                for line in proc.stdout:
                    raw.write(line)
                    raw.flush()
                    try:
                        _handle_event(rid, json.loads(line.decode("utf-8", "replace")))
                    except json.JSONDecodeError:
                        pass
            proc.wait()
            err = proc.stderr.read().decode("utf-8", "replace").strip()
            if err:
                (d / "stderr.txt").write_text(err, encoding="utf-8")
            job_now = read_job(rid)
            if job_now.get("status") == "cancelled":
                return
            status = "done" if proc.returncode == 0 else "error"
            if status == "error":
                _feed(rid, "error", f"Claude hata ile çıktı (kod {proc.returncode}). {err[:400]}")
            update_job(rid, status=status, finished=datetime.now().isoformat(timespec="seconds"))
            if on_finish and status == "done":
                try:
                    on_finish(rid)
                except Exception as e:  # noqa: BLE001
                    _feed(rid, "error", f"Sonuç işlenemedi: {e}")
                    update_job(rid, status="error")
        except Exception as e:  # noqa: BLE001
            _feed(rid, "error", f"Başlatılamadı: {e}")
            update_job(rid, status="error")
        finally:
            _procs.pop(rid, None)

    threading.Thread(target=worker, daemon=True).start()
    return rid


def cancel(rid: str) -> bool:
    proc = _procs.get(rid)
    update_job(rid, status="cancelled")
    _feed(rid, "error", "İptal edildi.")
    if proc and proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.kill()
        return True
    return False


def recover_stale() -> None:
    """Sunucu yeniden başladığında yarım kalan işleri işaretle."""
    for j in list_jobs(limit=200):
        if j.get("status") == "running":
            update_job(j["id"], status="error")
            _feed(j["id"], "error", "Sunucu yeniden başlatıldı; iş yarım kaldı.")
