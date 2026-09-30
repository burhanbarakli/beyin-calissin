"""Seçilen soruları A4 çalışma kâğıdı PDF'ine dönüştürür.

Sorular kaynak PDF'ten vektör olarak (show_pdf_page + clip) alınır; kalite kaybı olmaz.
Orijinal soru numarası beyaz kutuyla kapatılıp yeni numara yazılır. Sonda cevap anahtarı yer alır.
"""
import os
import re
from datetime import datetime
from pathlib import Path

import pymupdf

from . import config, qbank

A4 = pymupdf.paper_rect("a4")
M = 34            # kenar boşluğu
GUTTER = 16       # sütun arası
HEADER_H = 22     # sayfa üst bilgisi
FOOTER_H = 18
GAP = 14          # sorular arası boşluk
ROLE_TITLES = {
    "hatirlatici": "Hatırlatıcı / Öğretici Sorular",
    "pekistirme": "Pekiştirme Soruları",
    "zorlayici": "Zorlayıcı Sorular",
}
ROLE_COLORS = {"hatirlatici": (0.13, 0.55, 0.35), "pekistirme": (0.15, 0.4, 0.75), "zorlayici": (0.75, 0.25, 0.2)}


def _font_files():
    cands = [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ]
    for reg, bold in cands:
        if os.path.exists(reg):
            return reg, bold if os.path.exists(bold) else reg
    return None, None


class Writer:
    def __init__(self, title: str, subtitle: str):
        self.doc = pymupdf.open()
        self.title, self.subtitle = title, subtitle
        self.reg, self.bold = _font_files()
        self.colw = (A4.width - 2 * M - GUTTER) / 2
        self.page = None
        self.pageno = 0
        self.new_page()

    # -- yazı
    def text(self, page, pos, s, size=10, bold=False, color=(0, 0, 0)):
        kw = {"fontsize": size, "color": color}
        f = self.bold if bold else self.reg
        if f:
            kw.update(fontname="B" if bold else "R", fontfile=f)
        else:
            kw.update(fontname="hebo" if bold else "helv")
        page.insert_text(pos, s, **kw)

    def text_width(self, s, size, bold=False):
        f = self.bold if bold else self.reg
        font = pymupdf.Font(fontfile=f) if f else pymupdf.Font("helv")
        return font.text_length(s, fontsize=size)

    # -- sayfa
    def new_page(self, divider=True):
        self.page = self.doc.new_page(width=A4.width, height=A4.height)
        self.pageno += 1
        p = self.page
        self.text(p, (M, M - 8), self.title, 9, True, (0.25, 0.25, 0.25))
        right = self.subtitle
        self.text(p, (A4.width - M - self.text_width(right, 8), M - 8), right, 8, False, (0.4, 0.4, 0.4))
        p.draw_line((M, M - 3), (A4.width - M, M - 3), color=(0.75, 0.75, 0.75), width=0.6)
        num = str(self.pageno)
        self.text(p, ((A4.width - self.text_width(num, 8)) / 2, A4.height - M / 2), num, 8, False, (0.4, 0.4, 0.4))
        if divider:
            p.draw_line((A4.width / 2, M + 2), (A4.width / 2, A4.height - M - FOOTER_H + 6), color=(0.88, 0.88, 0.88), width=0.5)
        self.top = M + 6
        self.y = [self.top, self.top]
        self.col = 0

    def bottom(self):
        return A4.height - M - FOOTER_H

    def col_x(self, col):
        return M + col * (self.colw + GUTTER)

    def reserve(self, h, full=False):
        """h yüksekliğinde yer ayırır, (page, x, y, w) döner."""
        if full:
            y = max(self.y)
            if y + h > self.bottom():
                self.new_page()
                y = self.top
            self.y = [y + h, y + h]
            self.col = 0
            return self.page, M, y, A4.width - 2 * M
        for _ in range(3):
            if self.y[self.col] + h <= self.bottom():
                y = self.y[self.col]
                self.y[self.col] += h
                return self.page, self.col_x(self.col), y, self.colw
            if self.col == 0:
                self.col = 1
            else:
                self.new_page()
        # tek başına sayfaya sığmıyor: yine de yerleştir (ölçek küçülecek)
        y = self.y[self.col]
        self.y[self.col] = self.bottom()
        return self.page, self.col_x(self.col), y, self.colw

    def fit(self, s, size, width, bold=False):
        if self.text_width(s, size, bold) <= width:
            return s
        while s and self.text_width(s + "…", size, bold) > width:
            s = s[:-1]
        return s.rstrip() + "…"

    def section(self, title, color=(0.2, 0.2, 0.2), sub=""):
        # başlık sütun akışında yer alır; altında en az bir soruluk yer yoksa sonraki sütuna geç
        if self.y[self.col] + 26 + 150 > self.bottom():
            if self.col == 0:
                self.col = 1
            if self.y[self.col] + 26 + 150 > self.bottom():
                self.new_page()
        h = 34 if sub else 26
        page, x, y, w = self.reserve(h)
        page.draw_rect(pymupdf.Rect(x, y + 2, x + w, y + h - 6), color=None, fill=color, fill_opacity=0.1)
        page.draw_rect(pymupdf.Rect(x, y + 2, x + 3, y + h - 6), color=None, fill=color)
        self.text(page, (x + 9, y + 15.5), self.fit(title, 11, w - 14, True), 11, True, color)
        if sub:
            self.text(page, (x + 9, y + 25.5), self.fit(sub, 8, w - 14), 8, False, (0.3, 0.3, 0.3))

    # -- soru yerleştirme
    def question(self, number: int, q: dict, src: pymupdf.Document, show_source: bool):
        bbox = pymupdf.Rect(q["bbox"])
        full = bbox.width > self.colw * 1.35
        avail_w = (A4.width - 2 * M) if full else self.colw
        scale = min(1.0, avail_w / bbox.width)
        if bbox.width * scale < avail_w * 0.8 and not full:
            scale = min(1.15, avail_w / bbox.width)
        h = bbox.height * scale
        max_h = self.bottom() - self.top
        if h > max_h:
            scale *= max_h / h
            h = max_h
        extra = 10 if show_source else 0
        page, x, y, w = self.reserve(h + GAP + extra, full=full)
        target = pymupdf.Rect(x, y, x + bbox.width * scale, y + h)
        page.show_pdf_page(target, src, q["page"] - 1, clip=bbox)
        # orijinal numarayı kapat, yenisini yaz
        num = q.get("num")
        if num:
            nr = pymupdf.Rect(num)
            cover = pymupdf.Rect(x + (nr.x0 - bbox.x0 - 1) * scale, y + (nr.y0 - bbox.y0 - 1) * scale,
                                 x + (nr.x1 - bbox.x0 + 1) * scale, y + (nr.y1 - bbox.y0 + 1) * scale)
            page.draw_rect(cover, color=None, fill=(1, 1, 1))
            size = max(8, min(11, cover.height * 0.85))
            self.text(page, (cover.x0 + 1, cover.y1 - (cover.height - size) / 2 - 1.5), f"{number}.", size, True)
        else:
            self.text(page, (x - 2, y + 9), f"{number}.", 10, True)
        if show_source:
            label = source_label(q)
            self.text(page, (x, y + h + 7), label, 6.5, False, (0.55, 0.55, 0.55))

    def image(self, path: str, caption: str):
        pix = pymupdf.Pixmap(path)
        w0, h0 = pix.width, pix.height
        full = w0 / h0 > 2.4
        avail = (A4.width - 2 * M) if full else self.colw
        scale = avail / w0
        h = min(h0 * scale, self.bottom() - self.top - 20)
        wimg = w0 * (h / h0)
        page, x, y, w = self.reserve(h + 12 + GAP, full=full)
        self.text(page, (x, y + 8), caption, 7.5, True, (0.6, 0.2, 0.2))
        page.insert_image(pymupdf.Rect(x, y + 11, x + wimg, y + 11 + h), filename=path)
        page.draw_rect(pymupdf.Rect(x, y + 11, x + wimg, y + 11 + h), color=(0.8, 0.8, 0.8), width=0.5)

    def answer_key(self, rows: list[tuple[int, str, str]], title="Cevap Anahtarı"):
        self.new_page(divider=False)
        p = self.page
        self.text(p, (M, M + 18), title, 14, True)
        y = M + 40
        # kompakt tablo: 5 sütun
        cols = 5
        cw = (A4.width - 2 * M) / cols
        for i, (n, ans, _) in enumerate(rows):
            c, r = i % cols, i // cols
            self.text(p, (M + c * cw, y + r * 16), f"{n}.  {ans or '?'}", 11, bool(ans))
        y += ((len(rows) - 1) // cols + 1) * 16 + 24
        self.text(p, (M, y), "Kaynaklar", 10, True)
        y += 14
        for n, _, src in rows:
            if y > A4.height - M - 10:
                self.new_page(divider=False)
                p = self.page
                y = M + 20
            self.text(p, (M, y), f"{n}. {src}", 7.5, False, (0.3, 0.3, 0.3))
            y += 10.5

    def save(self, path: Path):
        self.doc.subset_fonts()
        self.doc.save(path, garbage=3, deflate=True)


def source_label(q: dict) -> str:
    b = q["book"]
    parts = [f"{b['exam']} {b['subject_name']} {b['kind_name']}", f"s.{q['page']} no {q['n']}"]
    if q.get("topic"):
        parts.append(q["topic"][:50])
    if q.get("level"):
        parts.append(q["level"])
    if q.get("osym"):
        parts.append(q["osym"])
    return " · ".join(parts)


def build(items: list[dict], title: str, student: str, out_name: str | None = None,
          wrong_images: list[dict] | None = None, show_source: bool = False, group_by_role: bool = True) -> Path:
    """items: [{"qid", "role"?, "group"?}] sıralı.  wrong_images: [{"path", "caption"}]"""
    date = datetime.now().strftime("%d.%m.%Y")
    w = Writer(title, f"{student} · {date}")
    docs: dict[str, pymupdf.Document] = {}

    if wrong_images:
        w.section("Hatırla: Denemede yapamadığın sorular", (0.6, 0.2, 0.2))
        for im in wrong_images:
            try:
                w.image(im["path"], im.get("caption", ""))
            except Exception:  # noqa: BLE001
                pass

    rows, number = [], 0
    last_head = None
    for it in items:
        q = qbank.get_question(it["qid"])
        if not q:
            continue
        role = it.get("role", "")
        title = ROLE_TITLES.get(role, "") if group_by_role else ""
        sub = it.get("group", "")
        head = (title, sub)
        if (title or sub) and head != last_head:
            w.section(title or sub, ROLE_COLORS.get(role, (0.2, 0.2, 0.2)), sub if title else "")
            last_head = head
        path = q["book"]["path"]
        if path not in docs:
            docs[path] = pymupdf.open(path)
        number += 1
        w.question(number, q, docs[path], show_source)
        rows.append((number, q.get("answer", ""), source_label(q)))

    w.answer_key(rows)
    safe = re.sub(r"[^\w\-çğıöşüÇĞİÖŞÜ ]+", "", out_name or title).strip().replace(" ", "_")[:60] or "calisma"
    out = config.OUTPUT_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M')}_{safe}.pdf"
    w.save(out)
    return out
