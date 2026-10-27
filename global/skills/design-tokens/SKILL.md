---
name: design-tokens
description: 디자인 시스템을 코드 토큰 중심으로 만드는 절차(브리프→토큰→반응형 3구간 폰트→미리보기 HTML 1장→사람 확정). "디자인 시스템", "토큰", "DESIGN.md", "화면 디자인" 요청 시 사용.
---

# design-tokens — 토큰이 정답, 시안은 초안

## 원칙 (토큰을 아끼는 이유 포함)
1. **정답 소스는 코드 하나**: Tailwind CSS v4면 `src/styles/tokens.css`의 `@theme` 블록(라이트·다크). DESIGN.md의 표는 토큰에서 다시 만든 사본이다.
   → 문서와 코드를 따로 고치는 왕복이 사라진다.
2. **시안 대신 미리보기 1장**: 화면 이미지를 여러 장 생성하지 않는다. 토큰을 읽는 `design/preview.html` 하나에 컴포넌트 × 상태 × 라이트/다크를 띄운다.
3. **변경은 토큰 diff로**: "버튼을 더 둥글게" → `--radius-control: 8px → 12px` 한 줄. 화면 코드를 다시 쓰지 않는다.
4. **값 검색은 도구로**: `ui-ux-pro-max` 스킬이 설치돼 있으면 `scripts/search.py`로 팔레트·서체를 검색해 결과만 쓴다(데이터 CSV를 Read 하지 않는다).
5. **사람이 확정**: 비주얼 수치는 사람이 미리보기를 보고 확정한다. 에이전트는 후보 2~3개를 준비할 뿐이다.

## 절차
| 단계 | 담당 | 결과 |
|---|---|---|
| 0 시안 초안 | 스크립트 | 화면 표가 있으면 `plan2spec` → `design/wireframes/`(화면별 3구간 HTML, 토큰 반영) — 모델이 시안을 그리지 않음 |
| 1 브리프 | 팀장 | 대상·주된 일·분위기 3단어·피할 것 (DESIGN.md 1장, 10줄) |
| 2 토큰 초안 | designer | 없으면 `design-preview --init src/styles/tokens.css`(3구간 폰트 포함 시작본) → 값만 수정 |
| 3 반응형 | designer | 아래 3구간 폰트 표 채움 (`@media (width >= 768px/1200px)`의 `:root` 덮어쓰기) |
| 4 미리보기 | 스크립트 | `design-preview src/styles/tokens.css -o design/preview.html --md docs/DESIGN_TOKENS.md` — HTML·표를 모델이 쓰지 않음 |
| 4.5 검사 | 스크립트 | `design-preview <tokens> --check --scan src/components`(대비·토큰 우회) → `plan2spec`(시안 갱신) → `shot design/wireframes` |
| 5 확정 | 사용자 | `design/preview.html` + `design/wireframes/index.html` 확인 → 수정 값 → 토큰 한 줄 수정 → 4번 재실행 |
| 6 화면 | builder | 컴포넌트 단위 구현(확정 전에는 화면 작업 시작 안 함) |

## 반응형 3구간 폰트 표 (필수)
| 토큰 | 모바일 ~767 | 태블릿 768~1199 | 데스크톱 1200~ |
|---|---|---|---|
| `--text-display` | 28px | 36px | 48px |
| `--text-h1` | 24px | 28px | 34px |
| `--text-h2` | 20px | 22px | 26px |
| `--text-body` | 15px | 16px | 16px |
| `--text-caption` | 12px | 13px | 13px |
값은 시작점이다. 한국어 본문 서체를 반드시 지정한다(예: Pretendard). 숫자·금액은 고정폭 서체 토큰을 따로 둔다.

## 색 토큰 규칙 (대비 검사가 이 이름으로 짝을 찾는다)
`--color-bg` · `--color-surface` 위의 `--color-text` · `--color-text-muted`(4.5:1), `--color-X` 위의 `--color-X-fg`(4.5:1),
입력창·체크박스 경계 `--color-input`(3:1, WCAG 1.4.11) — 장식용 구분선은 `--color-border`(기준 없음).
Flutter는 같은 이름을 `lib/theme/tokens.dart` 상수로 옮기고 위젯에는 테마 값만 쓴다(`design-preview --scan lib`이 `Color(0x…)` 탐지).

## 출시 전 체크
- [ ] `shot <URL>` 375 · 768 · 1280 · 1440px에서 깨짐·페이지 가로 스크롤 없음 (표·보드는 카드 안 스크롤)
- [ ] 대비 4.5:1(본문), 포커스 링 보임, `prefers-reduced-motion` 존중
- [ ] 컴포넌트에 hex·px 직접 사용 0건 (`Grep "#[0-9a-fA-F]{3,6}"` in components)
