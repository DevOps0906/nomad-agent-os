---
description: 상시 로드 컨텍스트(CLAUDE.md·에이전트·스킬 설명) 토큰을 측정하고 줄일 곳 제안
---
`~/.claude/nomad/bin/token-audit .` 을 실행하고, 경고 항목마다 고칠 파일과 줄일 방법을 표로 제안한다.
사용자가 승인하면 고친다. 절대 규칙은 줄이지 않고, 경로 한정 규칙은 `.claude/rules/*.md`(paths)로 옮긴다.
