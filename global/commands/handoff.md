---
description: 모델 한도 전에 작업을 체크포인트하고 Codex/Sonnet 이관 준비
---
Claude가 아직 살아 있을 때 쓴다. (한도가 완전히 소진됐다면 터미널에서 `handoff codex`를 직접 실행)

1. `tasks/NOW.md`를 지금 상태로 갱신한다: SDLC 단계 · 담당 모델/역할 · 수정 파일 · 테스트 상태 · 남은 작업.
2. `~/.claude/nomad/bin/delta --checkpoint` 실행.
3. `~/.claude/nomad/bin/handoff codex --dry-run` 실행 → 생성된 `.nomad/handoff/<시각>.md` 경로를 사용자에게 알린다.
4. 안내: 이어서 하려면 터미널에서 `handoff codex`(Codex) 또는 `handoff sonnet`(Opus만 한도), 돌아올 때는 `handoff claude`.

## 대응표 (TEAM.md에서 옮김) (반자동 — 상태는 항상 `tasks/NOW.md`에)
| 상황 | 대응 |
|---|---|
| Opus만 제한 | `handoff sonnet` → Sonnet이 임시 팀장 |
| Sonnet·Claude 전체 제한 | `handoff codex` → Codex가 NOW.md·변경 파일로 이어서 수행 |
| Codex도 제한 | 다른 가용 모델 확인(`oss`), 없으면 체크포인트 후 안전 중단 |
| 복귀 | `handoff claude` → NOW.md + `delta --changed`로 재개 |
- 같은 제공자의 공유 한도는 모델 이름만 바꿔도 소용없다 — 실제 가용성 확인. 유료 API 추가 사용은 사용자 승인 후만.
