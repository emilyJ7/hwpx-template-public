"""양식 hwpx를 읽어 문단 역할별 서식(paraPr·charPr·표 테두리)을 찾아 style_map.json으로 저장한다.

사용: python analyze_template.py 양식.hwpx [style_map.json]

역할 판별(문단 첫 글자 기준)
  title     첫 문단(구역 설정 포함). 표가 있으면 제목 상자로 보고 통째로 재사용
  dateline  둘째 문단이 '('로 시작하거나 짧은 한 줄이면 날짜·부제 줄
  h1        □ ■ ◆ ◇ ▣ ❏ Ⅰ Ⅱ … 로 시작
  h2        '1.' '가.' '①' 처럼 번호로 시작
  bullet1   ○ ◦ ㅇ ● • 로 시작 (괄호 머리말 '(…)' 런이 따로 있으면 lead로 기록)
  bullet2   '-' '–' 로 시작
  bullet3   '·' '∙' 로 시작
  note      ※ 로 시작
  spacer    빈 문단
  body      그 밖의 글
  table     본문 첫 표(제목 상자 제외)의 머리행·본문행 셀 서식
"""
import sys, re, json, zipfile, collections
from lxml import etree

HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
H1_MARK = "□■◆◇▣❏❑◼▶Ⅰ Ⅱ Ⅲ Ⅳ Ⅴ Ⅵ Ⅶ Ⅷ Ⅸ Ⅹ".replace(" ", "")
B1_MARK = "○◦ㅇ●•◎"


def runs_of(p):
    out = []
    for r in p.findall(HP + "run"):
        out.append((r.get("charPrIDRef"), "".join(t.text or "" for t in r.iter(HP + "t"))))
    return out


def classify(text):
    s = text.lstrip()
    if not s:
        return "spacer"
    c = s[0]
    if c in H1_MARK:
        return "h1"
    if c == "※":
        return "note"
    if c in B1_MARK:
        return "bullet1"
    if c in "-–":
        return "bullet2"
    if c in "·∙":
        return "bullet3"
    if re.match(r"^\d+\.\d+\.?\s", s):
        return "h2dec"   # 2.1. 제목
    if re.match(r"^[가-하]\.\s", s):
        return "h3"      # 가. 제목
    if re.match(r"^(\d+|[①-⑳])[.)]?\s", s) or re.match(r"^[①-⑳]", s):
        return "h2"
    return "body"


def table_style(tbl):
    rows = tbl.findall(HP + "tr")
    def cell(tc):
        p = tc.find(".//" + HP + "p")
        r = p.find(HP + "run") if p is not None else None
        m = tc.find(HP + "cellMargin")
        return {"borderFill": tc.get("borderFillIDRef"), "paraPr": p.get("paraPrIDRef") if p is not None else "0",
                "charPr": r.get("charPrIDRef") if r is not None else "0",
                "margin": dict(m.attrib) if m is not None else {"left": "510", "right": "510", "top": "141", "bottom": "141"},
                "vertAlign": (tc.find(HP + "subList").get("vertAlign") if tc.find(HP + "subList") is not None else "CENTER")}
    def row(tr):
        tcs = tr.findall(HP + "tc")
        return {"first": cell(tcs[0]), "middle": cell(tcs[1] if len(tcs) > 2 else tcs[0]), "last": cell(tcs[-1])}
    sz = tbl.find(HP + "sz")
    inm = tbl.find(HP + "inMargin")
    return {
        "attrs": {k: v for k, v in tbl.attrib.items() if k not in ("id", "rowCnt", "colCnt", "zOrder")},
        "width": int(sz.get("width")) if sz is not None else 48000,
        "inMargin": dict(inm.attrib) if inm is not None else {},
        "header": row(rows[0]),
        "body": row(rows[1] if len(rows) > 1 else rows[0]),
    }


def analyze(path):
    z = zipfile.ZipFile(path)
    sec = etree.fromstring(z.read("Contents/section0.xml"))
    _hh = "{http://www.hancom.co.kr/hwpml/2011/head}"
    BOLD = {c.get("id") for c in etree.fromstring(z.read("Contents/header.xml")).iter(_hh + "charPr") if c.find(_hh + "bold") is not None}
    ps = sec.findall(HP + "p")
    FRONT = detect_front(ps)
    BODY0 = FRONT["body_start"] if FRONT else 0
    roles = collections.defaultdict(list)
    seq = []  # 문단 역할 순서(빈 줄 배치 규칙 추정용)
    tables = []
    for i, p in enumerate(ps):
        rs = runs_of(p)
        text = "".join(t for _, t in rs)
        tbl = p.find(".//" + HP + "tbl")
        if i == 0:
            seq.append("title"); continue
        if i < BODY0:  # 표지·문서정보·목차 같은 앞쪽 페이지는 본문 서식 분석에서 뺀다
            continue
        if tbl is not None:
            tables.append(tbl); seq.append("table")
            roles["table_anchor"].append({"paraPr": p.get("paraPrIDRef"), "charPr": rs[0][0] if rs else "0"})
            continue
        if i == 1 and not FRONT and text.strip() and (text.strip().startswith("(") or len(text.strip()) < 60) and classify(text) in ("body", "h2"):
            roles["dateline"].append({"index": 1})
            seq.append("dateline"); continue
        role = classify(text)
        seq.append(role)
        info = {"paraPr": p.get("paraPrIDRef"), "runs": rs}
        nonempty = [(c, t) for c, t in rs if t]
        if role == "h1":
            s = text.lstrip()
            mark = s[0]
            mrun = next(((c, t) for c, t in nonempty if t.strip().startswith(mark)), nonempty[0])
            rest = [(c, t) for c, t in nonempty if (c, t) != mrun]
            if mrun[1].strip() == mark:  # □ 와 제목이 다른 런
                info.update(markChar=mrun[0], marker=mrun[1].rstrip(), textChar=rest[0][0] if rest else mrun[0],
                            textPrefix=re.match(r"^\s*", rest[0][1]).group(0) if rest else " ")
            else:  # 「□ 제목」 한 런
                gap = re.match(r"^\s*\S(\s*)", mrun[1]).group(1)
                info.update(markChar=mrun[0], marker=mrun[1].lstrip()[0], textChar=mrun[0], textPrefix=gap or " ")
            info["order"] = i
        elif role in ("bullet1", "bullet2", "bullet3", "note"):
            s = text
            # 머리말 = 기호 바로 다음 런이 「(…)」일 때만 (문장 끝 「(붙임1)」 같은 참조는 제외)
            sym0 = text.strip()[:1]
            ki = next((k for k, (c, t) in enumerate(nonempty) if sym0 and sym0 in t), -1)
            nxt = nonempty[ki + 1] if 0 <= ki < len(nonempty) - 1 else None
            lead = nxt if nxt and re.match(r"^\s*\(.+\)\s*$", nxt[1]) else None
            m = re.match(r"^(\s*\S\s*)", s)
            sym = s.strip()[:1]
            mk = next((c for c, t in nonempty if sym and sym in t), nonempty[0][0] if nonempty else "0")
            body_runs = [(c, t) for c, t in nonempty if (c, t) != lead and not (sym and t.strip() == sym)]
            body_runs = [x for x in body_runs if x[0] not in BOLD] or body_runs  # 기본 글자는 굵지 않은 서식
            info.update(prefix=m.group(1) if m else "", markChar=mk,
                        textChar=(collections.Counter(c for c, t in body_runs for _ in range(len(t))).most_common(1)[0][0]
                                  if body_runs else (nonempty[-1][0] if nonempty else "0")))
            if lead:
                info.update(leadChar=lead[0])
        else:
            info.update(textChar=nonempty[0][0] if nonempty else (rs[0][0] if rs else "0"))
            if role in ("h2", "h2dec", "h3"):
                info["textChar"] = max(nonempty, key=lambda x: len(x[1].strip()))[0]  # 앞 공백 런 말고 제목 글자 런
                info["indent"] = re.match(r"^\s*", text).group(0)
        roles[role].append(info)

    def pick(lst):  # 가장 흔한 서식
        if not lst:
            return None
        key = lambda d: json.dumps({k: v for k, v in d.items() if k not in ("runs", "order")}, sort_keys=True, ensure_ascii=False)
        cnt = collections.Counter(key(d) for d in lst)
        best = cnt.most_common(1)[0][0]
        d = dict(json.loads(best)); d["count"] = len(lst)
        if any("leadChar" in x for x in lst):
            d["leadChar"] = next(x["leadChar"] for x in lst if "leadChar" in x)
        d["example"] = "".join(t for _, t in lst[0].get("runs", []))[:40]
        return d

    # □ 대제목이 없는 양식(매뉴얼 등): 「1.」= 대제목, 「2.1.」= 중제목, 「가.」= 소제목
    if not roles.get("h1") and roles.get("h2"):
        roles["h1"] = roles.pop("h2")
        if roles.get("h2dec"):
            roles["h2"] = roles.pop("h2dec")
    elif not roles.get("h2") and roles.get("h2dec"):
        roles["h2"] = roles.pop("h2dec")
    roles.pop("h2dec", None)
    for d in roles.get("h1", []):
        d.setdefault("order", 0)
    if not roles.get("bullet1") and not roles.get("body") and roles.get("note"):
        plain = [d for d in roles["note"] if d.get("textChar") not in BOLD] or roles["note"]
        b = {k: v for k, v in plain[0].items() if k not in ("leadChar",)}
        b.update(prefix="  - ", markChar=b.get("textChar"))
        roles["bullet1"] = [b]
    style = {"template": path, "roles": {}}
    for r in ("h1", "h2", "h3", "bullet1", "bullet2", "bullet3", "note", "spacer", "body", "table_anchor"):
        v = pick(roles.get(r, []))
        if v:
            style["roles"][r] = v
    # □ 대제목은 문서에 처음 나오는 모양, 다른 모양(붙임 소제목 등)은 h1b 로
    h1s = roles.get("h1", [])
    if h1s:
        sig = lambda d: (d["paraPr"], d.get("markChar"), d["textChar"])
        firstv = min(h1s, key=lambda d: d["order"])
        same = [d for d in h1s if sig(d) == sig(firstv)]
        other = [d for d in h1s if sig(d) != sig(firstv)]
        style["roles"]["h1"] = pick(same)
        if other:
            style["roles"]["h1b"] = pick(other)
    # 본문 첫 문단(쪽 번호 새로 시작) 전용 서식이 대제목으로 잡혔으면 일반 대제목 모양으로 바꾼다
    if FRONT and style["roles"].get("h1b") and style["roles"]["h1"].get("paraPr") == FRONT.get("body_paraPr")             and style["roles"]["h1b"].get("textChar") == style["roles"]["h1"].get("textChar"):
        style["roles"]["h1"] = style["roles"].pop("h1b")
    for k in ("h1", "h1b"):
        style["roles"].get(k, {}).pop("order", None)
    title = ps[0]
    style["title"] = {"hasBox": title.find(".//" + HP + "tbl") is not None}
    style["dateline"] = bool(roles.get("dateline"))
    # 표 종류: 1×1 = 강조 박스, 1행×N열이고 첫 칸이 「붙임」 = 붙임 제목 상자, 그 밖 = 일반 표
    def shape(t):
        rows = t.findall(HP + "tr")
        return len(rows), max(len(r.findall(HP + "tc")) for r in rows)
    def first_cell_text(t):
        tc = t.find(HP + "tr").find(HP + "tc")
        return "".join(x.text or "" for x in tc.iter(HP + "t")).strip()
    anchor_para = lambda t: next(a for a in t.iterancestors() if a.tag == HP + "p" and a.getparent() is sec)
    strip_ns = lambda s: s
    for t in tables:
        nr, nc = shape(t)
        if nr == 1 and nc == 1 and "box" not in style:
            style["box"] = etree.tostring(anchor_para(t), encoding="unicode")
        elif nr == 1 and nc >= 2 and re.match(r"^붙\s*임", first_cell_text(t)) and "attach" not in style:
            style["attach"] = etree.tostring(anchor_para(t), encoding="unicode")
    grid = [t for t in tables if shape(t)[0] >= 2 and shape(t)[1] >= 2]
    if grid or tables:
        style["table"] = table_style((grid or tables)[0])
    # 빈 줄 규칙: h1 앞뒤, 표 뒤
    def around(role):
        before = after = 0; n = 0
        for i, s in enumerate(seq):
            if s == role:
                n += 1
                before += i > 0 and seq[i - 1] == "spacer"
                after += i + 1 < len(seq) and seq[i + 1] == "spacer"
        return {"before": n > 0 and before * 2 >= n, "after": n > 0 and after * 2 >= n}
    style["spacing"] = {"h1": around("h1"), "h2": around("h2"), "table": around("table")}
    style.update(extras(z, sec, ps))
    if FRONT:
        style["front"] = FRONT
    law = law_roles(ps)
    if law:
        style["law"] = law
    return style


def law_roles(ps):
    """법령 조문 양식(제N조(제목) → ① 항 → 1. 호 → 가. 목, 부칙)이면 단계별 서식을 돌려준다."""
    JO = re.compile(r"^제\d+조(의\d+)?\(.+\)$")
    roles, first_jo, n_jo = {}, None, 0
    for i, p in enumerate(ps):
        rs = [(r.get("charPrIDRef"), "".join(t.text or "" for t in r.findall(HP + "t"))) for r in p.findall(HP + "run")]
        ne = [(c, t) for c, t in rs if t]
        text = "".join(t for _, t in rs)
        tag = next((c for c, t in rs if re.match(r"^\s*<(개정|신설|삭제|전문개정)", t)), None) or \
              next((c for c, t in rs[1:] if not t), None)
        if ne and JO.match(ne[0][1].strip()):
            n_jo += 1
            first_jo = i if first_jo is None else first_jo
            roles.setdefault("jo", {"paraPr": p.get("paraPrIDRef"), "leadChar": ne[0][0],
                                    "textChar": ne[1][0] if len(ne) > 1 else ne[0][0], "tagChar": tag})
        elif re.match(r"^\s*[①-⑳]", text) and ne:
            roles.setdefault("hang", {"paraPr": p.get("paraPrIDRef"), "textChar": ne[0][0], "indent": re.match(r"^\s*", text).group(0)})
        elif re.match(r"^\s*\d+\.\s", text) and ne:
            roles.setdefault("ho", {"paraPr": p.get("paraPrIDRef"), "textChar": ne[0][0], "indent": re.match(r"^\s*", text).group(0)})
        elif re.match(r"^\s*[가-힣]\.\s", text) and ne:
            roles.setdefault("mok", {"paraPr": p.get("paraPrIDRef"), "textChar": ne[0][0], "indent": re.match(r"^\s*", text).group(0)})
        elif re.match(r"^\s*제\d+장", text) and ne:
            roles.setdefault("jang", {"paraPr": p.get("paraPrIDRef"), "textChar": ne[0][0], "indent": ""})
        elif re.match(r"^\s*부\s*칙", text) and ne:
            roles.setdefault("buchik", {"paraPr": p.get("paraPrIDRef"), "leadChar": ne[0][0], "lead": ne[0][1],
                                        "tagChar": ne[1][0] if len(ne) > 1 else ne[0][0]})
            nxt = ps[i + 1] if i + 1 < len(ps) else None
            if nxt is not None:
                r0 = nxt.find(HP + "run")
                roles["buchik_body"] = {"paraPr": nxt.get("paraPrIDRef"), "textChar": r0.get("charPrIDRef") if r0 is not None else "0"}
            prv = ps[i - 1] if i > 0 else None
            if prv is not None and not "".join(t.text or "" for t in prv.iter(HP + "t")).strip():
                r0 = prv.find(HP + "run")
                roles["spacer"] = {"paraPr": prv.get("paraPrIDRef"), "textChar": r0.get("charPrIDRef") if r0 is not None else "0"}
    if n_jo < 2:
        return None
    roles["preamble"] = first_jo  # 첫 조문 앞 문단(제목·시행일·소관부처)은 양식 그대로 두고 글자만 바꾼다
    return roles


HH = "{http://www.hancom.co.kr/hwpml/2011/head}"


def extras(z, sec, ps):
    """머리말·꼬리말·각주·그림에 필요한 서식(스타일, 정렬, 본문 폭)과 양식에 이미 있는 개체."""
    head = etree.fromstring(z.read("Contents/header.xml"))
    styles = {}
    for st in head.iter(HH + "style"):
        styles[st.get("engName") or st.get("name")] = {"style": st.get("id"), "paraPr": st.get("paraPrIDRef"), "charPr": st.get("charPrIDRef")}
    align = {}
    for pp in head.iter(HH + "paraPr"):
        al = pp.find(".//" + HH + "align")
        h = al.get("horizontal") if al is not None else None
        if h and h not in align:
            align[h] = pp.get("id")
    # 본문 폭: 쪽 너비 − 좌우 여백 (가로 방향이면 높이 사용)
    text_width = None
    pg = sec.find(".//" + HP + "pagePr")
    if pg is not None:
        mg = pg.find(HP + "margin")
        w, h = int(pg.get("width", 59528)), int(pg.get("height", 84186))
        if pg.get("landscape") == "NARROWLY" and h < w:
            pass
        if mg is not None:
            text_width = w - int(mg.get("left", 0)) - int(mg.get("right", 0)) - int(mg.get("gutter", 0))
    fnf = sec.find(".//" + HP + "footNotePr/" + HP + "autoNumFormat")
    found = {"header": False, "footer": False}
    first = ps[0]
    for k in found:
        found[k] = first.find(".//" + HP + k) is not None
    fn = sec.find(".//" + HP + "footNote")
    fn_style = None
    if fn is not None:
        fp = fn.find(".//" + HP + "p"); fr = fp.find(HP + "run")
        fn_style = {"style": fp.get("styleIDRef"), "paraPr": fp.get("paraPrIDRef"), "charPr": fr.get("charPrIDRef") if fr is not None else "0"}
    pic = sec.find(".//" + HP + "pic")
    pic_para = None
    if pic is not None:
        par = pic.getparent()
        while par is not None and par.tag != HP + "p":
            par = par.getparent()
        if par is not None:
            pic_para = par.get("paraPrIDRef")
    bins = [m for m in re.findall(r'<opf:item [^>]*id="([^"]+)"[^>]*href="BinData/', z.read("Contents/content.hpf").decode("utf-8"))]
    return {
        "styles": {k: styles[k] for k in ("Header", "Footer", "Footnote", "Normal", "Body", "Caption") if k in styles},
        "align": align,
        "textWidth": text_width,
        "footNoteFormat": dict(fnf.attrib) if fnf is not None else {"type": "DIGIT", "userChar": "", "prefixChar": "", "suffixChar": ")", "supscript": "0"},
        "existing": {**found, "footnoteStyle": fn_style, "pictureParaPr": pic_para, "binData": bins},
    }



def detect_front(ps):
    """앞쪽 페이지(표지·문서 정보·목차) 찾기. 목차(점선 탭 문단) 또는 쪽 번호 새로 시작(newNum)이 있을 때만."""
    txt = lambda e: "".join(t.text or "" for t in e.iter(HP + "t"))
    toc = [i for i, p in enumerate(ps) if p.find(".//" + HP + "tbl") is None
           and any(t.get("leader") not in (None, "0", "NONE") for t in p.iter(HP + "tab"))]
    def page_start(i):
        ls = ps[i].find(HP + "linesegarray")
        l0 = ls.find(HP + "lineseg") if ls is not None else None
        return (l0 is not None and l0.get("vertpos") == "0") or ps[i].get("pageBreak") == "1"
    newnum = next((i for i, p in enumerate(ps) if i > 0 and p.find(".//" + HP + "newNum") is not None), None)
    if newnum is not None and not any(page_start(k) for k in range(1, newnum + 1)):
        newnum = None  # 첫 쪽 안에서 쪽 번호만 다시 매기는 경우(보고서 날짜 줄 등)는 앞쪽 페이지가 아님
    if len(toc) < 3 and newnum is None:
        return None
    if newnum is not None:
        body_start = newnum
    else:
        body_start = next((i for i in range(toc[-1] + 1, len(ps)) if txt(ps[i]).strip()), len(ps))
    toc = [i for i in toc if i < body_start]
    levels = {}
    for i in toc:
        p = ps[i]
        runs = p.findall(HP + "run")
        tr = next((r for r in runs if r.find(".//" + HP + "tab") is not None), None)
        if tr is None:
            continue
        t0 = tr.find(HP + "t")
        head = (t0.text or "") if t0 is not None else ""
        lvl = "2" if re.match(r"^\s*\d+\.\d+", head) else "3" if re.match(r"^\s*[가-하]\.", head) else "1"
        tab = tr.find(".//" + HP + "tab")
        levels.setdefault(lvl, {"paraPr": p.get("paraPrIDRef"), "char": tr.get("charPrIDRef"),
                                "pre": [(r.get("charPrIDRef"), txt(r)) for r in runs[:runs.index(tr)]],
                                "indent": re.match(r"^\s*", head).group(0), "tab": dict(tab.attrib)})
    starts = []
    for i in range(1, body_start):  # 원 양식에서 새 쪽이 시작된 문단(줄 위치 0)
        ls = ps[i].find(HP + "linesegarray")
        l0 = ls.find(HP + "lineseg") if ls is not None else None
        if (l0 is not None and l0.get("vertpos") == "0") or ps[i].get("pageBreak") == "1":
            starts.append(i)
    nn = None
    if newnum is not None:
        r = next((r for r in ps[newnum].findall(HP + "run") if r.find(".//" + HP + "newNum") is not None), None)
        nn = etree.tostring(r, encoding="unicode") if r is not None else None
    return {"body_start": body_start, "toc": [toc[0], toc[-1]] if toc else None, "toc_levels": levels,
            "page_starts": starts, "newnum_run": nn, "body_paraPr": ps[body_start].get("paraPrIDRef") if body_start < len(ps) else None}


if __name__ == "__main__":
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "style_map.json"
    s = analyze(src)
    json.dump(s, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("style map:", out)
    for k, v in s["roles"].items():
        print(f"  {k:12s} paraPr={v.get('paraPr')} char={v.get('textChar', v.get('charPr'))} n={v['count']}  예: {v.get('example', '')}")
    print("  title box:", s["title"]["hasBox"], "| dateline:", s["dateline"], "| table:", "있음" if "table" in s else "없음",
          "| 강조 박스:", "있음" if "box" in s else "없음", "| 붙임 상자:", "있음" if "attach" in s else "없음")
    print("  spacing:", s["spacing"])
