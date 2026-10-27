---
description: 단순 텍스트 작업을 로컬/오픈소스 LLM(Ollama 등)에 맡기고 결과 파일만 받기
---
요청: $ARGUMENTS

맞는 일(요약·추출·번역·커밋 메시지·Mermaid 초안·분류)인지 먼저 판단한다. 설계·보안·결제 판단이면 맡기지 않고 이유를 말한다.
`~/.claude/nomad/bin/oss "<지시>" <입력 파일...> -o .nomad/oss/<이름>.md` 로 실행하고, 결과 파일을 읽어 검토한 뒤 사용한다.
연결 실패면 `ollama serve` · `NOMAD_OSS_URL` · `NOMAD_OSS_MODEL` 확인을 안내하고 Claude 팀원(intern)으로 대신 처리한다.
