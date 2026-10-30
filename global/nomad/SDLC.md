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
