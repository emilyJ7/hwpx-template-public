"""docx → Markdown (제목, 글머리표, 표, 하이퍼링크 보존)"""
import sys, re, os, zipfile
import docx
from docx.oxml.ns import qn

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
CTX = {"img_dir": None, "imgs": 0, "part": None}


def para_text(p, rels):
    out = []
    for child in p._p:
        if child.tag == W + "r":
            for el in child.iter():
                if el.tag == W + "t":
                    out.append(el.text or "")
                elif el.tag == W + "footnoteReference":
                    out.append(f"[^{el.get(W + 'id')}]")
                elif el.tag == A + "blip" and CTX["part"] is not None:
                    img = CTX["part"].related_parts.get(el.get(R + "embed"))
                    if img is not None:
                        os.makedirs(CTX["img_dir"], exist_ok=True)
                        CTX["imgs"] += 1
                        ext = os.path.splitext(img.partname)[1] or ".png"
                        fp = os.path.join(CTX["img_dir"], f"image{CTX['imgs']}{ext}")
                        open(fp, "wb").write(img.blob)
                        out.append(chr(10) * 2 + "![](" + fp.replace(os.sep, "/") + ")" + chr(10) * 2)
        elif child.tag == W + "hyperlink":
            text = "".join(t.text or "" for t in child.iter(W + "t"))
            rid = child.get(R + "id")
            url = rels.get(rid)
            out.append(f"[{text}]({url})" if url else text)
    return "".join(out).strip()


def footnotes(path):
    """word/footnotes.xml → {id: 글}"""
    from lxml import etree
    z = zipfile.ZipFile(path)
    if "word/footnotes.xml" not in z.namelist():
        return {}
    root = etree.fromstring(z.read("word/footnotes.xml"))
    res = {}
    for fn in root.findall(W + "footnote"):
        i = fn.get(W + "id")
        if fn.get(W + "type") in ("separator", "continuationSeparator"):
            continue
        res[i] = "".join(t.text or "" for t in fn.iter(W + "t")).strip()
    return res


def is_bold(p):
    runs = [r for r in p.runs if r.text.strip()]
    return bool(runs) and all(r.bold for r in runs)


def convert(path, out):
    d = docx.Document(path)
    rels = {r.rId: r.target_ref for r in d.part.rels.values() if r.is_external}
    CTX.update(part=d.part, img_dir=re.sub(r"\.md$", "", out) + "_files", imgs=0)
    lines, first = [], True
    body = d.element.body
    for el in body.iterchildren():
        if el.tag == W + "p":
            p = docx.text.paragraph.Paragraph(el, d)
            t = para_text(p, rels)
            if not t:
                continue
            style = (p.style.name or "").lower()
            if first:
                lines.append(f"# {t}\n"); first = False; continue
            if style.startswith("heading 1"):
                lines.append(f"\n## {t}\n")
            elif style.startswith("heading 2"):
                lines.append(f"\n### {t}\n")
            elif el.find(f"{W}pPr/{W}numPr") is not None:
                lvl = el.find(f"{W}pPr/{W}numPr/{W}ilvl")
                ind = "  " * int(lvl.get(W + "val")) if lvl is not None else ""
                lines.append(f"{ind}- {t}")
            elif p.alignment is not None and int(p.alignment) == 1 and len(lines) < 4:
                lines.append(f"*{t}*\n")
            else:
                lines.append(t + "\n")
        elif el.tag == W + "tbl":
            tbl = docx.table.Table(el, d)
            rows, prev = [], None
            for row in tbl.rows:
                cells, tcs = [], []
                for ci, c in enumerate(row.cells):
                    tcs.append(c._tc)
                    if ci > 0 and c._tc is tcs[ci - 1]:
                        cells.append("<"); continue          # 가로 병합(왼쪽 칸에 합침)
                    if prev is not None and ci < len(prev) and c._tc is prev[ci]:
                        cells.append("^"); continue          # 세로 병합(위 칸에 합침)
                    txt = "<br>".join(x for x in (para_text(p, rels) for p in c.paragraphs) if x)
                    cells.append(txt.replace("|", "\\|") or " ")
                rows.append(cells); prev = tcs
            if not rows:
                continue
            n = max(len(r) for r in rows)
            rows = [r + [""] * (n - len(r)) for r in rows]
            grid = [int(g.get(W + "w")) for g in el.iter(W + "gridCol") if g.get(W + "w")]
            lines.append("")
            if len(grid) == n and sum(grid):
                lines.append("<!-- widths: " + ",".join(str(round(100 * g / sum(grid))) for g in grid) + " -->")
            lines.append("| " + " | ".join(rows[0]) + " |")
            lines.append("|" + "---|" * n)
            for r in rows[1:]:
                lines.append("| " + " | ".join(r) + " |")
            lines.append("")
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    open(out, "w", encoding="utf-8").write(text)
    print("written", out, len(text))


if __name__ == "__main__":
    for src in sys.argv[1:]:
        convert(src, re.sub(r"\.docx$", ".md", src))
