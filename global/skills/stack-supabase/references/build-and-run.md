# stack-supabase — build & run

명령의 정본은 프로젝트 `AGENTS.md` 의 "명령" 표다. 아래는 Supabase CLI 의 일반적인 형태이며
**설치된 CLI 버전의 `--help` 로 확인한 뒤** 사용한다. 이 PC 에서 CLI 가 없거나 Docker 가 없으면 "미검증"으로 보고한다.

| 목적 | 일반 형태 | 비고 |
|---|---|---|
| 로컬 스택 시작 | `supabase start` | Docker 필요 |
| 마이그레이션 생성 | `supabase migration new <name>` | 빈 SQL 파일 생성 |
| 로컬 DB 재현 | `supabase db reset` | 로컬 데이터 초기화 — 로컬 한정 |
| 타입 생성 | `supabase gen types typescript --local` | 출력 경로는 프로젝트 확인 |
| 원격 적용 | `supabase db push` | **원격 변경 — 실행하지 않고 제시만** |

- 원격 프로젝트 연결·적용·삭제는 사용자 확인 대상이다. 에이전트가 실행하지 않는다.
- 환경 변수·키는 `.env*` 에만 두고 저장소에 커밋하지 않는다(`.env.example` 에 키 이름만).
