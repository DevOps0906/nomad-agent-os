#!/usr/bin/env python3
"""docs/GUIDE.md -> docs/guide/index.html (+ --pdf: NOMAD_GUIDE.pdf). 표준 라이브러리만 사용."""
import html, os, posixpath, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "GUIDE.md"
OUT = HERE / "index.html"
PDF = HERE / "NOMAD_GUIDE.pdf"
REPOS = [
    ("nomad-agent-os", "https://github.com/DevOps0906/nomad-agent-os"),
    ("nomad-blueprints-module", "https://github.com/DevOps0906/nomad-blueprints-module"),
    ("nomad-secure-pack-module", "https://github.com/DevOps0906/nomad-secure-pack-module"),
    ("nomad-docker-module", "https://github.com/DevOps0906/nomad-docker-module"),
]
esc = html.escape
ITEM = re.compile(r"([-*]|\d+\.)\s+(.*)")
REPO_URL = "https://github.com/DevOps0906/nomad-agent-os/blob/main/"


def link(url):
    """GUIDE.md의 상대 링크(docs/ 기준)는 웹·PDF에서 열리도록 GitHub 주소로 바꾼다."""
    if re.match(r"(https?:|mailto:|#)", url):
        return url
    return REPO_URL + posixpath.normpath("docs/" + url)


def inline(text):
    codes = []

    def keep(m):
        codes.append("<code>%s</code>" % esc(m.group(1)))
        return "\x00%d\x00" % (len(codes) - 1)

    t = re.sub(r"`([^`]+)`", keep, text)
    t = esc(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
               lambda m: '<a href="%s">%s</a>' % (link(m.group(2)).replace('"', "%22"), m.group(1)), t)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], t)


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells, cur, tick, i = [], "", False, 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if c == "`":
            tick = not tick
        if c == "|" and not tick:
            cells.append(cur.strip())
            cur = ""
        else:
            cur += c
        i += 1
    cells.append(cur.strip())
    return cells


def convert(md):
    lines = md.splitlines()
    out, toc = [], []  # toc: (level, id, title, chapter no)
    title, date = "NOMAD Agent OS 사용 가이드", ""
    m0 = re.search(r"작성일\s*([\d-]+)", md)
    if m0:
        date = m0.group(1)
    i, n, ch, sub = 0, len(lines), 0, 0
    para = []

    def flush():
        if para:
            out.append("<p>%s</p>" % inline(" ".join(para)))
            para.clear()

    while i < n:
        s = lines[i].strip()
        if s.startswith("```"):
            flush()
            lang = s[3:].strip()
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append('<div class="code"><button type="button" class="copy" aria-label="코드 복사">복사</button>'
                       '<pre><code%s>%s</code></pre></div>'
                       % (' data-lang="%s"' % esc(lang) if lang else "", esc("\n".join(buf))))
            continue
        if not s:
            flush()
            i += 1
            continue
        if re.fullmatch(r"-{3,}", s):
            flush()
            out.append("<hr>")
            i += 1
            continue
        m = re.match(r"(#{1,3})\s+(.*)", s)
        if m:
            flush()
            lv, tx = len(m.group(1)), m.group(2).strip()
            if lv == 1:
                title = tx
            elif lv == 2:
                ch += 1
                sub = 0
                hid = "ch%d" % ch
                toc.append((2, hid, tx, ch))
                out.append('<h2 id="%s">%s</h2>' % (hid, inline(tx)))
            else:
                sub += 1
                hid = "ch%d-%d" % (ch, sub)
                toc.append((3, hid, tx, ch))
                out.append('<h3 id="%s">%s</h3>' % (hid, inline(tx)))
            i += 1
            continue
        if s.startswith("|") and i + 1 < n and re.match(r"\|?\s*:?-{2,}", lines[i + 1].strip()):
            flush()
            head = split_row(s)
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            h = "".join('<th scope="col">%s</th>' % inline(c) for c in head)
            b = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in rows)
            out.append('<div class="tbl" tabindex="0" role="region" aria-label="표">'
                       '<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (h, b))
            continue
        if s.startswith(">"):
            flush()
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote><p>%s</p></blockquote>" % inline(" ".join(buf)))
            continue
        m = ITEM.match(s)
        if m:
            flush()
            ordered = m.group(1)[0].isdigit()
            items = []
            while i < n:
                cur = lines[i].strip()
                mm = ITEM.match(cur)
                if cur and mm and mm.group(1)[0].isdigit() == ordered:
                    items.append(mm.group(2))
                    i += 1
                elif lines[i].startswith("  ") and cur and items and not mm:
                    items[-1] += " " + cur
                    i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            out.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % inline(x) for x in items), tag))
            continue
        para.append(s)
        i += 1
    flush()
    return title, date, out, toc


CSS = r"""
:root{
 --bg:#ffffff;--surface:#f5f6f8;--text:#1b1f24;--muted:#4a5460;--border:#d0d7de;
 --accent:#0b57d0;--accent-bg:#e3edfd;--code-bg:#f0f2f5;--pre-bg:#16191d;--pre-text:#e6e9ee;
 --focus:#b45309;--gnb-w:240px;
 --fs-body:16px;--fs-h1:28px;--fs-h2:22px;--fs-h3:18px;--fs-code:13px;
}
@media (prefers-color-scheme:dark){:root{
 --bg:#0f1318;--surface:#171c23;--text:#e6e9ee;--muted:#a9b3bf;--border:#2e3641;
 --accent:#8ab4f8;--accent-bg:#1f2d46;--code-bg:#1d232b;--pre-bg:#0a0d11;--pre-text:#e6e9ee;--focus:#fbbf24;}}
@media (min-width:768px){:root{--fs-body:16px;--fs-h1:32px;--fs-h2:24px;--fs-h3:19px;--fs-code:13.5px}}
@media (min-width:1200px){:root{--gnb-w:280px;--fs-body:17px;--fs-h1:36px;--fs-h2:28px;--fs-h3:21px;--fs-code:14px}}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:72px;background:var(--bg)}
body{margin:0;background:var(--bg);color:var(--text);font:var(--fs-body)/1.75 -apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif}
a{color:var(--accent)}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
.skip{position:absolute;left:8px;top:-60px;background:#0b57d0;color:#fff;padding:8px 14px;border-radius:6px;z-index:100}
.skip:focus{top:8px}
.topbar{position:sticky;top:0;z-index:30;display:flex;align-items:center;gap:12px;padding:10px 16px;background:var(--bg);border-bottom:1px solid var(--border)}
.menu-btn{display:inline-flex;align-items:center;gap:6px;background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:8px 12px;font:inherit;font-size:14px;cursor:pointer}
.topbar .t{font-weight:700;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gnb{position:fixed;top:0;left:0;bottom:0;width:min(86vw,320px);background:var(--surface);border-right:1px solid var(--border);overflow-y:auto;padding:16px 12px 32px;z-index:50;transform:translateX(-102%);transition:transform .2s;visibility:hidden}
.gnb.open{transform:none;visibility:visible}
.scrim{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:40;display:none}
.scrim.open{display:block}
.gnb .gt{font-weight:700;font-size:15px;margin:0 4px 10px;display:flex;justify-content:space-between;align-items:center}
.gnb .close{background:none;border:1px solid var(--border);color:var(--text);border-radius:6px;padding:4px 10px;font:inherit;font-size:13px;cursor:pointer}
.search{width:100%;padding:9px 10px;margin-bottom:12px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);font:inherit;font-size:14px}
.gnb ul{list-style:none;margin:0;padding:0}
.gnb li{margin:0}
.gnb a{display:block;padding:6px 10px;border-radius:6px;color:var(--text);text-decoration:none;font-size:14px;line-height:1.45}
.gnb a:hover{background:var(--accent-bg)}
.gnb a.cur{background:var(--accent-bg);color:var(--accent);font-weight:700}
.gnb .subs{display:none;margin:0 0 4px 10px;border-left:2px solid var(--border)}
.gnb .ch.open>.subs,.gnb.filtering .subs{display:block}
.gnb .subs a{font-size:13px;color:var(--muted)}
.gnb .subs a.cur{color:var(--accent)}
.gnb .none{display:none;color:var(--muted);font-size:14px;padding:6px 10px}
.gnb.empty .none{display:block}
.content{padding:20px 16px 80px}
.inner{max-width:860px;margin:0 auto}
.hero h1{font-size:var(--fs-h1);line-height:1.3;margin:8px 0 6px}
.meta{color:var(--muted);font-size:14px;margin:0 0 10px}
.repos{display:flex;flex-wrap:wrap;gap:8px;list-style:none;margin:10px 0 24px;padding:0}
.repos a{display:inline-block;padding:5px 12px;border:1px solid var(--border);border-radius:999px;font-size:13px;text-decoration:none;background:var(--surface)}
.repos a:hover{background:var(--accent-bg)}
h2{font-size:var(--fs-h2);line-height:1.35;margin:56px 0 16px;padding-bottom:8px;border-bottom:2px solid var(--border)}
h3{font-size:var(--fs-h3);line-height:1.4;margin:32px 0 10px}
p{margin:12px 0}
ul,ol{padding-left:1.4em;margin:12px 0}
li{margin:4px 0}
hr{border:0;border-top:1px solid var(--border);margin:28px 0}
blockquote{margin:16px 0;padding:4px 16px;border-left:4px solid var(--accent);background:var(--surface);color:var(--muted)}
code{font-family:ui-monospace,Consolas,"Cascadia Mono",monospace;font-size:var(--fs-code);background:var(--code-bg);padding:.1em .35em;border-radius:4px;overflow-wrap:anywhere}
.code{position:relative;margin:16px 0}
.code pre{margin:0;padding:14px 16px;background:var(--pre-bg);color:var(--pre-text);border-radius:8px;overflow-x:auto;line-height:1.55}
.code pre code{background:none;padding:0;color:inherit;overflow-wrap:normal;white-space:pre}
.copy{position:absolute;top:6px;right:6px;background:#2b323b;color:#fff;border:1px solid #556070;border-radius:6px;padding:3px 10px;font:inherit;font-size:12px;cursor:pointer}
.copy:hover{background:#3a4450}
.tbl{overflow-x:auto;margin:16px 0;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:.92em}
th,td{word-break:keep-all;border:1px solid var(--border);padding:8px 10px;text-align:left;vertical-align:top}
th{background:var(--surface)}
.print-toc{display:none}
@media (min-width:768px){
 .topbar{display:none}
 .gnb{width:var(--gnb-w);transform:none;visibility:visible;transition:none}
 .gnb .close{display:none}
 .scrim{display:none!important}
 .content{margin-left:var(--gnb-w);padding:32px 32px 100px}
}
@media (min-width:1200px){.content{padding:40px 48px 120px}}
@media print{
 @page{size:A4;margin:16mm 14mm}
 :root{--bg:#fff;--surface:#f3f4f6;--text:#000;--muted:#333;--border:#999;--accent:#0b3d91;--code-bg:#eef0f3;--pre-bg:#f3f4f6;--pre-text:#000;--fs-body:10.5pt;--fs-h1:24pt;--fs-h2:17pt;--fs-h3:13pt;--fs-code:8.5pt}
 html,body{background:#fff;color:#000}
 body{line-height:1.6}
 .gnb,.scrim,.topbar,.skip,.copy,.search{display:none!important}
 .content{margin:0;padding:0}
 .inner{max-width:none}
 .hero{break-after:page;page-break-after:always}
 .print-toc{display:block}
 .print-toc ol{list-style:none;padding:0;font-size:12pt}
 .print-toc li{margin:6px 0}
 .print-toc a{text-decoration:none;color:#000}
 h2{break-before:page;page-break-before:always;margin-top:0}
 .print-toc h2{break-before:auto;page-break-before:auto}
 h2,h3{break-after:avoid;page-break-after:avoid}
 .tbl{overflow:visible}
 table,tr,pre,.code,blockquote{break-inside:avoid;page-break-inside:avoid}
 .code pre{overflow:visible;white-space:pre-wrap;word-break:break-all;border:1px solid #999}
 .code pre code{white-space:pre-wrap}
 a{color:#0b3d91}
 .content a[href^="http"]::after,.content a[href$=".md"]::after{content:" (" attr(href) ")";font-size:.85em;color:#333;overflow-wrap:anywhere}
 .repos a{border:0;padding:0;background:none}
 .repos{display:block}.repos li{margin:2px 0}
}
"""

JS = r"""
(function(){
 var gnb=document.getElementById('gnb'),scrim=document.getElementById('scrim'),mb=document.getElementById('menuBtn'),q=document.getElementById('q');
 function setOpen(o){gnb.classList.toggle('open',o);scrim.classList.toggle('open',o);mb.setAttribute('aria-expanded',o);if(o){q.focus()}else if(gnb.contains(document.activeElement)){mb.focus()}}
 mb.addEventListener('click',function(){setOpen(!gnb.classList.contains('open'))});
 scrim.addEventListener('click',function(){setOpen(false)});
 document.getElementById('gclose').addEventListener('click',function(){setOpen(false)});
 document.addEventListener('keydown',function(e){if(e.key==='Escape'&&gnb.classList.contains('open'))setOpen(false)});
 gnb.addEventListener('click',function(e){if(e.target.closest('a')&&window.innerWidth<768)setOpen(false)});
 var links={};[].forEach.call(gnb.querySelectorAll('a[href^="#"]'),function(a){links[a.getAttribute('href').slice(1)]=a});
 var heads=[].slice.call(document.querySelectorAll('h2[id],h3[id]'));
 function setCur(id){
  [].forEach.call(gnb.querySelectorAll('a.cur'),function(a){a.classList.remove('cur');a.removeAttribute('aria-current')});
  [].forEach.call(gnb.querySelectorAll('.ch.open'),function(l){l.classList.remove('open')});
  var a=links[id];if(!a)return;a.classList.add('cur');a.setAttribute('aria-current','true');
  var li=a.closest('.ch');if(li)li.classList.add('open');
  if(window.innerWidth>=768||gnb.classList.contains('open')){var r=a.getBoundingClientRect(),g=gnb.getBoundingClientRect();if(r.top<g.top+60||r.bottom>g.bottom-20)a.scrollIntoView({block:'center'})}
 }
 if('IntersectionObserver' in window){
  var vis={};
  var io=new IntersectionObserver(function(es){
   es.forEach(function(e){vis[e.target.id]=e.isIntersecting});
   for(var i=0;i<heads.length;i++){if(vis[heads[i].id]){setCur(heads[i].id);return}}
  },{rootMargin:'-60px 0px -70% 0px'});
  heads.forEach(function(h){io.observe(h)});
 }
 q.addEventListener('input',function(){
  var v=q.value.trim().toLowerCase(),any=false;
  gnb.classList.toggle('filtering',!!v);
  [].forEach.call(gnb.querySelectorAll('.ch'),function(ch){
   var hit=!v||ch.firstElementChild.textContent.toLowerCase().indexOf(v)>-1,sh=false;
   [].forEach.call(ch.querySelectorAll('.subs li'),function(s){var m=!v||hit||s.textContent.toLowerCase().indexOf(v)>-1;s.style.display=m?'':'none';if(m&&v&&!hit)sh=true});
   var show=hit||sh;ch.style.display=show?'':'none';if(show)any=true;
  });
  gnb.classList.toggle('empty',!any);
 });
 [].forEach.call(document.querySelectorAll('.copy'),function(b){
  b.addEventListener('click',function(){
   var t=b.parentNode.querySelector('code').textContent;
   function done(){b.textContent='복사됨';setTimeout(function(){b.textContent='복사'},1500)}
   function fb(){var ta=document.createElement('textarea');ta.value=t;ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();try{document.execCommand('copy');done()}catch(e){}document.body.removeChild(ta)}
   if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(t).then(done,fb)}else fb();
  });
 });
})();
"""


def build():
    title, date, body, toc = convert(SRC.read_text(encoding="utf-8"))
    nav, ptoc = [], []
    chs = [t for t in toc if t[0] == 2]
    for _, cid, ctitle, num in chs:
        subs = [t for t in toc if t[0] == 3 and t[3] == num]
        sub_html = ""
        if subs:
            sub_html = '<ul class="subs">%s</ul>' % "".join(
                '<li><a href="#%s">%s</a></li>' % (sid, esc(st)) for _, sid, st, _ in subs)
        nav.append('<li class="ch"><a href="#%s">%s</a>%s</li>' % (cid, esc(ctitle), sub_html))
        ptoc.append('<li><a href="#%s">%s</a></li>' % (cid, esc(ctitle)))
    repos = "".join('<li><a href="%s">%s</a></li>' % (u, n) for n, u in REPOS)
    doc = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{esc(title)}</title>
<style>{CSS}</style></head>
<body>
<a class="skip" href="#main">본문 바로가기</a>
<div class="topbar"><button type="button" class="menu-btn" id="menuBtn" aria-controls="gnb" aria-expanded="false">&#9776; 메뉴</button><span class="t">{esc(title)}</span></div>
<div class="scrim" id="scrim"></div>
<nav class="gnb" id="gnb" aria-label="가이드 목차">
<div class="gt"><span>목차</span><button type="button" class="close" id="gclose">닫기</button></div>
<input class="search" id="q" type="search" placeholder="메뉴 검색" aria-label="메뉴 검색" autocomplete="off">
<ul>{"".join(nav)}</ul>
<p class="none">일치하는 항목이 없습니다.</p>
</nav>
<main class="content" id="main" tabindex="-1"><div class="inner">
<header class="hero">
<h1>{esc(title)}</h1>
<ul class="repos" aria-label="GitHub 레포지토리">{repos}</ul>
<section class="print-toc" aria-label="인쇄용 목차"><h2>목차</h2><ol>{"".join(ptoc)}</ol></section>
</header>
{chr(10).join(body)}
</div></main>
<script>{JS}</script>
</body></html>
"""
    OUT.write_text(doc, encoding="utf-8")
    print("wrote", OUT, "(chapters: %d)" % len(chs))


def pdf():
    cands = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
    exe = (next((c for c in cands if os.path.exists(c)), None)
           or shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("msedge"))
    if not exe:
        sys.exit("Chrome/Edge를 찾지 못했습니다.")
    cmd = [exe, "--headless", "--disable-gpu", "--no-pdf-header-footer",
           "--print-to-pdf=" + str(PDF), OUT.as_uri()]
    subprocess.run(cmd, check=True, timeout=180, capture_output=True)
    if not PDF.exists():
        sys.exit("PDF 생성 실패")
    print("wrote", PDF, PDF.stat().st_size, "bytes")


if __name__ == "__main__":
    build()
    if "--pdf" in sys.argv:
        pdf()
