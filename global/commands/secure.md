---
description: 보안 점검(SBOM·취약점·라이선스) 또는 보안 설정 파일 생성
---
`security-baseline` 스킬 기준으로 진행한다. 인자: $ARGUMENTS (없으면 점검)

**점검** (인자 없음 · `--kev`)
1. `~/.claude/nomad/bin/secscan all . $ARGUMENTS` 실행. 출력의 "먼저 고칠 것"과 ⚠️만 본다(전체는 `.nomad/sbom/report.json`, 필요한 항목만 Read).
2. PRD `8. 보안·공급망`의 레벨과 비교해 부족한 것을 표(항목 / 현재 / 필요 / 작업 제안)로 보고한다. PRD가 없으면 레벨 판정 질문 3개(스킬 1절)를 사용자에게 묻는다.
3. 고치는 작업은 `tasks/README.md`에 등록만 한다(위험도 높음, 근거 = `security-baseline` 해당 reference). 바로 고치는 것은 사용자가 요청할 때만.

**설정** (`setup` · `setup --ci`)
1. `~/.claude/nomad/bin/secscan setup . [--ci]` 실행 — 실제 매니페스트만 Dependabot에 넣고, 기존 파일은 덮어쓰지 않는다(모델이 YAML을 손으로 쓰지 않음).
2. 생성된 파일을 `git diff --stat`으로 확인하고, 출력된 GitHub 저장소 설정(사람이 할 일)을 사용자에게 그대로 전달한다.
3. 커밋은 사용자 확인 후 `[security] Dependabot·SECURITY.md 추가` 형식으로.
