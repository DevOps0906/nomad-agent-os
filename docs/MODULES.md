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

## 0. 지금 연결된 모듈 레포

| 레포 | 용도 | 브랜치 | 공개 |
|---|---|---|---|
| [nomad-blueprints-module](https://github.com/DevOps0906/nomad-blueprints-module) | 도메인 기획 청사진 — 모듈마다 폴더 하나 | `main` | 비공개 |
| [nomad-secure-pack-module](https://github.com/DevOps0906/nomad-secure-pack-module) | 보안 L3 (납품 · 규제) | `main` | 비공개 |
| [nomad-docker-module](https://github.com/DevOps0906/nomad-docker-module) | 컨테이너 실행 템플릿 (실행 파일 포함) | `master` | 비공개 |

| 모듈 (`add` 이름) | 레포 · 위치 | 버전 | 상태 | 내용 |
|---|---|---|---|---|
| `contracts` | blueprints-module · `contracts/` | 0.1.0 | ✅ 사용 가능 | 공통 계약 정본 — EVENTS · JOBS · ACCESS · CONVENTIONS. 다른 모듈의 `requires` (함께 가져와야 문서 링크가 열림) |
| `funnel` | blueprints-module · `funnel/` | 0.1.0 | ✅ 사용 가능 | 퍼널 마케팅 — 화면 12 · 흐름 5 · API 11 · 테이블 16 · 전용 필수 구조 |
| `secure-pack` | secure-pack-module · `/` | 0.0.1 | 🟡 뼈대 | 구조 계획만 — OpenChain · 정책 · VEX · SPDX · CRA · 공공 제출 순서로 채울 예정 |
| `docker` | docker-module · `/` | 0.0.1 | 🟡 뼈대 | 구조 계획만 — api · worker · stt-whisper · ocr-paddle · embeddings · clamav. NOMAD 도구가 docker 유형을 지원한 뒤 채움 |
| `crm` | blueprints-module · `crm/` | 0.1.0 | ✅ 사용 가능 | CRM — 화면 14 · 흐름 5 · API 14 · 테이블 14 · funnel 리드 전환 연결 |
| `erp` | blueprints-module · `erp/` | 0.1.0 | ✅ 사용 가능 | ERP — 화면 19 · 흐름 6 · API 20 · 테이블 21 · 하위 영역은 화면 ID 구간 |
| `lms` | blueprints-module · `lms/` | 0.1.0 | ✅ 사용 가능 | LMS — 화면 16 · 흐름 6 · API 17 · 테이블 16 · 결제는 payments 이벤트 계약 |
| `auth-rbac` | blueprints-module · `auth-rbac/` | 0.1.0 | ✅ 사용 가능 | 공통 기반 · 인증·권한 — 화면 12 · 흐름 5 · API 16 · 테이블 11 |
| `admin-audit` | blueprints-module · `admin-audit/` | 0.1.0 | ✅ 사용 가능 | 공통 기반 · 관리 콘솔·감사 — 화면 11 · 흐름 4 · API 10 · 테이블 8 |
| `notify` | blueprints-module · `notify/` | 0.1.0 | ✅ 사용 가능 | 공통 기반 · 알림 — 화면 9 · 흐름 5 · API 13 · 테이블 11 |
| `payments` | blueprints-module · `payments/` | 0.1.0 | ✅ 사용 가능 | 공통 기반 · 결제(토스) — 화면 12 · 흐름 5 · API 14 · 테이블 12 |
| `files-storage` | blueprints-module · `files-storage/` | 0.1.0 | ✅ 사용 가능 | 공통 기반 · 파일 — 화면 9 · 흐름 5 · API 13 · 테이블 8 |
| `stt-voice` | blueprints-module · `stt-voice/` | 0.1.0 | ✅ 사용 가능 | AI · 음성 받아쓰기(whisper) · AI 작업 계약 정본 — 화면 10 · 흐름 5 · API 13 · 테이블 11 |
| `rag-chat` | blueprints-module · `rag-chat/` | 0.1.0 | ✅ 사용 가능 | AI · 문서 질의응답 — 화면 9 · 흐름 5 · API 13 · 테이블 11 |
| `ocr-docs` | blueprints-module · `ocr-docs/` | 0.1.0 | ✅ 사용 가능 | AI · 문서 인식 — 화면 8 · 흐름 4 · API 11 · 테이블 8 |

- **비공개 레포**라서 GitHub에 로그인된 PC(Git Credential Manager · `gh auth login`)에서만 가져올 수 있습니다.
- **넣는 기준:** 도메인 기획 청사진은 모두 blueprints-module, 보안 납품·규제 자료는 secure-pack-module. 공개 범위나 관리 주체가 다를 때만 레포를 따로 만듭니다.
- 모듈 내용은 **본체에 복사하지 않습니다**(같은 내용이 두 곳에 생기면 어긋남). 본체에는 등록 목록(`modules.json`)만 있습니다.

---

## 1. 모듈 종류

| 유형 | 가져오는 곳 | 내용 | 레포 |
|---|---|---|---|
| `blueprint` | `docs/blueprints/<이름>/` | 화면 · 상태 · 흐름 · API · 데이터 표 + 도메인 분석 + 추가 필수 구조 → `plan2spec`이 바로 읽음 | `nomad-blueprints-module` |
| `security` | `security/<이름>/` | L3 납품 · 규제 (OpenChain · VEX · SPDX · CRA) | `nomad-secure-pack-module` |
| `docker` | `infra/<이름>/` | 컨테이너 실행 템플릿(Dockerfile · compose · 설정) + 운영 · 보안 문서. 가져올 때 `--allow-scripts`로 검토 확인 필수 | `nomad-docker-module` |

### 분류 · 의존 (`module.json`)
| 필드 | 뜻 | 도구 동작 |
|---|---|---|
| `category` | core · foundation · domain · ai · infra · security | `module list`가 분류별로 묶어 표시 |
| `requires` | 꼭 함께 있어야 하는 모듈(예: AI 모듈 → contracts · files-storage) | `module add` 때 먼저 자동 설치(등록부 ref 기준, 같은 출처). 하나라도 검증 실패면 아무것도 설치하지 않음. 실행 파일을 포함한 모듈은 자동 설치하지 않고 직접 `--allow-scripts`로 받게 안내 |
| `integrates` | 같이 쓰면 연결되는 모듈 | 설치 끝에 "함께 쓰면 연결: …(설치됨/미설치)" 안내만 |

`module remove`는 다른 설치 모듈이 requires로 쓰고 있으면 경고합니다(기록은 `nomad-modules.json`의 requires).

## 2. 등록 목록
`modules.json`(NOMAD 저장소, 설치 때 `~/.claude/nomad/`로 복사)에 이름 → 레포 · 하위 경로 · 참조(태그·브랜치)를 적습니다.
내 레포를 더하려면 `~/.claude/nomad/modules.local.json`에 같은 형식으로 추가합니다(NOMAD 업데이트에 덮이지 않음).

## 3. 기록 — `nomad-modules.json` (프로젝트 루트, 커밋 권장)
```json
{ "modules": { "funnel": { "source": "https://github.com/DevOps0906/nomad-blueprints-module.git", "ref": "main",
  "commit": "75bbc38…", "install_to": "docs/blueprints/funnel", "files": { "screens.md": "<sha256>" } } } }
```
- **커밋까지 고정** — 같은 기록으로 팀원 · CI가 같은 내용을 받습니다.
- 파일 해시로 "내가 고친 파일"을 구분합니다. 업데이트가 내 수정을 덮지 않고, 새 버전은 `<파일>.upstream`으로 둡니다.

## 4. 안전장치 (외부에서 가져오는 것이므로)
| 위험 | 막는 방법 |
|---|---|
| 스크립트 · 실행 파일 | 허용 확장자만(.md .json .yml .csv .txt .svg .png .mmd .css .html). 스크립트는 `--allow-scripts`로 검토 후에만 |
| docker 모듈 | Dockerfile · .dockerignore · .env.example · .conf · .toml만 추가 허용, `--allow-scripts` 필수. 셸 스크립트(.sh 등)는 플래그가 있어도 거부 |
| requires 조작 | 이름 형식(`a-z0-9-`)만 · 등록부(또는 같은 `--from` 루트)에 있는 모듈만 · 깊이 8 · 순환 거부. `--allow-scripts`는 requires에 전파 안 됨 |
| 설치 위치 조작 | `install_to`는 docs/ · security/ · infra/ 아래만, `.git` · `.github` · `.vscode` 경로 거부 |
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
1. `nomad-blueprints-module/<이름>/`에 파일을 만듭니다 — 형식은 그 레포 README의 "모듈 형식"(funnel이 예시).
2. 검증(아래) → 커밋 → push → 필요하면 `<이름>-v0.1.0` 태그.
3. 본체 `modules.json`에 등록(또는 `status: planned` 제거) → 본체 커밋 · push → 각 PC에서 `install.ps1` 재실행.

검증:
```bash
mkdir -p /tmp/t/docs && nomad-os module add <이름> /tmp/t --from <nomad-blueprints-module 경로> && cd /tmp/t && plan2spec --strict
```
