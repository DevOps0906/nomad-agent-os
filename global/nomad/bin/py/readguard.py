#!/usr/bin/env python3
"""readguard — "이미 읽은 내용은 다시 읽지 않는다"를 Claude Code 훅으로 강제하고, 바뀐 줄만 전달한다.

훅 모드 (settings.json 에서 hook-read 래퍼로 호출, stdin = 훅 JSON):
  pre            PreToolUse(Read)
                 · 같은 대화에서 이미 읽은 범위 + 내용 그대로       → 차단: "맥락에 있는 내용을 쓰라"
                 · 일부만 읽은 긴 파일을 통째로 다시 읽음            → 차단: "안 읽은 범위만"
                 · 읽은 뒤 바뀐 파일(다른 에이전트·Bash·사람이 수정) → 차단 + **바뀐 줄을 차단 메시지에 담아 전달**
                   (변경이 크면 그냥 허용 — 통째 읽기가 더 싸다)
                 · 같은 요청을 연속 두 번째 하면 허용(맥락에서 사라진 경우의 탈출구 — 절대 갇히지 않음)
  post           PostToolUse(Read|Edit|Write|MultiEdit) : 이 대화가 본/쓴 내용을 대화별 스냅샷으로 기록
  session-start  SessionStart(startup·resume·clear·compact) : 이 대화 기록 초기화 + 7일 지난 기록 정리
CLI 모드 (사람·모든 AI 도구가 Bash로):
  delta <파일...>                 마지막으로 delta로 본 뒤 바뀐 줄만 (훅과 별개의 기준)
  changed [--since REF]           체크포인트 이후 바뀐 파일 목록 (새 세션 재진입용)
  checkpoint                      현재 상태를 체크포인트로 저장 (refs/nomad/checkpoint)
  reset [파일...|--all]           이 폴더의 훅 기록 삭제
원칙: 훅 내부 오류는 절대 작업을 막지 않는다(fail-open → exit 0). 차단은 exit 2 뿐이다.
"""
import difflib, hashlib, json, os, shutil, subprocess, sys, time
try:  # 한국어 Windows(cp949) 콘솔에서도 이모지·한글 출력이 죽지 않게
    sys.stdout.reconfigure(encoding="utf-8", errors="replace"); sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BIG_LINES = 150          # 이보다 짧은 파일이 바뀌면 그냥 다시 읽게 둔다(delta보다 싸다)
DEFAULT_LIMIT = 2000     # Read 도구 기본 줄 수
SNAP_MAX = 2_000_000     # 스냅샷 최대 크기(바이트)
DIFF_MAX_LINES = 120     # 차단 메시지에 담을 변경 줄 상한 — 넘으면 차단하지 않고 Read 허용
DIFF_MAX_CHARS = 9000
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".pdf", ".ipynb", ".zip", ".gz", ".woff", ".woff2", ".ttf", ".mp4", ".mp3", ".wav"}

# ───────── 공통 ─────────
def norm(p):
    return os.path.normcase(os.path.abspath(p)).replace("\\", "/")

def base_dir(cwd=None):
    root = os.path.join(cwd or os.getcwd(), ".nomad")
    d = os.path.join(root, "read")
    os.makedirs(d, exist_ok=True)
    gi = os.path.join(root, ".gitignore")
    if not os.path.exists(gi):  # 스냅샷(비밀값 포함 가능)이 실수로 커밋되지 않게
        with open(gi, "w", encoding="utf-8") as f: f.write("*\n")
    return d

def is_text(path):
    try:
        if os.path.splitext(path)[1].lower() in SKIP_EXT or os.path.getsize(path) > SNAP_MAX: return False
        with open(path, "rb") as f: return b"\0" not in f.read(8192)
    except OSError:
        return False

def sha(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    return h.hexdigest()

def lines(path):
    with open(path, encoding="utf-8", errors="replace", newline=None) as f: return f.read().splitlines()

def key_of(d):
    """대화(맥락) 단위 키. 하위 에이전트는 훅 입력에 agent_id가 있어 따로 기록된다."""
    raw = f"{d.get('session_id') or 'nosession'}|{d.get('agent_id') or ''}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]

def conv_dir(bd, key):
    d = os.path.join(bd, key); os.makedirs(os.path.join(d, "snap"), exist_ok=True); return d

def load(p):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return {}

def save(p, data):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f)
    os.replace(tmp, p)

def snap_file(cd, ap): return os.path.join(cd, "snap", hashlib.sha1(ap.encode()).hexdigest() + ".txt")

def write_snap(cd, path, ap):
    try: shutil.copyfile(path, snap_file(cd, ap))
    except OSError: pass

def read_snap(cd, ap):
    p = snap_file(cd, ap)
    if not os.path.exists(p): return None
    with open(p, encoding="utf-8", errors="replace", newline=None) as f: return f.read().splitlines()

def req_range(ti, n):
    off = int(ti.get("offset") or 1); lim = int(ti.get("limit") or DEFAULT_LIMIT)
    a = max(off, 1); return [a, max(a, min(a + lim - 1, n))]

def covered(ranges, r): return any(a <= r[0] and r[1] <= b for a, b in ranges)

def merge(ranges, r):
    out = []
    for a, b in sorted(ranges + [r]):
        if out and a <= out[-1][1] + 1: out[-1][1] = max(out[-1][1], b)
        else: out.append([a, b])
    return out

def render_diff(old, new):
    """바뀐 줄만, 줄 번호와 함께. 덧붙임이면 새 줄만."""
    if new[:len(old)] == old:
        body = [f"➕ 끝에 {len(new) - len(old)}줄 추가 (기존 {len(old)}줄 생략)"]
        body += [f"{i:>6}\t{l}" for i, l in enumerate(new[len(old):], len(old) + 1)]
        return body
    sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    ops = [o for o in sm.get_opcodes() if o[0] != "equal"]
    body = [f"✏️ 변경 {len(ops)}곳 (이전 {len(old)}줄 → 현재 {len(new)}줄)"]
    for tag, i1, i2, j1, j2 in ops:
        body.append(f"@@ 이전 {i1 + 1}-{i2} → 현재 {j1 + 1}-{j2}")
        body += [f"-{k + 1:>5}\t{old[k]}" for k in range(i1, i2)]
        body += [f"+{k + 1:>5}\t{new[k]}" for k in range(j1, j2)]
    return body

def hook_input():
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else {}

def block(msg):
    sys.stderr.write(msg.rstrip() + "\n"); return 2

# ───────── 훅 ─────────
def cmd_pre():
    d = hook_input()
    if d.get("tool_name") != "Read": return 0
    ti = d.get("tool_input") or {}; path = ti.get("file_path")
    if not path or not os.path.isfile(path) or not is_text(path): return 0
    bd = base_dir(d.get("cwd")); cd = conv_dir(bd, key_of(d)); lp = os.path.join(cd, "ledger.json")
    led = load(lp); ap = norm(path); ent = led.get(ap)
    if not ent: return 0
    cur = sha(path); new = lines(path); n = len(new); r = req_range(ti, n)
    req_sig = f"{cur}:{r[0]}-{r[1]}:{bool(ti.get('offset') or ti.get('limit'))}"
    if ent.get("last_block") == req_sig:          # 같은 요청 두 번째 → 허용(갇히지 않게)
        ent.pop("last_block", None); save(lp, led); return 0
    ranged = bool(ti.get("offset") or ti.get("limit"))

    if cur == ent["sha"]:
        if covered(ent["ranges"], r) or (ent.get("full") and not ranged):
            ent["last_block"] = req_sig; save(lp, led)
            return block(f"[readguard] 이미 이 대화에서 읽은 내용입니다(변경 없음): {path} {r[0]}-{r[1]}줄. "
                         "맥락에 있는 내용을 그대로 쓰세요. 다른 부분이 필요하면 아직 안 읽은 범위만 offset/limit로 읽으세요. "
                         "(맥락에서 사라진 경우에만 같은 Read를 한 번 더 요청하면 허용됩니다.)")
        if not ranged and n > BIG_LINES:
            gaps, pos = [], 1
            for a, b in ent["ranges"]:
                if a > pos: gaps.append(f"{pos}-{a - 1}")
                pos = max(pos, b + 1)
            if pos <= n: gaps.append(f"{pos}-{n}")
            ent["last_block"] = req_sig; save(lp, led)
            return block(f"[readguard] {path}: {', '.join(f'{a}-{b}' for a, b in ent['ranges'])}줄은 이미 읽었습니다(변경 없음). "
                         f"처음부터 다시 읽지 말고 안 읽은 범위만 offset/limit로 읽으세요 → {', '.join(gaps)}")
        return 0

    # 읽은 뒤 바뀐 파일
    if n <= BIG_LINES: return 0
    old = read_snap(cd, ap)
    if old is None: return 0
    diff = render_diff(old, new)
    if len(diff) > DIFF_MAX_LINES or sum(len(x) for x in diff) > DIFF_MAX_CHARS:
        return 0                                    # 변경이 크면 통째로 읽는 편이 낫다
    if ranged and not any(a <= r[1] and r[0] <= b for a, b in ent["ranges"]):
        return 0                                    # 안 읽었던 범위를 새로 읽는 것은 허용
    ent["sha"] = cur
    if ent.get("full"): ent["ranges"] = [[1, max(n, 1)]]
    write_snap(cd, path, ap); save(lp, led)         # 이제 이 대화는 최신 내용을 안다
    return block(f"[readguard] {path} 는 이 대화에서 읽은 뒤 바뀌었습니다. 처음부터 다시 읽지 않도록 바뀐 줄만 전달합니다 "
                 "(이 내용을 맥락의 이전 내용에 적용해 쓰세요):\n" + "\n".join(diff))

def cmd_post():
    d = hook_input()
    tool = d.get("tool_name"); ti = d.get("tool_input") or {}; path = ti.get("file_path")
    if tool not in ("Read", "Edit", "Write", "MultiEdit") or not path or not os.path.isfile(path) or not is_text(path): return 0
    bd = base_dir(d.get("cwd")); cd = conv_dir(bd, key_of(d)); lp = os.path.join(cd, "ledger.json")
    led = load(lp); ap = norm(path); ent = led.get(ap); cur = sha(path); n = len(lines(path))
    if tool == "Read":
        r = req_range(ti, n)
        ranges = merge(ent["ranges"], r) if ent and ent["sha"] == cur else [r]
        full = covered(ranges, [1, max(n, 1)])
    else:   # 이 대화가 직접 쓴 내용 — 전체를 알던 파일·새로 쓴 파일은 계속 전체를 안다
        if not ent and tool != "Write": return 0
        full = tool == "Write" or bool(ent and ent.get("full"))
        ranges = [[1, max(n, 1)]] if full else ent["ranges"]
    led[ap] = {"sha": cur, "ranges": ranges, "full": full, "t": int(time.time())}
    save(lp, led); write_snap(cd, path, ap)
    return 0

def cmd_session_start():
    d = hook_input(); bd = base_dir(d.get("cwd")); key = key_of(d)
    for name in os.listdir(bd):
        p = os.path.join(bd, name)
        if not os.path.isdir(p) or name == "cli": continue
        if name == key or time.time() - os.path.getmtime(p) > 7 * 86400:
            shutil.rmtree(p, ignore_errors=True)
    return 0

# ───────── CLI ─────────
def cmd_delta(paths):
    bd = base_dir(); cd = conv_dir(bd, "cli"); code = 0
    for path in paths:
        if not os.path.isfile(path): print(f"❌ 없음: {path}"); code = 1; continue
        ap = norm(path); new = lines(path); old = read_snap(cd, ap)
        if old is None:
            print(f"ℹ️ {path}: 처음 보는 파일({len(new)}줄) — 기준을 저장했습니다. 내용이 필요하면 필요한 범위만 읽으세요.")
        elif old == new:
            print(f"✅ {path}: 마지막으로 본 뒤 변경 없음 ({len(new)}줄)")
        else:
            print(f"{path}:"); print("\n".join(render_diff(old, new)))
        write_snap(cd, path, ap)
    return code

def git(*args):
    p = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def cmd_changed(args):
    rc, _, _ = git("rev-parse", "--is-inside-work-tree")
    if rc != 0: print("git 저장소가 아니어서 체크포인트 비교를 할 수 없습니다. 개별 파일은 delta를 쓰세요."); return 1
    if "--since" in args: since = args[args.index("--since") + 1]
    else:
        rc, since, _ = git("rev-parse", "--verify", "-q", "refs/nomad/checkpoint")
        if rc != 0 or not since:
            print("체크포인트가 없습니다 → 지금 상태로 저장합니다. 다음 세션부터 이후 변경만 봅니다."); return cmd_checkpoint()
    _, head, _ = git("rev-parse", "--verify", "-q", "HEAD")
    now = worktree_commit(head or None)
    rc, out, err = git("diff", "--numstat", "-M", since, now or "HEAD", "--")
    if rc != 0: print(f"❌ 체크포인트 비교 실패: {err}"); return 1
    print(f"■ 체크포인트 {since[:10]} 이후 바뀐 파일 — 이것만 보세요(처음부터 다시 읽지 않기)")
    rows = [l.split("\t") for l in out.splitlines() if l]
    for a, dl, p in rows: print(f"  {p}  (+{a} -{dl})" if a != "-" else f"  {p}  (바이너리)")
    news = []
    if not rows and not news: print("  (변경 없음 — 다시 읽을 것 없음)")
    return 0

def worktree_commit(parent):
    """작업 트리 전체(추적 안 된 새 파일 포함, .gitignore 존중)를 임시 인덱스로 커밋 객체로 만든다."""
    rc, gd, _ = git("rev-parse", "--absolute-git-dir")
    if rc != 0: return None
    env = dict(os.environ, GIT_INDEX_FILE=os.path.join(gd, "nomad-index"))
    run = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True, env=env)
    if parent: run("read-tree", parent)
    run("add", "-A", "--", ".", ":(exclude).nomad")
    tree = run("write-tree").stdout.strip()
    if not tree: return None
    args = ["commit-tree", tree, "-m", "nomad checkpoint"] + (["-p", parent] if parent else [])
    return run(*args).stdout.strip() or None

def cmd_checkpoint():
    _, head, _ = git("rev-parse", "--verify", "-q", "HEAD")
    ref = worktree_commit(head or None)
    if not ref: print("❌ 체크포인트를 만들 수 없습니다(git 저장소 확인)."); return 1
    rc, _, err = git("update-ref", "refs/nomad/checkpoint", ref)   # 참조로 고정 → GC로 사라지지 않음
    if rc != 0: print(f"❌ 체크포인트 저장 실패: {err}"); return 1
    print(f"✅ 체크포인트 저장: {ref[:10]} — 다음 세션은 `delta --changed`로 이후 변경만 봅니다")
    return 0

def cmd_reset(args):
    bd = base_dir()
    for name in os.listdir(bd):
        p = os.path.join(bd, name)
        if not os.path.isdir(p): continue
        if "--all" in args or not args: shutil.rmtree(p, ignore_errors=True); continue
        lp = os.path.join(p, "ledger.json"); led = load(lp)
        for a in args: led.pop(norm(a), None)
        if os.path.exists(lp): save(lp, led)
    print("✅ 기록 초기화: " + (" ".join(args) if args else "전체"))
    return 0

def main():
    if len(sys.argv) < 2: print(__doc__); return 2
    c, rest = sys.argv[1], sys.argv[2:]
    if c in ("pre", "post", "session-start"):
        try:
            return {"pre": cmd_pre, "post": cmd_post, "session-start": cmd_session_start}[c]()
        except Exception as e:      # fail-open
            sys.stderr.write(f"[readguard] 내부 오류 무시: {e}\n"); return 0
    if c == "delta":
        if rest and rest[0] == "--changed": return cmd_changed(rest[1:])
        if rest and rest[0] == "--checkpoint": return cmd_checkpoint()
        if not rest: print("사용: delta <파일...> | delta --changed [--since REF] | delta --checkpoint"); return 2
        return cmd_delta(rest)
    if c == "changed": return cmd_changed(rest)
    if c == "checkpoint": return cmd_checkpoint()
    if c == "reset": return cmd_reset(rest)
    print(__doc__); return 2

if __name__ == "__main__":
    sys.exit(main())
