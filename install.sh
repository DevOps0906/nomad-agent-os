#!/usr/bin/env bash
# NOMAD Agent OS 설치 (macOS · Linux · Windows Git Bash)
#   bash install.sh                 전역 설치 (~/.claude) — 모든 프로젝트에서 같은 팀 사용
#   bash install.sh init <프로젝트>  프로젝트에 AGENTS.md · CLAUDE.md · rules · tasks 템플릿 적용(기존 파일 보존·병합)
#   옵션: --no-path (PATH 등록 안 함)  --codex (Codex CLI 전역 AGENTS.md에도 CORE 규칙 추가)
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
CL="$HOME/.claude"; TS=$(date +%Y%m%d-%H%M%S); BK="$CL/.nomad-backup/$TS"
PY=""
for c in python3 python; do "$c" -c "import sys; sys.exit(sys.version_info < (3, 8))" >/dev/null 2>&1 && { PY=$c; break; }; done
if [ -z "$PY" ] && command -v py >/dev/null 2>&1 && py -3 -c 1 >/dev/null 2>&1; then PY="py -3"; fi
[ -n "$PY" ] || { echo "❌ Python 3.8+ 가 필요합니다 (Windows: python.org 설치본 + 설정 > 앱 실행 별칭에서 python3 스텁 끄기)"; exit 1; }
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

# JSON 병합 도우미: settings.json 에 훅 병합(mode=hooks) 또는 permissions.deny 병합(mode=deny)
merge_json() { # merge_json <대상> <추가분> <mode> <백업폴더>
  $PY - "$@" <<'PYEOF'
import json, os, shutil, sys
dst, add, mode, bk = sys.argv[1:5]
cur = {}
if os.path.exists(dst):
    os.makedirs(bk, exist_ok=True); shutil.copy(dst, os.path.join(bk, os.path.basename(dst)))
    try:
        with open(dst, encoding="utf-8-sig") as f: cur = json.load(f)   # BOM 허용
    except Exception as e:
        print(f"  ⚠️ {dst} 를 읽지 못해 병합을 건너뜀({e}) — 수동으로 {add} 내용을 합치세요"); sys.exit(0)
with open(add, encoding="utf-8") as f: new = json.load(f)
changed = False
if mode == "hooks":
    hooks = cur.setdefault("hooks", {})
    for ev, groups in new["hooks"].items():
        lst = hooks.setdefault(ev, [])
        have = {h.get("command") for g in lst if isinstance(g, dict) for h in g.get("hooks", []) if isinstance(h, dict)}
        for g in groups:
            if not any(h.get("command") in have for h in g["hooks"]): lst.append(g); changed = True
else:
    deny = cur.setdefault("permissions", {}).setdefault("deny", [])
    for rule in new.get("permissions", {}).get("deny", []):
        if rule not in deny: deny.append(rule); changed = True
    if "model" in new and "model" not in cur: cur["model"] = new["model"]; changed = True
if changed:
    with open(dst, "w", encoding="utf-8") as f: json.dump(cur, f, ensure_ascii=False, indent=2)
print(f"  {'+ 병합' if changed else '· 이미 적용됨'}  {dst} ({mode})")
PYEOF
}

append_line() { # append_line <파일> <줄> : 마지막 줄바꿈을 보장하고 없을 때만 추가
  touch "$1"; grep -qxF "$2" "$1" && return 1
  [ -s "$1" ] && [ "$(tail -c1 "$1" | od -An -c | tr -d ' ')" != '\n' ] && printf '\n' >> "$1"
  printf '%s\n' "$2" >> "$1"; return 0
}

if [ "${1:-}" = "init" ]; then
  P="${2:-.}"; mkdir -p "$P"; P="$(cd "$P" && pwd)"; PBK="$P/.nomad/backup-$TS"
  echo "■ 프로젝트 템플릿 → $P (기존 파일은 보존, 필요한 줄만 병합)"
  (cd "$SRC/project-template" && find . -type f ! -name .gitignore) | while read -r f; do
    if [ -e "$P/$f" ]; then
      case "$f" in
        ./CLAUDE.md)
          if grep -qxF "@AGENTS.md" "$P/CLAUDE.md"; then echo "  · 유지  CLAUDE.md"
          else mkdir -p "$PBK"; cp "$P/CLAUDE.md" "$PBK/"; { echo "@AGENTS.md"; echo; cat "$PBK/CLAUDE.md"; } > "$P/CLAUDE.md"; echo "  + CLAUDE.md 맨 위에 @AGENTS.md 추가 (백업 .nomad/)"; fi ;;
        ./.claude/settings.json) merge_json "$P/.claude/settings.json" "$SRC/project-template/.claude/settings.json" deny "$PBK" ;;
        *) echo "  · 유지  ${f#./}" ;;
      esac
    else mkdir -p "$P/$(dirname "$f")"; cp "$SRC/project-template/$f" "$P/$f"; echo "  + 생성  ${f#./}"; fi
  done
  while read -r line; do append_line "$P/.gitignore" "$line" && echo "  + .gitignore: $line"; done < "$SRC/project-template/.gitignore"
  echo "■ 다음: AGENTS.md 의 <프로젝트명>·스택·명령·고유 규칙을 채우고 \`claude\` → /plan 또는 /next"
  exit 0
fi

echo "■ NOMAD Agent OS 전역 설치 → $CL"
mkdir -p "$CL"
# 1) 설정 병합을 먼저(실패해도 반쯤 설치된 상태가 남지 않게)
merge_json "$CL/settings.json" "$SRC/global/settings.nomad.json" hooks "$BK"

# 2) 파일 복사: 같은 이름이 있으면 백업 후 교체
copy_dir() {
  local s="$1" d="$2"; mkdir -p "$d"
  for item in "$s"/* "$s"/.[!.]*; do
    [ -e "$item" ] || continue
    local name; name=$(basename "$item")
    if [ -e "$d/$name" ]; then mkdir -p "$BK/$(basename "$d")"; cp -R "$d/$name" "$BK/$(basename "$d")/"; rm -rf "${d:?}/$name"; fi
    cp -R "$item" "$d/"
  done
}
copy_dir "$SRC/global/agents" "$CL/agents"
copy_dir "$SRC/global/skills" "$CL/skills"
copy_dir "$SRC/global/commands" "$CL/commands"
copy_dir "$SRC/global/nomad" "$CL/nomad"
cp "$SRC/docs/ARCHITECTURE.md" "$CL/nomad/ARCHITECTURE.md"
# Windows에서 CRLF로 받은 경우 스크립트가 깨지지 않게 줄바꿈 정리 후 실행 권한
$PY -c "import sys
for p in [x for x in sys.argv[1:] if __import__('os').path.isfile(x)]:
    b = open(p, 'rb').read()
    if b'\r\n' in b: open(p, 'wb').write(b.replace(b'\r\n', b'\n'))" "$CL/nomad/bin/"* "$CL/nomad/bin/py/"*.py || echo "  ⚠️ 줄바꿈 정리 실패"
chmod +x "$CL/nomad/bin/"* 2>/dev/null || true

# 3) 전역 CLAUDE.md: 없으면 생성, 있으면 import 한 줄만 맨 위에(기존 내용 보존)
if [ ! -f "$CL/CLAUDE.md" ]; then cp "$SRC/global/CLAUDE.md" "$CL/CLAUDE.md"; echo "  + CLAUDE.md 생성"
elif ! grep -qxF "@nomad/TEAM.md" "$CL/CLAUDE.md"; then
  mkdir -p "$BK"; cp "$CL/CLAUDE.md" "$BK/CLAUDE.md"
  { echo "@nomad/TEAM.md"; echo; cat "$BK/CLAUDE.md"; } > "$CL/CLAUDE.md"; echo "  + 기존 CLAUDE.md 맨 위에 @nomad/TEAM.md 추가"
else echo "  · 유지  CLAUDE.md (@nomad/TEAM.md 있음)"; fi

# 4) PATH
if [[ " $* " != *" --no-path "* ]]; then
  RC="$HOME/.bashrc"; { [ -n "${ZSH_VERSION:-}" ] || [ "$(basename "${SHELL:-}")" = "zsh" ]; } && RC="$HOME/.zshrc"
  append_line "$RC" 'export PATH="$HOME/.claude/nomad/bin:$PATH"' && echo "  + PATH 등록 ($RC) — 새 터미널부터 q·delta·codemap 이름만으로 실행" || true
fi

# 5) Codex CLI (선택)
if [[ " $* " == *" --codex "* ]]; then
  CX="$HOME/.codex/AGENTS.md"; mkdir -p "$HOME/.codex"
  if ! grep -q "NOMAD CORE" "$CX" 2>/dev/null; then { echo; cat "$CL/nomad/CORE.md"; } >> "$CX"; echo "  + Codex 전역 AGENTS.md 에 CORE 규칙 추가"; fi
fi

echo "■ 완료. 확인: ~/.claude/nomad/bin/token-audit <프로젝트>   ·   Claude Code에서 /agents 로 팀 10명 확인"
[ -d "$BK" ] && echo "  (교체·병합 전 원본 백업: $BK)"
exit 0
