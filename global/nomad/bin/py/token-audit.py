#!/usr/bin/env python3
"""token-audit — 세션마다 '항상' 들어가는 컨텍스트(상시 로드)를 추정하고 예산 초과를 경고한다.

측정 대상: 전역/프로젝트 CLAUDE.md(+@import), 경로 조건 없는 .claude/rules, 에이전트·스킬·명령 description.
추정식: ASCII 4자 ≈ 1토큰, 한글 등 비ASCII 1.3자 ≈ 1토큰 (실측과 ±20% 차이 가능 — 비교용).

사용: token-audit [프로젝트 폴더=.] [--global ~/.claude] [--no-global] [--json]
"""
import argparse, json, os, re, sys

try:  # 한국어 Windows(cp949) 콘솔에서도 이모지·한글 출력이 죽지 않게
    sys.stdout.reconfigure(encoding="utf-8", errors="replace"); sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BUDGET = {"memory": 2500, "desc_each": 70, "desc_total": 1500, "total": 4000}

def tok(s):
    a = sum(1 for c in s if ord(c) < 128)
    return round(a / 4 + (len(s) - a) / 1.3)

def read(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f: return f.read()
    except OSError: return ""

def with_imports(path, seen=None, depth=0):
    seen = seen or set()
    path = os.path.abspath(os.path.expanduser(path))
    if path in seen or depth > 5 or not os.path.isfile(path): return "", []
    seen.add(path); text = read(path); used = [path]
    base = os.path.dirname(path)
    for m in re.finditer(r"(?m)^\s*@([~\w./-]+\.md)\s*$", text):
        p = m.group(1)
        p = os.path.expanduser(p) if p.startswith("~") else os.path.join(base, p)
        t, u = with_imports(p, seen, depth + 1); text += "\n" + t; used += u
    return text, used

def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    return m.group(1) if m else ""

def desc_of(fm):
    m = re.search(r"(?ms)^description:\s*(.*?)(?=^\w[\w-]*:|\Z)", fm)
    if not m: return ""
    return re.sub(r"\s+", " ", m.group(1).replace(">-", "").replace("|", "")).strip()

def scan_claude_dir(d, label, rows):
    if not os.path.isdir(d): return
    for kind, pat in (("agent", "agents"), ("skill", "skills"), ("command", "commands")):
        root = os.path.join(d, pat)
        if not os.path.isdir(root): continue
        for dp, _, names in os.walk(root):
            for n in names:
                if not n.endswith(".md") or n.upper() == "README.MD": continue
                if kind == "skill" and n != "SKILL.md": continue
                if kind == "agent" and dp != root: continue
                fm = frontmatter(read(os.path.join(dp, n)))
                d_ = desc_of(fm)
                if not d_ and kind != "command": continue
                name = os.path.basename(dp) if kind == "skill" else n[:-3]
                rows.append({"src": label, "kind": kind, "name": name, "tokens": tok(d_)})
    rules = os.path.join(d, "rules")
    if os.path.isdir(rules):
        for dp, _, names in os.walk(rules):
            for n in names:
                if n.endswith(".md"):
                    t = read(os.path.join(dp, n)); fm = frontmatter(t)
                    scoped = bool(re.search(r"(?m)^(paths|globs):", fm))
                    rows.append({"src": label, "kind": "rule(scoped)" if scoped else "rule", "name": n, "tokens": tok(t)})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--global", dest="glob", default="~/.claude")
    ap.add_argument("--no-global", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    proj = os.path.abspath(a.project); g = os.path.expanduser(a.glob)
    rows, mem = [], []
    if not a.no_global:
        t, used = with_imports(os.path.join(g, "CLAUDE.md"))
        if t: mem.append(("global CLAUDE.md(+import)", tok(t), used))
        scan_claude_dir(g, "global", rows)
    t, used = with_imports(os.path.join(proj, "CLAUDE.md"))
    if t: mem.append(("project CLAUDE.md(+import)", tok(t), used))
    elif os.path.isfile(os.path.join(proj, "AGENTS.md")):
        t = read(os.path.join(proj, "AGENTS.md")); mem.append(("project AGENTS.md(fallback)", tok(t), []))
    scan_claude_dir(os.path.join(proj, ".claude"), "project", rows)

    mem_tok = sum(m[1] for m in mem)
    rule_tok = sum(r["tokens"] for r in rows if r["kind"] == "rule")
    desc = [r for r in rows if r["kind"] in ("agent", "skill", "command")]
    desc_tok = sum(r["tokens"] for r in desc)
    total = mem_tok + rule_tok + desc_tok
    if a.json:
        print(json.dumps({"memory": mem_tok, "rules": rule_tok, "descriptions": desc_tok, "total": total,
                          "agents": sum(1 for r in desc if r["kind"] == "agent"),
                          "skills": sum(1 for r in desc if r["kind"] == "skill")}, ensure_ascii=False)); return
    print(f"■ 상시 로드 추정 — {proj}")
    for name, t, _ in mem: print(f"  {name:32s} {t:6d} tok")
    if rule_tok: print(f"  {'rules (경로 조건 없음)':32s} {rule_tok:6d} tok")
    for k in ("agent", "skill", "command"):
        ks = [r for r in desc if r["kind"] == k]
        if ks: print(f"  {k + ' description × ' + str(len(ks)):32s} {sum(r['tokens'] for r in ks):6d} tok")
    print(f"  {'합계':32s} {total:6d} tok   (예산 {BUDGET['total']})")
    warn = []
    if mem_tok > BUDGET["memory"]: warn.append(f"CLAUDE.md 계열 {mem_tok} > {BUDGET['memory']} → 절대 규칙만 남기고 나머지는 rules(paths)·스킬로")
    for r in desc:
        if r["tokens"] > BUDGET["desc_each"]: warn.append(f"{r['kind']} '{r['name']}' description {r['tokens']} tok > {BUDGET['desc_each']} → 한 문장으로")
    names = {}
    for r in desc: names.setdefault(r["name"].split(":")[-1], set()).add(r["kind"])
    for n, ks in names.items():
        if {"agent", "skill"} <= ks: warn.append(f"'{n}' 에이전트·스킬 description 중복 로드 → 에이전트 쪽 description만 남기고 skills: 로 연결")
    if total > BUDGET["total"]: warn.append(f"합계 {total} > {BUDGET['total']}")
    print("■ 경고" if warn else "■ 예산 안 ✅")
    for w in warn[:25]: print("  - " + w)
    if len(warn) > 25: print(f"  … 외 {len(warn) - 25}건")

if __name__ == "__main__":
    main()
