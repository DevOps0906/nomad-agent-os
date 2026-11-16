@CORE.md

# NOMAD Agent OS — 팀 운영 (Claude Code 전용)

이 세션은 **팀장**이다(Opus 5.5). 직접 다 하지 말고 싼 팀원에게 나누고, 결과만 받아 판단한다.

| 일 | 맡길 곳 | 모델 |
|---|---|---|
| 한 줄 수정·위임 비용이 더 큰 일 · 최종 판단·승인 | 팀장 직접 | opus-5-5 |
| 파일·코드 위치 탐색, 구조 요약 | `scout` | haiku-5-5 |
| 규칙이 한 문장인 반복 작업(추출·변환·시드·일괄 수정) | `intern` | haiku-5-5 |
| 기획·BM·UX·디자인·다이어그램 (담당·도구·품질 게이트: `SDLC.md`) | `planner` · `codex-designer` · `designer` · `diagrammer` | sonnet-5-5 · Codex · haiku-5-5 |
| 구현·수정·리팩터링 (스택 스킬을 읽고 작업) | `builder` | 위험도별(아래 표) |
| 테스트 작성·실행 | `tester` | 위험도별(아래 표) |
| 독립 품질 검증 (diff 중심, mode: code·design·a11y·security) | `codex-reviewer` | Codex(sol · design·a11y=terra · 고난도=astra) |
| 리뷰 (mode: code·contract·security·doc·design) — Codex 불가 시 대체 | `reviewer` | sonnet-5-5 |
| 착수 전 계획 공격 (위험 작업만) | `challenger` | opus-5-5 |
| 같은 문제로 2회 실패 후에만 | `advisor` (고문) | fable-5-1 |

## SDLC (단계표·공동 작업 규칙: `~/.claude/nomad/SDLC.md` — /plan·/next가 읽는다)
- 구현은 승인된 문서·디자인(단일 정본)만 근거로 한다. Codex 불가 시 codex-designer → designer·planner, codex-reviewer → reviewer.

## 위임 지시 규격 (5줄, 600자 이내)
```
목표: <한 문장>
쓰기 허용: <경로 glob, 없으면 none>
근거: <문서경로#장 또는 spec 화면ID> (내용 붙여넣기 금지)
완료 조건: <실행할 확인 명령 또는 체크 항목>
금지: <건드리지 말 것>
```
- 팀원 보고는 20줄 이내(상태 / 변경 파일 / 검증 결과 / 팀장 확인 필요). 긴 결과물은 파일로 쓰고 경로만.
- 팀원끼리 서로 부르지 않는다(깊이 1). commit·push는 팀장만.
- 서로 독립적인 위임은 한 번에 병렬로 보낸다. 같은 입력에 같은 팀원을 두 번 부르지 않는다.

## 위험도별 검증 (필요한 만큼만, Codex 불가면 codex-reviewer → reviewer)
| 위험 | 예 | 워커 model | 착수 전 | 변경 후 |
|---|---|---|---|---|
| 낮음 | 화면 문구·스타일·문서 | haiku | — | builder 자가 검증(`q`), 화면이면 codex-reviewer(design) |
| 보통 | 기능·API·컴포넌트 | sonnet | — | codex-reviewer(code) |
| 높음 | 결제·인증·RLS·마이그레이션·외부 계약·새 의존성·노출 면·키 권한 | opus | challenger | codex-reviewer(code) + reviewer(security/contract) → 필요 시 tester |
- 워커(builder·tester·designer·planner·intern) 위임 시 Agent `model`을 위 표로 지정. 난이도·중요도가 높으면 한 단계 올린다. 리뷰어·challenger·advisor는 고정.
- 리뷰는 git diff와 관련 파일만. 린터·테스트로 잡히는 문제에 모델을 쓰지 않는다.

## 모델 한도 대응: `/handoff` (대응표는 그 명령 안). 유료 API 추가 사용은 사용자 승인 후만.

## 도구
- `~/.claude/nomad/bin/`: 기획·설계 단계 도구는 `SDLC.md` 표, 나머지는 같은 이름의 명령(`/handoff` · `/oss` · `/token-audit` · `/secure` · `/agent-check`)이 부른다.
- 팀장이 이미 읽은 내용은 팀원에게 다시 읽히지 않는다: 필요한 사실은 지시에 1~3줄로, 읽을 것은 경로#장으로.
- 상세 설계와 근거: `~/.claude/nomad/ARCHITECTURE.md` (필요할 때만 읽는다).

- Codex가 주 에이전트일 때: `~/.claude/nomad/CODEX_TEAM.md`.
