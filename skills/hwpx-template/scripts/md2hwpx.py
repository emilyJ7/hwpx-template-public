"""Markdown → hwpx. 양식 hwpx의 구역 설정·제목 상자·문단/글자/표 서식을 그대로 쓴다.

사용: python md2hwpx.py 양식.hwpx 입력.md 출력.hwpx [--style style_map.json] [--verify] [--pdf 출력.pdf] [--png 폴더]
  --verify  한글로 실제 열어 확인(verify_hwp.py). --pdf/--png 를 주면 PDF와 쪽 이미지도 만든다.

Markdown 규칙
  ---                      (맨 앞 머리 정보, 선택)
  header: 머리말 글         양식 머리말이 있으면 글자만 교체, 없으면 새로 만듦. none = 삭제
  footer: - {page} -       {page} = 쪽 번호
  header_align: right      left / center / right (선택)
  ---
  # 제목                   → 제목(제목 상자 안 글자 교체)
  (날짜·부제) 또는 *부제*    → 제목 바로 다음 줄이면 날짜 줄
  ## 대제목 / ### 소제목     → □ 대제목 / 번호 소제목
  - 글, - **머리말** 글      → ○ 글머리 (2칸 들여쓰기 → -, 4칸 → ·)
  ※ 주석                   → ※ 주석
  글[^1] … [^1]: 각주 내용   → 각주
  ![캡션](그림.png){width=60%} → 그림(가운데, 캡션 있으면 아래 줄)
  <!-- widths: 15,25,60 --> → 바로 다음 표의 열 너비(%)
  | 표 |  셀에 < = 왼쪽 칸과 병합, ^ = 위 칸과 병합, <br> = 셀 안 줄바꿈
"""
import sys, os, re, json, copy, zipfile, struct, zlib, argparse, random, subprocess
from xml.sax.saxutils import escape
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze_template import analyze, HP

ap = argparse.ArgumentParser()
ap.add_argument("template"); ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("style_pos", nargs="?")
ap.add_argument("--style"); ap.add_argument("--verify", action="store_true")
ap.add_argument("--pdf"); ap.add_argument("--png")
ap.add_argument("--toc-pages", help="목차 쪽 번호 json(자동 계산 2단계에서 씀)")
ap.add_argument("--no-toc-pages", action="store_true", help="목차 쪽 번호 자동 계산 안 함")
A = ap.parse_args()
TPL, SRC, OUT = A.template, A.src, A.out
SM = A.style or A.style_pos
S = json.load(open(SM, encoding="utf-8")) if SM else analyze(TPL)
R = S["roles"]
SRC_DIR = os.path.dirname(os.path.abspath(SRC))
uid = lambda: str(random.randint(1_000_000_000, 2_000_000_000))


# ---------------------------------------------------------------- 글자 처리
# 백슬래시로 감싼 문자(\*, \[ 등)는 서식으로 해석하지 않도록 사용자 영역 문자로 바꿔 두었다가 출력 때 되돌린다
import html
_ESC = "*[]()!#<>_-|^`\\"
PH = {c: chr(0xE000 + i) for i, c in enumerate(_ESC)}
RPH = {v: k for k, v in PH.items()}
protect = lambda s: re.sub(r"\\([*\[\]()!#<>_\-|^`\\])", lambda m: PH[m.group(1)], s)
unph = lambda s: html.unescape("".join(RPH.get(ch, ch) for ch in s))


def strip_md(t):
    t = re.sub(r"\[([^\]^][^\]]*)\]\(([^)]+)\)", lambda m: m.group(1) if m.group(1) == m.group(2) else f"{m.group(1)}({m.group(2)})", t)
    t = re.sub(r"(?<![\*\w])\*(?!\*)(.+?)(?<!\*)\*(?![\*\w])", r"\1", t)
    return t.replace("`", "")


# ---------------------------------------------------------------- 굵게: 양식 글자 서식의 굵은 판(없으면 새로 만듦)
HH = "{http://www.hancom.co.kr/hwpml/2011/head}"
HEAD = etree.fromstring(zipfile.ZipFile(TPL).read("Contents/header.xml"))
CHARS = {c.get("id"): c for c in HEAD.iter(HH + "charPr")}
_canon = lambda c: re.sub(r'\sid="\d+"', "", etree.tostring(c, encoding="unicode"))
_bold_cache, NEW_CHARS = {}, []


def bold_of(cid):
    cid = str(cid)
    if cid in _bold_cache:
        return _bold_cache[cid]
    base = CHARS.get(cid)
    if base is None or base.find(HH + "bold") is not None:
        _bold_cache[cid] = cid
        return cid
    want = copy.deepcopy(base)
    off = want.find(HH + "offset")
    b = etree.Element(HH + "bold")
    if off is not None:
        off.addnext(b)
    else:
        want.insert(0, b)
    key = _canon(want)
    hit = next((i for i, c in CHARS.items() if _canon(c) == key), None)
    if hit is None:
        hit = str(max(int(i) for i in CHARS) + 1)
        want.set("id", hit)
        CHARS[hit] = want
        NEW_CHARS.append(want)
    _bold_cache[cid] = hit
    return hit


FOOTDEFS, FN = {}, [0]


def footnote_xml(key):
    FN[0] += 1
    n = FN[0]
    st = S["existing"].get("footnoteStyle") or S["styles"].get("Footnote") or {"style": "0", "paraPr": "0", "charPr": "0"}
    fmt = " ".join(f'{k}="{escape(v)}"' for k, v in S["footNoteFormat"].items())
    body = escape(unph(strip_md(FOOTDEFS.get(key, f"(각주 {key} 내용 없음)")).replace("**", "")))
    return (f'<hp:ctrl><hp:footNote number="{n}" suffixChar="41" instId="{uid()}">'
            f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
            f'<hp:p id="0" paraPrIDRef="{st["paraPr"]}" styleIDRef="{st["style"]}" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{st["charPr"]}"><hp:ctrl><hp:autoNum num="{n}" numType="FOOTNOTE"><hp:autoNumFormat {fmt}/></hp:autoNum></hp:ctrl>'
            f'<hp:t> {body}</hp:t></hp:run></hp:p></hp:subList></hp:footNote></hp:ctrl>')


def run_xml(c, text):
    """한 런. **굵게** 는 굵은 글자 서식 런으로, [^키] 는 각주 개체로 바꾼다."""
    if "**" in text:
        segs = re.split(r"\*\*(.+?)\*\*", text)
        return "".join(run_xml(bold_of(c) if i % 2 else c, seg) for i, seg in enumerate(segs) if seg)
    parts = re.split(r"\[\^([^\]]+)\]", text)
    inner = []
    for i, seg in enumerate(parts):
        if i % 2:
            inner.append(footnote_xml(seg))
        elif seg:
            inner.append(f"<hp:t>{escape(unph(seg))}</hp:t>")
    if not inner:
        inner.append("<hp:t></hp:t>")
    return f'<hp:run charPrIDRef="{c}">{"".join(inner)}</hp:run>'


def para(pid, runs, style="0"):
    return (f'<hp:p id="2147483648" paraPrIDRef="{pid}" styleIDRef="{style}" pageBreak="0" columnBreak="0" merged="0">'
            + "".join(run_xml(c, t) for c, t in runs) + "</hp:p>")


def spacer():
    sp = R.get("spacer") or R.get("body") or {"paraPr": "0", "textChar": "0"}
    return para(sp["paraPr"], [(sp.get("textChar", "0"), "")])


def role(name, *fallbacks):
    for n in (name,) + fallbacks:
        if n in R:
            return R[n]
    return {"paraPr": "0", "textChar": "0", "prefix": ""}


def h1(text, variant="h1"):
    r = role(variant, "h1", "h2", "body")
    text = re.sub(r"^[□■◆◇▣❏❑◼▶]\s*", "", text)
    if "marker" in r:
        return para(r["paraPr"], [(r["markChar"], r["marker"]), (r["textChar"], r.get("textPrefix", " ") + text)])
    return para(r["paraPr"], [(r["textChar"], text)])


def bullet(level, text):
    name = {1: "bullet1", 2: "bullet2", 3: "bullet3"}[level]
    r = role(name, "bullet2" if level == 3 else "bullet1", "body")
    prefix = r.get("prefix", "")
    if level > 1 and name not in R:  # 하위 글머리 서식이 없으면 ○ 서식에 기호만 바꿈
        prefix = "     - " if level == 2 else "        · "
    # 머리말: (머리말) 글 / **머리말:** 글 / **머리말**: 글  — 그냥 **굵게**로 시작하면 강조로 처리
    m = (re.match(r"^\*\*([^*]+?)[:：]\*\*\s*(.*)$", text) or re.match(r"^\*\*([^*]+?)\*\*\s*[:：]\s*(.*)$", text)
         or re.match(r"^\(([^)]+)\)\s*(.*)$", text))
    if m and "leadChar" in r:
        lead = m.group(1).strip().rstrip(":：").strip()
        return para(r["paraPr"], [(r.get("markChar", r["textChar"]), prefix), (r["leadChar"], f"({lead}) "), (r["textChar"], strip_md(m.group(2)))])
    return para(r["paraPr"], [(r["textChar"], prefix + strip_md(text))])


def note(text):
    r = role("note", "body")
    text = strip_md(re.sub(r"^※\s*", "", text))
    pre = r.get("prefix", "")
    return para(r["paraPr"], [(r["textChar"], (pre.rstrip() + " " if pre.strip() else (pre + "※ ")) + text)])


def body(text):
    if "body" in R:
        return para(R["body"]["paraPr"], [(R["body"]["textChar"], strip_md(text))])
    r = role("bullet1")
    return para(r["paraPr"], [(r["textChar"], r.get("prefix", "") + strip_md(text))])


# ---------------------------------------------------------------- 강조 박스(1칸 표)·붙임 상자
def _clean(el):
    for l in list(el.iter(HP + "linesegarray")):
        l.getparent().remove(l)
    for t in el.iter(HP + "tbl"):
        _tid[0] += 1
        t.set("id", str(_tid[0]))
    return el


def box(lines_):
    """> 줄들 → 양식의 1칸 강조 박스. 박스가 없는 양식은 ※ 주석으로."""
    if "box" not in S:
        return [note(x) for x in lines_]
    el = _clean(etree.fromstring(S["box"]))
    sub = el.find(".//" + HP + "subList")
    model = sub.find(HP + "p")
    runs = [(r.get("charPrIDRef"), "".join(t.text or "" for t in r.iter(HP + "t"))) for r in model.findall(HP + "run")]
    base = max(runs, key=lambda x: len(x[1]))[0] if runs else "0"
    lead = runs[0][0] if runs and runs[0][0] != base else base
    for p in sub.findall(HP + "p"):
        sub.remove(p)
    for ln in lines_:
        m = re.match(r"^(※\s*\([^)]*\)|\([^)]*\))(.*)$", ln)
        rs = [(lead, m.group(1)), (base, m.group(2))] if m else [(base, ln)]
        sub.append(etree.fromstring(para(model.get("paraPrIDRef"), [(c, strip_md(t)) for c, t in rs])
                                    .replace("<hp:p ", f'<hp:p xmlns:hp="{HP[1:-1]}" ', 1)))
    return [etree.tostring(el, encoding="unicode")]


def attach(label, title):
    """붙임 제목 → 새 쪽 + 양식의 붙임 상자(라벨 칸 + 제목 칸)."""
    if "attach" not in S:
        return [h1(f"{label} {title}").replace('pageBreak="0"', 'pageBreak="1"', 1)]
    el = _clean(etree.fromstring(S["attach"]))
    el.set("pageBreak", "1")
    tcs = el.findall(".//" + HP + "tc")
    def put(tc, text):
        ts = list(tc.iter(HP + "t"))
        if ts:
            ts[0].text = text
            for t in ts[1:]:
                t.text = ""
        else:
            r = tc.find(".//" + HP + "run")
            etree.SubElement(r, HP + "t").text = text
    put(tcs[0], unph(label))
    put(tcs[-1], " " + unph(strip_md(title)))
    return [etree.tostring(el, encoding="unicode")]


# ---------------------------------------------------------------- 표(병합·열 너비)
_tid = [1300000000]


def col_widths(rows, W, pct=None):
    ncol = len(rows[0])
    if pct and len(pct) == ncol:
        ws = [int(W * p / sum(pct)) for p in pct]
    else:
        wt = []
        for c in range(ncol):
            vals = [len(strip_md(r[c])) for r in rows[1:] if r[c] not in ("<", "^")] or [0]
            longest_line = [max((len(x) for x in re.split(r"<br\s*/?>", r[c])), default=0) for r in rows[1:] if r[c] not in ("<", "^")] or [0]
            hl = len(rows[0][c]) if rows[0][c] not in ("<", "^") else 2
            avg = sum(vals) / len(vals)
            w = max(hl * 1.1, 0.5 * avg + 0.5 * min(max(longest_line), 30), 2)
            wt.append(w ** 0.75)
        tot = sum(wt)
        share = [max(0.07, x / tot) for x in wt]
        ws = [int(W * s / sum(share)) for s in share]
    ws[-1] += W - sum(ws)
    return ws


def table(rows, pct=None):
    T = S.get("table")
    if not T:
        return [body(" | ".join(r)) for r in rows]
    _tid[0] += 1
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    nrow = len(rows)
    W = T["width"]
    widths = col_widths(rows, W, pct)
    lineh = lambda txt, w: max(1, len(txt) * 600 // max(w - 1000, 1000) + 1)
    trs = []
    for ri, row in enumerate(rows):
        st = T["header"] if ri == 0 else T["body"]
        tcs = []
        for ci, txt in enumerate(row):
            if txt in ("<", "^"):
                continue  # 병합으로 가려지는 칸
            cs_ = 1
            while ci + cs_ < ncol and row[ci + cs_] == "<":
                cs_ += 1
            rs_ = 1
            while ri + rs_ < nrow and rows[ri + rs_][ci] == "^":
                rs_ += 1
            last = ci + cs_ - 1 == ncol - 1
            cs = st["first"] if ci == 0 else (st["last"] if last else st["middle"])
            w = sum(widths[ci:ci + cs_])
            lines = [strip_md(x).strip() for x in re.split(r"<br\s*/?>", txt)] or [""]
            ps = "".join(para(cs["paraPr"], [(cs["charPr"], ln)]) for ln in lines)
            h = 1800 * max(1, sum(lineh(ln, w) for ln in lines))
            mg = " ".join(f'{k}="{v}"' for k, v in cs["margin"].items())
            tcs.append(
                f'<hp:tc name="" header="{1 if ri == 0 else 0}" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="{cs["borderFill"]}">'
                f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="{cs.get("vertAlign", "CENTER")}" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">{ps}</hp:subList>'
                f'<hp:cellAddr colAddr="{ci}" rowAddr="{ri}"/><hp:cellSpan colSpan="{cs_}" rowSpan="{rs_}"/>'
                f'<hp:cellSz width="{w}" height="{h}"/><hp:cellMargin {mg}/></hp:tc>')
        trs.append("<hp:tr>" + "".join(tcs) + "</hp:tr>")
    a = dict(T["attrs"]); a.update(textWrap="TOP_AND_BOTTOM", noAdjust="0")
    attrs = " ".join(f'{k}="{v}"' for k, v in a.items())
    inm = " ".join(f'{k}="{v}"' for k, v in T["inMargin"].items()) or 'left="510" right="510" top="141" bottom="141"'
    tbl = (f'<hp:tbl id="{_tid[0]}" zOrder="{_tid[0] % 1000}" rowCnt="{nrow}" colCnt="{ncol}" {attrs}>'
           f'<hp:sz width="{W}" widthRelTo="ABSOLUTE" height="{2400 * nrow}" heightRelTo="ABSOLUTE" protect="0"/>'
           f'<hp:pos treatAsChar="0" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
           f'<hp:outMargin left="0" right="0" top="0" bottom="0"/><hp:inMargin {inm}/>' + "".join(trs) + "</hp:tbl>")
    an = R.get("table_anchor") or {"paraPr": "0", "charPr": "0"}
    return [f'<hp:p id="2147483648" paraPrIDRef="{an["paraPr"]}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="{an["charPr"]}">{tbl}<hp:t/></hp:run></hp:p>']


# ---------------------------------------------------------------- 그림
IMAGES = []  # (id, 압축 안 경로, 원본 경로, media-type)
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".bmp": "image/bmp"}


def img_size(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        b = open(path, "rb").read(64 * 1024)
        if b[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", b[16:24])
        i = 2
        while i < len(b) - 9:  # JPEG SOF
            if b[i] == 0xFF and b[i + 1] in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", b[i + 5:i + 9]); return w, h
            i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0] if b[i] == 0xFF else 1
        return 800, 600


def picture(alt, path, width_pct=None):
    p = path if os.path.isabs(path) else os.path.join(SRC_DIR, path)
    if not os.path.exists(p):
        return [note(f"※ 그림 파일 없음: {path}")]
    ext = os.path.splitext(p)[1].lower()
    used = set(S["existing"].get("binData", [])) | {i[0] for i in IMAGES}
    k = 1
    while f"image{k}" in used:
        k += 1
    iid = f"image{k}"
    IMAGES.append((iid, f"BinData/{iid}{ext}", p, MIME.get(ext, "image/png")))
    pw, ph = img_size(p)
    tw = S.get("textWidth") or (S.get("table") or {}).get("width") or 48000
    w = min(int(pw * 75), tw)  # 96dpi 기준 1px = 75 HWPUNIT
    if width_pct:
        w = int(tw * width_pct / 100)
    h = int(w * ph / max(pw, 1))
    pid = S["existing"].get("pictureParaPr") or S["align"].get("CENTER", "0")
    ch = (R.get("body") or role("bullet1"))["textChar"]
    pic = (f'<hp:pic id="{uid()}" zOrder="{len(IMAGES)}" numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" groupLevel="0" instid="{uid()}" reverse="0">'
           f'<hp:offset x="0" y="0"/><hp:orgSz width="{w}" height="{h}"/><hp:curSz width="0" height="0"/><hp:flip horizontal="0" vertical="0"/>'
           f'<hp:rotationInfo angle="0" centerX="{w // 2}" centerY="{h // 2}" rotateimage="1"/>'
           f'<hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/><hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/><hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>'
           f'<hc:img binaryItemIDRef="{iid}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
           f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{w}" y="0"/><hc:pt2 x="{w}" y="{h}"/><hc:pt3 x="0" y="{h}"/></hp:imgRect>'
           f'<hp:imgClip left="0" right="{pw * 75}" top="0" bottom="{ph * 75}"/><hp:inMargin left="0" right="0" top="0" bottom="0"/><hp:imgDim dimwidth="{pw * 75}" dimheight="{ph * 75}"/><hp:effects/>'
           f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>'
           f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
           f'<hp:outMargin left="0" right="0" top="0" bottom="0"/><hp:shapeComment>{escape(unph(alt) or os.path.basename(p))}</hp:shapeComment></hp:pic>')
    out = [f'<hp:p id="2147483648" paraPrIDRef="{pid}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="{ch}">{pic}<hp:t/></hp:run></hp:p>']
    if alt:
        cc = (R.get("note") or R.get("body") or role("bullet1"))["textChar"]
        out.append(para(S["align"].get("CENTER", pid), [(cc, strip_md(alt))]))
    return out


# ---------------------------------------------------------------- 머리말·꼬리말
def hf_runs(charpr, text):
    """{page} → 쪽 번호 자동 번호"""
    out = []
    for i, seg in enumerate(re.split(r"(\{page\})", text)):
        if seg == "{page}":
            out.append(f'<hp:run charPrIDRef="{charpr}"><hp:ctrl><hp:autoNum num="1" numType="PAGE"><hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar="" supscript="0"/></hp:autoNum></hp:ctrl></hp:run>')
        elif seg:
            out.append(f'<hp:run charPrIDRef="{charpr}"><hp:t>{escape(unph(seg))}</hp:t></hp:run>')
    return "".join(out) or f'<hp:run charPrIDRef="{charpr}"><hp:t></hp:t></hp:run>'


def apply_header_footer(first, meta, nsdecl):
    # 꼬리말·머리말에 {page}를 쓰면 양식의 쪽 번호(pageNum)와 겹치므로 양식 것을 뺀다
    if any("{page}" in meta.get(k, "") for k in ("header", "footer")):
        for pn in first.findall(".//" + HP + "pageNum"):
            ctrl = pn.getparent()
            (ctrl.getparent().remove(ctrl) if ctrl.tag == HP + "ctrl" and len(ctrl) == 1 else ctrl.remove(pn))
    if meta.get("page_number", "").lower() == "none":
        for pn in first.findall(".//" + HP + "pageNum"):
            ctrl = pn.getparent()
            (ctrl.getparent().remove(ctrl) if ctrl.tag == HP + "ctrl" and len(ctrl) == 1 else ctrl.remove(pn))
    for kind in ("header", "footer"):
        if kind not in meta:
            continue
        val = meta[kind]
        el = first.find(".//" + HP + kind)
        if el is not None and meta.get(kind + "_reset", "").lower() in ("true", "yes", "1"):
            ctrl = el.getparent(); ctrl.getparent().remove(ctrl); el = None  # 양식 머리말·꼬리말(로고 등)을 지우고 새로 만듦
        if val.lower() == "none":
            if el is not None:
                ctrl = el.getparent(); ctrl.getparent().remove(ctrl)
            continue
        al = meta.get(kind + "_align")
        al_id = S["align"].get({"left": "LEFT", "center": "CENTER", "right": "RIGHT"}.get(al or "", ""), None)
        if el is not None:
            sub = el.find(HP + "subList")
            if sub.find(".//" + HP + "tbl") is not None or sub.find(".//" + HP + "pic") is not None:
                ts = [t for t in sub.iter(HP + "t") if (t.text or "").strip()]  # 복잡한 머리말: 가장 긴 글만 교체
                if ts:
                    max(ts, key=lambda t: len(t.text)).text = val.replace("{page}", "")
                continue
            ps = sub.findall(HP + "p")
            p0 = ps[0]
            r0 = p0.find(HP + "run")
            cp = r0.get("charPrIDRef") if r0 is not None else "0"
            for p in ps[1:]:
                sub.remove(p)
            for ch in list(p0):
                p0.remove(ch)
            if al_id:
                p0.set("paraPrIDRef", al_id)
            for r in etree.fromstring(f"<w {nsdecl}>{hf_runs(cp, val)}</w>"):
                p0.append(r)
        else:
            st = S["styles"].get("Header") or S["styles"].get("Normal") or {"style": "0", "paraPr": "0", "charPr": "0"}
            pid = al_id or (S["align"].get("CENTER") if kind == "footer" else st["paraPr"]) or st["paraPr"]
            tw = S.get("textWidth") or 42520
            x = (f'<hp:run charPrIDRef="0"><hp:ctrl><hp:{kind} id="{uid()}" applyPageType="BOTH">'
                 f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="{"TOP" if kind == "header" else "BOTTOM"}" linkListIDRef="0" linkListNextIDRef="0" textWidth="{tw}" textHeight="4252" hasTextRef="0" hasNumRef="0">'
                 f'<hp:p id="0" paraPrIDRef="{pid}" styleIDRef="{st["style"]}" pageBreak="0" columnBreak="0" merged="0">{hf_runs(st["charPr"], val)}</hp:p>'
                 f'</hp:subList></hp:{kind}></hp:ctrl></hp:run>')
            run = etree.fromstring(f"<w {nsdecl}>{x}</w>")[0]
            runs = first.findall(HP + "run")
            pos = next((i for i, r in enumerate(runs) if r.find(".//" + HP + "secPr") is not None), 0)
            runs[pos].addnext(run)


# ---------------------------------------------------------------- md 읽기
text_all = open(SRC, encoding="utf-8-sig").read()
meta = {}
META_LIST = {}  # replace: / clear_table: / table_row: 처럼 여러 번 쓰는 머리 정보
m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text_all, re.S)
if m:
    for ln in m.group(1).splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1); meta[k.strip().lower()] = v.strip()
            META_LIST.setdefault(k.strip().lower(), []).append(v.strip())
    text_all = text_all[m.end():]
text_all = protect(text_all)
lines = []
for ln in text_all.splitlines():
    fm = re.match(r"^\[\^([^\]]+)\]:\s*(.*)$", ln.strip())
    if fm:
        FOOTDEFS[fm.group(1)] = fm.group(2)
    else:
        lines.append(ln)

title, dateline, blocks, pending_w = None, None, [], None
i = 0
while i < len(lines):
    ln = lines[i]; s = ln.strip()
    if not s or re.match(r"^-{3,}$", s):
        i += 1; continue
    wm = re.match(r"^<!--\s*widths?\s*:\s*([\d.,\s]+)-->$", s)
    if wm:
        pending_w = [float(x) for x in wm.group(1).split(",") if x.strip()]; i += 1; continue
    if re.match(r"^<!--\s*page\s*break\s*-->$", s, re.I) or s in ("\\newpage", "\\pagebreak"):
        blocks.append(("pagebreak",)); i += 1; continue
    if s.startswith("<!--"):
        i += 1; continue
    # 붙임: 「# 붙임 제목」 또는 「#/##/### 붙임N 제목」 (소제목 「### 붙임·쪽」 같은 글은 제외)
    am = re.match(r"^#\s*(붙\s*임\s*\d*)\s*[.:]?\s+(.*)$", s) or re.match(r"^#{1,3}\s*(붙\s*임\s*\d+)\s*[.:]?\s*(.*)$", s)
    if am and title is not None:
        blocks.append(("attach", re.sub(r"\s+", "", am.group(1)), am.group(2))); i += 1; continue
    if s.startswith("```"):  # 코드 블록 → 강조 박스(없으면 본문)
        i += 1; code = []
        while i < len(lines) and not lines[i].strip().startswith("```"):
            if lines[i].strip():
                code.append(lines[i].rstrip())
            i += 1
        i += 1
        blocks.append(("box", code)); continue
    if s.startswith(">"):
        bl = []
        while i < len(lines) and lines[i].strip().startswith(">"):
            t = lines[i].strip().lstrip(">").strip()
            if t:
                bl.append(t)
            i += 1
        blocks.append(("box", bl)); continue
    if s.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            raw = lines[i].strip().strip("|").replace("\\|", "\x00")
            cells = [c.strip().replace("\x00", "|") for c in raw.split("|")]
            if not all(re.match(r"^:?-{2,}:?$", c) for c in cells if c):
                rows.append(cells)
            i += 1
        blocks.append(("table", rows, pending_w)); pending_w = None; continue
    pm = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*(\{\s*width\s*=\s*(\d+)\s*%\s*\})?$", s)
    if pm:
        blocks.append(("pic", pm.group(1), pm.group(2), int(pm.group(4)) if pm.group(4) else None)); i += 1; continue
    if s.startswith("# ") and title is None:
        title = strip_md(s[2:]); i += 1
        subs = []
        while i < len(lines):
            t = lines[i].strip()
            if not t:
                i += 1; continue
            if t.startswith("(") or re.match(r"^[*_][^*_].*[*_]$", t):
                subs.append(strip_md(t).strip("_*() ")); i += 1
            else:
                break
        if subs:
            dateline = "(" + " / ".join(subs) + ")"
        continue
    if s.startswith("## ") or (s.startswith("# ") and title):
        blocks.append(("h1", strip_md(s.lstrip("#").strip())))
    elif s.startswith("####"):
        blocks.append(("h3", strip_md(s.lstrip("#").strip())))
    elif s.startswith("###"):
        blocks.append(("h2", strip_md(s.lstrip("#").strip())))
    elif re.match(r"^\s*([-*+]|\d+\.)\s+", ln):
        ind = len(ln) - len(ln.lstrip())
        txt = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", ln)
        blocks.append(("bullet", 1 if ind < 2 else (2 if ind < 4 else 3), txt))
    elif s.startswith("※"):
        blocks.append(("note", s))
    else:
        blocks.append(("body", s))
    i += 1

# ---------------------------------------------------------------- 조립
sp = S.get("spacing", {})
out = []
SPACER = spacer()
pb = False
HEADS = []  # 목차용 (단계, 제목)
for b in blocks:
    k = b[0]
    n0 = len(out)
    if k == "pagebreak":
        pb = True
        continue
    if k == "attach":
        out += attach(b[1], b[2])
        if sp.get("table", {}).get("after"):
            out.append(SPACER)
    elif k == "box":
        out += box(b[1])
    elif k == "h1":
        if sp.get("h1", {}).get("before") and out and out[-1] != SPACER:
            out.append(SPACER)
        out.append(h1(b[1]))
        HEADS.append(("1", b[1]))
        if sp.get("h1", {}).get("after"):
            out.append(SPACER)
    elif k == "h2":
        if sp.get("h2", {}).get("before") and out and out[-1] != SPACER:
            out.append(SPACER)
        if "h2" in R:
            out.append(para(R["h2"]["paraPr"], [(R["h2"]["textChar"], R["h2"].get("indent", "") + b[1])]))
        else:  # 양식에 번호 소제목이 없으면 □ 소제목 모양(h1b, 없으면 대제목)으로
            out.append(h1(b[1], "h1b"))
        HEADS.append(("2", b[1]))
    elif k == "h3":
        r3 = R.get("h3") or R.get("h2")
        if r3:
            out.append(para(r3["paraPr"], [(r3["textChar"], r3.get("indent", "") + b[1])]))
        else:
            out.append(h1(b[1], "h1b"))
        HEADS.append(("3", b[1]))
    elif k == "bullet":
        out.append(bullet(b[1], b[2]))
    elif k == "note":
        out.append(note(b[1]))
    elif k == "body":
        out.append(body(b[1]))
    elif k == "table":
        out += table(b[1], b[2])
        if sp.get("table", {}).get("after"):
            out.append(SPACER)
    elif k == "pic":
        out += picture(b[1], b[2], b[3])
    if pb and len(out) > n0:
        if out[n0] == SPACER and len(out) > n0 + 1:
            del out[n0]  # 새 쪽 맨 위 빈 줄은 뺀다
        out[n0] = out[n0].replace('pageBreak="0"', 'pageBreak="1"', 1)
        pb = False

# ---------------------------------------------------------------- 법령 조문 모드
LAW = S.get("law")
law_subs = []
if LAW:
    JO = re.compile(r"^(제\d+조(?:의\d+)?\([^)]*\))\s*(.*)$")
    TAG = re.compile(r"\s*(<(?:개정|신설|삭제|전문개정|본조신설)[^>]*>)\s*$")
    def tagged(role_, lead_runs, text):
        m = TAG.search(text)
        body_, tg = (text[:m.start()], m.group(1)) if m else (text, None)
        runs = lead_runs + [(role_["textChar"], body_)]
        if tg and LAW["jo"].get("tagChar"):
            runs.append((LAW["jo"]["tagChar"], " " + tg))
        return runs
    lsp = LAW.get("spacer") or R.get("spacer") or {"paraPr": "0", "textChar": "0"}
    out, title, in_buchik = [], None, False
    FN[0] = 0; IMAGES.clear()  # 일반 조립 결과는 버리고 조문으로 다시 조립
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("<!--"):
            continue
        if title is None and s.startswith("# "):
            title = strip_md(s[2:]); continue
        s = re.sub(r"^#+\s*", "", s)
        m = JO.match(s)
        if m:
            in_buchik = False
            out.append(para(LAW["jo"]["paraPr"], tagged(LAW["jo"], [(LAW["jo"]["leadChar"], m.group(1))], " " + strip_md(m.group(2)))))
            continue
        bm = re.match(r"^부\s*칙\s*(.*)$", s)
        if bm and "buchik" in LAW:
            in_buchik = True
            out.append(para(lsp["paraPr"], [(lsp["textChar"], "")]))
            b = LAW["buchik"]
            out.append(para(b["paraPr"], [(b["leadChar"], b["lead"].rstrip() + " "), (b["tagChar"], " " + bm.group(1))]))
            continue
        if re.match(r"^제\d+장", s):
            out.append(para(S["align"].get("CENTER", "0"), [(LAW["jo"]["leadChar"], s)]))
            continue
        if not out and not in_buchik:  # 첫 조문 앞 줄 = 시행일·소관부처 등 머리 부분
            law_subs.append(strip_md(s)); continue
        for key, rx in (("hang", r"^[①-⑳]"), ("ho", r"^\d+\.\s"), ("mok", r"^[가-힣]\.\s")):
            if re.match(rx, s) and key in LAW:
                r_ = LAW[key]
                out.append(para(r_["paraPr"], tagged(r_, [], r_.get("indent", "") + strip_md(s))))
                break
        else:
            r_ = LAW.get("buchik_body") if in_buchik else (LAW.get("hang") or LAW["jo"])
            out.append(para(r_["paraPr"], [(r_["textChar"], ("" if in_buchik else r_.get("indent", "")) + strip_md(s))]))

z = zipfile.ZipFile(TPL)
sec = etree.fromstring(z.read("Contents/section0.xml"))
nsdecl = " ".join(f'xmlns:{k}="{v}"' for k, v in sec.nsmap.items())
if "hc" not in sec.nsmap:
    nsdecl += ' xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core"'
ps = sec.findall(HP + "p")
first = copy.deepcopy(ps[0])
if LAW:
    # 머리 부분(첫 조문 앞 문단)을 그대로 복사: 첫 글 = 제목, 다음 글들 = 제목 아래 줄들(없으면 비움)
    pre = [copy.deepcopy(p) for p in ps[:LAW["preamble"]]]
    in_hf = lambda t: any(a.tag in (HP + "header", HP + "footer") for a in t.iterancestors())
    slots = []
    for p in pre:
        ts_ = [t for t in p.iter(HP + "t") if (t.text or "").strip() and not in_hf(t)]
        if ts_:
            slots.append(ts_)
    vals = [title or ""] + law_subs
    for k, ts_ in enumerate(slots):
        ts_[0].text = unph(vals[k]) if k < len(vals) else ""
        for t in ts_[1:]:
            t.text = ""
    if meta.get("keep_pictures", "").lower() not in ("true", "yes", "1"):
        for p in pre:  # 원 문서 전용 그림(QR 등) 제거
            for pic in list(p.iter(HP + "pic")):
                if not in_hf(pic):
                    pic.getparent().remove(pic)
    for p in pre:
        for l in list(p.iter(HP + "linesegarray")):
            l.getparent().remove(l)
        if p.find(".//" + HP + "header") is not None or p.find(".//" + HP + "footer") is not None or p.find(".//" + HP + "pageNum") is not None:
            apply_header_footer(p, meta, nsdecl)
    first = pre[0]
# ---------------------------------------------------------------- 앞쪽 페이지(표지·문서 정보·목차) 유지 모드
FRONT = S.get("front") if (not LAW and meta.get("front", "keep").lower() != "none") else None
TOC_PAGES = json.load(open(A.toc_pages, encoding="utf-8")) if A.toc_pages else {}
if FRONT:
    in_hf = lambda t: any(a.tag in (HP + "header", HP + "footer") for a in t.iterancestors())
    pre = [copy.deepcopy(p) for p in ps[:FRONT["body_start"]]]
    for i in FRONT.get("page_starts", []):  # 원 양식에서 새 쪽이던 문단은 쪽 나눔을 명시(로고·내용이 줄어도 쪽 구성 유지)
        pre[i].set("pageBreak", "1")
    repl = [tuple(x.strip() for x in v.split("=>", 1)) for v in META_LIST.get("replace", []) if "=>" in v]
    for old, new in repl:
        exact = old.startswith("=")  # 「=개발 => 검토」: 글 전체가 같을 때만(짧은 낱말 오치환 방지)
        old = old[1:].strip() if exact else old
        for p in pre:
            for t in p.iter(HP + "t"):
                if not t.text:
                    continue
                if exact and t.text.strip() == old:
                    t.text = unph(new)
                elif not exact and old in t.text:
                    t.text = t.text.replace(old, unph(new))
    if title and not repl:  # 바꿀 글을 안 주면 표지에서 가장 큰 글자를 제목으로
        def _h(t):
            c = t.getparent().get("charPrIDRef")
            return int(CHARS[c].get("height", 0)) if c in CHARS else 0
        cand = [t for p in pre for t in p.iter(HP + "t") if (t.text or "").strip() and not in_hf(t)]
        if cand:
            max(cand, key=_h).text = unph(title)
    if meta.get("front_pictures", "keep").lower() == "remove":
        for p in pre:
            for pic in list(p.iter(HP + "pic")):
                if not in_hf(pic):
                    pic.getparent().remove(pic)
    # 표 비우기·채우기: clear_table: 표 안 글 또는 표 바로 위 제목 / table_row: 칸1 | 칸2 | …
    last_tbl, fill_at = None, 1
    for key in META_LIST.get("clear_table", []):
        for k, p in enumerate(pre):
            tb = p.find(".//" + HP + "tbl")
            if tb is None:
                continue
            above = "".join(t.text or "" for t in pre[k - 1].iter(HP + "t")) if k else ""
            if key in "".join(t.text or "" for t in tb.iter(HP + "t")) or key in above:
                for tr in tb.findall(HP + "tr")[1:]:
                    for t in tr.iter(HP + "t"):
                        t.text = ""
                last_tbl, fill_at = tb, 1
                break
    for row in META_LIST.get("table_row", []):
        if last_tbl is None:
            break
        trs = last_tbl.findall(HP + "tr")
        if fill_at >= len(trs):
            break
        vals = [v.strip() for v in row.split("|")]
        for tc in trs[fill_at].findall(HP + "tc"):
            ci = int(tc.find(HP + "cellAddr").get("colAddr"))
            v = unph(vals[ci]) if ci < len(vals) else ""
            ts_ = list(tc.iter(HP + "t"))
            if ts_:
                ts_[0].text = v
            elif v:
                r_ = tc.find(".//" + HP + "run")
                if r_ is not None:
                    etree.SubElement(r_, HP + "t").text = v
        fill_at += 1
    # 목차: 양식 목차 항목을 지우고 원고 제목으로 새로 만듦(쪽 번호는 2단계 계산)
    if FRONT.get("toc"):
        a0, a1 = FRONT["toc"]
        lv = FRONT["toc_levels"]
        entries = []
        for lvl, text in HEADS:
            st = lv.get(lvl)
            if not st:
                continue
            pg = TOC_PAGES.get(text, "")
            tab = " ".join(f'{k}="{v}"' for k, v in st["tab"].items())
            pre_runs = "".join(f'<hp:run charPrIDRef="{c}"><hp:t>{escape(t)}</hp:t></hp:run>' for c, t in st["pre"])
            entries.append(f'<hp:p xmlns:hp="{HP[1:-1]}" id="0" paraPrIDRef="{st["paraPr"]}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">{pre_runs}'
                           f'<hp:run charPrIDRef="{st["char"]}"><hp:t>{escape(st["indent"] + unph(text))}<hp:tab {tab}/>{pg}</hp:t></hp:run></hp:p>')
        pre = pre[:a0] + [etree.fromstring(e) for e in entries] + pre[a1 + 1:]
    for p in pre:
        for l in list(p.iter(HP + "linesegarray")):
            l.getparent().remove(l)
        if p.find(".//" + HP + "header") is not None or p.find(".//" + HP + "footer") is not None or p.find(".//" + HP + "pageNum") is not None:
            apply_header_footer(p, meta, nsdecl)
    first = pre[0]
ts = [t for t in first.iter(HP + "t") if (t.text or "").strip() and not any(a.tag in (HP + "header", HP + "footer") for a in t.iterancestors())]
if LAW or FRONT:
    ts = []
if ts and title:
    big = max(ts, key=lambda t: len(t.text)); big.text = unph(title)
    for t in ts:
        if t is not big and not S["title"]["hasBox"]:
            t.text = ""
if not LAW and not FRONT:
    apply_header_footer(first, meta, nsdecl)
keep = pre if (LAW or FRONT) else [first]
if not LAW and not FRONT and S.get("dateline") and len(ps) > 1 and dateline:
    d = copy.deepcopy(ps[1])
    dts = [t for t in d.iter(HP + "t") if (t.text or "").strip()]
    if dts:
        dts[0].text = unph(dateline)
        for t in dts[1:]:
            t.text = ""
    for l in d.findall(HP + "linesegarray"):
        d.remove(l)
    keep.append(d)
for p in ps:
    sec.remove(p)
for p in keep:
    sec.append(p)
for n_, frag in enumerate(out):
    el = etree.fromstring(f"<wrap {nsdecl}>{frag}</wrap>")[0]
    if FRONT and n_ == 0:  # 본문은 새 쪽에서, 양식처럼 쪽 번호 1부터
        el.set("pageBreak", "1")
        if FRONT.get("newnum_run"):
            el.insert(0, etree.fromstring(FRONT["newnum_run"]))
    sec.append(el)
sec_xml = etree.tostring(sec, xml_declaration=True, encoding="UTF-8", standalone=True)


def png(w, h):
    raw = b"".join(b"\x00" + b"\xff" * (w * 3) for _ in range(h))
    ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b"")


prv = "\r\n".join([title or ""] + [b[1] if b[0] != "bullet" else b[2] for b in blocks if b[0] in ("h1", "h2", "body", "bullet")])[:2000]
zo = zipfile.ZipFile(OUT, "w")
for info in z.infolist():
    data = z.read(info.filename)
    if info.filename == "Contents/section0.xml":
        data = sec_xml
    elif info.filename == "Preview/PrvText.txt":
        data = prv.encode("utf-8")
    elif info.filename == "Preview/PrvImage.png":
        data = png(200, 283)
    elif info.filename == "Contents/header.xml" and NEW_CHARS:
        cps = HEAD.find(".//" + HH + "charProperties")
        for c in NEW_CHARS:
            cps.append(c)
        cps.set("itemCnt", str(len(cps.findall(HH + "charPr"))))
        data = etree.tostring(HEAD, xml_declaration=True, encoding="UTF-8", standalone=True)
    elif info.filename == "Contents/content.hpf":
        if title:
            data = re.sub(rb"<opf:title>.*?</opf:title>", f"<opf:title>{escape(title)}</opf:title>".encode("utf-8"), data, flags=re.S)
        if IMAGES:
            items = "".join(f'<opf:item id="{iid}" href="{href}" media-type="{mt}" isEmbeded="1"/>' for iid, href, _, mt in IMAGES)
            data = data.replace(b"</opf:manifest>", items.encode("utf-8") + b"</opf:manifest>", 1)
    zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    zi.compress_type = info.compress_type  # mimetype은 무압축 유지
    zo.writestr(zi, data)
for iid, href, src, _ in IMAGES:
    zi = zipfile.ZipInfo(href, date_time=(2026, 1, 1, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED
    zo.writestr(zi, open(src, "rb").read())
zo.close()
print(f"written {OUT}  (블록 {len(blocks)}, 표 {sum(1 for b in blocks if b[0] == 'table')}, 그림 {len(IMAGES)}, 각주 {FN[0]}, "
      f"머리말 {'header' in meta}, 꼬리말 {'footer' in meta})")

# 목차 쪽 번호 2단계: 한글로 PDF를 만들어 제목이 나오는 쪽을 찾은 뒤 번호를 채워 다시 만든다(Windows+한글)
if FRONT and FRONT.get("toc") and HEADS and not A.toc_pages and not A.no_toc_pages and os.name == "nt":
    import tempfile
    tmpd = tempfile.mkdtemp(prefix="hwptoc_")
    pdf1 = os.path.join(tmpd, "p1.pdf")
    r1 = subprocess.run([sys.executable, "-X", "utf8", os.path.join(HERE, "verify_hwp.py"), OUT, "--pdf", pdf1],
                        capture_output=True, text=True, encoding="utf-8")
    try:
        import fitz
        doc = fitz.open(pdf1)
        norm = lambda x: re.sub(r"\s+", "", x)
        pt = [norm(pg.get_text()) for pg in doc]
        key = lambda x: norm(unph(x))[:14]
        occ = [k for k, t in enumerate(pt) if key(HEADS[0][1]) in t]
        bs = occ[-1]
        pages, cur = {}, bs
        for _, text in HEADS:
            hit = next((k for k in range(cur, len(pt)) if key(text) in pt[k]), None)
            if hit is not None:
                pages[text] = (hit - bs + 1) if FRONT.get("newnum_run") else hit + 1
                cur = hit
        jp = os.path.join(tmpd, "toc_pages.json")
        json.dump(pages, open(jp, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"목차 쪽 번호 계산: {len(pages)}/{len(HEADS)}")
        r2 = subprocess.run([sys.executable, "-X", "utf8"] + sys.argv + ["--toc-pages", jp])
        sys.exit(r2.returncode)
    except Exception as e:
        print("목차 쪽 번호 계산 생략:", e, (r1.stdout or "")[:200])

if A.verify or A.pdf or A.png:
    cmd = [sys.executable, "-X", "utf8", os.path.join(HERE, "verify_hwp.py"), OUT]
    if A.pdf or A.png:
        cmd += ["--pdf", A.pdf or os.path.splitext(OUT)[0] + "_검증.pdf"]
    if A.png:
        cmd += ["--png", A.png]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    print("한글 검증:", (r.stdout or r.stderr).strip())
    sys.exit(r.returncode)
