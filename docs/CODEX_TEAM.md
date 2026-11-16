# Codex 네이티브 멀티에이전트

Claude Code 팀과 별도로 Codex가 직접 역할별 하위 에이전트를 실행할 수 있도록 구성한다. `.codex/agents/*.toml` 네이티브 형식을 사용한다.

## 적용

설치된 NOMAD에서는 `nomad-os codex init <프로젝트> --worker-model <지원_ID>`를 사용한다. 설치 전에는 `python global/nomad/bin/py/codex_team.py init <프로젝트> --worker-model <지원_ID>`로 실행할 수 있다. 주 모델 기본값은 `gpt-6.1-sol`이며 `--primary-model`로 명시적으로 변경 가능하다.

`--worker-model`에는 사용자가 지정하고 실제 모델 목록에서 확인한 ID가 필요하다. 예를 들어 지원되는 환경에서 `gpt-6-luna`를 사용할 수 있다. `luna-6.1`과 같은 미확인 이름을 지원 ID로 간주하거나 자동 대체하지 않는다. 모델을 확인하기 전에는 기존 설정을 바꾸지 않는다.

`nomad-os codex check <프로젝트>`는 config와 5개 역할의 스키마/모델 일치를 확인한다. check는 Python 3.11+, init은 Python 3.8+를 지원한다. 네트워크·유료 모델 호출·전역 설정 변경은 하지 않는다. 모델 접근 가능 여부는 확인하지 않는다.

## 역할과 운영

`nomad_scout`, `nomad_designer`, `nomad_builder`, `nomad_tester`, `nomad_reviewer`를 만든다. 모든 역할 모델은 명시한 부 모델로 고정한다. 주 에이전트가 최대 3개 독립 작업에 소유 파일·근거·수용 기준을 정해 위임하고 최종 통합한다. 위임 깊이는 1이며 작업자는 다른 작업자의 수정을 되돌리지 않는다. 읽기 전용 scout/reviewer 제약은 역할 지침이며 별도 OS 샌드박스를 제공하지 않는다.

세부 규칙은 `global/nomad/CODEX_TEAM.md`다. 프로젝트의 AGENTS.md에서 해당 파일 또는 프로젝트에 복사한 지침을 연결한다. 기존 sandbox/approval/MCP 설정을 보존하며, config 변경 전 `config.toml.nomad-backup`을 한 번 만든다. 사용자 정의 역할 충돌은 덮어쓰지 않고 중단한다. init은 재실행 가능하며 기존 프로젝트 config를 갱신할 때 명시적으로 실행한다. 일반 `nomad-os init`은 기존 파일을 보존하므로 모델 설정을 강제로 덮어쓰지 않는다.

파일을 적용한 다음 신뢰된 프로젝트에서 새 Codex 세션을 시작한다. 실행 중인 주 에이전트의 모델은 파일 수정으로 전환되지 않는다. 설정/검증 통과를 실제 멀티에이전트 실행 완료로 보고하지 않는다.

공식 문서: [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
