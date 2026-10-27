# 설치 가이드

[← README](../README.md)

- [1. 준비물](#1-준비물)
- [2. 전역 설치 — PC마다 한 번](#2-전역-설치--pc마다-한-번)
- [3. 프로젝트 적용 — 프로젝트마다 한 번](#3-프로젝트-적용--프로젝트마다-한-번)
- [4. 설치 확인](#4-설치-확인)
- [5. 업데이트](#5-업데이트)
- [6. 제거](#6-제거)

---

## 1. 준비물

| 프로그램 | 메모 |
|---|---|
| [Claude Code](https://claude.com/claude-code) | 필수 |
| git | Windows는 [Git for Windows](https://git-scm.com/download/win). PowerShell만 써도 필요합니다 |
| Python 3.8 이상 | Windows는 python.org 설치본 |
| Node.js | 다이어그램 그림 만들 때만 |
| Codex CLI · Gemini CLI | 선택. ChatGPT · Gemini도 쓸 때만 |

> **Windows 파이썬 주의**
> *설정 → 앱 → 고급 앱 설정 → 앱 실행 별칭*에서 `python.exe` · `python3.exe`를 끄세요.
> 켜져 있으면 Microsoft Store 안내 창이 대신 실행됩니다.

---

## 2. 전역 설치 — PC마다 한 번

이 저장소를 받은 폴더에서 실행합니다.

**PowerShell**
```powershell
cd ~\work\nomad-agent-os
.\install.ps1
```

**Git Bash · macOS · Linux**
```bash
cd ~/work/nomad-agent-os
bash install.sh
```

설치가 끝나면 **새 터미널**을 엽니다. 그래야 `token-audit` 같은 도구를 이름만으로 실행할 수 있습니다.

### 무엇이 설치되나

`~/.claude` 폴더에 들어갑니다. 모든 프로젝트가 같이 씁니다.

- 팀원 10명 (`agents/`)
- 스킬 7개 · 슬래시 명령 7개
- 도구 12개 (`nomad/bin/`)
- 반복 읽기 차단 훅 (`settings.json`)

기존 파일은 지우지 않습니다.

- `~/.claude/CLAUDE.md` → 맨 위에 한 줄만 추가
- `~/.claude/settings.json` → 훅만 추가
- 이름이 같은 에이전트 · 스킬 · 명령 → 백업 후 교체 (`~/.claude/.nomad-backup/<시각>/`)

### 옵션

명령 뒤에 붙입니다. 예: `.\install.ps1 --codex --gemini`

| 옵션 | 하는 일 |
|---|---|
| `--codex` | ChatGPT Codex에도 공통 원칙 추가 (`~/.codex/AGENTS.md`) |
| `--gemini` | Gemini CLI에도 공통 원칙 추가 (`~/.gemini/GEMINI.md`) |
| `--no-path` | 도구 폴더를 PATH에 등록하지 않음 |

### PowerShell에서 "스크립트를 실행할 수 없습니다"가 나오면

한 번만 실행합니다.
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

<details>
<summary>PowerShell 설치는 내부적으로 어떻게 동작하나</summary>

- `install.ps1`은 Git for Windows의 bash를 찾아 `install.sh`를 실행합니다. 결과는 Bash로 설치한 것과 같습니다.
- WSL의 `bash.exe`는 쓰지 않습니다.
- Git이 특이한 위치에 있으면 먼저 지정합니다: `$env:CLAUDE_CODE_GIT_BASH_PATH = 'C:\...\Git\bin\bash.exe'`
- `~/.claude/nomad/bin-win/`에 `token-audit.cmd` 같은 래퍼를 만들고, 이 폴더를 사용자 PATH에 추가합니다.
</details>

---

## 3. 프로젝트 적용 — 프로젝트마다 한 번

어느 폴더에서 실행해도 됩니다. 프로젝트 폴더가 없으면 만듭니다.

**PowerShell**
```powershell
~\work\nomad-agent-os\install.ps1 init ~\work\내프로젝트

# 표시 이름을 직접 정하려면
~\work\nomad-agent-os\install.ps1 init ~\work\내프로젝트 --name "쇼핑몰"
```

**Git Bash**
```bash
bash ~/work/nomad-agent-os/install.sh init ~/work/내프로젝트

# 표시 이름을 직접 정하려면
bash ~/work/nomad-agent-os/install.sh init ~/work/내프로젝트 --name "쇼핑몰"
```

### 프로젝트에 생기는 파일

| 파일 | 용도 |
|---|---|
| `AGENTS.md` | **가장 중요.** 스택 · 명령 · 규칙. 모든 AI 도구가 읽음 |
| `CLAUDE.md` | Claude Code용 (AGENTS.md를 불러옴) |
| `.claude/` | Claude Code 설정 · 영역 규칙 |
| `.codex/` | ChatGPT Codex 설정 |
| `.gemini/` · `.geminiignore` | Gemini CLI 설정 |
| `tasks/` | 작업 목록 · 현재 진행 상태 |

### 안심해도 되는 점

- 이미 있는 파일은 덮어쓰지 않습니다. 필요한 줄만 추가합니다.
- git 명령을 실행하지 않습니다. 커밋 기록 · 원격 연결은 그대로입니다.
- 이 저장소(nomad-agent-os) 안의 경로는 거부합니다. 프로젝트는 항상 밖에 둡니다.

---

## 4. 설치 확인

**PowerShell**
```powershell
token-audit ~\work\내프로젝트
```

**Git Bash**
```bash
token-audit ~/work/내프로젝트
```

`■ 예산 안 ✅`이 나오면 정상입니다.
그다음 프로젝트 폴더에서 `claude`를 실행하고 `/agents`를 입력합니다. 팀원 10명이 보이면 끝입니다.

> `token-audit`를 찾지 못하면 새 터미널을 열었는지 확인합니다.

---

## 5. 업데이트

이 저장소 폴더에서 실행합니다. 여러 번 실행해도 중복 추가되지 않습니다.

**PowerShell**
```powershell
git pull
.\install.ps1
```

**Git Bash**
```bash
git pull && bash install.sh
```

이미 적용한 프로젝트는 이렇게 합니다.

- 새로 생긴 설정 파일 → `init`을 한 번 더 실행하면 추가됩니다.
- `AGENTS.md` → 보존되므로 바뀐 장은 `project-template/AGENTS.md`를 보고 직접 옮깁니다.

---

## 6. 제거

1. 폴더 삭제: `~/.claude/nomad/`, 그리고 `~/.claude/agents` · `skills` · `commands` 안의 NOMAD 파일
2. `~/.claude/CLAUDE.md` 첫 줄 `@nomad/TEAM.md` 삭제
3. `~/.claude/settings.json`에서 `hook-read`가 들어간 훅 3개 삭제
4. PATH 정리
   - Git Bash: `~/.bashrc`에서 `.claude/nomad/bin` 줄 삭제
   - PowerShell:
     ```powershell
     $p = [Environment]::GetEnvironmentVariable('Path', 'User') -split ';' | Where-Object { $_ -notlike '*\.claude\nomad\bin-win' }
     [Environment]::SetEnvironmentVariable('Path', ($p -join ';'), 'User')
     ```
5. `--codex` · `--gemini`를 썼다면 `~/.codex/AGENTS.md` · `~/.gemini/GEMINI.md`에서 `# NOMAD CORE` 아래를 삭제
