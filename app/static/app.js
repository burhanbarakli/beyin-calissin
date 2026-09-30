// Beyin Çalışsın — arayüz
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = async (url, opt = {}) => {
  const r = await fetch(url, opt.body && !(opt.body instanceof FormData)
    ? { ...opt, headers: { "Content-Type": "application/json" }, body: JSON.stringify(opt.body) } : opt);
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
  return r.json();
};
const fileUrl = (p) => "/api/file?path=" + encodeURIComponent(p);
const cropUrl = (q) => "/api/crop?qid=" + encodeURIComponent(q);
const toast = (m, ms = 2600) => { const t = $("#toast"); t.textContent = m; t.classList.remove("hidden"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), ms); };
const modal = (html) => { $("#modalContent").innerHTML = html; $("#modal").classList.remove("hidden"); };
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal" || e.target.classList.contains("close")) $("#modal").classList.add("hidden"); });

const SUBJECTS = [["mat", "Matematik"], ["fizik", "Fizik"], ["kimya", "Kimya"], ["bio", "Biyoloji"], ["turkce", "Türkçe"], ["tarih", "Tarih"], ["cografya", "Coğrafya"], ["felsefe", "Felsefe"]];
const ROLE = { hatirlatici: "Hatırlatıcı", pekistirme: "Pekiştirme", zorlayici: "Zorlayıcı" };
const ROLE_ORDER = { hatirlatici: 0, pekistirme: 1, zorlayici: 2 };

const S = { state: null, exams: [], resultPdfs: [], selExams: new Set(), selImgs: new Set(), subjects: new Set(),
  job: null, since: 0, poll: null, cand: null, runId: "", basket: new Map() };
try { const b = JSON.parse(localStorage.getItem("basket") || "[]"); b.forEach((x) => S.basket.set(x.qid, x)); } catch {}
const saveBasket = () => { try { localStorage.setItem("basket", JSON.stringify([...S.basket.values()])); } catch {} renderBasket(); };

// ------------------------------------------------------------------ sekmeler
$$("#tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
function showTab(t) {
  $$("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === t));
  $$(".tab").forEach((s) => s.classList.toggle("active", s.id === "tab-" + t));
  if (t === "outputs") loadOutputs();
  if (t === "sources") loadState();
  if (t === "exams") loadExams().then(renderExamList);
  try { localStorage.setItem("tab", t); } catch {}
}

// ------------------------------------------------------------------ durum
async function loadState() {
  S.state = await api("/api/state");
  const c = S.state.config_raw || S.state.config;
  $("#student").textContent = "· " + c.student_name;
  const st = $("#claudeStatus");
  st.className = "status" + (S.state.claude ? " ok" : "");
  st.textContent = S.state.claude ? "Claude Code bulundu" : "Claude Code bulunamadı";
  st.title = S.state.claude || "Ayarlar'dan yolu girin";
  renderBooks();
  renderIndexLog();
  // ayarlar
  $("#setStudent").value = c.student_name; $("#setSources").value = (c.sources || []).join("\n");
  $("#setExams").value = c.exams_dir; $("#setClaude").value = c.claude_path || ""; $("#setModel").value = c.claude_model || "";
}

async function loadExams() {
  const r = await api("/api/exams");
  S.exams = r.exams; S.resultPdfs = r.result_pdfs; $("#examRoot").textContent = S.state?.config_raw?.exams_dir || r.root;
  return r;
}

// ------------------------------------------------------------------ BEYİN: seçim
function renderExamPick() {
  const box = $("#examPick");
  if (!S.exams.length) { box.innerHTML = `<p class="muted small" style="padding:10px">Sınav bulunamadı. Ayarlar'dan denemeler klasörünü kontrol edin.</p>`; return; }
  box.innerHTML = S.exams.map((e) => `
    <label><input type="checkbox" value="${esc(e.id)}" ${S.selExams.has(e.id) ? "checked" : ""}>
      <div><b>${esc(e.name)}</b> <span class="badge">${esc(e.type)}</span>
        ${e.analysis ? '<span class="badge ok">analiz</span>' : ""}${e.result_pdf ? '<span class="badge">sonuç</span>' : ""}
        <div class="meta">${esc(e.date || "tarih yok")} · ${e.images.length} soru görseli · ${esc(e.group)}</div></div></label>`).join("");
  $$("input", box).forEach((i) => i.addEventListener("change", () => { i.checked ? S.selExams.add(i.value) : S.selExams.delete(i.value); renderImgPick(); }));
  renderImgPick();
}
function renderImgPick() {
  const imgs = S.exams.filter((e) => S.selExams.has(e.id)).flatMap((e) => e.images.map((im) => ({ ...im, exam: e.name })))
    .filter((im) => !S.subjects.size || S.subjects.has(im.subject));
  $("#imgPick").innerHTML = imgs.map((im) => `
    <div class="thumb ${S.selImgs.has(im.path) ? "on" : ""}" data-p="${esc(im.path)}" title="${esc(im.file)}">
      <img loading="lazy" src="${fileUrl(im.path)}"><div class="cap"><b>${esc(im.subject_name)}</b> ${esc(im.topic)}<br>${esc(im.status)} · ${esc(im.code)} #${im.no ?? ""}</div></div>`).join("")
    || `<p class="muted small">Seçili sınavlarda görsel yok.</p>`;
  $$("#imgPick .thumb").forEach((t) => t.addEventListener("click", () => {
    const p = t.dataset.p; S.selImgs.has(p) ? S.selImgs.delete(p) : S.selImgs.add(p); t.classList.toggle("on"); countImgs();
  }));
  countImgs();
}
const countImgs = () => { $("#imgPickCount").textContent = S.selImgs.size ? `(${S.selImgs.size} seçili)` : ""; };
$$("[data-last]").forEach((b) => b.addEventListener("click", () => {
  S.selExams = new Set(S.exams.slice(0, +b.dataset.last).map((e) => e.id)); renderExamPick();
}));
$("#clearExams").addEventListener("click", () => { S.selExams.clear(); S.selImgs.clear(); renderExamPick(); });
$("#subjPick").innerHTML = SUBJECTS.map(([k, n]) => `<button class="chip" data-s="${k}">${n}</button>`).join("");
$$("#subjPick .chip").forEach((b) => b.addEventListener("click", () => {
  const s = b.dataset.s; S.subjects.has(s) ? S.subjects.delete(s) : S.subjects.add(s); b.classList.toggle("on"); renderImgPick();
}));

// ------------------------------------------------------------------ BEYİN: çalıştır + akış
$("#runBrain").addEventListener("click", async () => {
  if (!S.state?.claude) return toast("Claude Code bulunamadı — Ayarlar'a bakın.");
  const body = {
    exam_ids: [...S.selExams], image_paths: [...S.selImgs], subjects: [...S.subjects],
    counts: { hatirlatici: +$("#cH").value, pekistirme: +$("#cP").value, zorlayici: +$("#cZ").value },
    max_topics: +$("#cT").value, note: $("#note").value, allow_repeat: $("#allowRepeat").checked,
  };
  try {
    const r = await api("/api/brain", { method: "POST", body });
    watchJob(r.job, true);
    loadHistory();
  } catch (e) { toast(e.message); }
});

function watchJob(id, fresh = false) {
  S.job = id; S.since = 0; S.live = fresh; $("#feed").innerHTML = ""; clearInterval(S.poll);
  if (fresh) { $("#candidates").classList.add("hidden"); }
  S.poll = setInterval(pollJob, 1500); pollJob();
}
async function pollJob() {
  if (!S.job) return;
  let r; try { r = await api(`/api/jobs/${S.job}?since=${S.since}`); } catch { return; }
  S.since = r.next;
  const f = $("#feed");
  const atBottom = f.scrollTop + f.clientHeight >= f.scrollHeight - 30;
  r.feed.forEach((x) => { const d = document.createElement("div"); d.className = x.type; d.textContent = x.text; f.appendChild(d); });
  if (atBottom) f.scrollTop = f.scrollHeight;
  const j = r.job; const running = j.status === "running";
  $("#jobHead").innerHTML = `${running ? '<span class="spinner"></span>' : ""}<b>${esc(j.title)}</b> <span class="muted small">· ${esc(j.created.replace("T", " "))} · ${statusTr(j.status)}</span>`;
  $("#cancelJob").classList.toggle("hidden", !running);
  if (!running) {
    clearInterval(S.poll);
    if (j.kind === "brain" && r.has_candidates) loadCandidates(j.id, S.live);
    if (j.kind !== "brain") { loadState(); loadExams().then(() => { renderExamList(); renderExamPick(); }); }
  }
}
const statusTr = (s) => ({ running: "çalışıyor", done: "tamamlandı", error: "hata", cancelled: "iptal" }[s] || s);
$("#cancelJob").addEventListener("click", async () => { await api(`/api/jobs/${S.job}/cancel`, { method: "POST" }); toast("Durduruldu"); });

async function loadHistory() {
  const js = await api("/api/jobs");
  $("#runHistory").innerHTML = `<option value="">Geçmiş çalışmalar…</option>` +
    js.map((j) => `<option value="${j.id}">${esc(j.created.replace("T", " ").slice(0, 16))} · ${esc(j.title)} (${statusTr(j.status)})</option>`).join("");
}
$("#runHistory").addEventListener("change", (e) => { if (e.target.value) { showTab("brain"); watchJob(e.target.value); } });

// ------------------------------------------------------------------ BEYİN: adaylar
async function loadCandidates(id, scroll = false) {
  let c; try { c = await api(`/api/jobs/${id}/candidates`); } catch (e) { toast("Adaylar okunamadı: " + e.message); return; }
  S.cand = c; S.runId = id;
  $("#candidates").classList.remove("hidden");
  $("#summary").innerHTML = `<p>${esc(c.summary || "")}</p>`;
  $("#diagnosis").innerHTML = (c.diagnosis || []).map((d) => `<div class="d"><b>${esc(d.topic)}</b> <span class="muted small">${esc(d.subject)} · öncelik ${esc(d.priority ?? "")}</span>
    <div>${esc(d.skill || "")}</div><div class="muted small">${esc((d.evidence || []).join(", "))}</div><div class="small">${esc(d.level_note || "")}</div></div>`).join("");
  // önerilenleri sepete ekle (sepet boşsa)
  const fresh = !S.basket.size;
  $("#groups").innerHTML = "";
  (c.groups || []).forEach((g, gi) => {
    const items = (g.items || []).filter((it) => it.found).sort((a, b) => (ROLE_ORDER[a.role] ?? 9) - (ROLE_ORDER[b.role] ?? 9));
    if (fresh) items.filter((it) => it.recommended).forEach((it) => S.basket.set(it.qid, basketItem(it, g)));
    const el = document.createElement("div"); el.className = "group";
    el.innerHTML = `<div class="group-head"><div><h3>${esc(g.title)}</h3><div class="muted">${esc(g.why || "")}</div>
      <div class="row gap" style="margin-top:6px"><button class="chip" data-a="rec">Önerilenleri seç</button><button class="chip" data-a="all">Tümünü seç</button><button class="chip" data-a="none">Hiçbirini</button></div></div>
      <div class="src-imgs">${(g.source_images || []).map((p) => `<img src="${fileUrl(p)}" data-full="${fileUrl(p)}" title="Öğrencinin yapamadığı soru">`).join("")}</div></div>
      <div class="cards">${items.map((it) => cardHtml(it)).join("")}</div>`;
    $("#groups").appendChild(el);
    el._items = items; el._g = g;
  });
  bindCards($("#groups"));
  $$("#groups .group").forEach((el) => $$("[data-a]", el).forEach((b) => b.addEventListener("click", () => {
    el._items.forEach((it) => {
      const on = b.dataset.a === "all" || (b.dataset.a === "rec" && it.recommended);
      on ? S.basket.set(it.qid, basketItem(it, el._g)) : S.basket.delete(it.qid);
    });
    syncCards(); saveBasket();
  })));
  $$(".src-imgs img").forEach((i) => i.addEventListener("click", () => modal(`<img src="${i.dataset.full}">`)));
  syncCards(); saveBasket();
  if (scroll) $("#candidates").scrollIntoView({ behavior: "smooth" });
}
const basketItem = (it, g) => ({ qid: it.qid, role: it.role, group: g?.title || "", answer: it.answer || "",
  source: it.source || "", source_images: g?.source_images || [] });

const FB = [["kolay", "Kolay"], ["uygun", "Uygun"], ["zor", "Zor"], ["kullanma", "✕ Kullanma"]];
const STUDENT = { yapti: "✔ yaptı", yapamadi: "✘ yapamadı", bos: "boş" };
function diffHtml(d, it) {
  if (!d) return "";
  const why = [`kitap ${d.book}`, d.claude ? `Claude ${d.claude}` : "", d.teacher ? `öğretmen: ${d.teacher}` : "",
    d.student ? `öğrenci: ${STUDENT[d.student]}` : "", it?.difficulty_note || ""].filter(Boolean).join(" · ");
  const lvl = d.value <= 2.4 ? "d1" : d.value <= 3.6 ? "d2" : "d3";
  return `<span class="diff ${lvl}" title="${esc(why)}">Zorluk ${d.value}/5${d.claude ? " ⭐" : ""}</span>` +
    (d.student ? `<span class="badge ${d.student === "yapti" ? "ok" : "bad"}">${STUDENT[d.student]}</span>` : "");
}
function cardHtml(it) {
  const ans = it.bank_answer || it.answer || "";
  const claude = !it.bank_answer && it.answer;
  const d = it.diff || it.difficulty;
  const fb = d?.teacher || "";
  return `<div class="card" data-q="${esc(it.qid)}">
    <div class="img"><img loading="lazy" src="${cropUrl(it.qid)}"></div>
    <div class="body"><div class="top-line">${it.role ? `<span class="role ${it.role}">${ROLE[it.role] || it.role}</span>` : ""}
      ${it.recommended ? '<span class="badge ok">önerilen</span>' : ""}
      <span class="ans ${claude ? "claude" : ""}" title="${claude ? "Cevabı Claude çözdü — kontrol edin" : "Kaynağın cevap anahtarı"}">Cevap: ${esc(ans || "?")}${claude ? "*" : ""}</span>
      <button class="chip zoom" title="Büyüt">⤢</button><span class="sel">☐</span></div>
      <div class="top-line">${diffHtml(d, it)}</div>
      ${it.why ? `<div class="why">${esc(it.why)}</div>` : ""}<div class="src">${esc(it.source || it.qid)}</div>
      <div class="fb" title="Geri bildiriminiz sonraki seçimlerde kullanılır">${FB.map(([k, n]) => `<button data-fb="${k}" class="${fb === k ? "on" : ""}">${n}</button>`).join("")}</div>
    </div></div>`;
}
async function sendFeedback(card, value) {
  const qid = card.dataset.q;
  const cur = $(`[data-fb="${value}"]`, card).classList.contains("on");
  const r = await api("/api/feedback", { method: "POST", body: { qid, value: cur ? null : value } });
  $$("[data-fb]", card).forEach((b) => b.classList.toggle("on", !cur && b.dataset.fb === value));
  const line = $(".diff", card)?.parentElement;
  if (line && r.difficulty) line.innerHTML = diffHtml(r.difficulty);
  if (!cur && value === "kullanma" && S.basket.has(qid)) { S.basket.delete(qid); syncCards(); saveBasket(); }
  toast(cur ? "Geri bildirim kaldırıldı" : value === "kullanma" ? "Bu soru bir daha önerilmeyecek" : "Kaydedildi: " + value);
}
function bindCards(root, itemsLookup) {
  $$(".card", root).forEach((c) => c.addEventListener("click", (e) => {
    const qid = c.dataset.q;
    if (e.target.classList.contains("zoom")) return modal(`<img src="${cropUrl(qid)}" style="width:640px">`);
    const fb = e.target.closest("[data-fb]");
    if (fb) return sendFeedback(c, fb.dataset.fb);
    if (S.basket.has(qid)) S.basket.delete(qid);
    else {
      const g = c.closest(".group")?._g; const it = (c.closest(".group")?._items || []).find((x) => x.qid === qid) || (itemsLookup || {})[qid] || { qid };
      S.basket.set(qid, basketItem(it, g));
    }
    syncCards(); saveBasket();
  }));
}
function syncCards() { $$(".card").forEach((c) => { const on = S.basket.has(c.dataset.q); c.classList.toggle("on", on); $(".sel", c).textContent = on ? "☑" : "☐"; }); }

// ------------------------------------------------------------------ sepet + PDF
function renderBasket() {
  $("#basket").classList.toggle("hidden", !S.basket.size);
  $("#bCount").textContent = S.basket.size;
  const items = [...S.basket.values()];
  $("#bList").innerHTML = items.map((it, i) => `<div class="bi" data-i="${i}"><span class="role-dot ${it.role}"></span>
    <span class="t" title="${esc(it.source)}">${i + 1}. ${esc(it.group || "")} — ${esc(it.source || it.qid)}</span>
    <select data-role>${Object.entries(ROLE).map(([k, v]) => `<option value="${k}" ${k === it.role ? "selected" : ""}>${v}</option>`).join("")}</select>
    <button data-up>↑</button><button data-dn>↓</button><button data-x>×</button></div>`).join("");
  $$("#bList .bi").forEach((row) => {
    const i = +row.dataset.i;
    const move = (d) => { const a = [...S.basket.values()]; const j = i + d; if (j < 0 || j >= a.length) return; [a[i], a[j]] = [a[j], a[i]]; S.basket = new Map(a.map((x) => [x.qid, x])); saveBasket(); };
    $("[data-up]", row).onclick = () => move(-1); $("[data-dn]", row).onclick = () => move(1);
    $("[data-x]", row).onclick = () => { S.basket.delete(items[i].qid); syncCards(); saveBasket(); };
    $("[data-role]", row).onchange = (e) => { items[i].role = e.target.value; saveBasket(); };
  });
}
$("#bToggle").addEventListener("click", () => $("#bList").classList.toggle("hidden"));
$("#makePdf").addEventListener("click", async () => {
  let items = [...S.basket.values()];
  if ($("#optRole").checked) items = items.map((x, i) => ({ ...x, _i: i })).sort((a, b) => (a.group || "").localeCompare(b.group || "", "tr") || (ROLE_ORDER[a.role] ?? 9) - (ROLE_ORDER[b.role] ?? 9) || a._i - b._i);
  const wrong = [];
  if ($("#optWrong").checked) {
    const seen = new Set();
    items.forEach((it) => (it.source_images || []).forEach((p) => { if (!seen.has(p)) { seen.add(p); wrong.push({ path: p, caption: p.split(/[\\/]/).pop().replace(/\.\w+$/, "").replaceAll("_", " ") }); } }));
  }
  $("#makePdf").disabled = true; $("#makePdf").textContent = "Hazırlanıyor…";
  try {
    const r = await api("/api/pdf", { method: "POST", body: { title: $("#pdfTitle").value || "Çalışma Kâğıdı",
      items: items.map(({ qid, role, group, answer }) => ({ qid, role, group, answer })), wrong_images: wrong,
      show_source: $("#optSource").checked, group_by_role: $("#optRole").checked, run_id: S.runId } });
    window.open(r.url, "_blank");
    toast("PDF hazır: " + r.file);
  } catch (e) { toast("PDF hatası: " + e.message, 5000); }
  $("#makePdf").disabled = false; $("#makePdf").textContent = "📄 PDF Oluştur";
});

// ------------------------------------------------------------------ SINAVLAR
function renderExamList() {
  const box = $("#examList");
  box.innerHTML = S.exams.map((e, i) => `
  <div class="exam-card" data-i="${i}">
    <div class="row between"><div><h3>${esc(e.name)}</h3><div class="muted small" title="${esc(e.folder)}">📁 ${esc(e.id)}</div></div>
      <div class="row gap"><button class="ghost small" data-an>🧠 Sonucu analiz et</button></div></div>
    <div class="fields">
      <input data-f="name" value="${esc(e.name)}" placeholder="ad" style="min-width:220px">
      <input data-f="date" type="date" value="${esc(e.date)}">
      <select data-f="type"><option ${e.type === "TYT" ? "selected" : ""}>TYT</option><option ${e.type === "AYT" ? "selected" : ""}>AYT</option></select>
      <select data-f="result_pdf" title="Sonuç (karne) PDF'i"><option value="">— sonuç PDF'i yok —</option>
        ${[...new Set([...S.resultPdfs, ...e.booklet_pdfs, e.result_pdf].filter(Boolean))].map((p) => `<option value="${esc(p)}" ${p === e.result_pdf ? "selected" : ""}>${esc(p.split(/[\\/]/).pop())}</option>`).join("")}</select>
      <button class="small" data-save>Kaydet</button>
      ${e.result_pdf ? `<a href="${fileUrl(e.result_pdf)}" target="_blank" class="small">sonucu aç</a>` : ""}
      ${e.booklet_pdfs.map((p) => `<a href="${fileUrl(p)}" target="_blank" class="small">📘 ${esc(p.split(/[\\/]/).pop())}</a>`).join(" ")}
    </div>
    ${e.analysis ? analysisHtml(e.analysis) : ""}
    <div class="grid">${e.images.map((im) => `<div class="thumb" title="${esc(im.file)}"><img loading="lazy" src="${fileUrl(im.path)}" data-full="${fileUrl(im.path)}">
      <div class="cap"><b>${esc(im.subject_name)}</b> ${esc(im.topic)} · ${esc(im.status)} #${im.no ?? ""} (${esc(im.answer)}) <a href="#" data-del="${esc(im.path)}" title="Sil">🗑</a></div></div>`).join("")}</div>
    <div class="drop">
      <b>Yapamadığı soru ekle:</b> fotoğrafları sürükleyin veya seçin.
      <div class="fields">
        <select data-u="subject">${[["Mat", "Matematik"], ["Geo", "Geometri"], ["Fiz", "Fizik"], ["Kim", "Kimya"], ["Bio", "Biyoloji"], ["Tur", "Türkçe"], ["Tar", "Tarih"], ["Cog", "Coğrafya"], ["Fel", "Felsefe"], ["Din", "Din"]].map(([k, n]) => `<option value="${k}">${n}</option>`).join("")}</select>
        <input data-u="topic" placeholder="konu (örn. Fonksiyon)">
        <select data-u="status"><option>Yapamadı</option><option>Yanlış</option><option>Boş</option><option>Zorlandı</option></select>
        <input data-u="no" placeholder="soru no" style="width:80px">
        <input data-u="answer" placeholder="doğru cvp" style="width:90px" maxlength="1">
        <input type="file" multiple accept="image/*,.pdf" data-u="files">
        <button class="small" data-up>Yükle</button>
      </div>
      <div class="muted small">PDF yüklerseniz (sonuç karnesi / kitapçık) sınav klasörüne kopyalanır.</div>
    </div>
  </div>`).join("") || `<p class="muted">Sınav yok. "+ Yeni sınav" ile ekleyin.</p>`;

  $$(".exam-card", box).forEach((card) => {
    const e = S.exams[+card.dataset.i];
    $("[data-save]", card).onclick = async () => {
      const body = { id: e.id }; $$("[data-f]", card).forEach((f) => (body[f.dataset.f] = f.value));
      await api("/api/exams/meta", { method: "POST", body }); toast("Kaydedildi"); await loadExams(); renderExamList(); renderExamPick();
    };
    $("[data-an]", card).onclick = async () => {
      if (!e.result_pdf && !e.images.length) return toast("Önce sonuç PDF'i seçin veya görsel ekleyin.");
      const r = await api("/api/exams/analyze", { method: "POST", body: { id: e.id } });
      showTab("brain"); watchJob(r.job); loadHistory();
    };
    $$("[data-full]", card).forEach((i) => (i.onclick = () => modal(`<img src="${i.dataset.full}">`)));
    $$("[data-del]", card).forEach((a) => (a.onclick = async (ev) => {
      ev.preventDefault(); if (!confirm("Bu görsel .silinenler klasörüne taşınsın mı?")) return;
      await api("/api/exams/delete-image", { method: "POST", body: { path: a.dataset.del } }); await loadExams(); renderExamList();
    }));
    const drop = $(".drop", card); const fi = $('[data-u="files"]', card);
    drop.ondragover = (ev) => { ev.preventDefault(); drop.classList.add("over"); };
    drop.ondragleave = () => drop.classList.remove("over");
    drop.ondrop = (ev) => { ev.preventDefault(); drop.classList.remove("over"); fi.files = ev.dataTransfer.files; };
    $("[data-up]", card).onclick = async () => {
      if (!fi.files.length) return toast("Dosya seçin");
      const fd = new FormData(); fd.append("id", e.id);
      ["subject", "topic", "status", "no", "answer"].forEach((k) => fd.append(k, $(`[data-u="${k}"]`, card).value));
      [...fi.files].forEach((f) => fd.append("files", f));
      await api("/api/exams/upload", { method: "POST", body: fd }); toast("Yüklendi"); await loadExams(); renderExamList(); renderExamPick();
    };
  });
}
function analysisHtml(a) {
  const nets = Object.entries(a.nets || {}).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.d ?? ""}</td><td>${v.y ?? ""}</td><td>${v.b ?? ""}</td><td><b>${v.net ?? ""}</b></td></tr>`).join("");
  const weak = (a.weak_topics || []).slice(0, 8).map((w) => `<li><b>${esc(w.topic)}</b> <span class="muted">(${esc(w.subject)}, ${w.missed ?? "?"}/${w.total ?? "?"})</span> ${esc(w.note || "")}</li>`).join("");
  return `<div class="analysis"><div class="row gap" style="align-items:flex-start;flex-wrap:wrap">
    ${nets ? `<table><tr><th>Ders</th><th>D</th><th>Y</th><th>B</th><th>Net</th></tr>${nets}</table>` : ""}
    <div style="flex:1;min-width:260px"><b>Zayıf konular</b><ul style="margin:4px 0">${weak}</ul><div class="muted">${esc(a.comment || "")}</div></div></div></div>`;
}
$("#newExam").addEventListener("click", async () => {
  const folder = prompt("Klasör adı (örn. D05_Limit_2Ekim):"); if (!folder) return;
  const type = (prompt("TYT mi AYT mi?", "TYT") || "TYT").toUpperCase();
  await api("/api/exams", { method: "POST", body: { folder, type, name: folder } });
  await loadExams(); renderExamList(); renderExamPick();
});

// ------------------------------------------------------------------ KAYNAKLAR
function renderBooks() {
  const books = S.state.books;
  const subjName = Object.fromEntries(SUBJECTS);
  $("#bookTbl").innerHTML = `<tr><th>Kitap</th><th>Sınav</th><th>Ders</th><th>Tür</th><th>Soru</th><th>Konu</th><th>Cevap anahtarı</th><th>Claude zorluk puanı</th><th></th></tr>` +
    books.map((b) => {
      const pct = b.questions ? Math.round((100 * b.answered) / b.questions) : 0;
      const rp = b.questions ? Math.round((100 * (b.rated || 0)) / b.questions) : 0;
      return `<tr><td>${esc(b.id)}</td><td>${esc(b.exam)}</td><td>${esc(subjName[b.subject] || b.subject)}</td><td>${esc(b.kind_name)}</td>
      <td>${b.questions}</td><td>${b.topics}</td><td><span class="bar"><i style="width:${pct}%"></i></span>${pct}%</td>
      <td><span class="bar"><i style="width:${rp}%;background:#e0a100"></i></span>${b.rated || 0}</td>
      <td class="row gap"><button class="small ghost" data-key="${esc(b.id)}" ${pct >= 99 ? "disabled" : ""}>🧠 Cevapları çıkar</button>
        <button class="small ghost" data-rate="${esc(b.id)}" ${b.rated >= b.questions ? "disabled" : ""}>⭐ Zorluk puanla</button></td></tr>`;
    }).join("") + (books.length ? "" : `<tr><td colspan="9" class="muted">Henüz indeks yok. "Yeni kitapları indeksle"ye basın.</td></tr>`);
  $$("[data-key]").forEach((b) => (b.onclick = async () => {
    const r = await api(`/api/keys/${encodeURIComponent(b.dataset.key)}`, { method: "POST" });
    toast("Claude cevap anahtarını okuyor…"); showTab("brain"); watchJob(r.job); loadHistory();
  }));
  $$("[data-rate]").forEach((b) => (b.onclick = async () => {
    const n = prompt("Bu çalışmada kaç soru puanlansın? (Her 80 soru yaklaşık 3-5 dakika sürer.)", "80");
    if (!n) return;
    const r = await api(`/api/rate/${encodeURIComponent(b.dataset.rate)}`, { method: "POST", body: { limit: +n || 80 } });
    toast("Claude soruları puanlıyor…"); showTab("brain"); watchJob(r.job); loadHistory();
  }));
}
function renderIndexLog() {
  const ix = S.state.index; const el = $("#indexLog");
  el.classList.toggle("hidden", !ix.running && !ix.log.length);
  el.textContent = (ix.running ? "⏳ İndeksleniyor…\n" : "") + ix.log.join("\n");
  if (ix.running) setTimeout(() => api("/api/state").then((s) => { S.state = s; renderIndexLog(); if (!s.index.running) renderBooks(); }), 1500);
}
$("#indexNew").onclick = async () => { await api("/api/index", { method: "POST", body: {} }); loadState(); };
$("#indexAll").onclick = async () => { if (confirm("Tüm kitaplar yeniden indekslensin mi? (cevaplar korunur)")) { await api("/api/index", { method: "POST", body: { force: true } }); loadState(); } };
$("#sSubj").innerHTML = `<option value="">tüm dersler</option>` + SUBJECTS.map(([k, n]) => `<option value="${k}">${n}</option>`).join("");
$("#sGo").onclick = async () => {
  const p = new URLSearchParams({ limit: 60 });
  [["exam", "#sExam"], ["subject", "#sSubj"], ["topic", "#sTopic"], ["text", "#sText"], ["level", "#sLevel"]].forEach(([k, s]) => $(s).value && p.set(k, $(s).value));
  const res = await api("/api/search?" + p);
  const lookup = {};
  $("#sRes").innerHTML = res.map((r) => {
    const role = { 1: "hatirlatici", 2: "pekistirme", 3: "zorlayici" }[r.rank];
    const it = { qid: r.qid, role, bank_answer: r.answer, diff: r.difficulty, source: `${r.book} · ${r.topic} · ${r.level}${r.osym ? " · " + r.osym : ""}`, found: true };
    lookup[r.qid] = { ...it };
    return cardHtml(it);
  }).join("") || `<p class="muted">Sonuç yok.</p>`;
  bindCards($("#sRes"), lookup); syncCards();
};
["#sTopic", "#sText"].forEach((s) => $(s).addEventListener("keydown", (e) => e.key === "Enter" && $("#sGo").click()));

// ------------------------------------------------------------------ ÇIKTILAR
async function loadOutputs() {
  const outs = await api("/api/outputs");
  $("#outList").innerHTML = outs.map((o) => `<div class="out">📄<div class="t"><b>${esc(o.title)}</b><div class="muted small">${esc(o.file)} · ${o.count ?? "?"} soru · ${(o.size / 1024).toFixed(0)} KB
      ${o.results_entered ? ` · <b>sonuç: ${o.results_done}/${o.results_entered} yaptı</b>` : ""}</div></div>
    ${o.has_items ? `<button class="small ghost" data-res="${esc(o.file)}">📝 Sonuçları gir</button>` : ""}
    <a href="${o.url}" target="_blank">Aç</a><a href="${o.url}?download=true">İndir</a></div>`).join("") || `<p class="muted">Henüz PDF yok.</p>`;
  $$("[data-res]").forEach((b) => (b.onclick = () => openResults(b.dataset.res)));
}

// öğrencinin çalışma kâğıdı sonuçları: her soru için yaptı / yapamadı / boş
async function openResults(file) {
  const d = await api(`/api/outputs/${encodeURIComponent(file)}/items`);
  const opts = [["yapti", "✔ Yaptı"], ["yapamadi", "✘ Yapamadı"], ["bos", "Boş"]];
  modal(`<h2>📝 ${esc(d.title)} — öğrenci sonuçları</h2>
    <p class="muted small">Öğrenci kâğıdı çözdükten sonra her soruyu işaretleyin. Beyin sonraki çalışmada bu sonuçlara göre seviyeyi ayarlar:
      yapamadığı konulara daha çok hatırlatıcı koyar, yaptığı soruların zorluğunu bu öğrenci için düşürür.</p>
    <div class="row gap" style="margin:8px 0"><button class="chip" data-all="yapti">Hepsi yaptı</button><button class="chip" data-all="">Temizle</button></div>
    <div class="res-list">${d.items.map((it) => `<div class="res-row" data-q="${esc(it.qid)}">
      <b class="no">${it.no}.</b><img loading="lazy" src="${cropUrl(it.qid)}" data-zoom>
      <div class="meta"><span class="role ${it.role}">${ROLE[it.role] || ""}</span> <span class="muted small">cevap ${esc(it.answer || "?")}</span><div class="muted small">${esc(it.source)}</div></div>
      <div class="seg">${opts.map(([k, n]) => `<label class="${k}"><input type="checkbox" value="${k}" ${it.result === k ? "checked" : ""}> ${n}</label>`).join("")}</div>
    </div>`).join("")}</div>
    <div class="row gap" style="margin-top:12px"><button id="saveRes">Kaydet</button><span id="resSum" class="muted small"></span></div>`);
  const sum = () => { const v = $$(".res-row input:checked").map((i) => i.value); $("#resSum").textContent = `${v.filter((x) => x === "yapti").length} yaptı · ${v.filter((x) => x === "yapamadi").length} yapamadı · ${v.filter((x) => x === "bos").length} boş · ${d.items.length - v.length} işaretsiz`; };
  // aynı satırda tek seçim (checkbox ama radyo gibi; tekrar tıklayınca kalkar)
  $$(".res-row input").forEach((i) => i.addEventListener("change", () => {
    if (i.checked) $$("input", i.closest(".res-row")).forEach((o) => { if (o !== i) o.checked = false; });
    sum();
  }));
  $$("[data-all]").forEach((b) => (b.onclick = () => { $$(".res-row").forEach((r) => $$("input", r).forEach((i) => (i.checked = !!b.dataset.all && i.value === b.dataset.all))); sum(); }));
  $$(".res-row img[data-zoom]").forEach((im) => (im.onclick = () => window.open(im.src, "_blank")));
  $("#saveRes").onclick = async () => {
    const results = {};
    $$(".res-row").forEach((r) => (results[r.dataset.q] = $("input:checked", r)?.value || ""));
    await api("/api/results", { method: "POST", body: { pdf: file, results } });
    toast("Sonuçlar kaydedildi"); $("#modal").classList.add("hidden"); loadOutputs();
  };
  sum();
}

// ------------------------------------------------------------------ AYARLAR
$("#saveSettings").onclick = async () => {
  await api("/api/config", { method: "POST", body: { student_name: $("#setStudent").value,
    sources: $("#setSources").value.split("\n").map((s) => s.trim()).filter(Boolean), exams_dir: $("#setExams").value,
    claude_path: $("#setClaude").value.trim(), claude_model: $("#setModel").value.trim() } });
  $("#setMsg").textContent = "Kaydedildi."; await loadState(); await loadExams(); renderExamPick();
};
$("#resetUsed").onclick = async () => { if (confirm("Daha önce verilen sorular listesi sıfırlansın mı?")) { await api("/api/used/reset", { method: "POST" }); toast("Sıfırlandı"); } };

// ------------------------------------------------------------------ başlat
(async function init() {
  await loadState();
  await loadExams();
  renderExamPick(); renderBasket(); loadHistory();
  // adres satırından durum: ?tab=exams  ?run=<id>  ?last=3  ?subj=mat,fizik  ?results=<pdf>  ?scroll=candidates
  const qp = new URLSearchParams(location.search);
  if (qp.get("last")) { S.selExams = new Set(S.exams.slice(0, +qp.get("last")).map((e) => e.id)); renderExamPick(); }
  (qp.get("subj") || "").split(",").filter(Boolean).forEach((s) => $(`#subjPick [data-s="${s}"]`)?.click());
  if (qp.get("imgs")) $("#imgPickWrap").open = true;
  const last = qp.get("run") || (await api("/api/jobs?kind=brain"))[0]?.id;
  if (last) watchJob(last);
  let t = qp.get("tab") || "brain"; if (!qp.get("tab")) { try { t = localStorage.getItem("tab") || "brain"; } catch {} }
  if (t !== "brain") showTab(t);
  if (qp.get("results")) setTimeout(() => openResults(qp.get("results")), 800);
  if (qp.get("scroll")) setTimeout(() => $("#" + qp.get("scroll"))?.scrollIntoView(), 2500);
  if (qp.get("only") === "candidates") $(".brain-grid").classList.add("hidden");
})();
