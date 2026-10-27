# NOMAD Agent OS 설치 — Windows PowerShell 5.1 / PowerShell 7 용 진입점
#   .\install.ps1                                   전역 설치 (~/.claude) + PowerShell용 도구 명령(.cmd) 등록
#   .\install.ps1 init <프로젝트> [--name 이름]      프로젝트에 템플릿 적용 (기존 파일 보존·병합)
#   nomad-os init <프로젝트> [--name 이름]           전역 설치 뒤에는 어디서든 (이 파일 경로를 몰라도 됨)
#   옵션: --no-path  --codex  --gemini  (install.sh 와 같음)
# 실제 설치 로직은 install.sh 하나뿐이다. 이 스크립트는 Git Bash를 찾아 그것을 실행하고,
# 전역 설치 때 ~/.claude/nomad/bin 도구를 PowerShell·cmd에서 이름만으로 부를 수 있게 .cmd 래퍼를 만든다.
$ErrorActionPreference = 'Stop'
$prevOut = [Console]::OutputEncoding
[Console]::OutputEncoding = [Text.Encoding]::UTF8   # bash 출력(한국어)이 깨지지 않게

function Find-GitBash {
  # WSL의 C:\Windows\System32\bash.exe 와 헷갈리지 않도록 Git for Windows 의 bash.exe 만 찾는다
  $cands = @()
  if ($env:CLAUDE_CODE_GIT_BASH_PATH) { $cands += $env:CLAUDE_CODE_GIT_BASH_PATH }
  $git = Get-Command git -ErrorAction SilentlyContinue
  if ($git) { $cands += (Join-Path (Split-Path (Split-Path $git.Source)) 'bin\bash.exe') }   # <Git>\cmd\git.exe → <Git>\bin\bash.exe
  $cands += "$env:ProgramFiles\Git\bin\bash.exe", "${env:ProgramFiles(x86)}\Git\bin\bash.exe", "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"
  foreach ($c in $cands) { if ($c -and (Test-Path $c)) { return (Resolve-Path $c).Path } }
  return $null
}

$bash = Find-GitBash
if (-not $bash) {
  Write-Host "❌ Git Bash(bash.exe)를 찾지 못했습니다. Git for Windows를 설치하세요: https://git-scm.com/download/win"
  Write-Host "   다른 위치에 있으면: `$env:CLAUDE_CODE_GIT_BASH_PATH = 'C:\...\Git\bin\bash.exe'"
  exit 1
}

# init 의 프로젝트 경로는 절대경로 + 슬래시로 바꿔 넘긴다 (D:\work\a → D:/work/a)
$fwd = @(); $isInit = $args.Count -gt 0 -and $args[0] -eq 'init'
$isModule = $args.Count -gt 0 -and $args[0] -eq 'module'   # module <cmd> <이름> [프로젝트] [--from 경로]
for ($i = 0; $i -lt $args.Count; $i++) {
  $a = [string]$args[$i]
  $prev = if ($i -gt 0) { [string]$args[$i - 1] } else { '' }
  $isPath = ($isInit -and $i -gt 0 -and $prev -ne '--name' -and -not $a.StartsWith('--')) -or
            ($isModule -and (($i -ge 3 -and -not $a.StartsWith('--') -and $prev -ne '--ref') -or $prev -eq '--from') -and $a -notmatch '^(https?|ssh)://|^git@')
  if ($isPath) {
    $a = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($a).Replace('\', '/')
  }
  $fwd += $a
}

$env:PYTHONUTF8 = '1'; $env:PYTHONIOENCODING = 'utf-8'
$sh = (Join-Path $PSScriptRoot 'install.sh').Replace('\', '/')
& $bash $sh @fwd
$code = $LASTEXITCODE
if ($code -ne 0 -or $isInit -or $isModule) { [Console]::OutputEncoding = $prevOut; exit $code }

# 전역 설치 후: PowerShell·cmd 용 래퍼 (~/.claude/nomad/bin-win/<도구>.cmd → Git Bash로 실행)
$bin = Join-Path $HOME '.claude\nomad\bin'
$win = Join-Path $HOME '.claude\nomad\bin-win'
New-Item -ItemType Directory -Force $win | Out-Null
$skip = '_py', 'hook-read', 'readguard', 'nomad-os'   # 훅·내부용 제외, nomad-os 는 아래에서 따로
$n = 0
$utf8 = New-Object Text.UTF8Encoding $false
Get-ChildItem $bin -File | Where-Object { $_.Extension -eq '' -and $skip -notcontains $_.Name } | ForEach-Object {
  $cmd = "@echo off`r`n`"$bash`" `"%USERPROFILE%\.claude\nomad\bin\$($_.Name)`" %*`r`n"
  [IO.File]::WriteAllText((Join-Path $win "$($_.Name).cmd"), $cmd, $utf8)
  $n++
}
Write-Host "  + PowerShell용 도구 명령 $($n)개 → $win"
# nomad-os: 이 저장소의 install.ps1 을 거쳐 실행 → ~ · D:\ 같은 Windows 경로를 그대로 써도 된다
$ps1 = Join-Path $PSScriptRoot 'install.ps1'
$cmd = "@echo off`r`npowershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n"
[IO.File]::WriteAllText((Join-Path $win 'nomad-os.cmd'), $cmd, $utf8)
Write-Host "  + nomad-os 명령 → 어디서든 'nomad-os init <프로젝트 경로>' (저장소: $PSScriptRoot)"

if ($args -notcontains '--no-path') {
  $userPath = [string][Environment]::GetEnvironmentVariable('Path', 'User')
  if (-not (($userPath -split ';') -contains $win)) {
    [Environment]::SetEnvironmentVariable('Path', (($userPath.TrimEnd(';'), $win) -join ';').TrimStart(';'), 'User')
    Write-Host "  + 사용자 PATH 에 추가: $win (새 PowerShell 창부터 token-audit · q · delta 이름만으로 실행)"
  } else { Write-Host "  · 유지  사용자 PATH ($win 있음)" }
  if (-not (($env:Path -split ';') -contains $win)) { $env:Path = "$env:Path;$win" }   # 현재 창에도 바로 적용
}
[Console]::OutputEncoding = $prevOut
exit 0
