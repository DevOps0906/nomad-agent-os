# stack-nextjs — build & run

명령의 정본은 프로젝트 `AGENTS.md` 의 "명령" 표와 `apps/web/package.json` 의 `scripts` 다.
아래는 일반적인 형태이며, **프로젝트의 패키지 매니저(npm · pnpm · yarn)를 확인한 뒤** 사용한다.

| 목적 | 일반 형태 | 비고 |
|---|---|---|
| 의존성 설치 | `<pm> install` | 잠금 파일이 정본 |
| 개발 서버 | `<pm> run dev` | 포트·환경 변수는 `.env.local` |
| 타입체크 | `<pm> run typecheck` 또는 `tsc --noEmit` | 스크립트 없으면 보고 |
| 린트 | `<pm> run lint` | |
| 테스트 | `<pm> run test` | 없으면 "테스트 없음"으로 보고 |
| 빌드 | `<pm> run build` | 산출물(`.next/`) 커밋 금지 |

- 환경 변수 목록은 `.env.example` 이 정본이다. 값은 저장소에 두지 않는다.
- 실행하지 못한 명령은 "미검증"으로 쓰고 통과로 간주하지 않는다.
