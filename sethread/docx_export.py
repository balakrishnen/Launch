"""Markdown (from docs.build) -> styled landscape Word document, via pandoc + python-docx."""
import os, subprocess, shutil

def export(md_path: str, out_path: str) -> str:
    if not shutil.which("pandoc"): raise RuntimeError("pandoc not found")
    raw = out_path + ".raw.docx"
    subprocess.run(["pandoc", md_path, "-o", raw, "--resource-path", os.path.dirname(md_path)], check=True)
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.section import WD_ORIENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    d = Document(raw)
    for s in d.sections:
        s.orientation = WD_ORIENT.LANDSCAPE; s.page_width, s.page_height = Inches(11), Inches(8.5)
        s.left_margin = s.right_margin = Inches(0.7); s.top_margin = s.bottom_margin = Inches(0.7)
    st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
    for name, size in (("Heading 1", 18), ("Heading 2", 14), ("Heading 3", 12), ("Title", 24), ("Subtitle", 13), ("Caption", 9)):
        try: h = d.styles[name]; h.font.name = "Calibri"; h.font.size = Pt(size)
        except KeyError: pass
    total = Inches(9.6)
    for t in d.tables:
        b = OxmlElement("w:tblBorders")
        for e in ("top", "left", "bottom", "right", "insideH", "insideV"):
            el = OxmlElement(f"w:{e}"); el.set(qn("w:val"), "single"); el.set(qn("w:sz"), "4"); el.set(qn("w:color"), "999999"); b.append(el)
        t._tbl.tblPr.append(b)
        for i, row in enumerate(t.rows):
            for c in row.cells:
                if i == 0:
                    tcPr = c._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), "E8EEF4"); tcPr.append(shd)
                for p in c.paragraphs:
                    p.paragraph_format.space_after = Pt(2); p.paragraph_format.space_before = Pt(2)
                    for r in p.runs:
                        r.font.size = Pt(9)
                        if i == 0: r.font.bold = True
        ncol = len(t.columns); lens = []
        for ci in range(ncol):
            texts = [r.cells[ci].text for r in t.rows]
            body = max([len(x) for x in texts[1:]] or [1]); lens.append(max(4, min(body, 110) * 0.6 + len(texts[0]) * 0.4))
        sm = sum(lens); widths = [max(int(total * l / sm), Inches(0.5)) for l in lens]
        sc = total / sum(widths); widths = [int(w * sc) for w in widths]
        t.autofit = False
        for gc, w in zip(t._tbl.tblGrid.findall(qn("w:gridCol")), widths): gc.set(qn("w:w"), str(int(w / 635)))
        for row in t.rows:
            for c, w in zip(row.cells, widths): c.width = w
        tblW = t._tbl.tblPr.find(qn("w:tblW"))
        if tblW is not None: tblW.set(qn("w:w"), str(int(total / 635))); tblW.set(qn("w:type"), "dxa")
    for p in d.paragraphs:
        if p.style.name == "Heading 1" and p.runs: p.paragraph_format.page_break_before = True
    for sh in d.inline_shapes:
        r = sh.height / sh.width; sh.width = Inches(9.3); sh.height = int(Inches(9.3) * r)
    d.save(out_path); os.remove(raw); return out_path
