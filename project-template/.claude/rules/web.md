---
paths:
  - "apps/web/**"
---
# 웹 영역 규칙 (apps/web/** 작업 때만 로드)
- 먼저 `~/.claude/skills/stack-nextjs/SKILL.md`를 읽는다.
- 화면은 `DESIGN.md`와 `src/styles/tokens.css`(정답)를 따른다. 3구간(~767 / 768~1199 / 1200~)을 모두 확인한다.
- 서버 전용 코드는 `src/server/**`에만. 브라우저에서 LLM·결제·service_role을 직접 부르지 않는다.
