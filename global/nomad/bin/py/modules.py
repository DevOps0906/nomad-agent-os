#!/usr/bin/env python3
"""modules — NOMAD 모듈(기획 청사진 · 보안 팩)을 필요할 때 외부 깃허브 레포에서 가져온다.

사용: nomad-os module list [프로젝트=.]
      nomad-os module add <이름|깃 URL> [프로젝트=.] [--ref 태그·브랜치] [--from 로컬 경로·URL] [--allow-scripts]
      nomad-os module update <이름|all> [프로젝트=.]
      nomad-os module remove <이름> [프로젝트=.]
등록 목록: NOMAD 저장소 modules.json (+ ~/.claude/nomad/modules.local.json 으로 덮어쓰기)
기록: <프로젝트>/nomad-modules.json — 출처 · 참조 · **커밋** · 파일 해시 (커밋해 두면 팀원이 같은 버전을 받음)
안전: 모듈 폴더 밖 경로 거부 · 허용 확장자만(스크립트는 --allow-scripts) · 총 5MB 제한 · 라이선스 확인 ·
      내가 고친 파일은 업데이트로 덮어쓰지 않고 <파일>.upstream 으로 새 버전을 둔다.
"""
import argparse, copy, hashlib, json, os, re, shutil, subprocess, sys
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace"); sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
# bash 도구와 같은 홈을 쓴다(Windows 파이썬의 ~ 는 USERPROFILE 이라 Git Bash HOME 과 다를 수 있음)
HOME_NOMAD = os.environ.get("NOMAD_HOME") or os.path.join(os.environ.get("HOME") or os.path.expanduser("~"), ".claude", "nomad")
REGISTRIES = [os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "modules.json")),   # 저장소에서 실행
              os.path.join(HOME_NOMAD, "modules.json"), os.path.join(HOME_NOMAD, "modules.local.json")]
CACHE = os.path.join(HOME_NOMAD, "cache", "modules")
LOCK = "nomad-modules.json"
TYPES = {"blueprint": "docs/blueprints/{name}", "security": "security/{name}", "docker": "infra/{name}"}
DOCKER_NAMES = {"dockerfile", ".dockerignore", ".env.example"}      # docker 유형에서만 허용(경로 basename 기준)
DOCKER_EXT = {".conf", ".toml"}
FORBIDDEN_DIRS = {".git", ".github", ".vscode"}
CATEGORIES = [("core", "공통 계약"), ("foundation", "기반"), ("domain", "도메인"), ("ai", "AI"), ("infra", "인프라"), ("security", "보안")]
SAFE_EXT = {".md", ".json", ".yml", ".yaml", ".csv", ".txt", ".svg", ".png", ".jpg", ".webp", ".mmd", ".css", ".html"}
SCRIPT_EXT = {".sh", ".ps1", ".py", ".js", ".mjs", ".ts", ".bat", ".cmd", ".exe"}
MAX_BYTES = 5 * 1024 * 1024


def log(m=""):
    print(m, flush=True)


def die(m, code=1):
    log(f"❌ {m}"); sys.exit(code)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    return h.hexdigest()


def registry():
    reg = {}
    for p in REGISTRIES:
        if os.path.exists(p):
            try: reg.update((json.load(open(p, encoding="utf-8")).get("modules") or {}))
            except ValueError: log(f"  ⚠️ {p} JSON 오류 — 건너뜀")
    return reg


def git(*args, cwd=None):
    exe = shutil.which("git")
    if not exe: die("git 이 없습니다 — Git 설치 후 다시 실행")
    r = subprocess.run([exe, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def fetch(repo, ref):
    """repo 가 로컬 폴더면 그대로, URL 이면 캐시에 얕은 클론 후 ref 로 고정. (폴더, 커밋) 반환."""
    if os.path.isdir(repo):
        code, out, _ = git("rev-parse", "HEAD", cwd=repo)
        dirty = git("status", "--porcelain", cwd=repo)[1] if code == 0 else ""
        return os.path.abspath(repo), (out if code == 0 else "local") + ("+수정됨" if dirty else "")
    if not re.match(r"^(https://|git@|ssh://)", repo): die(f"모듈 출처를 알 수 없습니다: {repo}")
    # Windows 경로 길이(260자) 한도를 피하려고 캐시 폴더 이름은 짧게: <레포 이름>-<해시 10자>
    short = re.sub(r"[^A-Za-z0-9_-]", "", os.path.basename(repo.rstrip("/")).replace(".git", ""))[:20]
    dst = os.path.join(CACHE, f"{short}-{hashlib.sha1(f'{repo}@{ref}'.encode()).hexdigest()[:10]}")
    if os.path.isdir(os.path.join(dst, ".git")):
        code, _, err = git("fetch", "--depth", "1", "origin", ref or "HEAD", cwd=dst)
        if code != 0: die(f"가져오기 실패 — {err.splitlines()[-1] if err else repo}")
        git("reset", "--hard", "FETCH_HEAD", cwd=dst)
    else:
        os.makedirs(CACHE, exist_ok=True)
        args = ["-c", "core.longpaths=true", "clone", "--depth", "1"] +(["--branch", ref] if ref and ref != "HEAD" else []) + [repo, dst]
        code, _, err = git(*args)
        if code != 0:
            shutil.rmtree(dst, ignore_errors=True)
            die(f"클론 실패 — {err.splitlines()[-1] if err else repo}\n   레포가 아직 없거나 비공개면: 레포를 만들거나 --from <로컬 경로>")
    return dst, git("rev-parse", "HEAD", cwd=dst)[1]


def resolve(target, a):
    reg = registry()
    if a.source:                                     # --from: 로컬 경로 또는 URL (등록 목록 우회)
        base, name = a.source, target
        sub = "." if os.path.exists(os.path.join(base, "module.json")) else (reg.get(target, {}).get("path") or target)
    elif target in reg:
        m = reg[target]; base, sub, name = m["repo"], m.get("path", "."), target
        if m.get("status") == "planned" and not a.source:
            log(f"  ℹ️ '{target}'는 등록만 된 예정 모듈입니다 ({m['repo']}). 레포가 아직 없으면 --from <로컬 경로> 로 시험하세요.")
    elif re.match(r"^(https://|git@)", target):
        base, _, sub = target.partition("#")          # URL#하위경로
        sub = sub or "."; name = os.path.basename(sub.rstrip("/")) if sub != "." else os.path.basename(base).replace(".git", "")
    else:
        die(f"모르는 모듈: {target}  (목록: nomad-os module list)")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name or ""): die(f"모듈 이름이 올바르지 않습니다(영문·숫자·-·_ 만): {name}")
    ref = a.ref or (reg.get(target, {}).get("ref") if target in reg else "") or "HEAD"
    root, commit = fetch(base, ref)
    mdir = os.path.normpath(os.path.join(root, sub))
    nroot = os.path.normpath(root)
    if mdir != nroot and not mdir.startswith(nroot + os.sep): die("모듈 경로가 레포 밖을 가리킵니다")
    rroot, rm = os.path.realpath(root), os.path.realpath(mdir)
    if rm != rroot and not rm.startswith(rroot + os.sep): die("모듈 경로가 레포 밖을 가리킵니다(심볼릭 링크)")
    return name, base, ref, commit, mdir


def validate(mdir, allow_scripts, req_name=None):
    def need_scripts():
        if req_name: die(f"requires {req_name}은 실행 파일 포함 — 먼저 `module add {req_name} --allow-scripts`로 직접 검토·설치")

    mf = os.path.join(mdir, "module.json")
    if not os.path.exists(mf): die(f"module.json 이 없습니다: {mdir}")
    try: man = json.load(open(mf, encoding="utf-8"))
    except ValueError as e: die(f"module.json 형식 오류: {e}")
    t = man.get("type")
    if t not in TYPES: die(f"모르는 모듈 유형 '{t}' (허용: {', '.join(TYPES)})")
    if t == "docker" and not allow_scripts:
        need_scripts(); die("docker 모듈은 Dockerfile·compose를 포함 — 내용 검토 후 --allow-scripts")
    files = man.get("files") or sorted(
        os.path.relpath(os.path.join(d, f), mdir).replace("\\", "/") for d, _, fs in os.walk(mdir) for f in fs if f != "module.json")
    total, bad = 0, []
    rmdir = os.path.realpath(mdir)
    for rel in files:
        p = os.path.normpath(os.path.join(mdir, rel))
        if not p.startswith(os.path.normpath(mdir) + os.sep): die(f"모듈 밖을 가리키는 파일: {rel}")
        if os.path.islink(p): die(f"심볼릭 링크 거부: {rel}")
        if not os.path.isfile(p): die(f"목록의 파일이 없습니다: {rel}")
        if not os.path.realpath(p).startswith(rmdir + os.sep): die(f"모듈 밖을 가리키는 파일(심볼릭 링크): {rel}")
        if any(x.lower() in FORBIDDEN_DIRS for x in rel.replace("\\", "/").split("/")): die(f"허용되지 않은 경로(.git·.github·.vscode): {rel}")
        ext = os.path.splitext(rel)[1].lower()
        if t == "docker":                                # 스크립트는 --allow-scripts 여도 거부, 허용 목록 파일만
            if ext in SCRIPT_EXT or not (ext in SAFE_EXT | DOCKER_EXT or os.path.basename(rel).lower() in DOCKER_NAMES): bad.append(rel)
        elif ext in SCRIPT_EXT and not allow_scripts: need_scripts(); bad.append(rel)
        elif ext not in SAFE_EXT | SCRIPT_EXT: bad.append(rel)
        total += os.path.getsize(p)
    if bad: die(f"허용되지 않은 파일(스크립트·실행 파일·모르는 형식): {', '.join(bad)}\n   검토 후 필요하면 --allow-scripts")
    if total > MAX_BYTES: die(f"모듈이 너무 큽니다: {total // 1024}KB > {MAX_BYTES // 1024}KB")
    lic = (man.get("license") or "").strip()
    has_lic_file = any(os.path.exists(os.path.join(mdir, x)) for x in ("LICENSE", "LICENSE.md")) or \
        any(os.path.exists(os.path.join(mdir, "..", x)) for x in ("LICENSE", "LICENSE.md"))
    if not lic and not has_lic_file:
        log("  ⚠️ 라이선스가 지정되지 않았습니다 — 외부 모듈이면 사용 전 확인 (내 레포면 LICENSE 추가 권장)")
    elif re.match(r"^(A?GPL|SSPL|BUSL)", lic.upper()):
        log(f"  🔴 라이선스 {lic} — NOMAD 기본 정책상 거부 대상. 기획 문서라도 재사용 범위를 확인하세요")
    return man, files


def load_lock(proj):
    p = os.path.join(proj, LOCK)
    if os.path.exists(p):
        try: return json.load(open(p, encoding="utf-8"))
        except ValueError: die(f"{LOCK} 형식 오류 — 직접 고친 뒤 다시 실행")
    return {"_doc": "NOMAD 모듈 기록 — nomad-os module 이 관리. 커밋해 두면 같은 버전을 받는다.", "modules": {}}


def save_lock(proj, lock):
    with open(os.path.join(proj, LOCK), "w", encoding="utf-8", newline="\n") as f:
        json.dump(lock, f, ensure_ascii=False, indent=2); f.write("\n")


def dest_of(proj, name, man):
    dest_rel = (man.get("install_to") or TYPES[man["type"]]).format(name=name).replace("\\", "/")
    dest = os.path.normpath(os.path.join(proj, dest_rel))
    if not dest.startswith(os.path.normpath(proj) + os.sep): die(f"install_to 가 프로젝트 밖입니다: {dest_rel}")
    parts = os.path.relpath(dest, proj).split(os.sep)
    top = TYPES[man["type"]].split("/")[0]
    if parts[0] != top or len(parts) < 2: die(f"install_to 는 {top}/ 아래여야 합니다: {dest_rel}")
    if any(x.lower() in FORBIDDEN_DIRS for x in parts): die(f"install_to 에 허용되지 않은 경로(.git·.github·.vscode): {dest_rel}")
    return dest_rel, dest


def install(proj, name, base, ref, commit, mdir, man, files, lock):
    dest_rel, dest = dest_of(proj, name, man)
    prev = (lock["modules"].get(name) or {}).get("files", {})
    added, updated, kept, same = [], [], [], []
    rec = {}
    for rel in files:
        src, dst = os.path.join(mdir, rel), os.path.join(dest, rel)
        new_hash = sha256(src)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst):
            shutil.copyfile(src, dst); added.append(rel); rec[rel] = new_hash; continue
        cur = sha256(dst)
        if cur == new_hash:
            same.append(rel); rec[rel] = new_hash
        elif prev.get(rel) == cur:                       # 내가 안 고친 파일 → 새 버전으로 교체
            shutil.copyfile(src, dst); updated.append(rel); rec[rel] = new_hash
        else:                                            # 내가 고친 파일 → 보존, 새 버전은 .upstream
            shutil.copyfile(src, dst + ".upstream"); kept.append(rel); rec[rel] = prev.get(rel) or cur
    for rel in set(prev) - set(files):
        p = os.path.join(dest, rel)
        if os.path.exists(p) and sha256(p) == prev[rel]: os.remove(p); log(f"  - 삭제  {dest_rel}/{rel} (모듈에서 빠짐)")
    lock["modules"][name] = {"type": man["type"], "title": man.get("title", ""), "version": man.get("version", ""),
                             "source": base, "ref": ref, "commit": commit, "install_to": dest_rel,
                             "license": man.get("license", ""), "requires": list(man.get("requires") or []), "installed": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "files": rec}
    log(f"■ {name} {man.get('version', '')} → {dest_rel}  (커밋 {commit[:12]})")
    for x in added: log(f"  + 생성  {x}")
    for x in updated: log(f"  ↻ 갱신  {x}")
    for x in kept: log(f"  · 유지  {x} (내가 수정함 — 새 버전: {x}.upstream, 비교 후 합치기)")
    if same and not (added or updated or kept): log("  · 이미 최신")
    return dest_rel


def cmd_list(a):
    reg, lock = registry(), load_lock(a.project)
    log("■ 등록된 모듈 (nomad-os module add <이름>)")
    known = [c for c, _ in CATEGORIES]
    groups = [(c, t, [n for n, m in sorted(reg.items()) if m.get("category") == c]) for c, t in CATEGORIES]
    groups.append(("other", "기타", [n for n, m in sorted(reg.items()) if m.get("category") not in known]))
    for c, title, names in groups:
        if not names: continue
        log(f"\n■ {title} ({c})")
        log("  | 이름 | 유형 | 상태 | 출처 | 설명 |\n  |---|---|---|---|---|")
        for n in names:
            m, inst = reg[n], lock["modules"].get(n)
            st = f"설치됨 {inst['commit'][:7]}" if inst else ("예정" if m.get("status") == "planned" else "-")
            log(f"  | {n} | {m.get('type', '')} | {st} | {m['repo']}{'#' + m['path'] if m.get('path', '.') != '.' else ''} | {m.get('desc', '')} |")
    extra = [n for n in lock["modules"] if n not in reg]
    if extra:
        log("\n■ 등록 목록 밖 (other)")
        log("  | 이름 | 유형 | 상태 | 출처 | 설명 |\n  |---|---|---|---|---|")
        for n in extra: log(f"  | {n} | {lock['modules'][n]['type']} | 설치됨 | {lock['modules'][n]['source']} | (등록 목록 밖) |")


def after(man, dest_rel):
    if man["type"] == "blueprint":
        log(f"■ 다음: 쓰지 않을 화면·API·테이블 행은 {dest_rel}/*.md 에서 지운 뒤 → plan2spec")
    elif man["type"] == "security":
        log(f"■ 다음: {dest_rel}/README.md 의 순서대로 (L3 — security-baseline 스킬 1절)")


MAX_DEPTH = 8


def collect(a, chain, plan, lock, is_req, reg):
    """설치 계획을 먼저 만든다(resolve·validate 만, 파일은 건드리지 않음). requires 가 앞, 자신이 뒤."""
    name, base, ref, commit, mdir = resolve(a.target, a)
    if name in chain: die(f"requires 순환: {' → '.join(chain + (name,))}")
    if len(chain) >= MAX_DEPTH: die(f"requires 가 너무 깊습니다(최대 {MAX_DEPTH}단계): {' → '.join(chain + (name,))}")
    man, files = validate(mdir, a.allow_scripts and not is_req, name if is_req else None)
    dest_of(a.project, name, man)
    chain = chain + (name,)
    for r in man.get("requires") or []:
        if not isinstance(r, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", r): die(f"requires 이름이 올바르지 않습니다: {r!r}")
        if r in lock["modules"] or any(p[0] == r for p in plan): continue
        if r in chain: die(f"requires 순환: {' → '.join(chain + (r,))}")
        if a.source and os.path.isdir(a.source):
            if not os.path.isdir(os.path.join(a.source, reg.get(r, {}).get("path") or r)): die(f"requires {r} 폴더가 {a.source} 안에 없습니다")
        elif r not in reg: die(f"requires {r} 은(는) 등록부에 없습니다")
        b = copy.copy(a); b.target, b.ref, b._update = r, None, False
        collect(b, chain, plan, lock, True, reg)
    plan.append((name, base, ref, commit, mdir, man, files))


def cmd_add(a):
    lock = load_lock(a.project)
    plan = []
    collect(a, (), plan, lock, False, registry())
    top = plan[-1]
    if top[0] in lock["modules"] and not a._update:
        log(f"  ℹ️ 이미 설치됨 — 새 버전으로: nomad-os module update {top[0]}")
    if len(plan) > 1:
        log(f"■ 함께 설치(requires): {', '.join(p[0] for p in plan[:-1])}")
        if not a.source: log("  ℹ️ requires 는 등록부 ref 로 설치합니다")
    for name, base, ref, commit, mdir, man, files in plan:
        dest = install(a.project, name, base, ref, commit, mdir, man, files, lock)
        after(man, dest)
    save_lock(a.project, lock)
    man = top[5]
    integ = man.get("integrates") or []
    if integ: log("ℹ️ 함께 쓰면 연결: " + " · ".join(f"{x}({'설치됨' if x in lock['modules'] else '미설치'})" for x in integ))


def cmd_update(a):
    lock = load_lock(a.project)
    names = list(lock["modules"]) if a.target == "all" else [a.target]
    for n in names:
        if n not in lock["modules"]: die(f"설치되지 않은 모듈: {n}")
        m = lock["modules"][n]
        a.source = a.source or (m["source"] if os.path.isdir(m["source"]) or n not in registry() else None)
        a.ref = a.ref or m["ref"]; a.target, a._update = n, True
        cmd_add(a); a.source = a.ref = None


def dependents(lock, n):
    """설치된 모듈 n 의 requires — lock 기록(예전 항목은 없을 수 있음)."""
    return lock["modules"][n].get("requires") or []


def cmd_remove(a):
    lock = load_lock(a.project)
    m = lock["modules"].get(a.target) or die(f"설치되지 않은 모듈: {a.target}")
    dest = os.path.join(a.project, m["install_to"])
    kept = []
    for rel, h in m["files"].items():
        p = os.path.join(dest, rel)
        if not os.path.exists(p): continue
        if sha256(p) == h: os.remove(p)
        else: kept.append(rel)
        if os.path.exists(p + ".upstream"): os.remove(p + ".upstream")
    for d, _, _ in sorted(os.walk(dest), reverse=True):
        try: os.rmdir(d)
        except OSError: pass
    users = [n for n in lock["modules"] if n != a.target and a.target in dependents(lock, n)]
    del lock["modules"][a.target]; save_lock(a.project, lock)
    if users: log(f"  ⚠️ {', '.join(users)} 모듈이 {a.target} 을(를) requires 로 사용 중 — 연결이 끊길 수 있음")
    log(f"■ {a.target} 제거" + (f" — 내가 수정한 파일은 남김: {', '.join(kept)}" if kept else ""))


def main():
    ap = argparse.ArgumentParser(prog="nomad-os module")
    ap.add_argument("cmd", choices=["list", "add", "update", "remove"])
    ap.add_argument("target", nargs="?")
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--ref"); ap.add_argument("--from", dest="source"); ap.add_argument("--allow-scripts", action="store_true")
    a = ap.parse_args(); a._update = False
    if a.cmd == "list":
        if a.target and os.path.isdir(a.target): a.project = a.target
        a.project = os.path.abspath(a.project); cmd_list(a); return 0
    if not a.target: die("모듈 이름이 필요합니다 (nomad-os module list)", 2)
    a.project = os.path.abspath(a.project)
    if not os.path.isdir(a.project): die(f"프로젝트 폴더가 없습니다: {a.project}", 2)
    if os.path.normpath(a.project).lower().startswith(os.path.normpath(os.path.join(HERE, "..", "..", "..", "..")).lower() + os.sep) \
            or os.path.normpath(a.project).lower() == os.path.normpath(os.path.join(HERE, "..", "..", "..", "..")).lower():
        if os.path.exists(os.path.join(HERE, "..", "..", "..", "..", "install.sh")):
            die("NOMAD 저장소 안에는 모듈을 설치하지 않습니다 — 프로젝트 경로를 지정하세요", 2)
    {"add": cmd_add, "update": cmd_update, "remove": cmd_remove}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
