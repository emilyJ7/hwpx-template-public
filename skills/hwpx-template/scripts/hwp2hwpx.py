"""한글로 .hwp(또는 HWPML .hwp/.hml)를 열어 .hwpx로 저장한다. 양식이 hwp일 때 쓴다.

사용: python -X utf8 hwp2hwpx.py 입력.hwp 출력.hwpx
경로에 괄호 등이 있으면 한글 자동화가 멈출 수 있어 임시 폴더의 단순한 이름으로 복사해 변환한다.
"""
import sys, os, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_hwp import open_hwp, watchdog, hwp_pids

src, dst = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
tmp = tempfile.mkdtemp(prefix="hwpc_")
work_in = os.path.join(tmp, "in" + os.path.splitext(src)[1])
work_out = os.path.join(tmp, "out.hwpx")
shutil.copyfile(src, work_in)
wd = watchdog(hwp_pids(), 90)
hwp = open_hwp()
try:
    ok = hwp.Open(work_in, "", "forceopen:true")
    saved = bool(ok) and hwp.SaveAs(work_out, "HWPX", "")
    pages = hwp.PageCount if ok else 0
finally:
    try:
        hwp.Clear(1); hwp.Quit()
    except Exception:
        pass
    wd.cancel()
if saved and os.path.exists(work_out):
    shutil.move(work_out, dst)
print({"open": bool(ok), "saved": os.path.exists(dst), "pages": pages, "out": dst})
