"""한글(HWP 2018 이상, Windows)로 hwpx를 실제로 열어 검증하고 PDF·PNG 미리보기를 만든다.

사용: python verify_hwp.py 결과.hwpx [--pdf 결과.pdf] [--png 미리보기폴더]
결과(JSON 한 줄): ok, pages, tables, pictures, footnotes, headers, text_chars, pdf

보안 승인 창이 뜨지 않도록 FilePathCheckerModule(보안 모듈)을 등록해 쓴다.
모듈이 없으면(예: pyhwpx 미설치) 첫 실행에서 한글이 파일 접근 허용을 묻는다 → 「모두 허용」.
"""
import sys, os, json, argparse, glob


def find_module():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\HNC\HwpAutomation\Modules")
        v, _ = winreg.QueryValueEx(k, "FilePathCheckerModule")
        return v if os.path.exists(v) else None
    except OSError:
        return None


def hwp_pids():
    import subprocess
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Hwp.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    return {int(l.split('","')[1]) for l in out.splitlines() if l.startswith('"Hwp.exe"')}


def watchdog(before, seconds):
    """검증용으로 띄운 한글이 대화상자 등으로 멈추면 그 프로세스만 종료(사용자가 연 한글은 건드리지 않음)."""
    import threading, subprocess
    def kill():
        for pid in hwp_pids() - before:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        print(json.dumps({"ok": False, "error": f"한글이 {seconds}초 안에 응답하지 않음(파일 구조 오류 가능)"}, ensure_ascii=False), flush=True)
        os._exit(2)
    t = threading.Timer(seconds, kill); t.daemon = True; t.start()
    return t


def open_hwp():
    import win32com.client as w
    hwp = w.gencache.EnsureDispatch("HWPFrame.HwpObject") if False else w.Dispatch("HWPFrame.HwpObject")
    if find_module():
        hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    try:
        hwp.XHwpWindows.Item(0).Visible = False
    except Exception:
        pass
    hwp.SetMessageBoxMode(0x00020000 | 0x00000010)  # 확인/예 자동 선택
    return hwp


def count_ctrls(hwp):
    c = {"tables": 0, "pictures": 0, "footnotes": 0, "headers": 0, "footers": 0}
    ctrl = hwp.HeadCtrl
    while ctrl:
        cid = ctrl.CtrlID
        if cid == "tbl": c["tables"] += 1
        elif cid == "gso": c["pictures"] += 1
        elif cid == "fn": c["footnotes"] += 1
        elif cid == "head": c["headers"] += 1
        elif cid == "foot": c["footers"] += 1
        ctrl = ctrl.Next
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--pdf")
    ap.add_argument("--png", help="쪽별 PNG 저장 폴더")
    ap.add_argument("--timeout", type=int, default=90, help="한글 응답 대기 초(초과 시 검증용 한글만 종료)")
    a = ap.parse_args()
    path = os.path.abspath(a.path)
    if os.name != "nt":
        print(json.dumps({"file": path, "ok": None, "skipped": "한글 검증은 Windows + 한글(2018 이상)에서만 가능 — 생성은 완료"}, ensure_ascii=False))
        sys.exit(0)
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        print(json.dumps({"file": path, "ok": None, "skipped": "pywin32 미설치: pip install pywin32"}, ensure_ascii=False))
        sys.exit(0)
    # 한글 자동화는 괄호 등 특수문자가 든 경로에서 열기가 멈출 수 있어, 임시 폴더의 단순한 이름 복사본으로 연다
    import tempfile, shutil
    tmpdir = tempfile.mkdtemp(prefix="hwpv_")
    work = os.path.join(tmpdir, "doc" + (os.path.splitext(path)[1] or ".hwpx"))
    shutil.copyfile(path, work)
    res = {"file": path, "ok": False}
    wd = watchdog(hwp_pids(), a.timeout)
    hwp = open_hwp()
    try:
        ok = hwp.Open(work, "", "forceopen:true;suspendpassword:true")
        res["ok"] = bool(ok)
        if ok:
            res["pages"] = hwp.PageCount
            res.update(count_ctrls(hwp))
            res["text_chars"] = len(hwp.GetTextFile("TEXT", "") or "")
            if a.pdf:
                pdf = os.path.abspath(a.pdf)
                tmp_pdf = os.path.join(tmpdir, "out.pdf")
                hwp.SaveAs(tmp_pdf, "PDF", "")
                if os.path.exists(tmp_pdf):
                    shutil.move(tmp_pdf, pdf)
                res["pdf"] = pdf if os.path.exists(pdf) else None
    except Exception as e:
        res["error"] = str(e)
    finally:
        try:
            hwp.Clear(1)
            hwp.Quit()
        except Exception:
            pass
        wd.cancel()
    if a.png and res.get("pdf"):
        try:  # PDF → 쪽 이미지 (PyMuPDF)
            import fitz
            os.makedirs(a.png, exist_ok=True)
            doc = fitz.open(res["pdf"])
            res["pdf_sheets"] = doc.page_count
            res["png"] = []
            for i, pg in enumerate(doc):
                fp = os.path.join(os.path.abspath(a.png), f"page{i + 1:03d}.png")
                pg.get_pixmap(dpi=80).save(fp)
                res["png"].append(fp)
        except ImportError:
            res["png"] = "PyMuPDF(fitz) 없음: pip install pymupdf"
    print(json.dumps(res, ensure_ascii=False))
    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
