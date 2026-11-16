---
paths:
  - "supabase/**"
---
# DB 영역 규칙 (supabase/** 작업 때만 로드)
- 먼저 `~/.claude/skills/stack-supabase/SKILL.md`를 읽는다.
- 마이그레이션 파일명: `YYYYMMDDHHMMSS_<설명>.sql`. 적용된 파일 수정 금지.
- 새 테이블 = RLS 활성 + 정책 + 정책 컬럼 인덱스 + 코멘트 한 줄.
- 스키마를 바꾼 작업은 ERD와 타입을 갱신한다.
  - DB 초기화 · 타입: `supabase db reset` · `supabase gen types typescript --local > apps/web/src/types/db.ts`
  - ERD: `~/.claude/nomad/bin/sql2erd supabase/migrations -o docs/diagrams/erd.mmd`
