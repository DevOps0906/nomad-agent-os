#!/usr/bin/env python3
"""nomad-doctor — 멀티에이전트 구성 점검 · 자동 구성 (/agent-check 가 부른다, 모델 토큰 0).

사용: nomad-doctor [프로젝트=.] [--fix] [--json]
점검: ① 전역 설치(팀원·스킬·명령·도구·훅·CLAUDE.md, 본체 레포와 같은 버전인지) ② 프로젝트 적용(AGENTS.md·규칙·
      tasks·읽기 차단·.gitignore, 템플릿 미작성, 규칙 경로 불일치, 같은 이름 팀원 충돌) ③ 모듈 ④ 기획→시안(spec 최신)
      ⑤ 보안 기본 ⑥ 준비물(Python·git·Node·Chrome) ⑦ 상시 로드 토큰
--fix: 안전한 것만 고친다 — 전역 재설치 · 프로젝트 init(기존 파일 보존·병합) · plan2spec. 삭제는 하지 않는다.
"""
import argparse, glob, hashlib, importlib.util, json, os, re, shutil, subprocess, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace"); sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
CL = os.path.join(os.environ.get("HOME") or os.path.expanduser("~"), ".claude")
ROWS = []          # (영역, 항목, 상태, 내용, 고칠 방법 key)
FIX = {}           # key → (설명, 명령 list)


def add(area, item, st, msg, fix=None):
    ROWS.append((area, item, st, msg, fix))


def sha(p):
    try:
        with open(p, "rb") as f: return hashlib.sha1(f.read().replace(b"\r\n", b"\n")).hexdigest()
    except OSError:
        return None


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def repo_root():
    """설치 때 만든 nomad-os 실행기에서 본체 레포 위치를 읽는다(없으면 이 파일이 레포 안에 있는지)."""
    p = os.path.join(CL, "nomad", "bin", "nomad-os")
    try:
        m = re.search(r'exec bash "(.+?)/install\.sh"', open(p, encoding="utf-8").read())
        if m:
            r = m.group(1)
            if re.match(r"^/[a-zA-Z]/", r): r = r[1].upper() + ":" + r[2:]       # /d/x → D:/x (Git Bash 경로)
            if os.path.exists(os.path.join(r, "install.sh")): return os.path.normpath(r)
    except OSError:
        pass
    r = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
    return r if os.path.exists(os.path.join(r, "install.sh")) else None


def bash():
    if os.name != "nt": return shutil.which("bash")
    git = shutil.which("git")
    cands = [os.environ.get("CLAUDE_CODE_GIT_BASH_PATH", "")]
    if git: cands.append(os.path.join(os.path.dirname(os.path.dirname(git)), "bin", "bash.exe"))
    cands += [r"C:\Program Files\Git\bin\bash.exe", shutil.which("bash") or ""]
    return next((c for c in cands if c and os.path.exists(c) and "System32" not in c), None)


# ---------- ① 전역 ----------
def check_global(repo):
    names = lambda d, ext="": sorted(x for x in os.listdir(d) if not x.startswith(".") and (not ext or x.endswith(ext))) if os.path.isdir(d) else []
    src = os.path.join(repo, "global") if repo else None
    missing, outdated = [], []
    for sub, ext in (("agents", ".md"), ("commands", ".md"), ("skills", "")):
        want = names(os.path.join(src, sub), ext) if src else []
        have = set(names(os.path.join(CL, sub), ext))
        miss = [w for w in want if w not in have]
        missing += [f"{sub}/{m}" for m in miss]
        if src:
            for w in want:
                if w in miss: continue
                a, b = os.path.join(src, sub, w), os.path.join(CL, sub, w)
                files = [os.path.relpath(f, a) for f in glob.glob(os.path.join(a, "**", "*"), recursive=True) if os.path.isfile(f)] if os.path.isdir(a) else [""]
                if any(sha(os.path.join(a, f) if f else a) != sha(os.path.join(b, f) if f else b) for f in files): outdated.append(f"{sub}/{w}")
        add("전역", sub, "✅" if want and not miss else ("❌" if miss else "⚠️"),
            f"{len(want) - len(miss)}/{len(want)}" + (f" — 없음: {', '.join(miss[:4])}" if miss else "") if want else f"{len(have)}개 (본체 레포를 못 찾아 비교 불가)",
            "global" if miss else None)
    bdir = os.path.join(CL, "nomad", "bin")
    want = [f for f in names(os.path.join(src, "nomad", "bin")) if os.path.isfile(os.path.join(src, "nomad", "bin", f))] if src else []
    miss = [w for w in want if not os.path.exists(os.path.join(bdir, w))]
    if src:
        for f in want + [os.path.join("py", x) for x in names(os.path.join(src, "nomad", "bin", "py"), ".py")]:
            if f in miss: continue
            if sha(os.path.join(src, "nomad", "bin", f)) != sha(os.path.join(bdir, f)): outdated.append(f"bin/{f}")
        for f in ("TEAM.md", "CORE.md"):
            if sha(os.path.join(src, "nomad", f)) != sha(os.path.join(CL, "nomad", f)): outdated.append(f"nomad/{f}")
    add("전역", "도구", "✅" if want and not miss else ("❌" if miss else "⚠️"),
        f"{len(want) - len(miss)}/{len(want)}" + (f" — 없음: {', '.join(miss[:4])}" if miss else "") if want else "비교 불가", "global" if miss else None)
    try:
        st = json.load(open(os.path.join(CL, "settings.json"), encoding="utf-8-sig"))
        cmds = json.dumps(st.get("hooks", {}))
        n = sum(1 for ev in ("SessionStart", "PreToolUse", "PostToolUse") if ev in st.get("hooks", {}) and "hook-read" in json.dumps(st["hooks"][ev]))
    except (OSError, ValueError):
        n = 0
    add("전역", "읽기 차단 훅", "✅" if n == 3 else "❌", f"{n}/3 (SessionStart · PreToolUse · PostToolUse)", "global" if n < 3 else None)
    try:
        ok = "@nomad/TEAM.md" in open(os.path.join(CL, "CLAUDE.md"), encoding="utf-8").read()
    except OSError:
        ok = False
    add("전역", "CLAUDE.md 연결", "✅" if ok else "❌", "@nomad/TEAM.md " + ("있음" if ok else "없음 — 팀 규칙이 로드되지 않음"), None if ok else "global")
    if outdated:
        add("전역", "버전", "⚠️", f"본체 레포와 다른 파일 {len(outdated)}개 (예: {', '.join(outdated[:3])}) — git pull 후 재설치", "global")
    elif repo:
        add("전역", "버전", "✅", "본체 레포와 같음")
    if missing or outdated or n < 3 or not ok:
        FIX["global"] = ("전역 재설치 (기존 설정 보존, 백업 생성)", ["install.sh", "--no-path"])


# ---------- ② 프로젝트 ----------
TEMPLATE_MARKS = ["<프로젝트명>", "<한 문장", "<프로젝트 고유 규칙"]
NOMAD_AGENTS = {"advisor", "builder", "challenger", "designer", "diagrammer", "intern", "planner", "reviewer", "scout", "tester"}


def check_project(proj, repo):
    j = lambda *p: os.path.join(proj, *p)
    need = ["AGENTS.md", "CLAUDE.md", os.path.join(".claude", "settings.json"), os.path.join("tasks", "README.md"), os.path.join("tasks", "NOW.md")]
    miss = [n for n in need if not os.path.exists(j(n))]
    add("프로젝트", "NOMAD 적용", "✅" if not miss else "❌", "AGENTS.md · CLAUDE.md · 설정 · tasks" + (f" — 없음: {', '.join(m.replace(os.sep, '/') for m in miss)}" if miss else ""),
        "init" if miss else None)
    if os.path.exists(j("AGENTS.md")):
        t = open(j("AGENTS.md"), encoding="utf-8").read()
        left = [m for m in TEMPLATE_MARKS if m in t]
        add("프로젝트", "AGENTS.md 내용", "⚠️" if left else "✅",
            f"템플릿 자리표시 남음: {', '.join(left)} → 'AGENTS.md를 이 저장소에 맞게 채워줘'" if left else "작성됨")
    if os.path.exists(j("CLAUDE.md")) and "@AGENTS.md" not in open(j("CLAUDE.md"), encoding="utf-8").read():
        add("프로젝트", "CLAUDE.md 연결", "❌", "@AGENTS.md 없음 — 프로젝트 규칙이 로드되지 않음", "init")
    tpl = os.path.join(repo, "project-template") if repo else None
    if tpl and os.path.exists(j(".claude", "settings.json")):
        try:
            want = json.load(open(os.path.join(tpl, ".claude", "settings.json"), encoding="utf-8"))["permissions"]["deny"]
            have = json.load(open(j(".claude", "settings.json"), encoding="utf-8-sig")).get("permissions", {}).get("deny", [])
            lack = [x for x in want if x not in have]
            add("프로젝트", "읽기 차단(.env·키)", "✅" if not lack else "❌", f"{len(want) - len(lack)}/{len(want)}" + (f" — 없음: {', '.join(lack[:3])}" if lack else ""), "init" if lack else None)
        except (OSError, ValueError, KeyError):
            add("프로젝트", "읽기 차단(.env·키)", "⚠️", ".claude/settings.json 해석 실패 — JSON 확인")
    if tpl and os.path.exists(os.path.join(tpl, ".gitignore")):
        want = [l.strip() for l in open(os.path.join(tpl, ".gitignore"), encoding="utf-8") if l.strip()]
        have = set(l.strip() for l in open(j(".gitignore"), encoding="utf-8")) if os.path.exists(j(".gitignore")) else set()
        lack = [x for x in want if x not in have]
        add("프로젝트", ".gitignore", "✅" if not lack else "❌", "비밀·키·.nomad 제외" + (f" — 없음: {', '.join(lack[:4])}" if lack else ""), "init" if lack else None)
    # 규칙 경로가 실제 폴더와 맞는지
    rules = glob.glob(j(".claude", "rules", "*.md"))
    dead = []
    for r in rules:
        paths = re.findall(r'^\s*-\s*"([^"]+)"', open(r, encoding="utf-8").read(), re.M)
        roots = [p.split("*")[0].rstrip("/") for p in paths]
        if roots and not any(glob.glob(j(x)) for x in roots if x): dead.append(f"{os.path.basename(r)}({', '.join(paths)})")
    if rules:
        dirs = sorted({d.replace(os.sep, "/") for pat in ("apps/*", "packages/*", "services/*", "workers/*", "src", "lib", "supabase") for d in [os.path.relpath(x, proj) for x in glob.glob(j(pat)) if os.path.isdir(x)]})
        code = bool(dirs)
        add("프로젝트", "영역 규칙 경로", "✅" if not dead else ("⚠️" if code else "ℹ️"),
            ("모두 실제 폴더와 맞음" if not dead else f"맞는 폴더 없음: {', '.join(dead)}" + (f" → 실제 폴더: {', '.join(dirs[:6])} 에 맞게 paths 수정" if code else " (코드가 아직 없으면 무시)")))
    # tasks 템플릿 예시 행
    if os.path.exists(j("tasks", "README.md")) and "| task-001 | 프로젝트 생성 · 토큰 |" in open(j("tasks", "README.md"), encoding="utf-8").read():
        add("프로젝트", "작업 표", "⚠️", "템플릿 예시 행(task-001)이 그대로 — /plan 으로 작업 분해하거나 직접 등록")
    # 같은 이름 팀원 충돌
    clash = sorted(NOMAD_AGENTS & {os.path.splitext(os.path.basename(x))[0] for x in glob.glob(j(".claude", "agents", "*.md"))})
    add("프로젝트", "팀원 이름 충돌", "❌" if clash else "✅",
        f".claude/agents/ 의 {', '.join(clash)} 가 NOMAD 팀원을 덮어씀 → 지우거나 이름 변경(자동으로 지우지 않음)" if clash else "없음")
    if FIX.get("init") is None and any(r[4] == "init" for r in ROWS):
        FIX["init"] = ("프로젝트에 NOMAD 적용 (기존 파일 보존 · 필요한 줄만 병합)", ["install.sh", "init", proj])


# ---------- ③ 모듈 · ④ 기획→시안 · ⑤ 보안 ----------
def check_modules(proj):
    p = os.path.join(proj, "nomad-modules.json")
    if not os.path.exists(p):
        add("모듈", "설치된 모듈", "ℹ️", "없음 (도메인 청사진이 필요하면 nomad-os module list)"); return
    try:
        mods = json.load(open(p, encoding="utf-8")).get("modules", {})
    except ValueError:
        add("모듈", "nomad-modules.json", "❌", "JSON 오류"); return
    for n, m in mods.items():
        base = os.path.join(proj, m.get("install_to", ""))
        files = m.get("files", {})
        gone = [f for f in files if not os.path.exists(os.path.join(base, f))]
        edited = [f for f, h in files.items() if f not in gone and hashlib.sha256(open(os.path.join(base, f), "rb").read()).hexdigest() != h]
        ups = glob.glob(os.path.join(base, "**", "*.upstream"), recursive=True)
        st = "❌" if gone else ("⚠️" if ups else "✅")
        add("모듈", n, st, f"{m.get('version', '')} · 커밋 {m.get('commit', '')[:7]} · 파일 {len(files) - len(gone)}/{len(files)}"
            + (f" · 내가 수정 {len(edited)}" if edited else "") + (f" · 합칠 새 버전(.upstream) {len(ups)}" if ups else "")
            + (" → nomad-os module update " + n if gone else ""))


def check_spec(proj):
    docs = os.path.join(proj, "docs")
    if not os.path.isdir(docs): return
    try:
        p2 = load("plan2spec", "plan2spec.py")
        cur = p2.read_docs(docs)
    except Exception as e:
        add("기획·시안", "plan2spec", "⚠️", f"해석 실패: {e.__class__.__name__}"); return
    if not cur["screens"]:
        add("기획·시안", "화면 표", "ℹ️", "화면 행 없음 (기획 후 plan2spec)"); return
    sp = os.path.join(proj, "design", "spec.json")
    try:
        spec = json.load(open(sp, encoding="utf-8"))
        fresh = spec.get("sources", {}) == cur["sources"]   # 둘 다 프로젝트 폴더 기준 경로
    except (OSError, ValueError):
        spec, fresh = None, False
    if not spec:
        add("기획·시안", "사양·시안", "❌", f"화면 {len(cur['screens'])}개가 있는데 design/spec.json 없음 → plan2spec", "spec")
    elif not fresh:
        add("기획·시안", "사양·시안", "❌", "기획 표가 사양보다 새로움 → plan2spec (바뀐 화면만 다시 생성)", "spec")
    else:
        red = [i for i in spec.get("issues", []) if i[0] == "🔴"]
        add("기획·시안", "사양·시안", "⚠️" if red else "✅", f"화면 {len(spec['screens'])}개 · 필수 구조 🔴 {len(red)}" + (f" (예: {red[0][1]} {red[0][2][:40]})" if red else ""))
    if any(r[4] == "spec" for r in ROWS): FIX["spec"] = ("plan2spec 실행 (사양·구조도·시안·필수 구조 검사)", ["plan2spec"])


def check_security(proj):
    prd = glob.glob(os.path.join(proj, "docs", "**", "01_PRD.md"), recursive=True)
    if prd:
        t = open(prd[0], encoding="utf-8").read()
        ok = re.search(r"##\s*8\.\s*보안", t) and re.search(r"보안 레벨\s*\|\s*(L[0-3])", t)
        add("보안", "PRD 보안 절", "✅" if ok else "⚠️", "레벨 지정됨" if ok else "PRD `## 8. 보안·공급망`의 보안 레벨 미지정 → /plan 또는 직접 작성")
    if os.path.isdir(os.path.join(proj, ".git")):
        dep = os.path.exists(os.path.join(proj, ".github", "dependabot.yml"))
        add("보안", "Dependabot · SECURITY.md", "✅" if dep and os.path.exists(os.path.join(proj, "SECURITY.md")) else "⚠️",
            "있음" if dep else "없음 → /secure setup (L1)")


# ---------- ⑥ 준비물 · ⑦ 토큰 ----------
def check_tools():
    add("준비물", "Python", "✅", sys.version.split()[0])
    add("준비물", "git", "✅" if shutil.which("git") else "❌", "있음" if shutil.which("git") else "없음 — 설치 필요")
    add("준비물", "Node(npx)", "✅" if shutil.which("npx") else "⚠️", "있음" if shutil.which("npx") else "없음 — 다이어그램 검증(mmd-check) 불가")
    try:
        br = load("shot", "shot.py").find_browser()
    except Exception:
        br = None
    add("준비물", "Chrome·Edge", "✅" if br else "⚠️", os.path.basename(br) if br else "없음 — shot(3구간 스크린샷) 불가")


def check_tokens(proj):
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "token-audit.py"), proj, "--json"], capture_output=True, text=True, encoding="utf-8", timeout=60)
        d = json.loads(r.stdout)
        mem = d.get("memory", 0)
        add("토큰", "상시 로드 규칙", "✅" if mem <= 2500 else "⚠️", f"{mem} / 2500 tok" + ("" if mem <= 2500 else " → /token-audit"))
    except Exception:
        add("토큰", "상시 로드 규칙", "ℹ️", "측정 실패 — /token-audit 로 확인")


# ---------- 실행 ----------
def apply_fixes(repo, proj):
    bs, done, restart = bash(), [], False
    for key in ("global", "init", "spec"):
        if key not in FIX: continue
        desc, cmd = FIX[key]
        if key in ("global", "init"):
            if not repo or not bs:
                print(f"  ❌ {desc}: 본체 레포 또는 Git Bash 를 찾지 못함 — 수동으로 install.ps1 실행"); continue
            full = [bs, os.path.join(repo, "install.sh").replace("\\", "/")] + [c.replace("\\", "/") for c in cmd[1:]]
        else:
            full = [sys.executable, os.path.join(HERE, "plan2spec.py")]
        r = subprocess.run(full, cwd=proj, capture_output=True, text=True, encoding="utf-8", errors="replace")
        ok = r.returncode == 0
        print(f"  {'✅' if ok else '❌'} {desc}" + ("" if ok else f" — {(r.stdout + r.stderr).strip().splitlines()[-1:]}"))
        done.append(key); restart |= key == "global" and ok
    return restart


def main():
    ap = argparse.ArgumentParser(prog="nomad-doctor")
    ap.add_argument("project", nargs="?", default="."); ap.add_argument("--fix", action="store_true"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    proj = os.path.abspath(a.project); repo = repo_root()
    in_core = repo and os.path.normcase(proj).startswith(os.path.normcase(repo))
    check_global(repo)
    if in_core:
        add("프로젝트", "대상", "ℹ️", "NOMAD 본체 레포 안 — 프로젝트 점검 생략 (프로젝트 폴더에서 실행)")
    else:
        check_project(proj, repo); check_modules(proj); check_spec(proj); check_security(proj)
    check_tools(); check_tokens(proj)
    if a.json:
        print(json.dumps({"repo": repo, "project": proj, "rows": ROWS, "fixes": {k: v[0] for k, v in FIX.items()}}, ensure_ascii=False)); return 0
    bad = sum(r[2] == "❌" for r in ROWS); warn = sum(r[2] == "⚠️" for r in ROWS)
    print(f"■ /agent-check — {proj}")
    print(f"  본체 레포: {repo or '찾지 못함 (nomad-os 미설치?)'}")
    print("  | 영역 | 항목 | 상태 | 내용 |\n  |---|---|---|---|")
    for area, item, st, msg, _ in ROWS:
        print(f"  | {area} | {item} | {st} | {msg} |")
    print(f"■ 결과: ❌ {bad} · ⚠️ {warn}" + ("  — 멀티에이전트 구성 정상 ✅" if not bad else ""))
    if FIX and not a.fix:
        print("■ 자동으로 고칠 수 있는 것:")
        for k, (d, _) in FIX.items(): print(f"  - {d}")
        print("  → 적용: nomad-doctor --fix   (Claude Code: /agent-check fix)")
    if a.fix and FIX:
        print("■ 고치는 중")
        if apply_fixes(repo, proj):
            print("■ 전역 설치가 바뀌었습니다 → Claude Code 를 다시 시작해야 팀원·스킬·훅이 새로 로드됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
