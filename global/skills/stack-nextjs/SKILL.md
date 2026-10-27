---
name: stack-nextjs
description: Next.js App Router·React·TypeScript·Tailwind CSS v4·shadcn/ui·@supabase/ssr 작업 규약과 함정. 페이지·컴포넌트·서버 액션·Route Handler·인증 세션 작업 전에 읽는다.
---

# stack-nextjs

> 버전은 `package.json`과 공식 문서로 확인한다. 확인 못 한 API는 "미확인"으로 보고한다.

## 30초 요약
1. 서버 컴포넌트가 기본. `"use client"`는 상호작용이 필요한 말단만.
2. 비밀은 서버에만. `NEXT_PUBLIC_*`는 브라우저에 노출된다. service_role 키는 `src/server/**`에서만.
3. 권한의 최종 방어선은 RLS(stack-supabase). 클라이언트 검사는 UX일 뿐이다.
4. API 응답 타입은 계약 문서·생성 타입이 정본. 필드를 추정하지 않는다(`any` 금지).
5. Tailwind CSS v4: `@import "tailwindcss"` + `@theme` 토큰. `tailwind.config.js`·`@tailwind base` 같은 v3 문법 금지.
6. 반응형 3구간(~767 / 768~1199 / 1200~), 색·크기는 토큰만.

## 요청별 시작점
| 요청 | 읽을 곳 |
|---|---|
| 새 화면·라우트·인증·API 소비 | `references/conventions.md` 해당 절 |
| 캐싱·이상 동작, 리뷰 전 | `references/pitfalls.md` |
| 실행·검증 명령 | `references/build-and-run.md` |
| 디자인 시스템·토큰 | `design-tokens` 스킬 |

## 제출 전
- [ ] `q pnpm lint` · `q pnpm typecheck` · `q pnpm test` 결과 (못 했으면 "미검증")
- [ ] 에러·로딩·빈 상태, 서버 측 입력 검증·인가
- [ ] 비밀이 클라이언트 번들·로그에 없음
