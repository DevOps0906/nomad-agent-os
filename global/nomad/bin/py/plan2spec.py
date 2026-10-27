#!/usr/bin/env python3
"""plan2spec — 기획 표를 한 번만 해석해 사양 · 구조도 · 와이어프레임 · 필수 구조 검사를 만든다 (모델 토큰 0).

사용: plan2spec [docs=docs] [--tokens tokens.css] [--out design] [--diagrams docs/diagrams] [--strict] [--quiet]
      plan2spec get <ID...> [--docs docs]        (= spec <ID...>) 화면·흐름·API·테이블 하나만 15줄 안팎으로
입력: docs/**/*.md 의 표 — 화면(ID·화면·유형·경로·주된 일·구성·데이터·API·권한·다음) · 상태(ID·빈·로딩·오류·성공)
      · 흐름(ID·흐름·단계) · API(ID·메서드·경로…) · 데이터(테이블·목적…). 형식: ~/.claude/skills/ux-patterns/SKILL.md
출력: design/spec.json · docs/diagrams/{sitemap,screen-data,flow-<ID>}.mmd · design/wireframes/<ID>.html · index.html
원칙: 바뀐 화면만 다시 만든다(해시 비교). 팀원은 문서를 다시 읽지 않고 `spec <ID>` 결과만 받는다.
"""
import argparse, glob, hashlib, html, importlib.util, json, os, re, sys
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace"); sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

VERSION = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
PATTERNS = os.path.normpath(os.path.join(HERE, "..", "..", "..", "skills", "ux-patterns", "patterns.json"))
STATE_KEYS = ["빈", "로딩", "오류", "성공"]
NA = {"—", "-", "–", "없음", "해당 없음", "n/a", "na"}
SKIP = {"node_modules", ".git", ".next", "dist", "build", ".nomad", "wireframes"}
e = html.escape


def sha(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def load_dp():
    spec = importlib.util.spec_from_file_location("design_preview", os.path.join(HERE, "design-preview.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


# ---------- 마크다운 표 ----------
def cells(line):
    s = line.strip()
    if s.startswith("|"): s = s[1:]
    if s.endswith("|"): s = s[:-1]
    out = [c.replace("\\|", "|").strip().strip("`").replace("**", "").strip() for c in re.split(r"(?<!\\)\|", s)]
    return out


def tables(text):
    lines, out, i = text.splitlines(), [], 0
    while i < len(lines) - 1:
        if lines[i].lstrip().startswith("|") and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            head = cells(lines[i]); rows = []; j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                r = cells(lines[j]); rows.append(r + [""] * (len(head) - len(r))); j += 1
            out.append((head, rows)); i = j
        else:
            i += 1
    return out


def norm(h):
    return re.sub(r"[\s()·/]", "", h.lower())


def col(head, *keys):
    hs = [norm(h) for h in head]
    for k in keys:
        for idx, h in enumerate(hs):
            if h == k or h.startswith(k): return idx
    return None


def kind_of(head):
    hs = [norm(h) for h in head]
    has = lambda *k: any(any(h == x or h.startswith(x) for x in k) for h in hs)
    idc = has("id", "번호")
    if idc and has("빈", "로딩", "empty", "loading"): return "states"
    if idc and has("단계", "steps") and has("흐름", "flow", "이름"): return "flows"
    if idc and has("메서드", "method"): return "apis"
    if hs and hs[0] in ("테이블", "table"): return "tables"
    if idc and has("화면", "screen") and has("구성", "경로", "유형", "주된일", "블록", "route"): return "screens"
    return None


def split_list(s):
    return [x.strip() for x in re.split(r"[,，;·/]|\s→\s|->", s or "") if x.strip() and x.strip() not in NA]


def parse_blocks(s):
    out = []
    for part in re.split(r"[,，;]", s or ""):
        part = part.strip()
        if not part: continue
        t, _, label = part.partition(":")
        out.append({"type": t.strip().lower(), "label": label.strip(),
                    "items": [x.strip() for x in re.split(r"[·/|]", label) if x.strip()]})
    return out


# ---------- 해석 ----------
def read_docs(docs):
    files = []
    for p in sorted(glob.glob(os.path.join(docs, "**", "*.md"), recursive=True)):
        if any(part in SKIP for part in p.replace("\\", "/").split("/")): continue
        files.append(p)
    model = {"screens": {}, "states": {}, "flows": {}, "apis": {}, "tables": {}, "sources": {}, "counts": {}}
    for p in files:
        text = open(p, encoding="utf-8", errors="replace").read()
        found = False
        for head, rows in tables(text):
            k = kind_of(head)
            if not k: continue
            found = True; rel = os.path.relpath(p).replace("\\", "/")
            model["counts"].setdefault(rel, {}).setdefault(k, 0)
            idc = col(head, "id", "번호")
            for r in rows:
                if k == "tables":
                    name = r[0].strip()
                    if not name: continue
                    model["tables"][name] = {"name": name, "row": dict(zip(head, r)), "source": rel}
                    model["counts"][rel][k] += 1; continue
                rid = r[idc].strip() if idc is not None else ""
                if not rid or rid.startswith("<"): continue
                g = lambda *keys: (r[col(head, *keys)] if col(head, *keys) is not None else "").strip()
                model["counts"][rel][k] += 1
                if k == "screens":
                    combined = g("상태빈로딩오류", "상태")
                    model["screens"][rid] = {
                        "id": rid, "name": g("화면", "screen", "이름"), "type_raw": g("유형", "type"),
                        "route": g("경로", "route", "path"), "purpose": g("주된일", "목적", "purpose"),
                        "blocks": parse_blocks(g("구성", "블록", "components")), "data": split_list(g("데이터", "data", "테이블")),
                        "api": split_list(g("api")), "role": g("권한", "role", "access"),
                        "next": split_list(g("다음", "next", "이동")), "states_combined": combined, "source": rel,
                        "row": "|".join(r)}
                elif k == "states":
                    model["states"][rid] = {s: g(s) for s in STATE_KEYS}
                    model["states"][rid]["_row"] = "|".join(r)
                elif k == "flows":
                    model["flows"][rid] = {"id": rid, "name": g("흐름", "flow", "이름"),
                                           "steps": [x.strip() for x in re.split(r"→|->|>", g("단계", "steps")) if x.strip()],
                                           "source": rel}
                elif k == "apis":
                    model["apis"][rid] = {"id": rid, "method": g("메서드", "method"), "path": g("경로", "path"),
                                          "row": dict(zip(head, r)), "source": rel}
        if found: model["sources"][os.path.relpath(p).replace("\\", "/")] = sha(text)
    return model


def load_patterns(docs=None):
    """기본 patterns.json + 프로젝트 docs/**/patterns.json(모듈이 가져온 것)을 합친다.
    모듈은 새 유형(types.X.must)을 추가하거나, 기존 유형에 must_extra(applies_to_prefix 로 범위 한정)를 더한다."""
    try:
        pats = json.load(open(PATTERNS, encoding="utf-8"))
    except (OSError, ValueError):
        pats = {"types": {}, "aliases": {}, "states_all": []}
    pats["extra"], pats["module_files"] = [], []
    for p in sorted(glob.glob(os.path.join(docs, "**", "patterns.json"), recursive=True)) if docs else []:
        try:
            m = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pats["module_files"].append(p.replace("\\", "/"))
        for t, spec in (m.get("types") or {}).items():
            if "must" in spec and t not in pats["types"]: pats["types"][t] = spec
            if spec.get("must_extra"): pats["extra"].append((t, spec.get("applies_to_prefix", ""), spec["must_extra"]))
        pats["aliases"].update(m.get("aliases") or {})
    return pats


def type_of(raw, pats):
    r = (raw or "").strip().lower()
    if r in pats["types"]: return r
    for k, v in pats.get("aliases", {}).items():
        if k in r: return v
    return ""


def state_defined(s, states, key):
    if s["states_combined"] and s["id"] not in states:
        return key in s["states_combined"] or s["states_combined"] in NA
    v = (states.get(s["id"]) or {}).get(key, "")
    return bool(v.strip())


def req_ok(req, s, states):
    if req.get("next"): return bool(s["next"])
    if req.get("state"): return state_defined(s, states, req["state"])
    for alt in req.get("any", []):
        t, _, rx = alt.partition("~")
        for b in s["blocks"]:
            if b["type"] == t and (not rx or re.search(rx, b["label"], re.I)): return True
    return False


def check(model, pats):
    issues, S = [], model["screens"]
    incoming = {n for s in S.values() for n in s["next"]}
    for f in model["flows"].values():
        incoming |= set(f["steps"][1:])
    for sid, s in S.items():
        t = type_of(s["type_raw"], pats); s["type"] = t
        s["must_missing"], s["should_missing"], s["states_missing"] = [], [], []
        if not t:
            issues.append(("🟡", sid, f"유형 없음/모름('{s['type_raw']}') → 필수 구조 검사 불가 (대시보드·목록·상세·폼·보드·마법사·설정·로그인·랜딩)"))
        else:
            spec = pats["types"][t]
            musts = spec["must"] + [r for tt, pre, reqs in pats.get("extra", []) if tt == t and sid.startswith(pre) for r in reqs]
            kinds = {b["type"] for b in s["blocks"]}   # if_has: 그 블록이 있는 화면에만 적용 (예: 폼이 있는 랜딩만 동의 검사)
            musts = [r for r in musts if not r.get("if_has") or kinds & set(r["if_has"])]
            s["must_missing"] = [r["label"] for r in musts if not req_ok(r, s, model["states"])]
            s["should_missing"] = [r["label"] for r in spec.get("should", []) if not req_ok(r, s, model["states"])]
            need = list(dict.fromkeys(spec.get("states", []) + pats.get("states_all", []))) if t != "landing" else []
            s["states_missing"] = [k for k in need if not state_defined(s, model["states"], k)]
            if s["must_missing"]: issues.append(("🔴", sid, f"{s['name']}({spec['name']}) 필수 빠짐: {', '.join(s['must_missing'])}"))
            if s["states_missing"]: issues.append(("🔴", sid, f"{s['name']} 상태 미정의: {', '.join(s['states_missing'])}"))
            if s["should_missing"]: issues.append(("🟡", sid, f"{s['name']} 권장: {', '.join(s['should_missing'])}"))
        if not s["blocks"]: issues.append(("🔴", sid, f"{s['name']} 구성 비어 있음 → 와이어프레임 불가"))
        if not s["route"]: issues.append(("🟡", sid, f"{s['name']} 경로 없음"))
        for n in s["next"]:
            if n not in S: issues.append(("🔴", sid, f"다음 '{n}' — 없는 화면 ID"))
        if model["apis"]:
            for a in s["api"]:
                if a not in model["apis"]: issues.append(("🟡", sid, f"API '{a}' — 04_API 표에 없음"))
        if model["tables"]:
            for d in s["data"]:
                if d not in model["tables"]: issues.append(("🟡", sid, f"데이터 '{d}' — 05_DATA_MODEL 표에 없음"))
        unknown = [b["type"] for b in s["blocks"] if b["type"] not in BLOCKS]
        if unknown: issues.append(("ℹ️", sid, f"모르는 블록(회색 상자로 표시): {', '.join(sorted(set(unknown)))}"))
    for fid, f in model["flows"].items():
        bad = [x for x in f["steps"] if re.match(r"^[A-Z]+-", x) and x not in S]
        if bad: issues.append(("🔴", fid, f"흐름 '{f['name']}'의 없는 화면: {', '.join(bad)}"))
    first = next(iter(S), None)
    for sid in S:
        if sid != first and sid not in incoming and S[sid].get("type") not in ("auth", "landing"):
            issues.append(("ℹ️", sid, f"{S[sid]['name']} — 들어오는 경로 없음(메뉴에서만 진입이면 무시)"))
    return issues


# ---------- 다이어그램 ----------
def nid(x):
    return "n_" + re.sub(r"\W", "_", x)


def lbl(x):
    return x.replace('"', "#quot;")


def diagrams(model):
    S, out = model["screens"], {}
    lines = ["flowchart LR"]
    groups = {}
    for s in S.values(): groups.setdefault(s["role"] or "권한 미정", []).append(s)
    for gi, (role, ss) in enumerate(groups.items()):
        lines.append(f'  subgraph g{gi}["{lbl(role)}"]')
        for s in ss: lines.append(f'    {nid(s["id"])}["{lbl(s["id"] + " " + s["name"])}<br/>{lbl(s["route"] or "")}"]')
        lines.append("  end")
    for s in S.values():
        for n in s["next"]:
            if n in S: lines.append(f"  {nid(s['id'])} --> {nid(n)}")
    out["sitemap.mmd"] = "\n".join(lines) + "\n"
    for fid, f in model["flows"].items():
        fl = ["flowchart LR"]; prev = None
        for i, st in enumerate(f["steps"]):
            node = f"st{i}"
            name = f"{st} {S[st]['name']}" if st in S else st
            fl.append(f'  {node}["{lbl(name)}"]')
            if prev: fl.append(f"  {prev} --> {node}")
            prev = node
        out[f"flow-{re.sub(r'[^A-Za-z0-9_-]', '_', fid)}.mmd"] = "\n".join(fl) + "\n"
    if any(s["api"] or s["data"] for s in S.values()):
        dl = ["flowchart LR", '  subgraph SC["화면"]']
        dl += [f'    {nid(s["id"])}["{lbl(s["id"] + " " + s["name"])}"]' for s in S.values()]
        dl.append("  end")
        apis = sorted({a for s in S.values() for a in s["api"]}); tabs = sorted({d for s in S.values() for d in s["data"]})
        if apis:
            dl.append('  subgraph AP["API"]')
            for a in apis:
                x = model["apis"].get(a, {}); dl.append(f'    {nid("api_" + a)}["{lbl((a + " " + x.get("method", "") + " " + x.get("path", "")).strip())}"]')
            dl.append("  end")
        if tabs:
            dl.append('  subgraph DB["데이터"]')
            dl += [f'    {nid("t_" + t)}[("{lbl(t)}")]' for t in tabs]
            dl.append("  end")
        for s in S.values():
            dl += [f"  {nid(s['id'])} --> {nid('api_' + a)}" for a in s["api"]]
            dl += [f"  {nid(s['id'])} -.-> {nid('t_' + d)}" for d in s["data"]]
        out["screen-data.mmd"] = "\n".join(dl) + "\n"
    return out


# ---------- 와이어프레임 ----------
BASE_CSS = """
*{box-sizing:border-box}body{margin:0;font-family:var(--font-sans,system-ui,sans-serif);background:var(--color-bg,#fff);color:var(--color-text,#15171a);font-size:var(--text-body,15px);line-height:1.5}
.u{padding:calc(var(--spacing,4px)*4)}.meta{font-size:var(--text-caption,12px);color:var(--color-text-muted,#5b6270);background:var(--color-surface,#f6f7f9);border-bottom:1px dashed var(--color-border,#e3e6eb);padding:6px 16px;display:flex;gap:12px;flex-wrap:wrap}
.meta a{color:var(--color-primary,#2f5bea)}.shell{display:grid;grid-template-columns:1fr;min-height:60vh}.side{display:none;background:var(--color-surface,#f6f7f9);border-right:1px solid var(--color-border,#e3e6eb);padding:16px}
@media (min-width:1200px){.shell.has-side{grid-template-columns:220px 1fr}.side{display:block}.burger{display:none}}
main{display:grid;gap:calc(var(--spacing,4px)*4);padding:calc(var(--spacing,4px)*4);align-content:start;min-width:0}
.hd{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px;border-bottom:1px solid var(--color-border,#e3e6eb)}
.hd h1{font-size:var(--text-h1,24px);margin:0}.hd nav{display:none;gap:12px}@media (min-width:768px){.hd nav{display:flex}}
.burger{width:28px;height:20px;border-top:3px solid currentColor;border-bottom:3px solid currentColor;position:relative}
.box{background:var(--color-surface,#f6f7f9);border:1px solid var(--color-border,#e3e6eb);border-radius:var(--radius-card,12px);padding:16px;min-width:0}
.lab{font-size:var(--text-caption,12px);color:var(--color-text-muted,#5b6270);margin-bottom:6px}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.grid.wide{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.num{font-size:var(--text-h2,20px);font-weight:700}.delta{font-size:var(--text-caption,12px);color:var(--color-success,#1f9d55)}
.bars{display:flex;align-items:flex-end;gap:6px;height:120px}.bars i{flex:1;background:var(--color-primary,#2f5bea);opacity:.35;border-radius:4px 4px 0 0}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:480px}th,td{text-align:left;padding:8px;border-bottom:1px solid var(--color-border,#e3e6eb);font-size:var(--text-caption,13px)}
th{color:var(--color-text-muted,#5b6270)}.skel{display:inline-block;height:10px;width:70%;background:var(--color-border,#e3e6eb);border-radius:4px}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:0 16px;border-radius:var(--radius-control,8px);background:var(--color-primary,#2f5bea);color:var(--color-primary-fg,#fff);font-weight:600;border:0}
.btn.sec{background:transparent;color:var(--color-text,#15171a);border:1px solid var(--color-input,#858d9b)}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.in{display:block;width:100%;min-height:40px;border:1px solid var(--color-input,#858d9b);border-radius:var(--radius-control,8px);background:var(--color-bg,#fff);padding:8px 12px;color:var(--color-text-muted,#5b6270)}
.f{display:grid;gap:12px}.f label{display:grid;gap:4px;font-size:var(--text-caption,13px)}.chip{border:1px solid var(--color-input,#858d9b);border-radius:999px;padding:4px 12px;font-size:var(--text-caption,13px)}
.tabs{display:flex;gap:16px;border-bottom:1px solid var(--color-border,#e3e6eb);overflow-x:auto}.tabs span{padding:8px 0}.tabs span:first-child{border-bottom:2px solid var(--color-primary,#2f5bea);font-weight:600}
.board{display:flex;gap:12px;overflow-x:auto}.col{min-width:220px;flex:1}.card{background:var(--color-bg,#fff);border:1px solid var(--color-border,#e3e6eb);border-radius:var(--radius-control,8px);padding:10px;margin-top:8px}
.hero{padding:48px 16px;text-align:center}.hero h2{font-size:var(--text-display,28px);margin:0 0 8px}
.steps{display:flex;gap:8px;list-style:none;padding:0;margin:0;flex-wrap:wrap}.steps li{flex:1;min-width:90px;border-top:4px solid var(--color-border,#e3e6eb);padding-top:6px;font-size:var(--text-caption,13px)}.steps li:first-child{border-color:var(--color-primary,#2f5bea)}
.dash{border:1px dashed var(--color-input,#858d9b);border-radius:var(--radius-card,12px);padding:16px;text-align:center;color:var(--color-text-muted,#5b6270)}
.ft{margin-top:24px;padding:16px;border-top:1px solid var(--color-border,#e3e6eb);font-size:var(--text-caption,12px);color:var(--color-text-muted,#5b6270)}
.wf{margin:24px 16px;display:grid;gap:12px}.wf h3{margin:0;font-size:var(--text-h2,20px)}.st{display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.ok{color:var(--color-success,#1f9d55)}.no{color:var(--color-danger,#d64545);font-weight:600}.muted{color:var(--color-text-muted,#5b6270)}
"""
BLOCKS = {"header", "nav", "sidebar", "hero", "text", "stat", "chart", "table", "list", "card", "board", "form", "button", "link",
          "search", "filter", "daterange", "pagination", "loadmore", "sort", "tabs", "breadcrumb", "steps", "activity", "updated",
          "export", "modal", "footer", "pricing", "faq", "empty", "title", "badge", "fields", "back", "bulk", "view", "compare",
          "alert", "cta", "proof", "image", "danger", "autosave"}


def items_or(b, default):
    return b["items"] or default


def render_block(b):
    t, L = b["type"], e(b["label"])
    it = lambda d: [e(x) for x in items_or(b, d)]
    if t == "stat":
        return '<div class="grid">' + "".join(f'<div class="box"><div class="lab">{x}</div><div class="num">000</div><div class="delta">▲ 0%</div></div>' for x in it(["지표 1", "지표 2", "지표 3"])) + "</div>"
    if t == "chart":
        return f'<div class="box"><div class="lab">{L or "차트"}</div><div class="bars">' + "".join(f'<i style="height:{h}%"></i>' for h in (40, 65, 50, 80, 60, 90, 70)) + "</div></div>"
    if t in ("table", "fields"):
        cols = it(["항목", "값", "상태"])
        return '<div class="box tw"><table><thead><tr>' + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead><tbody>" + \
               "".join("<tr>" + "".join('<td><span class="skel"></span></td>' for _ in cols) + "</tr>" for _ in range(3)) + "</tbody></table></div>"
    if t in ("list", "activity"):
        return f'<div class="box"><div class="lab">{L or ("활동 이력" if t == "activity" else "목록")}</div>' + "".join('<div class="card"><span class="skel"></span></div>' for _ in range(3)) + "</div>"
    if t in ("card", "pricing", "proof"):
        return '<div class="grid wide">' + "".join(f'<div class="box"><b>{x}</b><p class="muted"><span class="skel"></span></p></div>' for x in it(["카드 1", "카드 2", "카드 3"])) + "</div>"
    if t == "board":
        return '<div class="board">' + "".join(f'<div class="col box"><div class="lab">{x} · 0건</div><div class="card"><span class="skel"></span></div><div class="card"><span class="skel"></span></div></div>' for x in it(["신규", "진행", "완료"])) + "</div>"
    if t == "form":
        return '<form class="box f">' + "".join(f'<label>{x}<span class="in"></span></label>' for x in it(["입력 1", "입력 2"])) + "</form>"
    if t in ("button", "cta", "export"):
        sec = re.search(r"취소|뒤로|cancel|back|내보내기|export", b["label"], re.I) or t == "export"
        return f'<div class="row"><span class="btn{" sec" if sec else ""}">{L or "내보내기"}</span></div>'
    if t in ("link", "back"):
        return f'<div class="row"><a href="#">{L or "뒤로"}</a></div>'
    if t == "search":
        return f'<span class="in">🔍 {L or "검색"}</span>'
    if t in ("filter", "sort", "view", "bulk"):
        return '<div class="row">' + "".join(f'<span class="chip">{x} ▾</span>' for x in it([{"filter": "필터", "sort": "정렬", "view": "보기", "bulk": "일괄 작업"}[t]])) + "</div>"
    if t == "daterange":
        return f'<div class="row"><span class="chip">📅 {L or "기간"}: 이번 달 ▾</span><span class="chip">이전 기간과 비교</span></div>'
    if t in ("pagination", "loadmore"):
        return '<div class="row"><span class="chip">‹</span><span class="chip">1</span><span class="chip">2</span><span class="chip">3</span><span class="chip">›</span></div>' if t == "pagination" else '<div class="row"><span class="btn sec">더 보기</span></div>'
    if t == "tabs":
        return '<div class="tabs">' + "".join(f"<span>{x}</span>" for x in it(["탭 1", "탭 2", "탭 3"])) + "</div>"
    if t == "breadcrumb":
        return f'<div class="lab">홈 › {L or "현재 위치"}</div>'
    if t == "steps":
        return '<ol class="steps">' + "".join(f"<li>{i}. {x}</li>" for i, x in enumerate(it(["1단계", "2단계", "3단계"]), 1)) + "</ol>"
    if t == "updated":
        return '<div class="lab">마지막 갱신: 방금 전 · ↻</div>'
    if t in ("hero",):
        return f'<section class="hero box"><h2>{L or "가치 제안 한 문장"}</h2><p class="muted">보조 설명</p><span class="btn">시작하기</span></section>'
    if t in ("text", "title", "badge", "compare", "alert"):
        return f'<div class="box"><div class="lab">{t}</div>{L or "<span class=skel></span>"}</div>'
    if t in ("modal", "danger"):
        return f'<div class="dash">{"모달" if t == "modal" else "위험 작업"}: {L}</div>'
    if t == "faq":
        return '<div class="box">' + "".join(f"<details><summary>{x}</summary><p class='muted'>답변</p></details>" for x in it(["질문 1", "질문 2"])) + "</div>"
    if t == "empty":
        return f'<div class="dash">빈 상태: {L or "아직 데이터가 없습니다"}</div>'
    if t == "image":
        return '<div class="dash" style="aspect-ratio:16/9">이미지</div>'
    if t in ("header", "nav", "sidebar", "footer"):
        return ""
    return f'<div class="dash">{e(t)}{": " + L if L else ""}</div>'


def wireframe(s, states, token_css, S):
    hdr = next((b for b in s["blocks"] if b["type"] == "header"), None)
    nav = next((b for b in s["blocks"] if b["type"] == "nav"), None)
    side = next((b for b in s["blocks"] if b["type"] == "sidebar"), None)
    foot = next((b for b in s["blocks"] if b["type"] == "footer"), None)
    navhtml = "".join(f'<a href="#">{e(x)}</a>' for x in (nav["items"] if nav else []))
    head = (f'<header class="hd"><h1>{e(s["name"])}</h1><nav>{navhtml}</nav><span class="burger" aria-label="메뉴"></span></header>'
            if hdr or nav else "")
    sidehtml = (f'<aside class="side"><div class="lab">메뉴</div>' + "".join(f"<div>{e(x)}</div>" for x in items_or(side, ["메뉴 1", "메뉴 2", "메뉴 3"])) + "</aside>") if side else ""
    body = "\n".join(render_block(b) for b in s["blocks"])
    st = states.get(s["id"]) or {}
    def stcell(k):
        if s["states_combined"] and s["id"] not in states: return f'<div class="box"><b>{k}</b><p class="muted">{e(s["states_combined"])}</p></div>'
        v = (st.get(k) or "").strip()
        need = k in s.get("states_missing", [])
        return f'<div class="box"><b>{k}</b><p class="{"no" if need else "muted"}">{e(v) if v else ("미정의 — 기획 필요" if need else "—")}</p></div>'
    must = "".join(f'<div class="no">❌ {e(x)}</div>' for x in s.get("must_missing", [])) or (
        '<div class="ok">✅ 필수 구조 충족</div>' if s.get("type") else '<div class="muted">유형 미지정 — 검사 안 함</div>')
    should = "".join(f'<div class="muted">· 권장: {e(x)}</div>' for x in s.get("should_missing", []))
    nexts = " · ".join(f'<a href="{e(n)}.html">{e(n)} {e(S[n]["name"])}</a>' for n in s["next"] if n in S) or "—"
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(s["id"])} {e(s["name"])} — 와이어프레임</title><style>{token_css}{BASE_CSS}</style></head><body>
<script>if(location.search.indexOf('dark')>=0)document.documentElement.classList.add('dark')</script>
<div class="meta"><b>{e(s["id"])}</b><span>{e(s["type_raw"] or "유형 미지정")}</span><span>{e(s["route"])}</span><span>권한: {e(s["role"] or "미정")}</span><span>{e(s["purpose"])}</span><a href="index.html">전체 화면</a></div>
<div class="shell{" has-side" if side else ""}">{sidehtml}<div>{head}<main>
{body}
</main>{f'<footer class="ft">{e(foot["label"] or "약관 · 개인정보처리방침 · 사업자 정보")}</footer>' if foot else ""}</div></div>
<section class="wf"><h3>상태</h3><div class="st">{"".join(stcell(k) for k in STATE_KEYS)}</div>
<h3>필수 구조 검사</h3><div>{must}{should}</div><h3>다음 화면</h3><div>{nexts}</div></section>
</body></html>
"""


def index_html(S, token_css):
    sizes = [("모바일 375", 375, 720, .55), ("태블릿 768", 768, 900, .42), ("데스크톱 1280", 1280, 860, .36)]
    cards = []
    for s in S.values():
        flag = ('<span class="no">❌ 필수 ' + str(len(s.get("must_missing", [])) + len(s.get("states_missing", []))) + "</span>") \
            if s.get("must_missing") or s.get("states_missing") else '<span class="ok">✅</span>'
        frames = "".join(f'<div><div class="lab">{n}</div><div style="width:{int(w*k)}px;height:{int(h*k)}px;overflow:hidden;border:1px solid var(--color-border,#e3e6eb);border-radius:8px">'
                         f'<iframe data-src="{e(s["id"])}.html" src="{e(s["id"])}.html" style="width:{w}px;height:{h}px;border:0;transform:scale({k});transform-origin:0 0" loading="lazy"></iframe></div></div>'
                         for n, w, h, k in sizes)
        cards.append(f'<section class="box" style="margin:16px"><div class="row"><b><a href="{e(s["id"])}.html">{e(s["id"])} {e(s["name"])}</a></b>'
                     f'<span class="muted">{e(s["type_raw"])} · {e(s["route"])}</span>{flag}</div><div class="row" style="align-items:flex-start;margin-top:8px">{frames}</div></section>')
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>와이어프레임 — 전체 화면</title><style>{token_css}{BASE_CSS}</style></head><body>
<div class="meta"><b>와이어프레임 {len(S)}개</b><span>plan2spec 생성 — 손으로 고치지 말고 기획 표·토큰을 고친 뒤 다시 실행</span>
<label><input type="checkbox" id="dk"> 다크 모드</label></div>{"".join(cards)}
<script>document.getElementById('dk').onchange=function(){{var d=this.checked;document.querySelectorAll('iframe').forEach(function(f){{f.src=f.dataset.src+(d?'?dark':'')}})}}</script>
</body></html>
"""


def token_css(tokens):
    dp = load_dp()
    if tokens and os.path.exists(tokens):
        src, note = open(tokens, encoding="utf-8").read(), tokens
    else:
        src, note = dp.STARTER, "기본 시작 토큰(프로젝트 토큰 없음)"
    base, dark, resp = dp.parse(src)
    css = ":root{" + ";".join(f"{k}:{v}" for k, v in base.items()) + "}"
    if dark: css += ".dark{" + ";".join(f"{k}:{v}" for k, v in dark.items()) + "}"
    for w, d in sorted(resp.items()):
        css += f"@media (min-width:{w}px){{:root{{{';'.join(f'{k}:{v}' for k, v in d.items())}}}}}"
    return css, note, sha(src)


def find_tokens(root):
    for pat in ("src/styles/tokens.css", "apps/*/src/styles/tokens.css", "app/styles/tokens.css", "styles/tokens.css", "tokens.css"):
        hit = sorted(glob.glob(os.path.join(root, pat)))
        if hit: return hit[0]
    return ""


def write_if_changed(path, text):
    if os.path.exists(path) and open(path, encoding="utf-8").read() == text: return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f: f.write(text)
    return True


# ---------- build / get ----------
def screen_hash(s, model, tok_hash, pat_hash):
    st = (model["states"].get(s["id"]) or {}).get("_row", "")
    api = [model["apis"].get(a, {}).get("row") for a in s["api"]]
    tab = [model["tables"].get(d, {}).get("row") for d in s["data"]]
    nxt = [model["screens"][n]["name"] for n in s["next"] if n in model["screens"]]
    return sha(json.dumps([VERSION, s["row"], st, api, tab, nxt, tok_hash, pat_hash], ensure_ascii=False, sort_keys=True))


def build(a, quiet=False):
    say = (lambda *x: None) if quiet else print
    model = read_docs(a.docs)
    S = model["screens"]
    if not S:
        empty = [p for p, c in model["counts"].items() if "screens" in c]
        say(f"■ plan2spec: 화면 표는 있지만 행이 없습니다 — {', '.join(empty)} 에 화면을 채운 뒤 다시 실행" if empty
            else f"■ plan2spec: '{a.docs}' 에서 화면 표를 찾지 못했습니다.")
        say("  형식: | ID | 화면 | 유형 | 경로 | 주된 일 | 구성 | 데이터 | API | 권한 | 다음 |  (~/.claude/skills/ux-patterns/SKILL.md 2절)")
        return None
    pats = load_patterns(a.docs)
    issues = check(model, pats)
    tokens = a.tokens or find_tokens(".")
    tcss, tnote, thash = token_css(tokens)
    phash = sha(json.dumps(pats, sort_keys=True))
    spec_path = os.path.join(a.out, "spec.json")
    old = {}
    if os.path.exists(spec_path):
        try: old = json.load(open(spec_path, encoding="utf-8"))
        except ValueError: old = {}
    old_hash = {k: v.get("hash") for k, v in (old.get("screens") or {}).items()}
    wdir = os.path.join(a.out, "wireframes")
    changed, new = [], []
    for sid, s in S.items():
        s["hash"] = screen_hash(s, model, thash, phash)
        s["wireframe"] = os.path.join(wdir, f"{sid}.html").replace("\\", "/")
        if old_hash.get(sid) != s["hash"] or not os.path.exists(s["wireframe"]):
            (new if sid not in old_hash else changed).append(sid)
            write_if_changed(s["wireframe"], wireframe(s, model["states"], tcss, S))
    removed = [k for k in old_hash if k not in S]
    for k in removed:
        p = os.path.join(wdir, f"{k}.html")
        if os.path.exists(p): os.remove(p)
    write_if_changed(os.path.join(wdir, "index.html"), index_html(S, tcss))
    dwrote = []
    for name, text in diagrams(model).items():
        if write_if_changed(os.path.join(a.diagrams, name), text): dwrote.append(name)
    for s in S.values(): s.pop("row", None)
    for st in model["states"].values(): st.pop("_row", None)
    spec = {"version": VERSION, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "docs": a.docs, "tokens": tnote, "sources": model["sources"], "changed": changed + new, "removed": removed,
            "screens": S, "states": model["states"], "flows": model["flows"],
            "apis": {k: {kk: vv for kk, vv in v.items()} for k, v in model["apis"].items()},
            "tables": model["tables"], "issues": [list(x) for x in issues]}
    os.makedirs(a.out, exist_ok=True)
    with open(spec_path, "w", encoding="utf-8", newline="\n") as f: json.dump(spec, f, ensure_ascii=False, indent=1)
    if quiet: return spec
    say(f"■ plan2spec → {spec_path}")
    names = {"screens": "화면", "states": "상태", "flows": "흐름", "apis": "API", "tables": "테이블"}
    say("  읽은 표: " + " · ".join(p + "(" + ", ".join(names[k] + " " + str(n) for k, n in c.items()) + ")"
                                   for p, c in model["counts"].items()))
    if changed or new or removed:
        say("  바뀐 화면: " + (", ".join(changed) or "없음") + (f" · 새로: {', '.join(new)}" if new else "") + (f" · 삭제: {', '.join(removed)}" if removed else ""))
    else:
        say("  변경 없음 — 다시 만들 것 없음")
    say(f"  와이어프레임: {wdir}/index.html (갱신 {len(changed) + len(new)} / 전체 {len(S)}) · 토큰: {tnote}")
    if dwrote: say(f"  다이어그램 갱신: {', '.join(os.path.join(a.diagrams, d).replace(chr(92), '/') for d in dwrote)}")
    red = [x for x in issues if x[0] == "🔴"]; yel = [x for x in issues if x[0] == "🟡"]; inf = [x for x in issues if x[0] == "ℹ️"]
    say(f"■ 필수 구조 검사: 🔴 {len(red)} · 🟡 {len(yel)} · ℹ️ {len(inf)}" + ("  ✅" if not red else ""))
    for lv, i, m in red + yel[:10] + inf[:5]:
        say(f"  {lv} {i} {m}")
    if len(yel) > 10: say(f"  … 🟡 외 {len(yel) - 10}건 (design/spec.json issues)")
    if dwrote: say(f"■ 다음: mmd-check {' '.join(os.path.join(a.diagrams, d).replace(chr(92), '/') for d in dwrote)}")
    return spec


def fresh_spec(a):
    spec_path = os.path.join(a.out, "spec.json")
    try:
        spec = json.load(open(spec_path, encoding="utf-8"))
        cur = read_docs(spec.get("docs", a.docs))["sources"]
        if cur == spec.get("sources"): return spec
    except (OSError, ValueError):
        pass
    return build(a, quiet=True)


def get(a):
    spec = fresh_spec(a)
    if not spec:
        print("❌ 사양이 없습니다 — 기획 표부터: plan2spec"); return 1
    S, st = spec["screens"], spec["states"]
    for want in a.ids:
        if want in S:
            s = S[want]
            print(f"■ {s['id']} {s['name']} ({s.get('type_raw') or '유형 미정'}) {s['route']} — 권한: {s['role'] or '미정'}")
            print(f"  주된 일: {s['purpose']}")
            print("  구성: " + " · ".join(b["type"] + (":" + b["label"] if b["label"] else "") for b in s["blocks"]))
            if want in st: print("  상태: " + " | ".join(f"{k}={st[want].get(k) or '미정의'}" for k in STATE_KEYS))
            elif s.get("states_combined"): print(f"  상태: {s['states_combined']}")
            if s.get("must_missing") or s.get("states_missing"):
                print("  🔴 빠짐: " + ", ".join(s.get("must_missing", []) + [f"상태 {x}" for x in s.get("states_missing", [])]))
            print("  다음: " + (" · ".join(f"{n} {S[n]['name']}" for n in s["next"] if n in S) or "—"))
            fl = [f for f in spec["flows"].values() if want in f["steps"]]
            for f in fl: print(f"  흐름: {f['id']} {f['name']} ({' → '.join(f['steps'])})")
            for x in s["api"]:
                ap = spec["apis"].get(x)
                print(f"  API: {x} " + (" | ".join(f"{k}:{v}" for k, v in ap["row"].items() if v and k.upper() != "ID") if ap else "(04_API 표에 없음)"))
            for d in s["data"]:
                t = spec["tables"].get(d)
                print(f"  데이터: {d} " + (" | ".join(f"{k}:{v}" for k, v in list(t["row"].items())[1:] if v) if t else "(05 표에 없음)"))
            print(f"  시안: {s['wireframe']}  · 원문: {s['source']}")
        elif want in spec["flows"]:
            f = spec["flows"][want]
            print(f"■ {f['id']} {f['name']}: " + " → ".join(f"{x} {S[x]['name']}" if x in S else x for x in f["steps"]))
        elif want in spec["apis"]:
            ap = spec["apis"][want]; print(f"■ {want} " + " | ".join(f"{k}:{v}" for k, v in ap["row"].items() if v))
            print("  쓰는 화면: " + (", ".join(k for k, s in S.items() if want in s["api"]) or "없음"))
        elif want in spec["tables"]:
            t = spec["tables"][want]; print(f"■ {want} " + " | ".join(f"{k}:{v}" for k, v in t["row"].items() if v))
            print("  쓰는 화면: " + (", ".join(k for k, s in S.items() if want in s["data"]) or "없음"))
        elif want in ("changed", "--changed"):
            print("■ 마지막 실행에서 바뀐 화면: " + (", ".join(spec.get("changed") or []) or "없음"))
        else:
            print(f"❓ {want} — 화면·흐름·API·테이블 어디에도 없음")
    return 0


def main():
    argv = sys.argv[1:]
    ap = argparse.ArgumentParser(prog="plan2spec")
    ap.add_argument("--docs", default=None); ap.add_argument("--tokens", default="")
    ap.add_argument("--out", default="design"); ap.add_argument("--diagrams", default=os.path.join("docs", "diagrams"))
    ap.add_argument("--strict", action="store_true"); ap.add_argument("--quiet", action="store_true")
    if argv and argv[0] == "get":
        ap.add_argument("ids", nargs="+"); a = ap.parse_args(argv[1:]); a.docs = a.docs or "docs"; return get(a)
    ap.add_argument("docs_pos", nargs="?", default="docs")
    a = ap.parse_args(argv); a.docs = a.docs or a.docs_pos
    if not os.path.isdir(a.docs):
        print(f"❌ 문서 폴더가 없습니다: {a.docs}"); return 2
    spec = build(a, a.quiet)
    if a.strict and spec and any(i[0] == "🔴" for i in spec["issues"]): return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
