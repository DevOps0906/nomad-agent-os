# 모듈 — 필요할 때 외부 레포에서 가져오기

NOMAD 본체에는 **구조(형식 · 가져오는 장치 · 검사기)**만 있습니다. 도메인 기획 청사진(Funnel · CRM · ERP · LMS)과 L3 보안 팩은 **별도 깃허브 레포**에 있고, 프로젝트에 필요할 때만 가져옵니다.

```bash
nomad-os module list [프로젝트]                     # 등록된 모듈 · 설치 상태
nomad-os module add funnel <프로젝트>              # 가져오기 (커밋 고정)
nomad-os module update funnel <프로젝트>           # 새 버전 (내가 고친 파일은 보존 → .upstream)
nomad-os module update all <프로젝트>
nomad-os module remove funnel <프로젝트>           # 고치지 않은 파일만 삭제
nomad-os module add <이름> <프로젝트> --from <로컬 경로>   # 레포 없이 로컬에서 (개발 · 시험용)
nomad-os module add https://github.com/<계정>/<레포>.git#<하위 경로> <프로젝트>   # 등록 안 된 레포
```
PowerShell · Git Bash 같은 명령입니다(설치 후 `nomad-module`로도 실행 가능).

---

## 1. 모듈 종류

| 유형 | 가져오는 곳 | 내용 | 레포 |
|---|---|---|---|
| `blueprint` | `docs/blueprints/<이름>/` | 화면 · 상태 · 흐름 · API · 데이터 표 + 도메인 분석 + 추가 필수 구조 → `plan2spec`이 바로 읽음 | `nomad-blueprints-module` |
| `security` | `security/<이름>/` | L3 납품 · 규제 (OpenChain · VEX · SPDX · CRA) | `nomad-secure-pack-module` |

## 2. 등록 목록
`modules.json`(NOMAD 저장소, 설치 때 `~/.claude/nomad/`로 복사)에 이름 → 레포 · 하위 경로 · 참조(태그·브랜치)를 적습니다.
내 레포를 더하려면 `~/.claude/nomad/modules.local.json`에 같은 형식으로 추가합니다(NOMAD 업데이트에 덮이지 않음).

## 3. 기록 — `nomad-modules.json` (프로젝트 루트, 커밋 권장)
```json
{ "modules": { "funnel": { "source": "https://github.com/…/nomad-blueprints-module.git", "ref": "v0.1.0",
  "commit": "48080bc…", "install_to": "docs/blueprints/funnel", "files": { "screens.md": "<sha256>" } } } }
```
- **커밋까지 고정** — 같은 기록으로 팀원 · CI가 같은 내용을 받습니다.
- 파일 해시로 "내가 고친 파일"을 구분합니다. 업데이트가 내 수정을 덮지 않고, 새 버전은 `<파일>.upstream`으로 둡니다.

## 4. 안전장치 (외부에서 가져오는 것이므로)
| 위험 | 막는 방법 |
|---|---|
| 스크립트 · 실행 파일 | 허용 확장자만(.md .json .yml .csv .txt .svg .png .mmd .css .html). 스크립트는 `--allow-scripts`로 검토 후에만 |
| 경로 조작 (`../`) · 심볼릭 링크 | 모듈 폴더 · 프로젝트 밖을 가리키면 거부 |
| 몰래 바뀐 내용 | 커밋 고정 + 파일 해시 기록 |
| 큰 파일 | 모듈당 5MB 제한 |
| 라이선스 | `module.json`의 license 확인 — 없으면 경고, GPL · AGPL 등은 🔴 표시 |
| NOMAD 저장소 오염 | NOMAD 저장소 안에는 설치 거부 |

## 5. 왜 오픈소스 CRM · ERP · LMS 코드를 그대로 가져오지 않나
| 대상 | 대표 오픈소스 | 판단 |
|---|---|---|
| CRM | Twenty · SuiteCRM | 라이선스가 AGPL · GPL 계열인 경우가 많음 → NOMAD 라이선스 정책상 **기본 거부**(SaaS에서 소스 공개 의무 위험). 구조만 벤치마킹 |
| ERP | Odoo · ERPNext | 거대한 단일 앱(수십만 줄) — 일부만 떼어 쓰기 어렵고 라이선스 확인 필요. 구조만 벤치마킹 |
| LMS | Moodle · Canvas | GPL · AGPL 계열 → 구조만 벤치마킹 |
| 마케팅 자동화 | Mautic | GPL-3.0 → 구조만 벤치마킹 |

그래서 모듈은 **코드가 아니라 기획 청사진**입니다. 청사진을 가져와 → 쓰지 않을 행을 지우고 → `plan2spec`으로 시안 · 검사 → 팀이 우리 스택으로 구현합니다.
코드 재사용은 라이선스가 허용(MIT · Apache 등)된 **라이브러리 · UI 블록** 단위로 하고, 그때도 `secscan license`로 확인합니다.
각 프로젝트의 정확한 라이선스는 사용 시점에 원문으로 확인하세요.

## 6. 새 모듈 만들기
`nomad-blueprints-module/README.md`의 "모듈 형식"을 따릅니다. 만든 뒤 검증:
```bash
mkdir -p /tmp/t/docs && nomad-os module add <이름> /tmp/t --from <nomad-blueprints-module 경로> && cd /tmp/t && plan2spec --strict
```
