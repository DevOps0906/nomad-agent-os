# NOMAD Agent OS

토큰을 아끼고 코딩·기획·디자인·다이어그램을 팀으로 처리하는 **Claude Code 멀티에이전트 최종 구조**.
4개 레포(platform-docs · tablet-kiosk-core · MultiAgent-Service-Fullstack-Tree-Framwork · Java-Service-Tree-Framework-Multi-Agent-Workspace)를 분석해 장점만 합쳤습니다.
설계 근거와 측정은 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

| | 기존 M | 기존 J | 기존 kiosk | **NOMAD Agent OS** |
|---|---|---|---|---|
| 상시 로드(추정 토큰) | 7,551 | 12,678 | 5,490 | **3,254** |
| 반복 읽기 차단 | ✗ | ✗ | ✗ | **훅으로 강제 + delta** |
| 그림·미리보기 생성 | 모델 | 모델 | 모델 | **스크립트(토큰 0)** |
| 오픈소스 도구·로컬 LLM | ✗ | ✗ | ✗ | **AGENTS.md 정본 + oss** |

## 설치 (macOS · Linux · Windows는 Git Bash)

**필요:** [Claude Code](https://claude.com/claude-code), git, Python 3.8+, (다이어그램 렌더링 시) Node.js — `npx`로 mermaid-cli 자동 사용.
Windows는 python.org 설치본을 쓰고, *설정 > 앱 > 앱 실행 별칭*에서 `python.exe`·`python3.exe` 스텁을 끄세요.

**1. 받기**
```bash
git clone https://github.com/DevOps0906/nomad-agent-os.git
cd nomad-agent-os
```

**2. 전역 설치** — 모든 프로젝트에서 같은 팀을 씁니다.
```bash
bash install.sh                 # ~/.claude: 팀 10명 · 스킬 7 · 명령 7 · 도구 12 · 훅
# 옵션: --no-path (PATH 등록 안 함), --codex (Codex CLI 전역 AGENTS.md에도 규칙 추가)
```
기존 `~/.claude/CLAUDE.md`·`settings.json`은 덮어쓰지 않고 한 줄 import·훅만 추가합니다. 같은 이름의 에이전트·스킬·명령은 백업 후 교체합니다(백업: `~/.claude/.nomad-backup/<시각>/`).
`~/.claude/nomad/bin`이 `~/.bashrc`(zsh면 `~/.zshrc`)의 PATH에 추가되니 **새 터미널**을 여세요.

> 1~2단계는 **PC마다 한 번**입니다. 새 프로젝트를 할 때마다 이 저장소를 다시 받지 않습니다.

**3. 프로젝트 적용** — 프로젝트마다 한 번. 어느 폴더에서 실행해도 됩니다.
```bash
bash ~/work/nomad-agent-os/install.sh init ~/work/내프로젝트                 # AGENTS.md 제목 = 폴더명
bash ~/work/nomad-agent-os/install.sh init ~/work/내프로젝트 --name "표시 이름"  # 제목 직접 지정
```
AGENTS.md · CLAUDE.md · rules · tasks를 복사합니다. 기존 파일은 보존·병합하고, `.git`과 원격 연결은 건드리지 않습니다(git 명령을 실행하지 않음).
그다음 `AGENTS.md`의 스택·명령·고유 규칙을 채우고, 프로젝트 폴더에서 `claude` 실행 → `/plan` 또는 `/next`.

- **이미 GitHub 저장소가 있으면:** 먼저 `git clone` → 그 폴더에 `init` → 추가된 파일을 커밋. (순서를 바꾸면 clone이 "폴더가 비어 있지 않음"으로 실패)
- **이 저장소 안의 경로는 거부됩니다.** 원본에 프로젝트 파일이 섞이지 않도록, 프로젝트는 항상 이 저장소 밖에 둡니다.

**4. 확인**
```bash
token-audit ~/work/내프로젝트    # 상시 로드 토큰 측정 (PATH 미등록 시 ~/.claude/nomad/bin/token-audit)
```
Claude Code에서 `/agents`를 열어 팀 10명이 보이면 끝입니다.

**업데이트:** 받은 폴더에서 `git pull && bash install.sh` — 다시 실행해도 훅·import는 중복 추가되지 않습니다.

## 매일 쓰는 법

| 하고 싶은 일 | 명령 |
|---|---|
| 다음 작업 하나를 팀으로 끝내기 | `/next` (끝나면 `/clear` 후 다시 `/next`) |
| 기획 (린 검증 → PRD → 명세 → 작업 분해) | `/plan 제품명` |
| 디자인 시스템 (토큰 → 3구간 폰트 → 미리보기) | `/design` |
| 구조도·흐름도·ERD | `/diagram erd` · `/diagram 결제 흐름` |
| 린트·타입·테스트 실패만 요약 | `/check` |
| 상시 로드 토큰 점검 | `/token-audit` |
| 단순 작업을 로컬 LLM에 | `/oss 이 로그 3줄 요약` |

## 팀

| 직급 | 에이전트 | 모델 |
|---|---|---|
| 고문 | advisor (2회 실패 시만) | Fable 5.1 |
| 팀장 | 주 세션 | Opus 5.5 |
| 검증 | challenger (위험 계획) | Opus 5.5 |
| 대리 | builder · planner · designer · tester · reviewer | Sonnet 5.5 |
| 사원 | scout · intern · diagrammer | Haiku 5.5 |

## 도구 (`~/.claude/nomad/bin`)

| 도구 | 하는 일 |
|---|---|
| `q <명령>` | 긴 출력 명령을 실행하고 실패 줄 + 꼬리만 표시, 전체 로그는 `.nomad/logs/` |
| `codemap [폴더] [--tree]` | 파일·export·함수 시그니처 지도 (통독 대신) |
| `delta <파일>` · `delta --changed` · `delta --checkpoint` | 바뀐 줄만(다른 AI 도구용) / 체크포인트 이후 바뀐 파일만 / 체크포인트 저장 |
| `plan-scaffold [docs] --name 제품명` | 기획 문서 8개 뼈대 |
| `design-preview tokens.css -o design/preview.html --md docs/DESIGN_TOKENS.md` · `--init` | 토큰 미리보기 HTML·표 자동 생성 |
| `deps2mmd <소스> -o docs/diagrams/architecture.mmd` | import 분석 구조도 |
| `sql2erd supabase/migrations -o docs/diagrams/erd.mmd [--match ^video_]` | SQL → ERD |
| `mmd-check <파일.mmd>` | Mermaid 검증 + SVG 렌더링 |
| `oss "<지시>" <파일> -o 결과.md` | Ollama 등 로컬 LLM에 위임 |
| `token-audit [프로젝트]` | 상시 로드 토큰 측정·경고 |
| `readguard` · `hook-read` | 반복 읽기 차단 훅 (자동) — 바뀐 파일은 바뀐 줄만 전달, 같은 요청 두 번째는 허용 |

## 제거
`~/.claude/agents|skills|commands`의 NOMAD 파일과 `~/.claude/nomad/`를 지우고, `~/.claude/CLAUDE.md` 첫 줄 `@nomad/TEAM.md`와 `settings.json`의 `hook-read` 훅 3개를 삭제합니다.
