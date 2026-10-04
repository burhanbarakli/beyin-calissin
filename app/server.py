"""Web sunucusu: Chrome'dan http://localhost:8765 ile yönetilir."""
import json
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, exams, indexer, pdfgen, qbank, runner

app = FastAPI(title="Beyin Çalışsın")
STATIC = Path(__file__).parent / "static"
USED_FILE = config.DATA / "used_qids.json"
ANSWER_OVERRIDES = config.DATA / "answer_overrides.json"

index_state = {"running": False, "log": [], "current": ""}


def _json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _check_path(p: str, roots: list[str]) -> Path:
    """Sadece izin verilen kök klasörlerdeki dosyalara erişim."""
    rp = Path(p).resolve()
    for r in roots:
        if r and (Path(r).resolve() in rp.parents or rp == Path(r).resolve()):
            return rp
    raise HTTPException(403, "izin verilmeyen yol")


# ------------------------------------------------------------------ genel
@app.get("/api/state")
def state():
    cfg = config.get()
    return {
        "config": cfg,
        "config_raw": {**cfg, **config._load()},  # ayarlar formu: göreli yollar göreli görünsün
        "version": (config.ROOT / "VERSION").read_text(encoding="utf-8").strip() if (config.ROOT / "VERSION").exists() else "",
        "claude": config.find_claude(),
        "books": qbank.all_books(),
        "source_pdfs": [str(p) for p in indexer.list_source_pdfs()],
        "index": index_state | {"log": index_state["log"][-30:]},
    }


@app.post("/api/config")
def set_config(patch: dict):
    cfg = config._load()  # ham hali: göreli yollar göreli kalsın
    for k in ("student_name", "sources", "exams_dir", "port", "claude_path", "claude_model"):
        if k in patch:
            cfg[k] = patch[k]
    config.save(cfg)
    return cfg


# ------------------------------------------------------------------ kaynak indeksi
@app.post("/api/index")
def start_index(body: dict | None = None):
    if index_state["running"]:
        return {"ok": False, "msg": "zaten çalışıyor"}
    force = bool((body or {}).get("force"))
    only = (body or {}).get("paths")

    def work():
        index_state.update(running=True, log=[])
        try:
            paths = [Path(p) for p in only] if only else None
            indexer.run(paths, force=force, log=lambda m: index_state["log"].append(m))
        except Exception as e:  # noqa: BLE001
            index_state["log"].append(f"HATA: {e}")
        finally:
            index_state["running"] = False
            qbank._load.cache_clear()

    threading.Thread(target=work, daemon=True).start()
    return {"ok": True}


@app.post("/api/keys/{book_id}")
def extract_keys(book_id: str):
    prompt = (f"brain/KEYS.md dosyasındaki talimatları uygula. BOOK = {book_id}. "
              f"Çalışma klasörü (RUN_DIR) = <RUN_DIR>. Türkçe çalış.")
    rid = runner.start("keys", f"Cevap anahtarı: {book_id}", prompt, {"book": book_id})
    return {"job": rid}


@app.get("/api/topics")
def topics(subject: str | None = None, exam: str | None = None):
    return qbank.topics(subject, exam)


@app.get("/api/search")
def search(subject: str | None = None, exam: str | None = None, topic: str | None = None,
           text: str | None = None, level: int | None = None, limit: int = 60):
    return qbank.search(subject, exam, topic, text, level, limit=limit)


@app.get("/api/crop")
def crop(qid: str):
    p = qbank.crop_png(qid)
    if not p:
        raise HTTPException(404)
    return FileResponse(p, media_type="image/png", headers={"Cache-Control": "max-age=86400"})


@app.get("/api/question")
def question(qid: str):
    q = qbank.get_question(qid)
    if not q:
        raise HTTPException(404)
    q["answer"] = _json(ANSWER_OVERRIDES, {}).get(qid) or q.get("answer", "")
    q["source"] = pdfgen.source_label(q)
    return q


# ------------------------------------------------------------------ sınavlar
@app.get("/api/exams")
def list_exams():
    return {"exams": exams.list_exams(), "result_pdfs": exams.result_pdfs(), "root": config.get()["exams_dir"]}


@app.post("/api/exams")
def create_exam(body: dict):
    if not body.get("folder"):
        raise HTTPException(400, "klasör adı gerekli")
    return exams.create_exam(body["folder"], body)


@app.post("/api/exams/meta")
def exam_meta(body: dict):
    return exams.save_meta(body["id"], body)


@app.post("/api/exams/upload")
async def exam_upload(id: str = Form(...), subject: str = Form(""), topic: str = Form(""),
                      status: str = Form("Yapamadı"), no: str = Form(""), answer: str = Form(""),
                      files: list[UploadFile] = File(...)):
    out = []
    imgs = [f for f in files if not f.filename.lower().endswith(".pdf")]
    for f in files:
        data = await f.read()
        if f.filename.lower().endswith(".pdf"):
            out.append({"pdf": exams.add_file(id, f.filename, data)})
        else:
            # soru no / cevap tek fotoğraf yüklenirken anlamlı; topluda otomatik numara verilir
            single = len(imgs) == 1
            out.append(exams.add_image(id, f.filename, data, subject, topic, status,
                                       no if single else "", answer if single else ""))
    return {"saved": out}


@app.post("/api/exams/delete-image")
def exam_delete_image(body: dict):
    exams.delete_image(body["path"])
    return {"ok": True}


@app.post("/api/exams/analyze")
def exam_analyze(body: dict):
    ex = exams.load_exam(exams.folder_of(body["id"]))
    prompt = ("brain/EXAM.md dosyasındaki talimatları uygula. Görev dosyası: <RUN_DIR>/task.json. "
              "RUN_DIR = <RUN_DIR>. Türkçe çalış.")

    def finish(rid):
        res = runner.run_dir(rid) / "analysis.json"
        if res.exists():
            (Path(ex["folder"]) / "analysis.json").write_text(res.read_text(encoding="utf-8"), encoding="utf-8")

    rid = runner.start("exam", f"Sınav analizi: {ex['name']}", prompt, {"exam": ex["id"]},
                       on_finish=finish, files={"task.json": {"exam": ex}})
    return {"job": rid}


@app.get("/api/file")
def get_file(path: str):
    cfg = config.get()
    p = _check_path(config.remap(path), [cfg["exams_dir"], *cfg["sources"], str(config.OUTPUT_DIR)])
    return FileResponse(p)


# ------------------------------------------------------------------ beyin
class BrainReq(BaseModel):
    exam_ids: list[str] = []
    image_paths: list[str] = []
    subjects: list[str] = []
    counts: dict = {"hatirlatici": 3, "pekistirme": 4, "zorlayici": 2}
    max_topics: int = 4
    note: str = ""
    allow_repeat: bool = False
    model: str = ""          # "" = ayarlardaki; opus / sonnet / haiku
    deep: bool = False       # soru-analisti ajanıyla derin analiz


@app.post("/api/brain")
def brain(req: BrainReq):
    all_ex = {e["id"]: e for e in exams.list_exams()}
    sel = [all_ex[i] for i in req.exam_ids if i in all_ex]
    images = []
    for e in all_ex.values():
        for im in e["images"]:
            if im["path"] in req.image_paths:
                images.append(im | {"exam": e["id"], "exam_name": e["name"]})
    if not sel and not images:
        raise HTTPException(400, "En az bir sınav veya soru görseli seçin.")
    for e in sel:
        # sadece eksik gösteren durumlar (doğru yapılanlar beyne gitmez); dersi belirsiz görseller filtrede kalır
        e["images"] = [im for im in e["images"]
                       if im["status"] in exams.ACTIVE_STATUSES or not im["status"]]
        if req.subjects:
            e["images"] = [im for im in e["images"] if not im["subject"] or im["subject"] in req.subjects]
    task = {
        "student": config.get()["student_name"],
        "teacher_note": req.note,
        "exams": sel,
        "images": images,
        "subjects": req.subjects,
        "counts": req.counts,
        "max_topics": req.max_topics,
        "exclude_qids": [] if req.allow_repeat else _json(USED_FILE, []),
        "deep": req.deep,
    }
    title_bits = [e["name"] for e in sel][:3] or [f"{len(images)} soru görseli"]
    if req.deep:
        title_bits[0] = "🔬 " + title_bits[0]
    prompt = ("brain/BRAIN.md dosyasındaki talimatları uygula. Görev dosyası: <RUN_DIR>/task.json. "
              "RUN_DIR = <RUN_DIR>. Sonucu <RUN_DIR>/candidates.json dosyasına yaz. Türkçe çalış.")
    rid = runner.start("brain", "Beyin: " + ", ".join(title_bits), prompt, req.model_dump(),
                       files={"task.json": task}, on_finish=_save_candidate_ratings, model=req.model)
    return {"job": rid}


def _save_candidate_ratings(rid: str) -> None:
    """Beynin adaylara verdiği zorluk puanlarını kalıcı depoya yaz."""
    data = _json(runner.run_dir(rid) / "candidates.json", {})
    patch = {}
    for g in data.get("groups", []):
        for it in g.get("items", []):
            try:
                v = int(it.get("difficulty"))
            except (TypeError, ValueError):
                continue
            if 1 <= v <= 5 and qbank.get_question(it.get("qid", "")):
                patch[it["qid"]] = {"claude": v, "note": str(it.get("difficulty_note", ""))[:200]}
    if patch:
        qbank.update_store("ratings", patch)


@app.post("/api/rate/{book_id}")
def rate_book(book_id: str, body: dict | None = None):
    limit = int((body or {}).get("limit", 80))
    prompt = (f"brain/RATE.md dosyasındaki talimatları uygula. BOOK = {book_id}. LIMIT = {limit}. "
              f"RUN_DIR = <RUN_DIR>. Türkçe çalış.")
    rid = runner.start("rate", f"Zorluk puanlama: {book_id} ({limit} soru)", prompt, {"book": book_id})
    return {"job": rid}


@app.post("/api/feedback")
def feedback(body: dict):
    """{"qid", "value": "kolay"|"uygun"|"zor"|"kullanma"|null}"""
    qid, v = body["qid"], body.get("value")
    if v not in (None, "", "kolay", "uygun", "zor", "kullanma"):
        raise HTTPException(400, "geçersiz değer")
    qbank.update_store("feedback", {qid: {"teacher": v} if v else None})
    q = qbank.get_question(qid)
    return {"qid": qid, "difficulty": qbank.difficulty(q["book"], q) if q else None}


@app.get("/api/outputs/{name}/items")
def output_items(name: str):
    meta = _json((config.OUTPUT_DIR / name).with_suffix(".json"), None)
    if meta is None:
        raise HTTPException(404, "PDF bilgisi yok")
    res = qbank.load_store("results")
    out = []
    for i, it in enumerate(meta.get("items", []), 1):
        q = qbank.get_question(it["qid"])
        if not q:
            continue
        r = res.get(it["qid"], {})
        out.append({"no": i, "qid": it["qid"], "role": it.get("role", ""), "group": it.get("group", ""),
                    "answer": q.get("answer") or it.get("answer", ""), "source": pdfgen.source_label(q),
                    "result": r.get("result", "") if r.get("pdf") == name else ""})
    return {"file": name, "title": meta.get("title", name), "items": out}


@app.post("/api/results")
def save_results(body: dict):
    """{"pdf": dosya, "results": {qid: "yapti"|"yapamadi"|"bos"|""}}"""
    from datetime import datetime
    pdf = body.get("pdf", "")
    patch = {}
    for qid, v in body.get("results", {}).items():
        if v in ("yapti", "yapamadi", "bos"):
            patch[qid] = {"result": v, "pdf": pdf, "t": datetime.now().isoformat(timespec="seconds")}
        elif not v:
            patch[qid] = None
    qbank.update_store("results", patch)
    meta_p = (config.OUTPUT_DIR / pdf).with_suffix(".json")
    meta = _json(meta_p, {})
    if meta:
        vals = [v for v in body.get("results", {}).values() if v]
        meta["results_entered"] = len(vals)
        meta["results_done"] = sum(v == "yapti" for v in vals)
        meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"saved": len(patch)}


@app.get("/api/jobs")
def jobs(kind: str | None = None):
    return runner.list_jobs(kind)


@app.get("/api/jobs/{rid}")
def job(rid: str, since: int = 0):
    try:
        j = runner.read_job(rid)
    except FileNotFoundError:
        raise HTTPException(404)
    feed = runner.read_feed(rid, since)
    cand = runner.run_dir(rid) / "candidates.json"
    return {"job": j, "feed": feed, "next": since + len(feed), "has_candidates": cand.exists()}


@app.post("/api/jobs/{rid}/cancel")
def job_cancel(rid: str):
    return {"ok": runner.cancel(rid)}


@app.get("/api/jobs/{rid}/candidates")
def job_candidates(rid: str):
    p = runner.run_dir(rid) / "candidates.json"
    data = _json(p, None)
    if data is None:
        raise HTTPException(404, "aday dosyası yok veya bozuk")
    overrides = _json(ANSWER_OVERRIDES, {})
    stores = {k: qbank.load_store(k) for k in qbank.STORES}
    for g in data.get("groups", []):
        for it in g.get("items", []):
            q = qbank.get_question(it.get("qid", ""))
            it["found"] = bool(q)
            if q:
                it["source"] = pdfgen.source_label(q)
                it["bank_answer"] = overrides.get(it["qid"]) or q.get("answer", "")
                it["text"] = q.get("text", "")[:300]
                it["diff"] = qbank.difficulty(q["book"], q, stores)
    return data


# ------------------------------------------------------------------ PDF
class PdfReq(BaseModel):
    title: str = "Çalışma Kâğıdı"
    items: list[dict]                   # [{"qid", "role", "group", "answer"?}]
    wrong_images: list[dict] = []       # [{"path", "caption"}]
    show_source: bool = False
    group_by_role: bool = True
    run_id: str = ""
    mark_used: bool = True


@app.post("/api/pdf")
def make_pdf(req: PdfReq):
    if not req.items:
        raise HTTPException(400, "soru seçilmedi")
    overrides = _json(ANSWER_OVERRIDES, {})
    for it in req.items:  # Claude'un çözdüğü cevapları kaydet
        if it.get("answer") and not qbank.get_question(it["qid"]).get("answer"):
            overrides[it["qid"]] = it["answer"]
    ANSWER_OVERRIDES.write_text(json.dumps(overrides, ensure_ascii=False, indent=1), encoding="utf-8")
    orig = qbank.get_question

    def with_override(qid):
        q = orig(qid)
        if q and not q.get("answer") and overrides.get(qid):
            q["answer"] = overrides[qid]
        return q

    qbank.get_question = with_override
    try:
        wrong = [{**w, "path": config.remap(w["path"])} for w in req.wrong_images]
        out = pdfgen.build(req.items, req.title, config.get()["student_name"], req.title,
                           wrong, req.show_source, req.group_by_role)
    finally:
        qbank.get_question = orig
    if req.mark_used:
        used = _json(USED_FILE, [])
        used += [it["qid"] for it in req.items if it["qid"] not in used]
        USED_FILE.write_text(json.dumps(used, ensure_ascii=False), encoding="utf-8")
    meta = {"file": out.name, "title": req.title, "run_id": req.run_id, "items": req.items,
            "count": len(req.items)}
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"file": out.name, "url": f"/api/outputs/{out.name}"}


@app.get("/api/outputs")
def outputs():
    res = []
    for p in sorted(config.OUTPUT_DIR.glob("*.pdf"), reverse=True):
        meta = _json(p.with_suffix(".json"), {})
        res.append({"file": p.name, "title": meta.get("title", p.stem), "count": meta.get("count"),
                    "size": p.stat().st_size, "url": f"/api/outputs/{p.name}", "has_items": bool(meta.get("items")),
                    "results_entered": meta.get("results_entered", 0), "results_done": meta.get("results_done", 0)})
    return res


@app.get("/api/outputs/{name}")
def output_file(name: str, download: bool = False):
    p = (config.OUTPUT_DIR / name).resolve()
    if p.parent != config.OUTPUT_DIR.resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="application/pdf",
                        filename=name if download else None,
                        content_disposition_type="attachment" if download else "inline")


@app.post("/api/outputs/delete")
def outputs_delete(body: dict):
    """PDF'leri (ve bilgi dosyalarını) siler; içindeki soruları 'verilen sorular' listesinden çıkarır."""
    out_dir = config.OUTPUT_DIR.resolve()
    freed, n = set(), 0
    for name in body.get("files", []):
        p = (config.OUTPUT_DIR / name).resolve()
        if p.parent != out_dir or p.suffix.lower() != ".pdf":
            continue
        meta = _json(p.with_suffix(".json"), {})
        freed |= {it["qid"] for it in meta.get("items", [])}
        for f in (p, p.with_suffix(".json")):
            if f.exists():
                f.unlink()
        n += 1
    # hâlâ duran PDF'lerdeki sorular "verilen" olarak kalsın
    still = set()
    for m in config.OUTPUT_DIR.glob("*.json"):
        still |= {it["qid"] for it in _json(m, {}).get("items", [])}
    used = [q for q in _json(USED_FILE, []) if q not in freed or q in still]
    USED_FILE.write_text(json.dumps(used, ensure_ascii=False), encoding="utf-8")
    return {"deleted": n, "freed": len(freed - still)}


@app.post("/api/jobs/delete")
def jobs_delete(body: dict):
    import shutil
    runs_dir = config.RUNS_DIR.resolve()
    n = 0
    for rid in body.get("ids", []):
        d = (config.RUNS_DIR / rid).resolve()
        if d.parent != runs_dir or not d.is_dir():
            continue
        try:
            if runner.read_job(rid).get("status") == "running":
                continue
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        shutil.rmtree(d, ignore_errors=True)
        n += 1
    return {"deleted": n}


@app.post("/api/used/reset")
def used_reset():
    USED_FILE.write_text("[]", encoding="utf-8")
    return {"ok": True}


# ------------------------------------------------------------------ statik
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    runner.recover_stale()
    from . import bank
    bank.seed()
    port =int(config.get().get("port", 8765))
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    url = f"http://localhost:{port}"
    print(f"\n  Beyin Çalışsın hazır → {url}\n  (kapatmak için bu pencereyi kapatın)\n")
    if "--no-browser" not in sys.argv:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
