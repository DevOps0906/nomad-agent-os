# NOMAD SDLC 9단계 — /plan · /next 가 읽는다 (TEAM.md에서 분리, 상시 로드 아님)

## 단계표 (02~07은 기능 단위로 반복, 단계마다 `tasks/NOW.md` 갱신)
| 단계 | 주담당 | 필수 산출물 | 다음 단계 조건 |
|---|---|---|---|
| 01 검증 | 팀장 + planner·codex-designer | `00_LEAN` 시장 검증·MVP 가설 | 수요·문제 확인 |
| 02 기획 | planner ⇄ codex-designer | `01_PRD`·기능 명세 | 범위 승인 |
| 03 UX | codex-designer ⇄ planner | IA·사용자 흐름·와이어(`03_SCREENS_UX`·`plan2spec`) | 흐름 검증 |
| 04 UI | codex-designer ⇄ designer | 토큰·DESIGN.md·Figma·미리보기 | 디자인 승인 |
| 05 기술 설계 | planner ⇄ codex-designer · diagrammer | 아키텍처·ERD·API·ADR (`.mmd` 원본) | 구현 계약 확정 |
| 06 구현 | builder (+ tester) | 코드·테스트 | 빌드·테스트 통과 |
| 07 QA | codex-reviewer (+ reviewer) | 리뷰·디자인 QA | 🔴 해결 |
| 08 배포 | builder + 팀장 승인 | 배포 기록·운영 설정 | 릴리스 승인 |
| 09 개선 | 팀장 + planner·codex-designer | 피드백·개선 백로그 | 차기 우선순위 |
- 공동 작업: 초안은 한쪽이 쓰고 상대는 **변경분만** 교차 검토 1회 → 심각한 충돌만 1회 더 → 이후 팀장이 결정. 작은 수정은 생략.

## 기획·설계 담당과 도구 (TEAM.md에서 이동)
| 일 | 담당(모델) | 스킬 · 도구 (`~/.claude/nomad/bin/`) |
|---|---|---|
| 린 검증·PRD·기능 명세·기술 타당성·ADR·작업 분해 | `planner` (sonnet-5-5) | `plan-docs` · `plan-scaffold`(뼈대) · `docmap`(바뀐 장만) |
| BM·사업성 7단계 (`/bm`) | `planner` (sonnet-5-5) | `bm-model` · 숫자는 `bm-calc`만 |
| UX·IA·흐름·와이어 초안, planner 초안 교차 검토 | `codex-designer` (Codex gpt-6.1-sol) | `ux-patterns` · `plan2spec`(화면 표→사양) · `spec <ID>` |
| 디자인 토큰·DESIGN.md·화면 미리보기 | `designer` (sonnet-5-5) | `design-tokens` · `design-preview` · `shot` |
| 구조도·흐름도·시퀀스·ERD (Mermaid) | `diagrammer` (haiku-5-5) | `diagram` · `deps2mmd` · `sql2erd` · `mmd-check` |

## 기획 품질 게이트 (단계를 넘기기 전에 팀장이 확인, 하나라도 ❌면 넘기지 않는다)
| 단계 | 통과 조건 |
|---|---|
| 01→02 | 가설마다 검증 방법·통과 기준(숫자)·결과가 있다. 통과 못 한 가설은 범위에서 빠졌다 |
| 02→03 | 요구사항마다 ID·수용 기준(관찰 가능한 결과)·MVP/이후 구분이 있다. 성공 지표는 측정 방법과 목표값이 함께 있다. 비즈니스 규칙(계산·판정)은 정본 1곳에만 있고 나머지는 링크한다. 미결 질문 표가 비었거나 담당·기한이 있다 |
| 03→04 | 모든 요구사항 ID가 화면 1개 이상에 연결된다. 화면마다 빈·로딩·오류·권한 없음 상태가 정의된다. `plan2spec` 필수 구조 🔴 0 |
| 04→05 | 토큰만 사용(색·크기 직접 값 0), 반응형 3구간·구간별 폰트, 대비 WCAG AA. 화면 구현 작업마다 위험도(낮음/보통/높음)가 지정됐다 |
| 05→06 | 화면의 모든 데이터가 API·테이블로 추적된다. 권한(RLS)·오류 코드가 표에 있다. 되돌리기 어려운 결정은 ADR로 남겼다. `mmd-check` 통과 |
| 작업 분해 | 작업마다 근거(문서#장)·완료 조건(실행 가능한 명령)·하지 않을 것·위험도(낮음/보통/높음 → 워커 model)가 있다 |
- 확인은 reviewer(mode=doc)에 위 표의 해당 행을 체크리스트로 넘겨 맡긴다. 결과는 행마다 ✅/❌ 한 줄로 받는다.
