# 예시: SceneFlow — 기획·설계 문서가 이미 있는 저장소

[← README](../../README.md)

> [시작하기](../GETTING_STARTED.md)의 "A. 기존 저장소에 적용"을 실제 저장소에 적용한 따라하기입니다.

[SceneFlow](https://github.com/DevOps0906/SceneFlow)는 **코드 없이 기획·설계 문서만 있는** 저장소입니다. 이 경우 A 방식(이미 저장소가 있을 때)을 쓰되, 기획을 새로 하지 않고 **있는 문서를 NOMAD가 읽는 자리에 연결**하는 것이 핵심입니다. 아래를 위에서부터 그대로 진행하면 됩니다.

## 0. 먼저 알아 둘 것

**우선순위 원칙 — 멀티에이전트 운영은 NOMAD가 우선합니다.**

| 무엇에 대한 것인가 | 우선 | 예 |
|---|---|---|
| **어떻게 일하나** — 팀 구성 · 위임 · 검증 강도 · 모델 · 작업 파일 형식 · 재진입 · 커밋 흐름 | **NOMAD** (`~/.claude/nomad/TEAM.md` · `CORE.md` · `commands/` · `agents/`) | 06장의 권장 모델(Fable/Opus/…), 안내서의 `claude-main` · `plan-challenger` · `review-expert` 같은 에이전트 이름, `task.md`·`context.md`·`log.md` 3파일 폴더, `gate.sh` 승인 게이트, "main worker는 …" 요청 프롬프트 → **참고만 하고 NOMAD 방식으로 실행** |
| **무엇을 만드나** — 요구사항 · 설계 · 데이터 · API · 화면 · 수용 기준 · 소유 경계 · 절대 규칙 · 착수 전 결정 | **SceneFlow 문서** (`docs/file/`) | PRD, 05_DATA_MODEL, 04-구현/CLAUDE.md 2절 절대 규칙, 06장의 작업 목록 · 웨이브 · 선행 · 수용 기준 → **그대로 따름** |

두 쪽이 부딪히면 위 표로 판정하고, 판정이 애매하면 팀장이 사용자에게 묻습니다. 이 원칙은 2단계에서 `AGENTS.md` 6장에 적어 두어 모든 세션이 따르게 합니다.

**겹치는 에이전트 · 스킬 · 도구 → NOMAD 쪽을 씁니다.** SceneFlow 안내서(9.2 · 9.4 · 10절)에 나오는 이름이 보이면 오른쪽으로 바꿔 읽습니다.

| SceneFlow 안내서 (platform 베이스) | NOMAD에서 대신 쓰는 것 |
|---|---|
| `claude-main` (오케스트레이터, Opus) | **팀장 = 주 세션** (`/next`가 계획 · 위임 · 검증 진행) |
| `plan-challenger` (착수 전 계획 공격) | **challenger** — 위험도 `높음`이면 자동 |
| `claude-reviewer` · `review-expert` | **reviewer** (mode = code · contract · security · doc) |
| `nextjs-expert` · `fastapi-expert` · `supabase-expert` | **builder** + 스킬 `stack-nextjs` · `stack-fastapi` · `stack-supabase` (영역 규칙이 자동 지정) |
| `frontend-design` · `ui-ux-pro-max` 스킬 | **designer** + `design-tokens` 스킬 (`/design`) |
| `deliverable-first` 스킬 · `_index.md` 추출 | `docs/file/_index.md`는 이미 완성본 → **scout**로 필요한 산출물만 찾기 |
| Haiku 작업 ("오케스트레이터가 직접 처리") | **intern** |
| 고문 Fable | **advisor** — 같은 문제 2회 실패 시만 |
| `tasks/<ID>/task.md · context.md · log.md` | `tasks/README.md` 작업 표 + `tasks/VID-06-###.md` 1파일 + `tasks/NOW.md` |
| `workers_approved` · `gate.sh` · `scope_check.sh` | 작업 파일의 **쓰기 허용** 행 + 위험도별 검증 (사용자 확인이 필요한 결정만 묻기) |
| `log.md`의 `[DECISION]` · `[APPROVAL]` | `tasks/NOW.md` "열린 결정" + 커밋 본문 |
| `reentry-check.sh` (재진입 점검) | `tasks/NOW.md` + `delta --changed` (`/next`가 자동) |
| `/agent-check` · `check-invariants.sh` | `/check` (AGENTS.md 명령 표 실행) |
| `llm-wiki` 스킬 (개발 위키 `docs/wiki/`) | NOMAD에 대응 없음 → **`docs/wiki/`는 문서로 유지**, 갱신이 필요하면 작업으로 등록해 planner에게 |

> ⚠️ **프로젝트에 같은 이름의 에이전트를 만들지 않습니다.** Claude Code는 프로젝트 `.claude/agents/`의 에이전트를 같은 이름의 전역(`~/.claude/agents/`) 에이전트보다 우선합니다. SceneFlow에 `builder.md` · `reviewer.md` 같은 파일이 생기면 NOMAD 팀원이 조용히 바뀌므로, 생겼다면 지우거나 다른 이름으로 바꿉니다. 확인: `ls .claude/agents 2>/dev/null` (아무것도 없어야 정상).

| SceneFlow에 이미 있는 것 | 위치 | NOMAD에서 쓰는 법 |
|---|---|---|
| 산출물 25개 (PRD · 아키텍처 · 화면 · API · 데이터 · 공용코어 · 디자인) | `docs/file/` (등록부 `_index.md`) | **정본 그대로 사용.** `AGENTS.md` 문서 지도에 경로만 연결 |
| 작업 114개 · 웨이브 W0~W8 · 소유 경계 · 수용 기준 | `docs/file/01-관리/06_AGENT_PLAN.md` | 웨이브 단위로 `tasks/`에 옮겨 `/next`로 실행 |
| 개발지침 (절대 규칙 · 디렉토리 소유 · 코드 규칙 · 완료 조건) | `docs/file/04-구현/CLAUDE.md` (181줄) | 핵심만 `AGENTS.md`에 요약, 상세는 작업 영역 절만 읽기 |
| 착수 전 결정 D-1 ~ D-29 | `docs/file/02-요구사항/01_PRD.md` 8절 | 해당 작업 직전에 확정 (`tasks/NOW.md` 열린 결정) |
| 대시보드 시안 · 디자인 시스템 기준 | `design/dashboard-canvas/` · `docs/file/03-설계/디자인/` | `/design`의 근거로 사용 |

> ⚠️ **둘 중 하나만 쓰세요.** SceneFlow 개발 안내서(`docs/guide/sceneflow_develop.md`)는 platform 베이스를 복사하는 `setup-sceneflow.sh`로 **별도의 에이전트 체계**(`claude-main` · `plan-challenger` · `_shared/` · `gate.sh` …)를 설치합니다. NOMAD를 쓴다면 이 setup 스크립트는 **실행하지 않습니다.** 두 체계를 같이 깔면 루트 `CLAUDE.md`와 에이전트가 겹쳐 지시가 충돌합니다. 안내서의 3~5장(베이스 복사 · project-profile) 대신 아래 1~4단계를, 9~10장(task 변환 · 웨이브 사이클) 대신 5~7단계를 씁니다. 그 밖의 장(결정 · AI 계층 · 디자인 · 인증 단계 · 위험)은 그대로 유효합니다.
>
> ⚠️ **`/plan`으로 기획을 다시 만들지 않습니다.** `plan-scaffold`가 `docs/00_LEAN.md` 등을 새로 만들어 기존 `docs/file/`과 중복됩니다. `/plan`은 나중에 *새 기능*을 추가할 때만, "기존 `docs/file/` 체계에 추가해줘"라고 지시해서 씁니다.

## 1. 받기 + NOMAD 적용
**Git Bash**
```bash
bash ~/workspace/dev/nomad-agent-os/install.sh            # PC에서 처음이면 1번만 (이미 했으면 생략)

cd ~/workspace/dev
git clone https://github.com/DevOps0906/SceneFlow.git
nomad-os init ~/workspace/dev/SceneFlow --name SceneFlow

cd SceneFlow
git status --short        # 새로 생긴 것: AGENTS.md CLAUDE.md .claude/ .codex/ .gemini/ .geminiignore .gitignore tasks/  (기존 파일 변경 없음)
claude
```
**PowerShell**
```powershell
~\workspace\dev\nomad-agent-os\install.ps1            # PC에서 처음이면 1번만 (이미 했으면 생략)

cd ~\workspace\dev
git clone https://github.com/DevOps0906/SceneFlow.git
nomad-os init ~\workspace\dev\SceneFlow --name SceneFlow

cd SceneFlow
git status --short
claude
```

## 2. `AGENTS.md` 채우기 — 모든 AI 도구가 매번 읽는 1장 (80줄 이내)
Claude에게 그대로 요청합니다.
```text
docs/file/04-구현/CLAUDE.md, docs/file/03-설계/02_ARCHITECTURE.md 1~2절, docs/file/_index.md 를 근거로
AGENTS.md 를 SceneFlow에 맞게 채워줘. 80줄 이내로, 아래 원칙을 지켜줘.
- 1장: 한 문장 설명 + 정본은 docs/file/, 상세 개발지침은 docs/file/04-구현/CLAUDE.md (작업 영역 절만 읽기)
- 2장 스택: apps/sceneflow(Next.js 16·React 19·Tailwind CSS v4) · supabase/ · workers/video-orchestrator(BullMQ)
  · services/media-worker(Python 3.11) · apps/api(FastAPI 3.12·LangGraph) · packages/sns-uploader
- 3장 명령: 04-구현/CLAUDE.md 6절 표를 그대로 (아직 코드가 없으니 "W1 이후 확정" 표시)
- 4장 절대 규칙: 04-구현/CLAUDE.md 2절에서 위반 시 사고가 나는 것만 8개 이내 (service_role · 크레딧 선차감 · 스키마 소유 · LLM 키 위치 · AI 경계 · 대가성 문구 · Tailwind v4 · 토큰 정답)
- 5장 문서 지도: docs/file/ 산출물 경로 표 (템플릿의 docs/01_PRD.md 같은 경로는 실제 경로로 교체)
- 6장 작업 방식: 작업 ID는 VID-06-###, 커밋은 "[VID-06-###] 요약", 쓰기 허용 경로 밖은 수정하지 않고 요청 작업을 남김,
  구현이 산출물과 다르면 코드를 맞추지 말고 산출물 갱신 작업을 따로 만듦
- 6장 맨 위에 우선순위 원칙: "멀티에이전트 운영(팀 구성·위임·검증·모델·작업 형식)은 NOMAD(~/.claude/nomad/TEAM.md)가 우선한다.
  docs/의 권장 모델·에이전트 이름(claude-main 등)·task 폴더 형식·gate.sh는 참고만 한다.
  요구사항·설계·수용 기준·소유 경계·절대 규칙은 docs/file/이 정본이다."
```
완성되면 첫 부분이 이런 모양이 됩니다.
```markdown
# AGENTS.md — SceneFlow
## 1. 무엇인가
말로 지시하면 AI가 편집안을 만들고 승인하면 실행하는 AI 자동편집 영상 SaaS. 정본: `docs/file/`(등록부 `_index.md`).
상세 개발지침: `docs/file/04-구현/CLAUDE.md` — 작업 영역의 절만 읽는다.
## 2. 스택
| 영역 | 선택 | 위치 |
|---|---|---|
| 웹 | Next.js 16 · React 19 · TS strict · Tailwind CSS v4 · shadcn/ui · zod · TanStack Query | `apps/sceneflow` |
| DB | Supabase (Postgres · pgvector · RLS) | `supabase/` |
| 오케스트레이터 | Node 20 · BullMQ FlowProducer | `workers/video-orchestrator` |
| 미디어 워커 | Python 3.11 · Whisper · demucs · FFmpeg | `services/media-worker` |
| AI 서비스 | FastAPI · Python 3.12 · LangGraph (LLM 키는 여기에만) | `apps/api` |
...
```

## 3. 영역 규칙 경로를 SceneFlow 구조에 맞추기
템플릿 규칙은 `apps/web/**` 기준이라 그대로 두면 **로드되지 않습니다.** Claude에게 요청합니다.
```text
.claude/rules/ 를 SceneFlow 디렉토리에 맞게 고쳐줘.
- web.md: paths 를 apps/sceneflow/** 로. "UI 작업이면 docs/file/03-설계/디자인/DESIGN_SYSTEM.md 먼저, 토큰 정답은
  apps/sceneflow/src/styles/tokens.css, 화면 작업은 VID-06-044 완료 뒤" 추가
- api.md: docs/04_API.md → docs/file/03-설계/04_API.md. "FastAPI는 영상·오디오 바이너리를 처리하지 않는다" 추가
- db.md: "video 스키마 변경은 VID-06-001(이후 066, 085)만", ERD 명령에 --match 로 영역 분할 추가
- docs.md: docs/file/ 은 DOC_TEMPLATE 체계를 따르고, 산출물 상태를 바꾸면 _index.md 변경 이력에 기록
- workers.md 새로 만들기: paths workers/** · services/media-worker/** · packages/sns-uploader/**,
  "미디어 워커와 FastAPI는 서로 호출하지 않는다, 미디어 워커는 LLM·ElevenLabs 키를 갖지 않는다, 하위 프로세스는 인자 배열·타임아웃·kill"
- AGENTS.md 7장 영역 규칙 표도 같은 경로로 고치고 workers.md 행을 추가 (ChatGPT Codex · Gemini는 이 표를 보고 규칙을 읽음)
```

## 4. 첫 커밋
```bash
git add -A
git commit -m "Add NOMAD agent config (AGENTS.md, rules, tasks)"
git push
```

## 5. 모델 배정 옮기기 — 06_AGENT_PLAN의 "권장 모델" → NOMAD 위험도
SceneFlow 계획서는 작업마다 권장 모델을 적어 두었습니다. NOMAD에서는 이것을 **위험도**로 바꾸면 검증 강도가 자동으로 맞춰집니다(전역 `TEAM.md` 위험도별 검증 표).

| 06장 권장 모델 | 작업 성격 | NOMAD 위험도 | 담당 | 자동으로 붙는 검증 |
|---|---|---|---|---|
| Fable | 결제 · 권한 · RLS · 데이터 모델 · 오케스트레이터 · AI 보안 | **높음** | builder | 착수 전 **challenger** → 변경 후 reviewer(code + security/contract) → 필요 시 tester |
| Opus | 기능 구현 · API 연동 · 워커 · 그래프 · 테스트 설계 | **보통** | builder (테스트 작업은 tester) | reviewer(code) |
| Sonnet | UI · 컴포넌트 · 3D 히어로 · 문서 | **낮음** (화면은 보통) | builder · designer · planner(문서) | builder 자가 검증 |
| Haiku | 보일러플레이트 · 린트 · 문구 · 반복 체크 | 낮음 | intern | — |
| 사람 | VID-06-043 디자인 검토 · G1/G2 게이트 · 원본 삭제 승인 | — | **사용자** (상태 `보류`) | 사용자가 판정 후 `완료` |

같은 문제로 2번 실패하면 advisor(Fable)가 자동 투입되므로 "Fable 작업"을 따로 Fable로 돌릴 필요는 없습니다.

## 6. 작업을 웨이브 단위로 `tasks/`에 옮기기
114개를 한 번에 옮기지 않습니다. **지금 시작할 웨이브만** 옮기고, 끝나면 다음 웨이브를 옮깁니다.
```text
docs/file/01-관리/06_AGENT_PLAN.md 2절(작업 목록)과 3절(웨이브)에서 W0 작업(VID-06-001, 040, 041)만
tasks/ 로 옮겨줘.
- tasks/README.md 작업 표: 번호=VID-06-###, 웨이브, 선행, 위험도(권장 모델 → 위 표 기준), 담당, 상태=대기. 템플릿 예시 행 task-001은 삭제
- 작업마다 tasks/VID-06-###.md (plan-docs 의 task 템플릿):
  근거 = 06_AGENT_PLAN.md 해당 행 + 그 행의 "출처" 문서#절, 쓰기 허용 = "소유 파일/디렉토리" 열,
  완료 조건 = "수용 기준" 열을 실행 가능한 확인으로, 하지 않을 것 = 다른 작업 소유 경로·원격 db push
- 이 웨이브에 걸린 착수 전 결정(01_PRD.md 8절, 예: VID-06-001 전 D-1, VID-06-041 전 D-19)을 tasks/NOW.md "열린 결정"에 적어줘
```
결과 예시 (`tasks/README.md`):
```markdown
| 번호 | 제목 | 웨이브 | 선행 | 위험도 | 담당 | 상태 |
|---|---|---|---|---|---|---|
| VID-06-001 | 1200 조각 적용 · 모놀리스 변환 · 타입 생성 | W0 | — | 높음 | builder | 대기 |
| VID-06-040 | 원본 정리 (git 태그 · 삭제는 사용자 승인 후) | W0 | — | 보통 | builder | 대기 |
| VID-06-041 | 디자인 레퍼런스 (디자인 시스템 1단계) | W0 | — | 낮음 | designer | 대기 |
```
결과 예시 (`tasks/VID-06-001.md`의 머리):
```markdown
| 항목 | 내용 |
|---|---|
| 웨이브 | W0 |
| 위험도 | 높음 (06장 권장 Fable: 데이터 모델) |
| 근거 | `docs/file/01-관리/06_AGENT_PLAN.md#2` VID-06-001 행 · `docs/file/03-설계/05_DATA_MODEL.md` · `docs/file/03-설계/공용코어/DB_CONVENTIONS.md` |
| 쓰기 허용 | `supabase/migrations/1200_video.sql` · `supabase/monolith/**` · `scripts/mono-convert.mjs` · `apps/sceneflow/src/types/supabase.ts` |
## 완료 조건
- [ ] `supabase db reset` 오류 0
- [ ] 타입 파일에 26개 테이블, AI 라우팅 17행 · 체인 검사 DO 블록 통과
```

## 7. 개발 반복 — 웨이브 사이클
```text
① 결정 확인   tasks/NOW.md 의 열린 결정을 사용자가 확정 (예: "D-1은 권고안대로 public 스키마")
② /next VID-06-001   → 팀장 계획 5줄 → 위험도 높음이라 challenger 먼저 → builder 구현 → reviewer(code+security) → 완료 조건 실행 → 커밋 [VID-06-001]
③ /clear → /next     → 다음 대기 작업 (tasks/NOW.md 에서 이어감)
④ 웨이브의 작업이 모두 완료 → 6단계 요청을 "W1 작업만"으로 바꿔 다시 실행 → ② 반복
```
| 웨이브 | 이때 쓰면 좋은 명령 |
|---|---|
| W0 (DB 적용) | 끝나면 ERD: `/diagram erd` → 77개 테이블이라 영역별 분할 — `sql2erd supabase/migrations -o docs/diagrams/erd-ai.mmd --match '^ai_'` (그 밖에 `^(storyboard\|longform\|edit)_`, `^(affiliate\|linkinbio)_` 등) |
| W1 (앱 · 워커 · AI 골격) | 골격이 생기면 `AGENTS.md` 3장 명령을 실제 값으로 확정 → `/check`로 확인 |
| W1-D (디자인 036 → 042 → **043 사람** → 044) | `/design` + "근거는 docs/file/03-설계/디자인/DESIGN_SYSTEM.md 와 design/dashboard-canvas/ 시안, 토큰 파일은 apps/sceneflow/src/styles/tokens.css" → 미리보기를 **직접 보고 확정**해야 화면 작업(W3~) 시작 |
| W2 ~ W6 | `/next` 반복. 웨이브 끝마다 `/diagram 코드 구조도`로 실제 구조 확인 |
| W7 (G1 → 063) · W8 (G2 → 064 · 065) | G1 · G2는 사람이 판정 (`docs/guide/sceneflow_develop.md` 19.3 · 19.5 체크리스트) → `tasks/NOW.md`에 "G1 통과" 기록 후 `/next` |

## 8. 진행 체크리스트
- [ ] `setup-sceneflow.sh`를 실행하지 않았다 (NOMAD와 이중 설치 방지)
- [ ] `AGENTS.md` 6장에 우선순위 원칙(운영은 NOMAD, 내용은 `docs/file/`)이 적혀 있다
- [ ] 프로젝트 `.claude/agents/`가 비어 있다 (NOMAD 팀원을 덮어쓰는 같은 이름 에이전트 없음)
- [ ] `AGENTS.md`가 80줄 이내이고, 문서 지도가 `docs/file/` 실제 경로를 가리킨다
- [ ] `.claude/rules/web.md` paths가 `apps/sceneflow/**`이고, `workers.md`가 있다
- [ ] `AGENTS.md` 7장 영역 규칙 표가 `.claude/rules/`의 실제 paths와 같다 (ChatGPT Codex · Gemini용)
- [ ] `tasks/README.md`에는 **현재 웨이브만** 있고, 예시 행 `task-001`은 지웠다
- [ ] 각 작업의 착수 전 결정(D-#)을 그 작업 직전에 확정했다
- [ ] 사람 작업(VID-06-043, G1, G2, VID-06-040의 삭제)은 `보류`로 두고 직접 판정했다
- [ ] 구현이 산출물과 달라지면 산출물 갱신 작업을 만들고, `_index.md` 상태 · 변경 이력을 고쳤다
