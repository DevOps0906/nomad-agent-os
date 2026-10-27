---
description: 다음 작업 하나를 팀(멀티에이전트)으로 끝까지 진행
---
팀장으로 진행한다. 인자: $ARGUMENTS (작업 번호, 없으면 다음 대기 작업)

1. `tasks/NOW.md`(있으면)와 `~/.claude/nomad/bin/delta --changed`(지난 체크포인트 이후 바뀐 파일만)로 재진입한다 — 문서를 처음부터 다시 읽지 않는다.
   `tasks/README.md`에서 선행이 끝난 가장 앞 `대기` 작업을 고른다.
2. 작업 파일의 "근거" 장만 읽는다. 모르는 위치는 `scout`에게 맡긴다(직접 통독 금지).
3. 계획 5줄 이내: 바꿀 파일 · 순서 · 맡길 팀원 · 완료 확인 방법 · 위험도. 위험도 높음이면 `challenger` 먼저.
4. 사용자 확인이 필요한 결정만 묻고, 나머지는 바로 위임한다(독립 위임은 병렬).
5. 변경 후 위험도별 검증(전역 CLAUDE.md 표). 🔴은 해당 팀원에게 되돌린다. 같은 문제 2회 실패 → `advisor`.
6. 완료 조건을 `~/.claude/nomad/bin/q`로 확인 → `tasks/README.md` 상태 `완료` → 커밋.
7. `tasks/NOW.md`를 다음 작업 기준으로 덮어쓰고(30줄 이내) `~/.claude/nomad/bin/delta --checkpoint` 실행 후 "`/clear` 후 `/next`"를 안내한다.
