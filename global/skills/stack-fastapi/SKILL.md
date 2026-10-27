---
name: stack-fastapi
description: FastAPI·Pydantic v2·Python 비동기 API 서버(LLM 게이트·LangChain/LangGraph 포함) 작업 규약과 함정. 라우터·모델·의존성·인증·pytest 작업 전에 읽는다.
---

# stack-fastapi

## 30초 요약
1. `async def` 안에서 블로킹 호출 금지(`requests`, 동기 DB 드라이버, `time.sleep`). `httpx.AsyncClient` 사용.
2. 모든 엔드포인트에 `response_model`. 내부 필드·예외 메시지를 그대로 응답하지 않는다.
3. 인증(누구인가) + 인가(이 데이터의 주인인가)를 둘 다 확인한다(IDOR).
4. LLM·외부 API 키는 이 서버에만. 모델·제공자를 코드에 하드코딩하지 않고 설정으로.
5. 설정은 `pydantic-settings` 필수 필드로 — 누락 시 조용한 기본값 금지.
6. 테스트는 의존성 오버라이드로 외부 호출을 가짜로 바꾼다.

## 요청별 시작점
| 요청 | 읽을 곳 |
|---|---|
| 라우터·모델·의존성 구조 | `references/conventions.md` |
| 리뷰 전 점검 | `references/pitfalls.md` |
| 실행·테스트 명령 | `references/build-and-run.md` |

## 제출 전
- [ ] `q ruff check .` · `q pytest -q` 결과
- [ ] 새 엔드포인트의 인가·응답 모델·오류 형식
