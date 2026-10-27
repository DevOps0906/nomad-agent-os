# 공급망 — 의존성 · 라이선스 · SBOM

## 1. 원칙
- lockfile(`pnpm-lock.yaml` · `package-lock.json` · `uv.lock` · `poetry.lock` · `pubspec.lock`)은 커밋한다. 버전 `latest`·범위 지정만으로 두지 않는다.
- lockfile은 패키지 매니저 명령으로만 바꾼다. 손으로 고치거나, 작업과 무관한 대량 변경을 섞지 않는다.
- 쓰지 않는 의존성은 지운다(체인의 재료를 줄인다).

## 2. 라이선스 정책 (기본값 — 프로젝트별 예외는 `security/policy.json`)
| 분류 | 라이선스 | 처리 |
|---|---|---|
| 허용 | MIT · Apache-2.0 · BSD-2/3-Clause · ISC · 0BSD · Unlicense · CC0-1.0 · Zlib · Python-2.0 | 그대로 사용 |
| 검토 | LGPL-* · MPL-2.0 · EPL-* · CDDL-* · CC-BY-* · 라이선스 미표기 | 사용 방식(동적 링크·수정 여부) 확인 후 팀장이 사용자에게 1줄 보고 |
| **기본 거부** | GPL-* · **AGPL-*** · SSPL-* · BUSL · Commons-Clause · CC-BY-NC-* | 쓰지 않는다. 꼭 필요하면 사용자 승인 후 예외 등록 |

AGPL은 네트워크로 서비스만 해도 소스 공개 의무가 생길 수 있어 SaaS에서 특히 위험하다.

예외 등록 (`security/policy.json`, 승인한 사람·날짜·이유 필수):
```json
{ "allow": ["LGPL-3.0-only"], "deny": [], "exceptions": [
  { "package": "pkg:npm/some-lib@2.1.0", "license": "GPL-3.0-only", "reason": "빌드 도구로만 사용, 배포물 미포함", "approved_by": "사용자", "date": "2026-10-27" } ] }
```

## 3. 새 의존성 체크리스트 (builder가 보고에 1줄: `의존성 점검: 이름@버전 · 라이선스 · 결과`)
| # | 확인 | 방법 |
|---|---|---|
| 1 | 정말 필요한가 (표준 라이브러리·기존 의존성으로 되나) | Grep 기존 코드 |
| 2 | 라이선스가 허용 목록인가 | 패키지 메타데이터 · `secscan license` |
| 3 | 유지되고 있나 (최근 릴리스, 이슈 대응) | 레지스트리 페이지 |
| 4 | 이름 사칭(typosquatting) 아닌가 — 철자·조직명·다운로드 수 | 공식 문서의 설치 명령과 대조 |
| 5 | 설치 스크립트(`postinstall` 등)가 있나 | 패키지 `package.json` scripts |
| 6 | 알려진 취약점 | `secscan vuln` |

## 4. SBOM
- 형식: 기본 **CycloneDX JSON**(보안 중심, 가벼움). 고객·규제가 요구하면 **SPDX**(ISO/IEC 5962)로 추가.
- 담기는 것: 컴포넌트 이름 · 버전 · 공급자 · purl · 의존 관계 · 라이선스 · 생성 도구 · 생성 시각.
- 로컬: `secscan sbom` → `.nomad/sbom/sbom.cdx.json` (커밋하지 않음).
- CI(L2): 릴리스마다 생성해 아티팩트로 보관 — `/secure setup --ci`가 워크플로를 만든다.
- SBOM은 "공개"가 아니라 **보관·제출**용이다. 고객·감독기관이 요청할 때 낸다.
