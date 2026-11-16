# AGENTS.md — <프로젝트명>

> 모든 AI 코딩 도구(Claude Code · ChatGPT Codex · Gemini CLI · OpenCode · Cursor)가 읽는 **단일 정본**. 80줄 이내로 유지한다.
> 영역별 상세 규칙은 `.claude/rules/*.md`(7장 표), 기획 근거는 `docs/`.

## 1. 무엇인가
<한 문장: 누구를 위한 무엇>. 기획 정본: `docs/01_PRD.md` · 구조: `docs/02_ARCHITECTURE.md`.

## 2. 스택 (작업 시 최신 stable 확인 후 버전 고정)
| 영역 | 선택 | 위치 |
|---|---|---|
| 웹 | Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · shadcn/ui | `apps/web` |
| DB·인증 | Supabase (Postgres · RLS · Auth · Storage · Edge Functions) | `supabase/` |
| API·AI | FastAPI · Pydantic v2 (LLM 키는 여기에만) | `apps/api` |
| 앱 | (해당 시) Flutter · Riverpod 3 · go_router · drift | `apps/app` |

## 3. 명령
| 목적 | 명령 |
|---|---|
| 설치 | `pnpm install` |
| 개발 서버 | `pnpm dev` |
| 린트 · 타입 | `pnpm lint` · `pnpm typecheck` |
| 테스트 | `pnpm test` · `cd apps/api && pytest -q` |
긴 출력 명령은 `~/.claude/nomad/bin/q <명령>`으로 실행한다.

## 4. 절대 규칙 (위반 = 리뷰 🔴)
- 비밀(API 키 · service_role · 결제 키)은 저장소·클라이언트 번들·로그에 넣지 않는다. `.env.example`에 이름만.
- 모든 테이블 RLS. 적용된 마이그레이션 파일은 수정하지 않고 새 번호 파일로 추가한다.
- 금액은 정수(원). 결제·차감 요청에는 멱등 키.
- UI는 반응형 3구간(~767 / 768~1199 / 1200~), 색·크기는 토큰만(hex·px 직접 금지).
- 문서·커밋·화면 문구는 한국어, 코드 식별자는 영어.
- 새 의존성은 `secscan license`로 확인(GPL·AGPL 거부). 보안 레벨 `docs/01_PRD.md#8`.
- <프로젝트 고유 규칙을 여기에 — 5개 이내>

## 5. 문서 지도 (필요한 장만 읽는다)
`docs/00_LEAN`(린 검증) · `01_PRD`~`05_DATA_MODEL`(기획·구조·화면·API·데이터) · `docs/diagrams/*.mmd` · `DESIGN.md`(정답은 `apps/web/src/styles/tokens.css`) · `tasks/README.md`(작업 표)·`NOW.md`(현재 상태)

## 6. 작업 방식
작업은 `tasks/README.md`의 순서대로 하나씩. 작업 표의 위험도(낮음/보통/높음)가 담당 모델(Claude: haiku/sonnet/opus)과 검증 수준을 정한다. 작업 파일의 "근거"와 "하지 않을 것"을 지키고, 완료 조건을 실행으로 확인한 뒤 커밋한다.
커밋: `[task-NNN] 요약` + 본문(무엇을 · 확인 방법).

## 7. 영역 규칙 · 도구별 로드 (규칙 정본은 `.claude/rules/` 한 곳)
아래 경로의 파일을 만들거나 고치기 **전에** 해당 규칙 파일을 읽는다. Claude Code는 `paths:` 조건으로 자동 로드하므로 다시 읽지 않는다.
| 작업 경로 | 규칙 파일 |
|---|---|
| `apps/web/**` | `.claude/rules/web.md` |
| `apps/api/**` | `.claude/rules/api.md` |
| `supabase/**` | `.claude/rules/db.md` |
| `docs/**` · `DESIGN.md` | `.claude/rules/docs.md` |
- 읽지 않는 파일: `.env*` · lock 파일 · `node_modules/` · `.next/` · `dist/` · `build/` · `coverage/` (Claude는 `.claude/settings.json`, Gemini는 `.geminiignore`가 강제, ChatGPT Codex는 이 줄로 지킨다).
- 새 규칙 파일을 추가하면 이 표에도 한 줄 추가한다.

## 8. Codex 네이티브 팀
- 주 모델은 gpt-6.1-sol, 부 모델은 사용자가 확인한 지원 ID로만 지정한다. 초기 설정은 비활성이다.
- `nomad-os codex init . --worker-model <ID>` 적용 후 새 세션에서 시작하고 `nomad-os codex check .`로 검사한다.
- nomad_scout/designer/builder/tester/reviewer, 부 작업 최대 3개·깊이 1. 소유 파일을 명시하고 타인의 변경을 되돌리지 않는다.
- 위험도 낮음·보통은 부 모델 팀원, 높음은 주 모델이 설계 확정 후 직접 구현하거나 좁혀 맡기고 reviewer·tester 검증.
- 설정 검사와 실제 모델 실행은 별개다. 운영 지침: NOMAD `global/nomad/CODEX_TEAM.md`.
