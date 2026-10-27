---
name: stack-supabase
description: Supabase(Postgres·RLS·Auth·Storage·Realtime·Edge Functions·마이그레이션) 작업 규약과 함정. 스키마·정책·시드·타입 생성 작업 전에 읽는다.
---

# stack-supabase

## 30초 요약
1. 모든 테이블에 RLS. 정책이 `true`로 열려 있으면 무방비다. update 정책에는 `with check`.
2. 적용된 마이그레이션 파일은 절대 수정하지 않는다. 변경은 새 번호 파일로.
3. 인가 근거로 사용자가 고칠 수 있는 메타데이터(`user_metadata`)를 쓰지 않는다.
4. 정책 조건 컬럼(`org_id`, `user_id`)에 인덱스.
5. 금액은 정수(원), 시간은 `timestamptz`. 생성 타입 파일은 손으로 고치지 않는다(재생성).
6. 스키마를 바꾸면 ERD를 다시 생성: `~/.claude/nomad/bin/sql2erd supabase/migrations -o docs/diagrams/erd.mmd`.

## 요청별 시작점
| 요청 | 읽을 곳 |
|---|---|
| 테이블·정책·함수 설계 | `references/conventions.md` |
| 리뷰 전 점검 | `references/pitfalls.md` |
| 로컬 실행·타입 생성·테스트 | `references/build-and-run.md` |

## 제출 전
- [ ] `q supabase db reset`(로컬) 성공, 가능하면 `q supabase test db`
- [ ] 새 테이블 RLS + 정책 + 인덱스, 컬럼 변경 시 앱 사용처 Grep
