#!/usr/bin/env python3
"""deps2mmd — 코드의 import를 분석해 모듈 의존 구조도(Mermaid flowchart)를 자동 생성한다 (모델 토큰 0).
지원: TS/JS(import·require·동적 import), Python(import·from), Dart(import 'package:' · 상대경로).

사용: deps2mmd <소스 폴더> [-o docs/diagrams/architecture.mmd] [--depth 2] [--max-nodes 25]
            [--alias @=src] [--external]   # --external: npm·pip 외부 패키지도 노드로 표시
"""
import argparse, os, re, sys

try:  # 한국어 Windows(cp949) 콘솔에서도 이모지·한글 출력이 죽지 않게
    sys.stdout.reconfigure(encoding="utf-8", errors="replace"); sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
from collections import Counter

EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".py", ".dart")
SKIP = {"node_modules", ".next", ".git", "dist", "build", ".dart_tool", "__pycache__", ".venv", "venv", "coverage", ".turbo"}
PAT = {
    "js": re.compile(r"""(?:import\s[^'"]*?from\s*|import\s*\(\s*|require\s*\(\s*|^\s*import\s+)['"]([^'"]+)['"]""", re.M),
    "py": re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.M),
    "dart": re.compile(r"""^\s*(?:import|export)\s+['"]([^'"]+)['"]""", re.M),
}

def kind(f):
    return "py" if f.endswith(".py") else "dart" if f.endswith(".dart") else "js"

def module_of(rel, depth):
    parts = rel.replace("\\", "/").split("/")
    dirs = parts[:-1] if len(parts) > 1 else ["(root)"]
    return "/".join(dirs[:depth])

def ident(s):
    return "m_" + re.sub(r"[^A-Za-z0-9_]", "_", s)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out")
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--max-nodes", type=int, default=25)
    ap.add_argument("--alias", action="append", default=[], help="경로 별칭, 예: @=src  ~=src")
    ap.add_argument("--external", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.src)
    if a.alias:
        aliases = [(x.split("=", 1)[0].rstrip("/"), os.path.join(root, x.split("=", 1)[1])) for x in a.alias]
    elif os.path.basename(root) != "src" and os.path.isdir(os.path.join(root, "src")):
        aliases = [("@", os.path.join(root, "src")), ("~", os.path.join(root, "src"))]
    else:   # 루트 자체가 src 이거나 src 폴더가 없으면 @ = 루트
        aliases = [("@", root), ("~", root)]
    files = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP]
        files += [os.path.join(dp, f) for f in fns if f.endswith(EXT)]
    pyroots = {os.path.relpath(f, root).split(os.sep)[0] for f in files if f.endswith(".py")}
    edges, size = Counter(), Counter()
    for f in files:
        rel = os.path.relpath(f, root); src_mod = module_of(rel, a.depth); size[src_mod] += 1
        try: text = open(f, encoding="utf-8", errors="replace").read()
        except OSError: continue
        k = kind(f)
        for m in PAT[k].finditer(text):
            spec = next(g for g in m.groups() if g)
            target = None
            if k == "py":
                top = spec.split(".")[0]
                if spec.startswith(".") or top in pyroots:
                    target = module_of(spec.lstrip(".").replace(".", "/") + "/x.py", a.depth) if not spec.startswith(".") else src_mod
                elif a.external: target = "ext:" + top
            elif spec.startswith("."):
                p = os.path.normpath(os.path.join(os.path.dirname(f), spec))
                target = module_of(os.path.relpath(p, root) + ("" if os.path.splitext(p)[1] else "/x"), a.depth)
            elif k == "dart" and spec.startswith("package:"):
                if a.external: target = "ext:" + spec[8:].split("/")[0]
                # 같은 앱 패키지(lib/...)는 경로로 매핑
                pkg_path = spec[8:].split("/", 1)
                if len(pkg_path) == 2 and os.path.isdir(os.path.join(root, "lib")):
                    target = module_of("lib/" + pkg_path[1], a.depth)
            else:
                hit = next(((al, base) for al, base in aliases if spec == al or spec.startswith(al + "/")), None)
                if hit:
                    p = os.path.join(hit[1], spec[len(hit[0]) + 1:])
                    target = module_of(os.path.relpath(p, root) + "/x", a.depth)
                elif a.external and not spec.startswith(("node:", "dart:")):
                    target = "ext:" + ("/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0])
            if target and target != src_mod and not target.startswith(".."):
                edges[(src_mod, target)] += 1
    deg = Counter()
    for (s, t), n in edges.items(): deg[s] += n; deg[t] += n
    for mod in size: deg[mod] += 0
    keep = {m for m, _ in deg.most_common(a.max_nodes)}
    out = ["flowchart LR"]
    groups = {}
    for m in sorted(keep):
        top = "외부 패키지" if m.startswith("ext:") else m.split("/")[0]
        groups.setdefault(top, []).append(m)
    for top, mods in groups.items():
        if len(mods) > 1:
            out.append(f'  subgraph {ident("g_" + top)}["{top}"]')
            out += [f'    {ident(m)}["{m.replace("ext:", "")} ({size.get(m, 0)})"]' for m in mods]
            out.append("  end")
        else:
            m = mods[0]; out.append(f'  {ident(m)}["{m.replace("ext:", "")} ({size.get(m, 0)})"]')
    shown = 0
    for (s, t), n in sorted(edges.items(), key=lambda x: -x[1]):
        if s in keep and t in keep:
            out.append(f"  {ident(s)} -->|{n}| {ident(t)}"); shown += 1
    result = "\n".join(out) + "\n"
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        open(a.out, "w", encoding="utf-8").write(result)
        print(f"✅ {a.out} — 파일 {len(files)}개 → 모듈 {len(keep)}개(전체 {len(deg)}), 의존 {shown}개")
        if len(deg) > a.max_nodes: print(f"⚠️ 모듈 {len(deg)}개 중 연결 많은 {a.max_nodes}개만 표시 — --depth 1 로 개요, 폴더 지정으로 상세")
    else:
        sys.stdout.write(result)

if __name__ == "__main__":
    main()
