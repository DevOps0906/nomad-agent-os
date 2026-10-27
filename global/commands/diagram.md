---
description: 구조도·흐름도·시퀀스·ERD를 Mermaid로 생성하고 검증·렌더링
---
`diagram` 스킬 규칙으로 진행한다. 대상: $ARGUMENTS

1. 기계 생성이 되면 모델을 쓰지 않는다: ERD → `sql2erd supabase/migrations -o docs/diagrams/erd.mmd`(25테이블 초과 시 `--match`로 분할),
   코드 구조도 → `deps2mmd <소스 폴더> -o docs/diagrams/architecture.mmd`. (도구 위치 `~/.claude/nomad/bin/`)
2. 그 밖에는 팀장이 노드·관계 목록(코드나 문서의 실제 이름)을 10~25개로 정리한다. 모르면 `scout`가 `codemap`으로 뽑는다.
3. `diagrammer`에게 목록 + 종류 + 저장 경로만 넘긴다(여러 장이면 병렬).
4. 결과는 `mmd-check` 통과본만 채택하고, 문서에는 `.mmd` 경로로 링크한다.
