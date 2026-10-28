#!/usr/bin/env python3
"""handoff — 모델 한도에 걸렸을 때 작업을 다른 모델로 넘긴다. 모델 없이 터미널에서 동작(표준 라이브러리만).

  handoff codex [--dry-run]   인수인계 파일(.nomad/handoff/<시각>.md)을 만들고 codex 대화형을 실행 (--dry-run: 파일만)
  handoff claude              Codex로 작업한 뒤 Claude로 돌아올 때의 재진입 프롬프트 출력
  handoff sonnet              Opus만 한도에 걸렸을 때: Sonnet 임시 팀장 실행 안내 출력
"""
import os, re, shutil, subprocess, sys, time
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace"); sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
FAIL_PAT = re.compile(r"(error|fail|failed|exception|traceback|panic|fatal|✗|✘|cannot|not found|ERR!)", re.I)

SECRET_FILE = re.compile(r"(^|[\/ ])(\.env[^\/\s]*|[^\/\s]*\.pem|[^\/\s]*\.key|id_rsa[^\/\s]*)(\s|$|\|)", re.I)
MASKS = [
    (re.compile(r"((?:KEY|TOKEN|SECRET|PASSWORD)\w*\s*[=:]\s*)\S+", re.I), r"\1***"),
    (re.compile(r"(Bearer\s+)\S+", re.I), r"\1***"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*"), "eyJ***"),
]

def mask(line):
    for pat, rep in MASKS: line = pat.sub(rep, line)
    return line

def drop_secret_files(text):
    return "\n".join(l for l in text.splitlines() if not SECRET_FILE.search(l))

def run(args, cwd=None):
    """(rc, 출력). 실행 실패·rc!=0이면 출력 자리에 '(확인 불가: 첫 줄)'."""
    try:
        p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    except OSError as e:
        return 1, f"(확인 불가: {e})"
    if p.returncode != 0:
        first = ((p.stderr or p.stdout).strip().splitlines() or ["오류"])[0]
        return p.returncode, f"(확인 불가: {first})"
    return 0, p.stdout.strip()

def read(path, limit=None):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit) if limit else f.read()
    except OSError:
        return ""

def last_q_failure(root):
    """.nomad/logs/ 의 가장 최근 로그 마지막 15줄 중 문제 줄만, 비밀은 마스킹."""
    d = os.path.join(root, ".nomad", "logs")
    if not os.path.isdir(d): return "(q 로그 없음)"
    logs = sorted((os.path.join(d, n) for n in os.listdir(d) if n.endswith(".log")), key=os.path.getmtime)
    if not logs: return "(q 로그 없음)"
    lines = read(logs[-1]).splitlines()[-15:]
    hits = [mask(l) for l in lines if FAIL_PAT.search(l)]
    body = "\n".join(hits) if hits else "(문제 줄 없음 — 통과한 실행으로 보임)"
    return f"로그: {logs[-1]}\n{body}"

def build_handoff():
    now = time.strftime("%Y%m%d-%H%M%S")
    rc, top = run(["git", "rev-parse", "--show-toplevel"])
    root = top if rc == 0 else os.getcwd()
    now_md = read(os.path.join(root, "tasks", "NOW.md")) or "(tasks/NOW.md 없음)"
    # 읽기 전용: 체크포인트가 없으면 readguard changed(체크포인트를 저장해 버림)를 부르지 않는다
    crc, _ = run(["git", "rev-parse", "--verify", "-q", "refs/nomad/checkpoint"], cwd=root)
    if crc != 0:
        changed = "(체크포인트 없음 — 아래 git diff --stat 참고)"
    else:
        _, changed = run([sys.executable, os.path.join(HERE, "readguard.py"), "changed"], cwd=root)
        changed = drop_secret_files(changed)
    _, stat = run(["git", "diff", "--stat", "HEAD"], cwd=root)
    stat = drop_secret_files(stat)
    agents = "AGENTS.md" if os.path.exists(os.path.join(root, "AGENTS.md")) else "(AGENTS.md 없음)"
    doc = f"""# 인수인계 — {now}

이전 모델이 한도에 걸려 작업을 넘깁니다. 아래 순서로 이어서 하세요.

## 지켜야 할 것
- 프로젝트 규칙: `{agents}` 를 먼저 읽는다 (절대 규칙 위반 금지).
- NOW.md의 "남은 작업"부터 이어서 한다. 이미 끝난 일은 다시 하지 않는다.
- commit·push는 하지 않는다. 끝나면 `tasks/NOW.md`를 갱신한다.

## tasks/NOW.md
{now_md}

## 체크포인트 이후 바뀐 파일
{changed or "(없음)"}

## git diff --stat (HEAD 기준)
{stat or "(변경 없음)"}

## 마지막 q 실행 결과
{last_q_failure(root)}
"""
    out_dir = os.path.join(root, ".nomad", "handoff")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{now}.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(doc)
    return path

def cmd_codex(args):
    path = build_handoff()
    print(f"✅ 인수인계 파일: {path}")
    if "--dry-run" in args:
        print("(dry-run) codex는 실행하지 않았습니다. 실행하려면: handoff codex"); return 0
    exe = shutil.which("codex")
    if not exe:
        print("❌ codex CLI를 찾지 못했습니다. 설치 후 다시 실행하거나, 아래 지시를 Codex에 직접 붙여 넣으세요."); print(f"  {prompt_for(path)}"); return 1
    return subprocess.call([exe, prompt_for(path)])

def prompt_for(path):
    # 인자 길이 한도를 피하려고 본문 대신 파일 경로를 읽으라고만 지시한다
    return f"'{path}' 파일을 먼저 읽고, 그 안의 지시와 '남은 작업'에 따라 이어서 작업하라."

def cmd_claude():
    print("""■ Claude 재진입 프롬프트 (Claude Code 새 세션에 붙여 넣기)
  tasks/NOW.md를 읽고, `~/.claude/nomad/bin/delta --changed`로 체크포인트 이후 바뀐 파일만 확인한 뒤
  NOW.md의 "남은 작업"부터 이어서 하라. Codex가 한 변경은 git diff로 검토하고, 이미 끝난 일은 다시 하지 않는다.""")
    return 0

def cmd_sonnet():
    print("""■ Opus 한도 → Sonnet 임시 팀장
  1) 새 터미널에서 실행:  claude --model claude-sonnet-5-5
  2) 첫 메시지로 붙여 넣기:
     너는 지금부터 임시 팀장이다(Opus 한도 소진). tasks/NOW.md를 읽고 `delta --changed`로 시작하라.
     위험도 '높음' 작업(결제·인증·RLS·마이그레이션·외부 계약)은 착수하지 말고 NOW.md의 "열린 결정"에 적어 두어라.
     위임 규격과 검증 규칙은 평소 팀장과 같다. 끝나면 NOW.md를 갱신하라.""")
    return 0

def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__); return 0 if argv else 2
    c, rest = argv[0], argv[1:]
    if c == "codex": return cmd_codex(rest)
    if c == "claude": return cmd_claude()
    if c == "sonnet": return cmd_sonnet()
    print(f"알 수 없는 명령: {c}\n{__doc__}"); return 2

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
