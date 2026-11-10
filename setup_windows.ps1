# hwpx-template 스킬 설치 도우미 (Windows)
#   1) Python 패키지 설치  2) 한글 설치 확인  3) (선택) 한글 보안 승인 모듈 등록  4) 스킬 복사(플러그인으로 설치하지 않을 때)
# 사용: PowerShell에서  powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 [-CopySkill] [-RegisterSecurityModule]
param([switch]$CopySkill, [switch]$RegisterSecurityModule)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "[1/4] Python 패키지 설치"
python -m pip install -r (Join-Path $here "requirements.txt")

Write-Host "[2/4] 한글 확인"
$hwp = Get-ItemProperty "Registry::HKEY_CLASSES_ROOT\HWPFrame.HwpObject" -ErrorAction SilentlyContinue
if ($hwp) { Write-Host "  한글 자동화 등록됨 → 한글 검증 사용 가능" } else { Write-Host "  한글 미설치 → 문서 생성만 가능(검증 생략)" }

if ($RegisterSecurityModule) {
  Write-Host "[3/4] 한글 보안 승인 모듈 등록(HKCU, 자동화 시 파일 접근 승인 창 생략)"
  $dll = python -c "import pyhwpx, os, glob; print((glob.glob(os.path.join(os.path.dirname(pyhwpx.__file__), '**', 'FilePathCheckerModule*.dll'), recursive=True) or [''])[0])"
  if ($dll) {
    New-Item -Path "HKCU:\Software\HNC\HwpAutomation\Modules" -Force | Out-Null
    Set-ItemProperty -Path "HKCU:\Software\HNC\HwpAutomation\Modules" -Name "FilePathCheckerModule" -Value $dll
    Write-Host "  등록: $dll"
  } else { Write-Host "  pyhwpx 안에서 모듈을 찾지 못함 → 첫 실행 때 한글 창에서 「모두 허용」을 누르면 됨" }
} else { Write-Host "[3/4] 보안 모듈 등록 생략(-RegisterSecurityModule 로 등록 가능)" }

if ($CopySkill) {
  $dst = Join-Path $env:USERPROFILE ".claude\skills\hwpx-template"
  Write-Host "[4/4] 스킬 복사 → $dst"
  New-Item -ItemType Directory -Force -Path $dst | Out-Null
  Copy-Item -Recurse -Force (Join-Path $here "skills\hwpx-template\*") $dst
} else { Write-Host "[4/4] 스킬 복사 생략(플러그인으로 설치했거나 -CopySkill 미지정)" }
Write-Host "완료. Claude Code를 다시 시작하면 '이 양식으로 한글 파일 만들어줘' 요청에 스킬이 자동으로 쓰입니다."
