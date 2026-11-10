# hwpx-template — 한글 양식 자동 적용 스킬

한글(hwpx) 양식을 주면 서식(제목 상자, □ 대제목, ○ 글머리, ※ 박스, 붙임 상자, 표·병합, 각주, 그림, 머리말·쪽 번호, 표지·목차)을 자동으로 읽어 **같은 모양의 한글 문서**를 만들고, Windows에서는 **한글로 직접 열어 검증**까지 하는 Claude 스킬입니다.

사용은 대화로 합니다.

> "C:\…\보고양식.hwpx 양식에 맞게 이 내용으로 한글 파일 만들어줘"

- **사용자 가이드(케이스별 프롬프트 예시)**: [docs/사용자가이드.md](docs/사용자가이드.md) · 슬라이드판 `docs/사용자가이드.pptx`(22장) · 한글판 `docs/사용자가이드.hwpx` · PDF `docs/사용자가이드.pdf`
- **발표자료(15장)**: `docs/발표자료/발표자료.pptx` · PDF `docs/발표자료/발표자료.pdf` · 장별 대본 [docs/발표자료/발표대본.md](docs/발표자료/발표대본.md)
- PPTX 다시 만들기: 원본 JSON(`docs/발표자료/slides.json`, `docs/사용자가이드.slides.json`)을 고친 뒤 `npm install pptxgenjs@3.12.0` → `node tools/build_slides.js [원본.json]`. PDF는 PowerPoint에서 PDF로 저장
- **예시 파일**: 견본 양식 `examples/양식예시.hwpx`, 원고 [examples/sample.md](examples/sample.md), 결과 `examples/결과예시.hwpx` · `examples/결과예시.pdf`
- 원고 문법 상세: [skills/hwpx-template/USAGE.md](skills/hwpx-template/USAGE.md)

## 변경 이력
- 0.2.2: 다른 AI 도구(Codex·Cursor·Gemini CLI·GitHub Copilot) 설치 안내와 `setup_windows.ps1 -Agents` 추가, SKILL.md에 license·compatibility 추가, setup_windows.ps1을 Windows PowerShell 5.1에서 열리도록 수정(UTF-8 BOM)
- 0.2.1: MIT 라이선스로 공개, 공개용 사용자 가이드·발표자료(PPTX)·견본 양식과 결과 예시 추가
- 0.2.0: 표지·문서 정보·목차가 있는 양식 지원(앞쪽 페이지 유지, 목차 자동 생성·쪽 번호 자동), 번호 제목(1. / 2.1. / 가.) 양식 자동 인식, 표지 글 바꾸기(replace)·표 비우기/채우기, 사용자 가이드
- 0.1.0: 첫 배포(보고서 양식, 표·병합·각주·그림·머리말, 한글 검증)

## 설치 (쓰는 도구에 맞게 하나)

### A. Claude Code 플러그인 (권장)
Claude Code에서 실행합니다. 직접 고친 판을 쓰려면 이 저장소를 포크한 뒤 그 주소를 넣습니다.
```
/plugin marketplace add emilyJ7/hwpx-template-public
/plugin install hwpx-template@hwpx-tools
```
포크해서 배포한다면, 고친 내용을 올리고 `plugin.json`의 version을 올리면 받는 쪽에서 업데이트됩니다.

### B. 스킬 폴더 복사 (개인·소수)
`skills/hwpx-template` 폴더를 `%USERPROFILE%\.claude\skills\` 아래에 복사합니다. 또는 아래 명령을 실행합니다.
```
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -CopySkill
```

### C. claude.ai 웹·데스크톱 앱
1. 저장소에서 `dist/hwpx-template-skill.zip` **파일 하나만** 내려받습니다(파일 클릭 → Download raw file).
   - `dist` 폴더를 통째로 압축하면 zip 안에 zip이 들어가 「Zip cannot contain nested zip files」 오류가 납니다.
2. 설정 → 기능(Capabilities) → 스킬에서 그 zip을 업로드합니다(코드 실행 기능 켜짐 필요).
3. 웹 환경에는 한글이 없으므로 **문서 생성만** 되고 한글 검증은 건너뜁니다.
4. 스킬을 고쳤다면 `python tools/build_skill_zip.py`로 zip을 다시 만듭니다(줄바꿈 LF 통일, SKILL.md 머리 검사).

### D. 다른 AI 도구 (Codex · Cursor · Gemini CLI · GitHub Copilot)
스킬은 공개 표준 [Agent Skills](https://agentskills.io/specification)(`SKILL.md`) 형식이며, 표준 검사기 `skills-ref validate`를 통과합니다. `skills/hwpx-template` 폴더를 각 도구가 읽는 위치에 복사합니다.

| 도구 | 개인 폴더 | 프로젝트 폴더 |
|---|---|---|
| OpenAI Codex | `~/.agents/skills/` | `.agents/skills/` |
| Cursor | `~/.cursor/skills/`, `~/.agents/skills/` | `.cursor/skills/`, `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/`, `~/.agents/skills/` | `.gemini/skills/`, `.agents/skills/` |
| GitHub Copilot(VS Code) | `~/.copilot/skills/`, `~/.agents/skills/` | `.github/skills/`, `.agents/skills/` |

`~/.agents/skills/`(Windows: `%USERPROFILE%\.agents\skills\`)는 위 도구들이 함께 읽는 공용 폴더입니다. 아래 명령은 Claude Code 폴더와 공용 폴더에 함께 복사합니다.
```
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -CopySkill -Agents
```
- 어느 도구든 Python과 `lxml`이 필요합니다. 한글로 열어 검증하는 단계는 Windows+한글 PC에서, 도구가 명령 실행을 허용할 때만 됩니다.
- 실제 실행은 Claude Code에서 확인했고, 다른 도구의 위치는 각 도구 공식 문서 기준(2026년 11월)입니다. 문서가 바뀌었을 수 있으니 처음 쓸 때 확인하세요.

## 필요 환경
| 기능 | 필요 |
|---|---|
| 문서 생성 | Python 3.9+, `lxml`, (docx 입력 시) `python-docx` |
| 한글로 열어 검증, .hwp 양식 변환 | Windows, 한글 2018 이상, `pywin32`, `pymupdf` |
| 승인 창 없이 자동 검증(선택) | 한글 보안 승인 모듈 등록(`setup_windows.ps1 -RegisterSecurityModule`, `pyhwpx` 포함 모듈 사용) |

설치: `python -m pip install -r requirements.txt` 또는 `setup_windows.ps1`

## 구성
```
.claude-plugin/plugin.json        플러그인 정보
.claude-plugin/marketplace.json   마켓플레이스(저장소 하나에 플러그인 하나)
skills/hwpx-template/SKILL.md     Claude가 읽는 절차
skills/hwpx-template/USAGE.md     사용자용 문법·예시
skills/hwpx-template/scripts/     analyze_template.py, md2hwpx.py, verify_hwp.py, hwp2hwpx.py, docx2md.py
examples/                         견본 양식(양식예시.hwpx), 원고 예시(sample.md), 결과 예시(hwpx·pdf)
docs/                             사용자 가이드(md·pptx·hwpx·pdf), 발표자료(pptx·pdf·대본)
tools/                            스킬 zip·발표자료 빌드 스크립트
setup_windows.ps1                 설치 도우미
```

## 직접 실행 (Claude 없이)
```
python -X utf8 skills/hwpx-template/scripts/md2hwpx.py examples/양식예시.hwpx examples/sample.md 결과.hwpx --pdf 검증.pdf --png 쪽이미지
```

## 라이선스
[MIT](LICENSE). 한글·한컴은 한글과컴퓨터의 상표이며, 이 프로젝트는 한글과컴퓨터와 관계없는 개인 프로젝트입니다. 제3자 구성요소(lxml, python-docx, pywin32, PyMuPDF, pyhwpx, 한글 프로그램)는 각자의 라이선스를 따릅니다.

## 유의
- 스킬 패키지에는 양식 파일을 넣지 않습니다. 각자 자기 양식을 씁니다. `examples/양식예시.hwpx`는 시험용 견본입니다.
- 대외비·개인정보가 담긴 문서는 소속 기관의 보안 지침에 맞는지 확인한 뒤 올립니다.
- 만든 문서의 내용 확인과 사용 책임은 작성자에게 있습니다.
- 같은 각주를 두 번 참조하면 각주가 두 개 생깁니다. 셀 병합은 원고 표에서 `<`(왼쪽), `^`(위)로 표시합니다.
