# 보안 가이드 — 기획부터 보안이 기본

NOMAD는 따로 요청하지 않아도 **기획 → 작업 분해 → 구현 → 리뷰** 단계마다 보안 점검이 들어갑니다.
무거운 규제 대응(공공 납품 · EU 판매)은 필요할 때만 단계적으로 올립니다.

---

## 1. 보안 레벨 — 프로젝트마다 하나 고릅니다

PRD `## 8. 보안·공급망`에 적습니다. `/plan`을 쓰면 planner가 자동으로 채우고, 비어 있으면 리뷰에서 막힙니다.

| 레벨 | 언제 | 하는 일 | 어떻게 |
|---|---|---|---|
| **L0 기본** | 모든 프로젝트 (자동) | 비밀 커밋 금지 · lockfile 커밋 · 새 의존성 점검 · 기능마다 위협 메모 · 보안 리뷰 | 그냥 쓰면 적용 |
| **L1 저장소** | GitHub 저장소가 생기면 | Dependabot · 의존성 그래프 · 비밀 스캔 · `SECURITY.md` | `/secure setup` |
| **L2 배포** | 배포 파이프라인이 생기면 | 릴리스마다 SBOM 보관 · 취약점 스캔 · 라이선스 점검 | `/secure setup --ci` |
| **L3 납품·규제** | 공공 · 금융 · 대기업 · EU 판매 협의 | VEX · SPDX · OpenChain ISO 5230/18974 · CRA | 별도 팩 (준비 중) |

**어떤 레벨인지 모르겠다면** 세 가지만 답합니다. 하나라도 "예"면 L3를 검토합니다.
1. 고객이 공공 · 금융 · 대기업인가?
2. 설치형 · 앱 · SDK로 **배포**하는가? (순수 웹 SaaS가 아닌가)
3. EU에 판매하는가?

---

## 2. 자동으로 들어가는 곳

| 단계 | 무엇이 바뀌었나 |
|---|---|
| 기획 (`/plan`) | PRD에 **보안·공급망** 절이 추가됩니다(레벨 · 고객 · 노출 면 · 민감 데이터 · 키). 공개 API · 웹훅 · 관리자 화면에는 **위협 메모**가 붙습니다 |
| 작업 분해 | 작업마다 **보안 영향**(없음 · 의존성 · 노출 면 · 키 · 민감 데이터)을 적습니다. "없음"이 아니면 위험도가 **높음**이 되어 착수 전에 challenger가 계획을 공격합니다 |
| 구현 | 새 의존성을 넣으면 builder가 라이선스 · 유지관리 · 이름 사칭 점검 결과를 보고합니다 |
| 리뷰 | reviewer(security)가 거부 라이선스 · lockfile 무단 변경 · 위협 메모 없는 노출 면 · 키 권한 확대 · **다른 약점과 이어지는 낮은 등급 약점**을 봅니다 |
| 읽기 차단 | Claude가 `.env` · `*.pem` · `*.key` · SSH 키 파일을 읽지 못하게 막습니다 |

---

## 3. `/secure` 사용법

### 점검
```text
/secure          ← SBOM 생성 + 취약점 + 라이선스 → "먼저 고칠 3가지"
/secure --kev    ← 실제 악용 중(CISA KEV) · 악용 가능성(EPSS)까지 반영
```
터미널에서 직접 실행해도 됩니다(PowerShell · Git Bash 같은 이름).
```bash
secscan all .            # 전부
secscan vuln . --kev     # 취약점만, 악용 정보 포함
secscan license .        # 라이선스만
secscan sbom .           # SBOM만 → .nomad/sbom/sbom.cdx.json
```

출력 예:
```text
■ 취약점 (OSV API): 6건 — KEV 0
  | # | 패키지@버전 | 취약점 | 심각도 | KEV | EPSS | 범위 | 수정 버전 |
  | 1 | lodash@4.17.20 | CVE-2026-4800 | HIGH 8.1 | - | - | 운영 | 4.18.0 |
  | 6 | minimist@1.2.5 | CVE-2021-44906 | CRITICAL 9.8 | - | - | 개발 | 1.2.6 |
■ 라이선스: 허용 3 · 검토 0 · 거부 1 · 정보 없음 0
  🔴 거부  gpl-lib@1.0.0 — GPL-3.0-only
■ 먼저 고칠 것
  1. 라이선스 거부 gpl-lib@1.0.0 (GPL-3.0-only) → 대체 패키지 또는 사용자 승인 후 security/policy.json 예외
  2. lodash@4.17.20 — CVE-2026-4800, CVE-2021-23337 (HIGH) → 4.18.0 이상으로 업데이트
```
**정렬 기준이 CVSS 점수가 아닙니다.** 실제 악용(KEV) → 운영 의존성 → 악용 가능성(EPSS) → 심각도 순입니다.
위 예에서 9.8점 minimist가 아래에 있는 이유는 **개발용** 의존성이라 배포물에 들어가지 않기 때문입니다.

### 설정 파일 만들기
```text
/secure setup        ← .github/dependabot.yml + SECURITY.md
/secure setup --ci   ← + .github/workflows/sbom.yml (릴리스마다 SBOM 보관 + 취약점 스캔)
```
- 프로젝트에 **실제로 있는** 패키지 관리자만 Dependabot에 넣습니다(없는 것을 넣으면 Dependabot이 오류를 냅니다).
- 이미 있는 파일은 덮어쓰지 않습니다.
- 코드가 아직 없으면 Dependabot 파일은 만들지 않고 알려 줍니다.
- 끝나면 GitHub에서 사람이 한 번 켜야 할 것(Settings → Code security)을 알려 줍니다.

---

## 4. 라이선스 정책 (기본값)

| 분류 | 라이선스 | 처리 |
|---|---|---|
| 허용 | MIT · Apache-2.0 · BSD · ISC · 0BSD · Unlicense · CC0 등 | 그대로 사용 |
| 검토 | LGPL · MPL · EPL · CDDL · 라이선스 미표기 | 사용 방식 확인 후 사용자에게 보고 |
| **기본 거부** | **GPL · AGPL** · SSPL · BUSL · Commons-Clause · CC-BY-NC | 쓰지 않음 |

AGPL은 네트워크로 서비스만 해도 소스 공개 의무가 생길 수 있어 SaaS에 특히 위험합니다.
꼭 써야 하면 승인 후 프로젝트의 `security/policy.json`에 예외로 등록합니다.
```json
{ "exceptions": [
  { "package": "pkg:npm/some-lib", "license": "GPL-3.0-only",
    "reason": "빌드 도구로만 사용, 배포물 미포함", "approved_by": "홍길동", "date": "2026-10-27" } ] }
```
`"package"`에 버전 없이 쓰면 모든 버전, `@버전`까지 쓰면 그 버전만 예외입니다.

---

## 5. 설치 없이 동작합니다 (있으면 더 정확)

| 하는 일 | 기본 (설치 불필요) | 설치돼 있으면 사용 |
|---|---|---|
| SBOM | lockfile 직접 해석 (npm · pnpm · yarn · pip · poetry · uv · Pipfile · Flutter · Go · Cargo) | [syft](https://github.com/anchore/syft) — 라이선스 정보가 더 많음 |
| 취약점 | [OSV](https://osv.dev) 공개 API (인터넷 필요) | [osv-scanner](https://google.github.io/osv-scanner/) |
| 악용 정보 | `--kev`: CISA KEV · FIRST EPSS (인터넷, 하루 캐시) | — |

- 인터넷이 안 되거나 도구가 없어도 **작업을 막지 않습니다.** 무엇을 확인하지 못했는지만 알려 줍니다.
- pnpm · yarn · pip lockfile에는 라이선스 정보가 없습니다. 라이선스까지 보려면 syft를 설치하세요.
- 결과 파일은 `.nomad/sbom/`에 생기며 커밋되지 않습니다(`.gitignore`).

---

## 6. 교육 내용이 어디에 들어갔나

| 개념 | NOMAD에서 |
|---|---|
| SBOM (CycloneDX · SPDX) | `secscan sbom` → CycloneDX JSON. CI에서 릴리스마다 보관(`/secure setup --ci`). SPDX는 L3 |
| 오픈소스 라이선스 (GPL · AGPL) | 기본 정책 + `secscan license` + 리뷰 🔴 |
| 취약점 체이닝 · CVSS의 한계 | 우선순위 = KEV → 노출·도달 → **체인의 중간 고리** → EPSS → 피해 범위 → CVSS. 낮은 등급 무기한 보류 금지 |
| KEV · EPSS | `secscan vuln --kev` |
| VEX ("우리 제품에서 실제로 악용 가능한가") | `security/vex.md` 기록 양식 (`vuln-priority.md` 4절). 정식 VEX 문서는 L3 |
| 인터넷 노출 자산 우선 | PRD 보안 절의 노출 면 + 기능별 위협 메모 |
| AIBOM · AI 에이전트 권한 | `docs/AI_INVENTORY.md` 양식(키 · 도구 · 데이터 · 승인) + 최소 권한 원칙 |
| 공공 2027 · EU CRA | `compliance.md`에 기준일과 함께 정리 (일정은 바뀌므로 협의 시 재확인) |
| OpenChain ISO 5230 · 18974 | L3 별도 팩에서 자가 체크리스트로 다룰 예정 |

자세한 기준은 Claude가 필요할 때 읽는 스킬 `~/.claude/skills/security-baseline/`에 있습니다.

> 이 문서와 스킬의 규제 정보는 **2026-10 기준**이며 법률 자문이 아닙니다. 실제 납품 · 판매 전에는 원문과 전문가 확인을 받으세요.
