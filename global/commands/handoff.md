---
description: 모델 한도 전에 작업을 체크포인트하고 Codex/Sonnet 이관 준비
---
Claude가 아직 살아 있을 때 쓴다. (한도가 완전히 소진됐다면 터미널에서 `handoff codex`를 직접 실행)

1. `tasks/NOW.md`를 지금 상태로 갱신한다: SDLC 단계 · 담당 모델/역할 · 수정 파일 · 테스트 상태 · 남은 작업.
2. `~/.claude/nomad/bin/delta --checkpoint` 실행.
3. `~/.claude/nomad/bin/handoff codex --dry-run` 실행 → 생성된 `.nomad/handoff/<시각>.md` 경로를 사용자에게 알린다.
4. 안내: 이어서 하려면 터미널에서 `handoff codex`(Codex) 또는 `handoff sonnet`(Opus만 한도), 돌아올 때는 `handoff claude`.
