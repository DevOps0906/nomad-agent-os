---
name: security-baseline
description: 보안 기본 적용 절차(레벨 L0~L3, 새 의존성·라이선스, SBOM, 취약점 우선순위, 위협 메모, 에이전트 키 권한). 의존성 추가·외부 노출·권한 변경·PRD 보안 절 작성 시 사용.
---

# security-baseline — 기획부터 보안을 기본으로

## 1. 레벨 판정 (PRD `## 8. 보안·공급망`에 기록)
| 레벨 | 언제 | 해야 할 것 | 도구 |
|---|---|---|---|
| **L0 기본** | 모든 프로젝트 | 비밀 금지 · lockfile 커밋 · 새 의존성 점검 · 기능마다 위협 메모 · 리뷰 security | 규칙 · reviewer · `secscan license` |
| **L1 저장소** | GitHub 저장소가 생기면 | Dependabot(실제 매니페스트만) · 의존성 그래프 · 비밀 스캔(push protection) · `SECURITY.md` | `/secure setup` |
| **L2 배포** | 배포 파이프라인이 생기면 | 릴리스마다 CycloneDX SBOM 보관 · OSV 취약점 스캔 · 라이선스 점검 | `/secure setup --ci` · `secscan all` |
| **L3 납품·규제** | 공공·금융·대기업·EU 판매 협의 | VEX · SPDX · OpenChain ISO/IEC 5230·18974 · CRA 필드 | 별도 팩 `nomad-secure-pack` (준비 중) |

판정 질문: ① 고객이 공공·금융·대기업인가 ② 설치형·앱·SDK로 **배포**하는가(순수 SaaS가 아닌가) ③ EU에 판매하는가 → 하나라도 예면 L3 검토, 법적 판단은 전문가 확인([compliance.md](references/compliance.md)).

## 2. 작업별로 읽을 것 (필요한 파일만)
| 작업 | 읽을 reference |
|---|---|
| 의존성 추가·업데이트, lockfile 변경, 라이선스 질문 | [supply-chain.md](references/supply-chain.md) |
| 취약점 경고 처리, 무엇부터 고칠지 | [vuln-priority.md](references/vuln-priority.md) |
| 새 기능 기획, 공개 API·웹훅·관리자 화면·파일 업로드 | [threat-model.md](references/threat-model.md) |
| AI 에이전트·LLM·외부 도구 연동, API 키 설계 | [agent-security.md](references/agent-security.md) |
| 공공 납품·EU 판매·인증 요구 | [compliance.md](references/compliance.md) |

## 3. 팀 흐름에 들어가는 자리
- **기획**: planner가 PRD 8절(레벨 · 대상 · 노출 면 · 민감 데이터 · 키/권한)을 채운다. 비어 있으면 reviewer(doc) 🔴.
- **작업 분해**: task 표의 `보안 영향`이 `없음`이 아니면 위험도 `높음` → challenger 먼저 + reviewer(security).
- **구현**: 새 의존성은 builder가 [supply-chain.md 3절](references/supply-chain.md) 체크리스트 결과를 보고에 1줄로 적는다.
- **검증**: `~/.claude/nomad/bin/secscan all` → "먼저 고칠 것" 표만 보고 판단(전체 로그는 `.nomad/sbom/`).
