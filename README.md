# NOMAD Agent OS

Claude Code를 **AI 개발팀**처럼 쓰게 해 주는 설정 모음입니다.

- 🧑‍🤝‍🧑 **팀으로 일합니다** — 기획 · 구현 · 디자인 · 테스트 · 리뷰를 팀원 12명이 나눠 맡습니다 (Codex 2명은 선택)
- 💰 **토큰을 아낍니다** — 같은 파일 반복 읽기를 막고, 그림 · 문서 뼈대는 스크립트가 만듭니다
- 🔀 **AI 도구를 가리지 않습니다** — ChatGPT(Codex) · Gemini CLI도 같은 규칙을 읽습니다

---

## 빠른 시작

설치는 PC마다 한 번, 적용은 프로젝트마다 한 번입니다.

### Windows PowerShell

```powershell
# 1. 받기
git clone https://github.com/DevOps0906/nomad-agent-os.git ~\workspace\dev\nomad-agent-os

# 2. 설치 (PC마다 한 번)
~\workspace\dev\nomad-agent-os\install.ps1

# 3. 내 프로젝트에 적용 (프로젝트마다 한 번)
nomad-os init ~\workspace\dev\내프로젝트명

# 4. 시작
cd ~\workspace\dev\내프로젝트명
claude
```

> 스크립트 실행이 막히면 한 번만: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
>
> **`~\workspace\dev`는 예시 위치입니다.** `~`는 `C:\Users\<사용자>`이므로, 저장소를 다른 곳(예: `D:\WorkSpace\DEV`)에 두었다면 그 경로로 바꿔 씁니다. 파일이 없는 경로로 `install.ps1`을 부르면 PowerShell이 `'~' 모듈을 로드할 수 없습니다`라고 표시합니다.
> 2단계 설치 뒤에는 **`nomad-os`** 명령이 생기므로, 3단계부터는 저장소 위치를 몰라도 어느 폴더에서나 `nomad-os init <프로젝트 경로>`로 실행합니다.

### Git Bash · macOS · Linux

```bash
# 1. 받기
git clone https://github.com/DevOps0906/nomad-agent-os.git ~/workspace/dev/nomad-agent-os

# 2. 설치 (PC마다 한 번)
bash ~/workspace/dev/nomad-agent-os/install.sh

# 3. 내 프로젝트에 적용 (프로젝트마다 한 번 — 설치 후 새 터미널에서)
nomad-os init ~/workspace/dev/내프로젝트명

# 4. 시작
cd ~/workspace/dev/내프로젝트명
claude
```

준비물(git · Python 3.8+)과 옵션은 → [설치 가이드](docs/INSTALL.md)

---

## 첫 명령

Claude Code가 열리면 상황에 맞게 입력합니다.

| 내 상황 | 입력 |
|---|---|
| 코드가 이미 있다 | `AGENTS.md를 이 저장소에 맞게 채워줘` → 그다음 `/next` |
| 처음부터 기획한다 | `/plan 제품명` |
| 쉬었다가 이어서 한다 | `/next` |

단계별 설명은 → [시작하기](docs/GETTING_STARTED.md)

---

## 자주 쓰는 명령

| 명령 | 하는 일 |
|---|---|
| `/next` | 다음 작업 하나를 끝까지 (끝나면 `/clear` 후 다시 `/next`) |
| `/plan 제품명` | 기획 문서 + 작업 목록 만들기 |
| `/design` | 디자인 토큰 + 미리보기 |
| `/diagram 결제 흐름` | 구조도 · 흐름도 · ERD |
| `/check` | 린트 · 테스트 실패만 요약 |
| `/agent-check` | 멀티에이전트 구성 점검 · 자동 구성 (`/agent-check fix`) |
| `/secure` | 보안 점검 — SBOM · 취약점(먼저 고칠 3가지) · 라이선스 |
| `plan2spec` · `spec S-03` | 기획 표 → 구조도 · 흐름도 · 화면별 시안 · 필수 구조 검사 / 화면 하나만 15줄 |
| `nomad-os module add funnel .` | 도메인 청사진(Funnel · CRM · ERP · LMS)을 외부 레포에서 가져오기 |
| `/bm 제품명` | BM 7단계: 고객 · 가치 · 가격 → 단위경제 · 시나리오 → 파트 배분 → 린 검증 → 사업성 점수. 숫자는 `bm-calc`가 계산 |
| `docmap docs/PRD.md` | 문서 목차와 장별 상태(바뀜 · 안 읽음 · 변경 없음). 읽은 뒤 `docmap --mark`로 기록 (Claude Code는 자동) |

📊 **사업성은 숫자와 증거로 봅니다.** `/bm`은 공헌이익 · LTV · CAC 상한 · 손익분기 · 시나리오를 모델 추정이 아니라 `bm-calc`로 계산하고, 점수마다 증거 등급(A 실결제 ~ E 가정)을 붙여 80 · 60 · 40점 구간으로 판정합니다. 방법의 정본은 [platform-docs `BM_METHOD.md`](https://github.com/DevOps0906/platform-docs/blob/main/Price_Plans/_common/BM_METHOD.md)입니다.

📖 **문서는 장 단위로 기억합니다.** 이전 세션에서 읽은 마크다운(80줄 초과)을 통째로 다시 열면 readguard 훅이 막고 목차만 줍니다. 바뀐 장과 안 읽은 장만 줄 범위로 읽으면 됩니다. 같은 요청을 한 번 더 하면 통과하고, `NOMAD_DOCGUARD=0`이면 끕니다.

🎨 **기획이 정해지면 구조도 · 시안이 자동으로 나옵니다.** 대시보드 · 목록 · 폼 등 화면 유형마다 반드시 있어야 하는 구조가 빠지면 🔴로 막습니다. 팀원은 기획 문서를 다시 읽지 않고 필요한 화면만 받습니다. → [기획 → 시안](docs/DESIGN.md)

🔒 **보안은 기본 적용됩니다.** 기획(PRD 보안 절) · 작업 분해(보안 영향) · 리뷰(의존성 · 노출 면 · 키 권한)에 들어가 있습니다. → [보안 가이드](docs/SECURITY.md)

전체 명령 · 팀 · 도구는 → [레퍼런스](docs/REFERENCE.md)

---

## 지원 AI 도구

| 도구 | 실행 | 쓸 수 있는 것 |
|---|---|---|
| Claude Code | `claude` | 전부 (팀 · 슬래시 명령 · 토큰 절약 훅) |
| ChatGPT Codex | `codex` | 같은 규칙 · 작업 목록 · 도구 |
| Gemini CLI | `gemini` | 같은 규칙 · 작업 목록 · 도구 |

설정 파일은 `init`이 자동으로 만듭니다. 자세히는 → [AI 도구 같이 쓰기](docs/MULTI_AI.md)

---

## README 작성 규칙

NOMAD를 기준으로 프로젝트의 README를 만들 때 따르는 규칙입니다. 규칙 원문은 `plan-docs` 스킬의 원칙 7입니다.

- 완성(출시) 단계가 아닌 프로젝트는 README에 **`## 진행 현황 (YYYY-MM-DD 기준)`을 반드시** 씁니다. 완성 단계면 생략할 수 있습니다.
- 형식은 [Arch-Studio README](https://github.com/DevOps0906/Arch-Studio)를 따릅니다.
  1. 요약 문장 — 완료·진행·대기 개수 또는 가중 추정치와 그 근거
  2. 영역 | 현재 상태 표, 그리고 제품 제한 사항
  3. `### 작업 진행률` — 웨이브 또는 영역별 완료·비중 표
  4. `### 구현된 주요 항목` — 체크 목록
  5. `### 다음 개발 단계` — 체크 목록
- 기능·범위가 바뀔 때 이 절도 함께 갱신합니다.
- 콘텐츠(화면·기능)와 문서가 있는 프로젝트는 `## 콘텐츠 바로가기`를 **반드시** 씁니다. 위치는 진행 현황(작업 진행률 포함) 바로 아래, `## 연관·참고 저장소` 바로 위입니다.
  - 콘텐츠별 한 줄 표: 콘텐츠 | 화면 경로 | 기획·명세 문서 | 구현 코드
  - 문서·코드는 저장소 안 상대 링크로 연결하고, 링크 대상이 실제로 있는지 확인합니다. 화면 경로는 로컬 주소이므로 링크 없이 코드 표기합니다.
  - 표 아래에 전체 문서 목록·디자인 명세·구현 현황으로 가는 링크를 한 줄 답니다.
- 이 규칙은 `global/nomad/CORE.md`에도 있어 NOMAD를 쓰는 모든 프로젝트·AI 도구에 적용됩니다.

---

## 문서 안내

| 문서 | 이럴 때 읽기 |
|---|---|
| **[사용 가이드](docs/GUIDE.md)** · [웹](docs/guide/index.html) · [PDF](docs/guide/NOMAD_GUIDE.pdf) | 처음부터 끝까지 한 문서: 설치 · 팀원 · 명령 · 모듈 16종 · 조합 레시피 · docker · 문제 해결 (웹·PDF는 `python docs/guide/build.py --pdf`로 재생성) |
| [설치 가이드](docs/INSTALL.md) | 준비물 · 옵션 · 확인 · 업데이트 · 제거 |
| [시작하기](docs/GETTING_STARTED.md) | 기존 저장소에 적용 / 처음부터 시작, 단계별 |
| [AI 도구 같이 쓰기](docs/MULTI_AI.md) | ChatGPT · Gemini도 쓸 때 |
| [기획 → 구조도 · 시안](docs/DESIGN.md) | plan2spec · 필수 구조 검사 · 대비 · 3구간 스크린샷 |
| [모듈](docs/MODULES.md) | 기획 청사진 15종([blueprints-module](https://github.com/DevOps0906/nomad-blueprints-module)), 컨테이너 템플릿([docker-module](https://github.com/DevOps0906/nomad-docker-module)), L3 보안 팩([secure-pack-module](https://github.com/DevOps0906/nomad-secure-pack-module))을 필요할 때 가져오기 |
| [보안 가이드](docs/SECURITY.md) | 보안 레벨 · `/secure` · SBOM · 라이선스 · 취약점 우선순위 |
| [레퍼런스](docs/REFERENCE.md) | 명령 · 팀 · 도구 · 폴더 구조 |
| [예시: SceneFlow](docs/examples/SCENEFLOW.md) | 기획 문서만 있는 저장소에 적용한 실제 사례 |
| [설계 문서](docs/ARCHITECTURE.md) | 왜 이렇게 만들었나 · 토큰 측정 결과 |

---

## 업데이트

이 저장소 폴더에서 실행합니다.

| PowerShell | Git Bash |
|---|---|
| `git pull; .\install.ps1` | `git pull && bash install.sh` |
