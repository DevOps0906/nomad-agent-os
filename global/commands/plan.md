---
description: 기획 문서(린 검증→PRD→명세→작업 분해)를 섹션 병렬로 작성
---
`plan-docs` 스킬 절차로 진행한다. 대상: $ARGUMENTS

1. 문서가 없으면 `~/.claude/nomad/bin/plan-scaffold docs --name "<제품명>"`. 있으면 `scout`로 문서 목록과 목차만 받는다.
2. 팀장이 목차 · 확정 결정 · 미결 질문을 쓴다(본문 쓰지 않음). 제품 방향 미결은 사용자에게 묻는다.
3. 새 제품·기능이면 `00_LEAN.md`부터. 통과 전에는 정식 개발 작업을 만들지 않는다.
   Funnel·CRM·ERP·LMS 같은 도메인이면 먼저 `nomad-os module list` → `module add <이름> .`으로 청사진을 가져와 그 표를 고친다(처음부터 쓰지 않음).
   핵심 화면은 비슷한 제품 3개를 `docs/benchmark.md`로 벤치마킹(ux-patterns 3절) — 채택한 요소는 화면 표 `구성`에 넣는다.
4. 독립 섹션은 `planner` 여러 명에게 병렬 위임(섹션당 근거 경로만 전달). 화면은 `03_SCREENS_UX.md` 표 형식(ux-patterns 2절) 그대로.
   UX·IA·흐름은 `codex-designer`(Codex 중계)와 공동 기획하고 변경분을 교차 검토한다(1회, 심각 충돌 시 1회 추가, 이후 팀장 결정). Codex 불가 보고 시 `designer`로 대체.
5. **화면 표가 채워지면 `~/.claude/nomad/bin/plan2spec`** — 사양(`design/spec.json`) · 구조도 · 흐름도 · 화면↔API↔데이터 연결도 · 와이어프레임을 스크립트가 만든다(diagrammer에게 그리게 하지 않음).
   출력의 🔴(필수 구조 · 상태 미정의 · 없는 ID)는 **작업 분해 전에 0으로** 만든다. 다이어그램은 `mmd-check`로 검증.
6. `reviewer`(mode=doc)로 모순·중복·근거 없는 수치를 점검하고 반영한다. 반영 후 `plan2spec` 재실행(바뀐 화면만 다시 만듦).
   다이어그램은 `diagram` 스킬의 8종 표 기준으로 단계에 맞게 요청한다.
7. 마지막에 작업 분해(`tasks/task-NNN.md`). 화면 작업의 근거는 문서 경로가 아니라 **`spec <화면 ID>`**로 적는다. 수익화·검증 1줄 요약.
   사용자에게는 `design/wireframes/index.html`(3구간 시안)을 열어 확인하도록 안내한다.
