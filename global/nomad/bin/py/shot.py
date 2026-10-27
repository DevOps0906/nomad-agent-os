#!/usr/bin/env python3
"""shot — 화면을 3구간(+와이드)으로 스크린샷 찍는다. 설치 없이 PC의 Edge·Chrome 헤드리스를 쓴다 (모델 토큰 0).

사용: shot <파일.html | 폴더 | URL> [-o design/shots] [--sizes 375,768,1280,1440] [--height 1600] [--dark]
  폴더를 주면 그 안의 *.html(index.html 제외)을 모두 찍는다 → design/wireframes 를 통째로.
  URL 예: shot http://localhost:3000/dashboard  (개발 서버 화면을 구간별로 확인)
브라우저 지정: NOMAD_BROWSER=<경로>. 못 찾으면 안내만 하고 실패로 끝내지 않는다.
"""
import argparse, glob, os, shutil, subprocess, sys, tempfile
from pathlib import Path

MIN_WIN = 520  # 헤드리스 창 최소 폭(여유 포함)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def find_browser():
    if os.environ.get("NOMAD_BROWSER") and os.path.exists(os.environ["NOMAD_BROWSER"]): return os.environ["NOMAD_BROWSER"]
    pf, pf86, la = os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""), os.environ.get("LOCALAPPDATA", "")
    cands = [os.path.join(pf, r"Google\Chrome\Application\chrome.exe"), os.path.join(pf86, r"Google\Chrome\Application\chrome.exe"),
             os.path.join(la, r"Google\Chrome\Application\chrome.exe"), os.path.join(pf86, r"Microsoft\Edge\Application\msedge.exe"),
             os.path.join(pf, r"Microsoft\Edge\Application\msedge.exe"),
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    cands += sorted(glob.glob(os.path.join(la, "ms-playwright", "chromium-*", "chrome-win*", "chrome.exe")), reverse=True)
    cands += sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")), reverse=True)
    for c in cands:
        if c and os.path.exists(c): return c
    for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge", "chrome"):
        p = shutil.which(n)
        if p: return p
    return None


def targets(t):
    if t.startswith(("http://", "https://", "file://")): return [(t, Path(t.rstrip("/")).name or "page")]
    p = Path(t)
    if p.is_dir():
        return [(f.resolve().as_uri(), f.stem) for f in sorted(p.glob("*.html")) if f.name != "index.html"]
    if p.is_file(): return [(p.resolve().as_uri(), p.stem)]
    return []


def main():
    ap = argparse.ArgumentParser(prog="shot")
    ap.add_argument("target"); ap.add_argument("-o", "--out", default=os.path.join("design", "shots"))
    ap.add_argument("--sizes", default="375,768,1280,1440"); ap.add_argument("--height", type=int, default=1600)
    ap.add_argument("--dark", action="store_true", help="와이어프레임을 다크 모드로 (?dark)")
    a = ap.parse_args()
    exe = find_browser()
    if not exe:
        print("⚠️ Chrome·Edge 를 찾지 못했습니다 — 설치하거나 NOMAD_BROWSER=<브라우저 경로> 지정 (스크린샷 생략)"); return 0
    pages = targets(a.target)
    if not pages:
        print(f"❌ 찍을 대상이 없습니다: {a.target}"); return 2
    os.makedirs(a.out, exist_ok=True)
    sizes = [int(x) for x in a.sizes.split(",") if x.strip()]
    made, failed = [], []
    with tempfile.TemporaryDirectory() as prof:
        for url, name in pages:
            if a.dark: url += ("&" if "?" in url else "?") + "dark"
            for w in sizes:
                out = os.path.abspath(os.path.join(a.out, f"{name}-{w}{'-dark' if a.dark else ''}.png"))
                # 헤드리스 Chrome 창은 약 500px 보다 좁아지지 않는다 → 좁은 구간은 정확한 폭의 iframe 에 담아 찍는다
                # (페이지의 미디어 쿼리는 iframe 폭 기준으로 적용됨, 오른쪽은 회색 여백)
                page, win = url, w
                if w < MIN_WIN:
                    wrap = os.path.join(prof, f"wrap-{w}.html")
                    Path(wrap).write_text(f'<!doctype html><html><body style="margin:0;background:#9aa0a6">'
                                          f'<iframe src="{url}" style="display:block;width:{w}px;height:{a.height}px;border:0;background:#fff">'
                                          f'</iframe></body></html>', encoding="utf-8")
                    page, win = Path(wrap).as_uri(), MIN_WIN
                cmd = [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
                       "--allow-file-access-from-files", f"--user-data-dir={prof}", f"--window-size={win},{a.height}",
                       "--virtual-time-budget=3000", f"--screenshot={out}", page]
                try:
                    subprocess.run(cmd, capture_output=True, timeout=60)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                (made if os.path.exists(out) and os.path.getsize(out) > 0 else failed).append(out)
    print(f"■ shot ({Path(exe).name}): {len(made)}장 → {a.out}" + (f" · 실패 {len(failed)}" if failed else ""))
    for m in made[:8]: print(f"  {os.path.relpath(m)}")
    if len(made) > 8: print(f"  … 외 {len(made) - 8}장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
