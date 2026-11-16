#!/usr/bin/env python3
"""NOMAD Codex native team initializer. No model calls or global config writes."""
import argparse
import json
from pathlib import Path
import re
import sys

PRIMARY = "gpt-6.1-sol"
ROLES = {
    "nomad_scout": ("구조·호출 관계를 확인하는 읽기 전용 탐색", "읽기 전용이다. codebase-memory 스킬과 커버리지 확인 후 필요한 소스만 읽는다. 파일을 수정하지 않는다."),
    "nomad_designer": ("지정된 화면·스타일 범위의 UX 구현", "부모가 지정한 화면·스타일 파일만 소유한다. 반응형 3구간과 접근성을 확인하고 서버·인증 계약을 바꾸지 않는다."),
    "nomad_builder": ("명시된 파일 범위의 기능 구현", "부모가 지정한 파일만 수정한다. 다른 작업자의 변경을 되돌리지 말고 맞춰서 구현한다. 관련 테스트를 실행한다."),
    "nomad_tester": ("지정된 기능의 회귀·부정 시나리오 검증", "테스트 파일과 검증 책임만 맡는다. 제품 코드를 수정해야 하면 부모에게 근거를 보고한다. 실행하지 않은 검사를 통과했다고 하지 않는다."),
    "nomad_reviewer": ("diff 중심의 독립 읽기 전용 리뷰", "읽기 전용이다. 정확성·회귀·인가·데이터 손실을 검토한다. 재현 조건과 파일 위치가 있는 발견만 우선 보고한다."),
}
COMMON = " AGENTS.md와 관련 영역 규칙을 따른다. 혼자 작업하는 저장소가 아니므로 타인의 변경을 되돌리지 않는다. 하위 에이전트를 만들거나 commit/push하지 않는다. 최종 보고는 변경 파일·검증 결과·남은 위험을 20줄 이내로 작성한다."

def valid_model(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", value):
        raise ValueError("모델 ID 형식이 올바르지 않습니다.")
    return value

def set_key(text, section, key, value):
    """Replace only one direct key while preserving unrelated TOML and comments."""
    lines = text.splitlines(keepends=True)
    start, end = 0, len(lines)
    if section:
        start = next((i + 1 for i, line in enumerate(lines) if re.fullmatch(r"\[" + re.escape(section) + r"\]\s*(?:#.*)?", line.strip())), None)
        if start is None:
            return text.rstrip() + "\n\n[" + section + "]\n" + key + " = " + value + "\n"
    for i in range(start, len(lines)):
        if lines[i].lstrip().startswith("["):
            end = i
            break
    matches = [i for i in range(start, end) if re.match(r"\s*" + re.escape(key) + r"\s*=", lines[i])]
    if len(matches) > 1:
        raise ValueError("중복 TOML 키: " + key)
    replacement = key + " = " + value + "\n"
    if matches:
        lines[matches[0]] = replacement
    else:
        lines.insert(start, replacement)
    return "".join(lines)

def role_text(name, model):
    description, instructions = ROLES[name]
    return '# NOMAD managed Codex role\nname = ' + json.dumps(name) + '\ndescription = ' + json.dumps(description, ensure_ascii=False) + '\nmodel = ' + json.dumps(model) + '\ndeveloper_instructions = ' + json.dumps(instructions + COMMON, ensure_ascii=False) + '\n'

def initialize(project, worker_model, primary_model=PRIMARY):
    root = Path(project).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("프로젝트 디렉터리가 아닙니다.")
    valid_model(worker_model); valid_model(primary_model)
    codex = root / ".codex"
    paths = [codex / "config.toml", *[codex / "agents" / (name + ".toml") for name in ROLES]]
    for path in paths:
        if root not in path.resolve().parents:
            raise ValueError("프로젝트 밖으로 연결된 설정 경로는 변경하지 않습니다.")
    config = paths[0]
    text = config.read_text(encoding="utf-8-sig") if config.exists() else 'approval_policy = "on-request"\nsandbox_mode = "workspace-write"\n'
    text = set_key(text, None, "model", json.dumps(primary_model))
    for key, value in (("enabled", "true"), ("default_subagent_model", json.dumps(worker_model)), ("max_concurrent_threads_per_session", "3")):
        text = set_key(text, "agents", key, value)
    # Preflight all conflicts before writing anything. Custom roles are never overwritten.
    for path in paths[1:]:
        if path.exists() and not path.read_text(encoding="utf-8-sig").startswith("# NOMAD managed Codex role\n"):
            raise ValueError("사용자 역할 파일을 보존합니다: " + str(path))
    try:
        import tomllib
    except ImportError:
        tomllib = None
    if tomllib:
        tomllib.loads(text)
    config.parent.mkdir(parents=True, exist_ok=True)
    if config.exists() and config.read_text(encoding="utf-8-sig") != text:
        backup = config.with_name("config.toml.nomad-backup")
        if not backup.exists():
            backup.write_bytes(config.read_bytes())
    config.write_text(text, encoding="utf-8")
    for name, path in zip(ROLES, paths[1:]):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(role_text(name, worker_model), encoding="utf-8")
    return {"project": str(root), "primary_model": primary_model, "worker_model": worker_model, "roles": list(ROLES), "availability_verified": False}

def check(project):
    try:
        import tomllib
    except ImportError:
        raise ValueError("check는 Python 3.11+가 필요합니다. init은 Python 3.8+에서 지원합니다.")
    root = Path(project).resolve(strict=True)
    config = tomllib.loads((root / ".codex/config.toml").read_text(encoding="utf-8-sig"))
    agents = config.get("agents", {})
    primary, worker = config.get("model"), agents.get("default_subagent_model")
    issues = []
    if not primary: issues.append("주 모델 미지정")
    if not worker: issues.append("부 모델 미지정 — 정확한 지원 ID 확인 필요")
    if agents.get("enabled") is not True: issues.append("멀티에이전트 비활성")
    for name in ROLES:
        path = root / ".codex/agents" / (name + ".toml")
        if not path.exists():
            issues.append("역할 없음: " + name); continue
        data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
        if data.get("name") != name or not data.get("description") or not data.get("developer_instructions"):
            issues.append("역할 스키마 오류: " + name)
        if not worker or data.get("model") != worker:
            issues.append("부 모델 불일치: " + name)
    return {"project": str(root), "primary_model": primary, "worker_model": worker, "issues": issues, "availability_verified": False}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    subs = ap.add_subparsers(dest="command", required=True)
    init = subs.add_parser("init"); init.add_argument("project", nargs="?", default=".")
    init.add_argument("--primary-model", default=PRIMARY); init.add_argument("--worker-model", required=True)
    verify = subs.add_parser("check"); verify.add_argument("project", nargs="?", default=".")
    args = ap.parse_args()
    try:
        result = initialize(args.project, args.worker_model, args.primary_model) if args.command == "init" else check(args.project)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("issues") else 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr); return 1

if __name__ == "__main__":
    sys.exit(main())
