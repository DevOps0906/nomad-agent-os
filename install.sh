#!/usr/bin/env bash
# NOMAD Agent OS 설치 (macOS · Linux · Windows Git Bash)
#   bash install.sh                 전역 설치 (~/.claude) — 모든 프로젝트에서 같은 팀 사용
#   bash install.sh init <프로젝트> [--name 이름]  프로젝트에 AGENTS.md · CLAUDE.md · rules · tasks · Codex·Gemini 설정 적용(기존 파일 보존·병합)
#                                    이름 생략 시 폴더명. NOMAD 저장소 안의 경로는 거부
#   옵션: --no-path (PATH 등록 안 함)  --codex (ChatGPT Codex 전역 ~/.codex/AGENTS.md에 CORE 추가)
#         --gemini (Gemini CLI 전역 ~/.gemini/GEMINI.md에 CORE 추가)
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
  shift; P="."; NAME=""
  while [ $# -gt 0 ]; do case "$1" in --name) shift; NAME="${1:-}" ;; *) P="$1" ;; esac; shift; done
  # 안전장치: NOMAD 저장소 자체나 그 하위 폴더에는 적용하지 않는다(원본 저장소 오염 방지)
  low() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }   # Windows 대소문자 무시 비교
  inside_src() { case "$(low "$1")/" in "$(low "$SRC")/"*) return 0 ;; esac; return 1; }
  refuse() { rmdir "$1" 2>/dev/null || true; echo "❌ 대상 경로가 NOMAD 저장소($SRC) 안입니다: $1"
    echo "   프로젝트는 저장소 밖에 두세요. 예: bash $SRC/install.sh init ~/workspace/dev/<프로젝트명>"; exit 1; }
  case "$P" in /*|[A-Za-z]:*) PA="$P" ;; *) PA="$PWD/$P" ;; esac
  inside_src "$PA" && refuse "$PA"                          # 폴더를 만들기 전에 1차 검사
  mkdir -p "$P" && PA="$(cd "$P" && pwd)" || { echo "❌ 폴더를 만들 수 없습니다: $P"; exit 1; }
  inside_src "$PA" && refuse "$PA"                          # ../ 나 링크로 우회한 경우 2차 검사
  P="$PA"; PBK="$P/.nomad/backup-$TS"; NAME="${NAME:-$(basename "$P")}"
  NEW_AGENTS=0; [ -e "$P/AGENTS.md" ] || NEW_AGENTS=1
  echo "■ 프로젝트 템플릿 → $P (기존 파일은 보존, 필요한 줄만 병합)"
  (cd "$SRC/project-template" && find . -type f ! -name .gitignore ! -name .geminiignore) | while read -r f; do
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
  for ig in .gitignore .geminiignore; do   # 줄 단위 병합(없는 줄만 추가)
    while read -r line; do append_line "$P/$ig" "$line" && echo "  + $ig: $line"; done < "$SRC/project-template/$ig"
  done
  # 새로 만든 AGENTS.md 에만 프로젝트명 치환(기존 파일은 건드리지 않음). sed 대신 bash 치환이라 이름에 / & 가 있어도 안전
  if [ "$NEW_AGENTS" = 1 ]; then
    c="$(cat "$P/AGENTS.md")"; printf '%s\n' "${c//<프로젝트명>/"$NAME"}" > "$P/AGENTS.md"; echo "  + AGENTS.md 프로젝트명: $NAME"
  fi
  echo "■ 다음: AGENTS.md 의 스택·명령·고유 규칙을 채우고 \`claude\` → /plan 또는 /next"
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

# 5) 다른 AI 도구 전역 지시 파일에 CORE 추가 (선택): --codex = ChatGPT Codex, --gemini = Gemini CLI
add_core() { # add_core <전역 지시 파일> <도구 이름>
  mkdir -p "$(dirname "$1")"
  if grep -q "NOMAD CORE" "$1" 2>/dev/null; then echo "  · 유지  $1 ($2, CORE 있음)"
  else { [ -s "$1" ] && echo; cat "$CL/nomad/CORE.md"; } >> "$1"; echo "  + $2 전역 지시 파일에 CORE 규칙 추가 ($1)"; fi
}
[[ " $* " == *" --codex "* ]] && add_core "$HOME/.codex/AGENTS.md" "ChatGPT Codex"
[[ " $* " == *" --gemini "* ]] && add_core "$HOME/.gemini/GEMINI.md" "Gemini CLI"

echo "■ 완료. 확인: ~/.claude/nomad/bin/token-audit <프로젝트>   ·   Claude Code에서 /agents 로 팀 10명 확인"
[ -d "$BK" ] && echo "  (교체·병합 전 원본 백업: $BK)"
exit 0
