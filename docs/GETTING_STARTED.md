# 시작하기

[← README](../README.md)

설치를 마쳤다면([설치 가이드](INSTALL.md)) 내 상황에 맞는 쪽을 따라 합니다.

| 내 상황 | 가는 곳 |
|---|---|
| GitHub에 코드가 이미 있다 | [A. 기존 저장소에 적용](#a-기존-저장소에-적용) |
| 아무것도 없고 기획부터 한다 | [B. 처음부터 시작](#b-처음부터-시작) |
| 기획 문서만 있고 코드는 없다 | [예시: SceneFlow](examples/SCENEFLOW.md) |

---

## A. 기존 저장소에 적용

### 1단계. 받기 + 적용

**순서가 중요합니다.** 먼저 clone, 그다음 init. 반대로 하면 clone이 실패합니다.

**PowerShell**
```powershell
cd ~\workspace\dev
git clone https://github.com/<계정>/<저장소명>.git
~\workspace\dev\nomad-agent-os\install.ps1 init ~\workspace\dev\<저장소명>
cd <저장소명>
claude
```

**Git Bash**
```bash
cd ~/workspace/dev
git clone https://github.com/<계정>/<저장소명>.git
bash ~/workspace/dev/nomad-agent-os/install.sh init ~/workspace/dev/<저장소명>
cd <저장소명> && claude
```

### 2단계. AGENTS.md를 실제 코드에 맞추기 ⭐ 가장 중요

템플릿의 스택 · 명령(`pnpm dev` 등)은 예시일 뿐입니다.
`/check` · `/next`가 이 명령을 그대로 실행하므로 반드시 맞춰야 합니다. Claude에게 이렇게 요청합니다.

```text
이 저장소를 분석해서 AGENTS.md의 스택 · 명령 표와 7장 영역 규칙 경로를 실제에 맞게 채워줘
```

### 3단계. 현재 구조 파악

| 명령 | 결과 |
|---|---|
| `/diagram 코드 구조도` | `docs/diagrams/architecture.mmd` |
| `/diagram erd` | DB 구조도 (DB가 있을 때) |
| `/check` | 린트 · 테스트가 도는지 확인 |

### 4단계. 작업 목록 만들기

`/next`는 `tasks/README.md`의 작업 표를 따라 움직입니다. (템플릿의 `task-001`은 예시라 지웁니다.)

- 새 기능 → `/plan 기능명`
- 작은 수정 → `tasks/README.md에 작업 등록해줘: ① … ② …`

### 5단계. 개발 반복

```text
/next  →  /clear  →  /next  →  /clear  → …
```

작업 하나가 끝날 때마다 자동으로 커밋됩니다.

### 6단계. 설정 파일 커밋

```bash
git add -A
git commit -m "Add NOMAD agent config"
git push
```

---

## B. 처음부터 시작

### 1단계. 폴더 만들기 + 적용

**PowerShell**
```powershell
~\workspace\dev\nomad-agent-os\install.ps1 init ~\workspace\dev\<프로젝트명> --name "<제품명>"
cd ~\workspace\dev\<프로젝트명>
git init -b main
claude
```

**Git Bash**
```bash
bash ~/workspace/dev/nomad-agent-os/install.sh init ~/workspace/dev/<프로젝트명> --name "<제품명>"
cd ~/workspace/dev/<프로젝트명> && git init -b main && claude
```

### 2단계. 기획 — `/plan <제품명>`

- `docs/`에 기획 문서 뼈대 8개가 생깁니다.
- **린 검증(00_LEAN)부터** 진행합니다. 통과하기 전에는 개발 작업을 만들지 않습니다.
- 제품 방향에 관한 질문만 사용자에게 묻고, 나머지는 팀이 채웁니다.
- 끝나면 `tasks/`에 작업 목록이 자동으로 생깁니다.

### 3단계. 그림 (선택)

```text
/diagram 회원가입 흐름
/diagram 결제 시퀀스
```

### 4단계. 디자인 — `/design`

1. 브리프 질문에 답합니다 (대상 · 주된 일 · 분위기 3단어 · 피할 것)
2. 디자인 토큰과 **미리보기 HTML**이 자동으로 생깁니다
3. 브라우저로 보고 `주색 더 진하게`처럼 요청합니다
4. **확정하기 전에는 화면 구현을 시작하지 않습니다**

### 5단계. AGENTS.md 확정

```text
기획 문서 기준으로 AGENTS.md 채워줘
```

### 6단계. 개발 반복

```text
/next  →  /clear  →  /next  →  /clear  → …
```

### 7단계. GitHub에 올리기

```bash
gh repo create <계정>/<프로젝트명> --private --source . --push
```

---

## 자주 묻는 것

**쉬었다가 다시 시작하려면?**
`/next`만 입력합니다. `tasks/NOW.md`에 적힌 곳에서 이어갑니다.

**같은 문제가 계속 실패하면?**
2번 실패하면 고문(advisor)이 자동으로 투입됩니다.

**`install … init`과 `git init`은 다른가요?**
다릅니다. `init`은 설정 파일만 복사하고 git은 건드리지 않습니다. `git init`은 B처럼 새 폴더에서만 씁니다.
