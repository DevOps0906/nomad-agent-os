#!/usr/bin/env python3
"""design-preview — 디자인 토큰 파일(Tailwind CSS v4 @theme / :root / .dark / @media)을 읽어
미리보기 HTML 1장을 자동 생성한다. 모델이 미리보기 HTML을 매번 새로 쓰지 않게 해 토큰을 0으로 만든다.

사용:
  design-preview <tokens.css> [-o design/preview.html] [--md DESIGN_TOKENS.md]
  design-preview --init <tokens.css>      # 반응형 3구간 폰트가 들어간 시작 토큰 파일 생성
"""
import argparse, html, os, re, sys

try:  # 한국어 Windows(cp949) 콘솔에서도 이모지·한글 출력이 죽지 않게
    sys.stdout.reconfigure(encoding="utf-8", errors="replace"); sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BP = [("모바일 ~767", None), ("태블릿 768~1199", 768), ("데스크톱 1200~", 1200)]

STARTER = """/* tokens.css — 디자인 시스템 정답 소스 (Tailwind CSS v4). DESIGN.md 표는 design-preview --md 로 재생성 */
@import "tailwindcss";
@custom-variant dark (&:where(.dark, .dark *));

@theme {
  /* 색 (의미 이름) */
  --color-bg: #ffffff;
  --color-surface: #f6f7f9;
  --color-text: #15171a;
  --color-text-muted: #5b6270;
  --color-border: #e3e6eb;
  --color-input: #858d9b;      /* 입력창·체크박스 경계 — 배경 대비 3:1 이상 (WCAG 1.4.11) */
  --color-primary: #2f5bea;
  --color-primary-fg: #ffffff;
  --color-success: #1f9d55;
  --color-warning: #c27c0e;
  --color-danger: #d64545;

  /* 서체 */
  --font-sans: "Pretendard Variable", Pretendard, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;

  /* 글자 크기 — 모바일 기준값 (태블릿·데스크톱은 아래 @media) */
  --text-display: 28px;
  --text-h1: 24px;
  --text-h2: 20px;
  --text-body: 15px;
  --text-caption: 12px;

  /* 간격 · 반경 · 그림자 */
  --spacing: 4px;
  --radius-control: 8px;
  --radius-card: 12px;
  --shadow-card: 0 1px 2px rgb(0 0 0 / 0.06), 0 4px 12px rgb(0 0 0 / 0.06);
}

@media (width >= 768px) {
  :root { --text-display: 36px; --text-h1: 28px; --text-h2: 22px; --text-body: 16px; --text-caption: 13px; }
}
@media (width >= 1200px) {
  :root { --text-display: 48px; --text-h1: 34px; --text-h2: 26px; --text-body: 16px; --text-caption: 13px; }
}

.dark {
  --color-bg: #0f1114;
  --color-surface: #181b20;
  --color-text: #eef0f3;
  --color-text-muted: #9aa2ae;
  --color-border: #2a2f37;
  --color-input: #666e7c;
  --color-primary: #6d8cff;
  --color-primary-fg: #0f1114;
}
"""

def blocks(css, opener):
    """opener 정규식 다음의 { ... } 본문들을 돌려준다."""
    out = []
    for m in re.finditer(opener, css):
        i = css.find("{", m.end() - 1)
        depth, j = 0, i
        while j < len(css):
            if css[j] == "{": depth += 1
            elif css[j] == "}":
                depth -= 1
                if depth == 0: break
            j += 1
        out.append((m, css[i + 1:j]))
    return out

def decls(body):
    body = re.sub(r"@media[^{]*\{(?:[^{}]|\{[^{}]*\})*\}", "", body)
    return {k: v.strip() for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", body)}

def parse(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    top = css  # @media 블록을 지운 최상위 CSS — 미디어 안의 :root 를 기본값으로 읽지 않기 위해
    for m, b in reversed(blocks(css, r"@media[^{]*\{")):
        top = top.replace(css[m.start():m.end()] + b + "}", "")
    base = {}
    for _, b in blocks(top, r"@theme\b[^{]*\{"): base.update(decls(b))
    for _, b in blocks(top, r"(?m)^\s*:root\s*\{"): base.update(decls(b))
    dark = {}
    for _, b in blocks(top, r"(?m)^\s*(?:\.dark|\[data-theme=['\"]?dark['\"]?\])\s*\{"): dark.update(decls(b))
    for _, b in blocks(css, r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{"): dark.update(decls(b))
    resp = {}
    for m, b in blocks(css, r"@media\s*\([^)]*?(?:min-width|width\s*>=)\s*:?\s*(\d+)px[^)]*\)\s*\{"):
        resp.setdefault(int(m.group(1)), {}).update(decls(b))
    return base, dark, resp

def group(base):
    g = {"color": [], "font": [], "text": [], "space": [], "radius": [], "shadow": [], "etc": []}
    for k, v in base.items():
        n = k[2:]
        if "--" in n or n.startswith(("font-weight", "leading", "tracking")):   # --text-h1--line-height 같은 보조 토큰
            g["etc"].append((k, v)); continue
        key = ("color" if n.startswith("color") else "font" if n.startswith("font") else
               "text" if n.startswith("text") else "space" if n.startswith(("spacing", "space")) else
               "radius" if n.startswith("radius") else "shadow" if n.startswith("shadow") else "etc")
        g[key].append((k, v))
    return g

def text_at(k, base, resp, bp):
    v = base.get(k, "")
    for w in sorted(resp):
        if bp and w <= bp and k in resp[w]: v = resp[w][k]
    return v

def build(path, out, md):
    css = open(path, encoding="utf-8").read()
    base, dark, resp = parse(css)
    if not base: sys.exit("토큰을 찾지 못했습니다 (@theme / :root 의 --변수)")
    g = group(base)
    root = ";".join(f"{k}:{v}" for k, v in base.items())
    darkcss = ";".join(f"{k}:{v}" for k, v in dark.items())
    media = "".join(f"@media (min-width:{w}px){{:root{{{';'.join(f'{k}:{v}' for k, v in d.items())}}}}}" for w, d in sorted(resp.items()))
    e = html.escape
    sw = "".join(f'<div class="sw"><i style="background:var({k})"></i><b>{e(k[8:])}</b><code>{e(v)}</code>'
                 f'{f"<code>dark {e(dark[k])}</code>" if k in dark else ""}</div>' for k, v in g["color"])
    rows = "".join(f'<tr><td><code>{e(k)}</code></td>' + "".join(f"<td>{e(text_at(k, base, resp, w))}</td>" for _, w in BP)
                   + f'<td><span style="font-size:var({k})">가나다 Aa 123</span></td></tr>' for k, _ in g["text"])
    rad = "".join(f'<div class="box" style="border-radius:var({k})">{e(k[9:])}<br><code>{e(v)}</code></div>' for k, v in g["radius"])
    sha = "".join(f'<div class="box" style="box-shadow:var({k})">{e(k[9:])}</div>' for k, v in g["shadow"])
    fonts = "".join(f'<p style="font-family:var({k})"><code>{e(k)}</code> 다람쥐 헌 쳇바퀴에 타고파 · The quick fox 0123456789</p>' for k, _ in g["font"])
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Design Tokens Preview</title><style>
:root{{{root}}} .dark{{{darkcss}}} {media}
body{{margin:0;padding:24px 16px;background:var(--color-bg,#fff);color:var(--color-text,#111);font-family:var(--font-sans,system-ui);font-size:var(--text-body,16px)}}
h1{{font-size:var(--text-h1,28px)}} h2{{font-size:var(--text-h2,20px);margin-top:40px;border-bottom:1px solid var(--color-border,#ddd);padding-bottom:6px}}
code{{font-family:var(--font-mono,monospace);font-size:12px;color:var(--color-text-muted,#666);display:block}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}}
.sw i{{display:block;height:56px;border-radius:8px;border:1px solid var(--color-border,#ddd)}} .sw b{{display:block;margin-top:6px;font-size:13px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} td,th{{border-bottom:1px solid var(--color-border,#ddd);padding:8px;text-align:left;vertical-align:middle}}
.box{{padding:18px;background:var(--color-surface,#f5f5f5);border:1px solid var(--color-border,#ddd);text-align:center;font-size:13px}}
.row{{display:flex;flex-wrap:wrap;gap:12px;align-items:center}}
.btn{{font:inherit;padding:10px 18px;border-radius:var(--radius-control,8px);border:1px solid transparent;background:var(--color-primary,#2f5bea);color:var(--color-primary-fg,#fff);cursor:pointer}}
.btn.sec{{background:transparent;color:var(--color-text);border-color:var(--color-border)}} .btn:disabled{{opacity:.45;cursor:not-allowed}}
.btn:focus-visible,input:focus-visible{{outline:3px solid var(--color-primary);outline-offset:2px}}
input{{font:inherit;padding:10px 12px;border-radius:var(--radius-control,8px);border:1px solid var(--color-border);background:var(--color-bg);color:var(--color-text)}}
input.err{{border-color:var(--color-danger,#d64545)}}
.card{{padding:20px;border-radius:var(--radius-card,12px);background:var(--color-surface);box-shadow:var(--shadow-card,none);max-width:360px}}
#bp{{position:sticky;top:0;background:var(--color-surface);padding:6px 10px;border-radius:6px;font-size:12px}}
@media (prefers-reduced-motion:no-preference){{.btn{{transition:transform .15s}} .btn:active{{transform:scale(.98)}}}}
</style></head><body>
<div class="row" style="justify-content:space-between"><h1 style="margin:0">디자인 토큰 미리보기</h1>
<button class="btn sec" onclick="document.documentElement.classList.toggle('dark')">라이트/다크 전환</button></div>
<p id="bp"></p>
<h2>색</h2><div class="grid">{sw or "<p>색 토큰 없음</p>"}</div>
<h2>글자 크기 — 반응형 3구간</h2><table><tr><th>토큰</th>{"".join(f"<th>{n}</th>" for n, _ in BP)}<th>현재 화면</th></tr>{rows or "<tr><td>text 토큰 없음</td></tr>"}</table>
<h2>서체</h2>{fonts or "<p>font 토큰 없음</p>"}
<h2>반경 · 그림자</h2><div class="grid">{rad}{sha}</div>
<h2>컴포넌트 상태</h2>
<div class="row"><button class="btn">기본</button><button class="btn sec">보조</button><button class="btn" disabled>비활성</button>
<input placeholder="입력"><input class="err" value="오류 상태"></div>
<div class="card" style="margin-top:16px"><b style="font-size:var(--text-h2)">카드 제목</b><p>본문 텍스트입니다. 금액 <span style="font-family:var(--font-mono)">12,900원</span></p>
<p style="font-size:var(--text-caption);color:var(--color-text-muted)">캡션 · 보조 설명</p></div>
<script>const f=()=>{{const w=innerWidth;document.getElementById('bp').textContent='현재 폭 '+w+'px → '+(w<768?'모바일':w<1200?'태블릿':'데스크톱')}};addEventListener('resize',f);f()</script>
</body></html>"""
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, "w", encoding="utf-8").write(page)
    print(f"✅ {out} — 색 {len(g['color'])} · 글자 {len(g['text'])} · 서체 {len(g['font'])} · 반경 {len(g['radius'])} · 그림자 {len(g['shadow'])} · 다크 {len(dark)} · 반응형 구간 {len(resp)}")
    if md:
        lines = ["# 디자인 토큰 (자동 생성 파일 — 직접 고치지 말 것. tokens.css 수정 → design-preview --md 재실행. 브리프·설명은 DESIGN.md에)", "",
                 "## 색", "| 토큰 | 라이트 | 다크 |", "|---|---|---|"]
        lines += [f"| `{k}` | `{v}` | `{dark.get(k, '—')}` |" for k, v in g["color"]]
        lines += ["", "## 글자 크기 (반응형 3구간)", "| 토큰 | " + " | ".join(n for n, _ in BP) + " |", "|---|---|---|---|"]
        lines += [f"| `{k}` | " + " | ".join(text_at(k, base, resp, w) for _, w in BP) + " |" for k, _ in g["text"]]
        lines += ["", "## 서체 · 반경 · 그림자 · 기타", "| 토큰 | 값 |", "|---|---|"]
        lines += [f"| `{k}` | `{v}` |" for key in ("font", "radius", "shadow", "space", "etc") for k, v in g[key]]
        os.makedirs(os.path.dirname(os.path.abspath(md)), exist_ok=True)
        open(md, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        print(f"✅ {md}")
    missing = [k for k, _ in g["text"] if not any(k in d for d in resp.values())]
    if g["text"] and missing:
        print(f"⚠️ 반응형 값이 없는 글자 토큰: {', '.join(missing)} — 3구간 폰트 크기를 지정하세요")

# ---------- 대비 검사 (WCAG 2.x) ----------
def _resolve(v, toks, depth=0):
    m = re.fullmatch(r"\s*var\(\s*(--[\w-]+)\s*(?:,\s*([^)]+))?\)\s*", v or "")
    if m and depth < 8:
        return _resolve(toks.get(m.group(1), m.group(2) or ""), toks, depth + 1)
    return (v or "").strip()

def to_linear_rgb(v):
    """CSS 색 → 선형 sRGB (0~1) 튜플. hex · rgb() · oklch() 지원, 그 밖은 None."""
    v = v.strip().lower()
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    m = re.fullmatch(r"#([0-9a-f]{3,8})", v)
    if m:
        h = m.group(1)
        if len(h) in (3, 4): h = "".join(ch * 2 for ch in h[:3])
        return tuple(lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    m = re.fullmatch(r"rgba?\(\s*([\d.]+%?)[\s,]+([\d.]+%?)[\s,]+([\d.]+%?).*\)", v)
    if m:
        return tuple(lin((float(x[:-1]) / 100) if x.endswith("%") else float(x) / 255) for x in m.groups())
    m = re.fullmatch(r"oklch\(\s*([\d.]+%?)\s+([\d.]+)\s+([\d.]+)(?:deg)?.*\)", v)
    if m:
        import math
        L = float(m.group(1)[:-1]) / 100 if m.group(1).endswith("%") else float(m.group(1))
        C, H = float(m.group(2)), math.radians(float(m.group(3)))
        a, b = C * math.cos(H), C * math.sin(H)
        l_, m_, s_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, (L - 0.1055613458 * a - 0.0638541728 * b) ** 3, \
                     (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
        rgb = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
               -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
               -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
        return tuple(min(1.0, max(0.0, c)) for c in rgb)
    return None

def contrast(fg, bg):
    a, b = to_linear_rgb(fg), to_linear_rgb(bg)
    if not a or not b: return None
    y = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    hi, lo = sorted((y(a), y(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)

def contrast_pairs(toks):
    """검사할 (전경, 배경, 기준, 용도) 목록 — 토큰 이름 규칙으로 자동 구성."""
    has = lambda k: k in toks
    bgs = [k for k in ("--color-bg", "--color-background", "--color-surface", "--color-card") if has(k)]
    texts = [k for k in ("--color-text", "--color-foreground", "--color-text-muted", "--color-muted-foreground") if has(k)]
    pairs = [(t, b, 4.5, "본문 글자") for t in texts for b in bgs]
    for k in toks:
        if k.endswith(("-fg", "-foreground")) and k not in texts:
            base = k.rsplit("-", 1)[0] if k.endswith("-fg") else k[: -len("-foreground")]
            if has(base): pairs.append((k, base, 4.5, "버튼·배지 글자"))
    for s in ("--color-primary", "--color-danger", "--color-success", "--color-warning", "--color-info"):
        if has(s) and bgs: pairs.append((s, bgs[0], 3.0, "아이콘·경계(글자로 쓰면 4.5 필요)"))
    if has("--color-input") and bgs:  # 입력창 경계는 3:1 필요, --color-border(장식용 구분선)는 기준 없음
        pairs += [("--color-input", b, 3.0, "입력창·체크박스 경계") for b in bgs]
    return pairs

def check_contrast(base, dark):
    rows, fails = [], 0
    for mode, toks in (("라이트", base), ("다크", {**base, **dark})):
        if mode == "다크" and not dark: continue
        for fg, bg, need, use in contrast_pairs(toks):
            r = contrast(_resolve(toks[fg], toks), _resolve(toks[bg], toks))
            ok = r is not None and r >= need
            if r is not None and not ok: fails += 1
            rows.append((mode, fg, bg, r, need, use, ok))
    print("■ 대비 검사 (WCAG 2.x — 본문 4.5:1, 아이콘·경계 3:1)")
    print("  | 모드 | 전경 | 배경 | 대비 | 기준 | 용도 | 결과 |\n  |---|---|---|---|---|---|---|")
    for mode, fg, bg, r, need, use, ok in rows:
        print(f"  | {mode} | `{fg}` | `{bg}` | {'?' if r is None else f'{r:.2f}'} | {need} | {use} | "
              f"{'⚠️ 색 형식 해석 불가' if r is None else '✅' if ok else '❌'} |")
    print(f"■ {'대비 실패 ' + str(fails) + '건 → 토큰 값만 고친 뒤 다시 실행' if fails else '대비 통과 ✅'}")
    return fails

def scan_hardcoded(root):
    """컴포넌트에 직접 쓴 색·px — 토큰 우회 탐지."""
    pat = [(re.compile(r"#[0-9a-fA-F]{3,8}\b"), "hex 색"), (re.compile(r"\[(?:#|\d+(?:\.\d+)?px)"), "Tailwind 임의값"),
           (re.compile(r"Color\(0x[0-9a-fA-F]{8}\)"), "Flutter Color 직접"), (re.compile(r"(?<![\w-])\d+px\b"), "px 직접")]
    exts = (".tsx", ".jsx", ".ts", ".js", ".vue", ".svelte", ".dart", ".css", ".scss")
    hits = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ("node_modules", ".next", "dist", "build", ".dart_tool")]
        for f in files:
            if not f.endswith(exts) or f.startswith("tokens"): continue
            p = os.path.join(d, f)
            for i, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
                if line.lstrip().startswith(("//", "/*", "*", "@import", "--")): continue
                for rx, what in pat:
                    if rx.search(line): hits.append((os.path.relpath(p, root).replace("\\", "/"), i, what, line.strip()[:70])); break
    print(f"■ 토큰 우회 검사 ({root}): {len(hits)}건")
    for f, i, what, s in hits[:15]: print(f"  ❌ {f}:{i} {what} — {s}")
    if len(hits) > 15: print(f"  … 외 {len(hits) - 15}건")
    return len(hits)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tokens", nargs="?")
    ap.add_argument("-o", "--out", default="design/preview.html")
    ap.add_argument("--md")
    ap.add_argument("--init", metavar="TOKENS_CSS")
    ap.add_argument("--check", action="store_true", help="색 대비(WCAG) 검사만 출력")
    ap.add_argument("--scan", metavar="DIR", help="컴포넌트 폴더에서 hex·px 직접 사용 탐지")
    a = ap.parse_args()
    if a.scan and not a.tokens and not a.check:
        scan_hardcoded(a.scan); return
    if a.check:
        if not a.tokens: ap.error("tokens.css 경로가 필요합니다")
        base, dark, _ = parse(open(a.tokens, encoding="utf-8").read())
        if not base: sys.exit("토큰을 찾지 못했습니다 (@theme / :root 의 --변수)")
        check_contrast(base, dark)
        if a.scan: scan_hardcoded(a.scan)
        return
    if a.init:
        if os.path.exists(a.init): sys.exit(f"이미 있음: {a.init} (덮어쓰지 않음)")
        os.makedirs(os.path.dirname(os.path.abspath(a.init)), exist_ok=True)
        open(a.init, "w", encoding="utf-8").write(STARTER); print(f"✅ 시작 토큰 생성: {a.init}"); return
    if not a.tokens: ap.error("tokens.css 경로가 필요합니다")
    build(a.tokens, a.out, a.md)

if __name__ == "__main__":
    main()
