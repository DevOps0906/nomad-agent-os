---
name: diagram
description: 구조도·흐름도·시퀀스·상태도·ERD·마인드맵을 Mermaid 텍스트로 싸게 만드는 규칙. ERD는 sql2erd 기계 생성, 검증·렌더링은 mmd-check. "다이어그램", "구조도", "흐름도", "ERD" 요청 시 사용.
---

# diagram — 그림은 텍스트로

## 왜 Mermaid인가 (토큰)
같은 구조도를 SVG·draw.io XML로 만들면 Mermaid보다 수십 배 길다. Mermaid는 고치기도 한 줄이다.
렌더링(SVG·PNG)은 오픈소스 `mermaid-cli`가 하고 모델은 하지 않는다.

## 종류 고르기
| 보여줄 것 | Mermaid 타입 | 비고 |
|---|---|---|
| 시스템 구성·경계 | `flowchart LR` + `subgraph` | 계층별 subgraph, 노드 ≤ 25 |
| 요청 순서·API 흐름 | `sequenceDiagram` | 참여자 ≤ 6 |
| 상태 변화(결제·주문) | `stateDiagram-v2` | 상태 값은 코드의 enum과 같은 이름 |
| 테이블 관계 | `erDiagram` | **`sql2erd`로 생성**, 손으로 그리지 않음 |
| 일정·웨이브 | `gantt` | |
| 기능 구조·아이디어 | `mindmap` | |
| 사용자 여정 | `journey` | |

## 규칙
1. 파일 하나에 다이어그램 하나: `docs/diagrams/<이름>.mmd`. 문서에는 경로로 링크하거나 코드블록으로 그대로 포함한다.
2. 노드 ID는 짧은 영문(`api`, `db`), 표시 이름은 한국어 라벨(`api["API 서버"]`). 라벨에 괄호·따옴표가 있으면 `"..."`로 감싼다.
3. 스타일·색 지정은 하지 않는다(테마가 처리). `classDef`는 강조가 꼭 필요할 때 1개만.
4. 25노드를 넘으면 개요 1장 + 영역별 상세로 나눈다.
5. 생성 후 반드시 `~/.claude/nomad/bin/mmd-check <파일>`. 통과해야 끝난다.

## 기계 생성 (모델 토큰 0)
- ERD: `~/.claude/nomad/bin/sql2erd supabase/migrations -o docs/diagrams/erd.mmd` (CREATE TABLE·REFERENCES 해석, 25테이블 초과 시 `--match '^video_'`로 분할)
- 모듈 구조도: `~/.claude/nomad/bin/deps2mmd apps/web/src -o docs/diagrams/architecture.mmd --depth 2` (import 분석, `--external`로 외부 패키지 포함)
- 폴더 구조: `~/.claude/nomad/bin/codemap <폴더> --tree` 출력을 그대로 문서에 붙인다.
