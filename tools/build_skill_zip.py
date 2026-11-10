"""claude.ai 업로드용 스킬 zip 만들기: skills/hwpx-template → dist/hwpx-template-skill.zip
- 줄바꿈을 LF로 통일(CRLF면 SKILL.md 머리 YAML을 못 읽는 경우가 있음)
- SKILL.md 머리(name, description) 검사
사용: python tools/build_skill_zip.py
"""
import os, re, sys, zipfile

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
skill = os.path.join(root, "skills", "hwpx-template")
out = os.path.join(root, "dist", "hwpx-template-skill.zip")
TEXT = (".md", ".py", ".json", ".txt", ".ps1")

s = open(os.path.join(skill, "SKILL.md"), "rb").read().decode("utf-8-sig").replace("\r\n", "\n")
m = re.match(r"^---\n(.*?)\n---\n", s, re.S)
assert m, "SKILL.md 맨 앞에 --- 로 감싼 YAML 머리가 없습니다"
name = re.search(r"^name:\s*(\S+)\s*$", m.group(1), re.M)
desc = re.search(r"^description:\s*(.+)$", m.group(1), re.M)
assert name and re.fullmatch(r"[a-z0-9-]{1,64}", name.group(1)), "name은 영문 소문자·숫자·하이픈 64자 이내"
assert desc and len(desc.group(1).strip("'\"")) <= 1024, "description은 1024자 이내"

os.makedirs(os.path.dirname(out), exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for d, _, fs in os.walk(skill):
        if "__pycache__" in d:
            continue
        for f in sorted(fs):
            p = os.path.join(d, f)
            arc = os.path.relpath(p, os.path.dirname(skill)).replace(os.sep, "/")
            data = open(p, "rb").read()
            if f.endswith(TEXT):
                data = data.decode("utf-8-sig").replace("\r\n", "\n").encode("utf-8")
            if f.endswith(".zip"):
                sys.exit("zip 안에 zip을 넣을 수 없습니다: " + arc)
            z.writestr(arc, data)
print("written", out, "| name:", name.group(1), "| description", len(desc.group(1)), "자")
