#!/usr/bin/env python3
"""sql2erd — SQL 마이그레이션(CREATE TABLE · REFERENCES · ALTER TABLE ... FOREIGN KEY)을 읽어
Mermaid erDiagram을 만든다. 모델이 ERD를 손으로 그리지 않게 해 토큰을 0으로 만든다.

사용: sql2erd <파일 또는 폴더...> [-o out.mmd] [--schema kiosk] [--match "^video_"] [--no-columns] [--max-cols 12]
테이블이 25개를 넘으면 --match 로 영역별로 나눠 여러 장을 만든다(한 장에 다 넣지 않는다).
"""
import argparse, os, re, sys

try:  # 한국어 Windows(cp949) 콘솔에서도 이모지·한글 출력이 죽지 않게
    sys.stdout.reconfigure(encoding="utf-8", errors="replace"); sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def read_sql(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                files += [os.path.join(root, n) for n in names if n.endswith(".sql")]
        elif p.endswith(".sql"):
            files.append(p)
    files.sort()
    text = ""
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            text += "\n" + fh.read()
    return re.sub(r"--[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S)), files

def split_top(body):
    parts, depth, cur = [], 0, ""
    for ch in body:
        if ch == "(": depth += 1
        elif ch == ")": depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur.strip()); cur = ""
        else:
            cur += ch
    if cur.strip(): parts.append(cur.strip())
    return parts

def find_block(text, start):
    depth, i = 0, start
    while i < len(text):
        if text[i] == "(": depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0: return text[start + 1:i]
        i += 1
    return text[start + 1:]

def short(name):
    return name.replace('"', "").split(".")[-1]

def ident(name):
    return re.sub(r"[^A-Za-z0-9_]", "_", short(name))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("-o", "--out")
    ap.add_argument("--schema", help="이 스키마의 테이블만 (예: public, kiosk)")
    ap.add_argument("--match", help="테이블 이름 정규식 (영역별 분할용, 예: ^video_)")
    ap.add_argument("--no-columns", action="store_true")
    ap.add_argument("--max-cols", type=int, default=12)
    a = ap.parse_args()
    text, files = read_sql(a.paths)
    if not files:
        sys.exit("SQL 파일이 없습니다: " + " ".join(a.paths))
    tables, rels = {}, []
    for m in re.finditer(r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w\".]+)\s*\(", text, re.I):
        full = m.group(1).replace('"', "")
        if a.schema and "." in full and full.split(".")[0] != a.schema:
            continue
        if a.schema and "." not in full and a.schema != "public":
            continue
        t = short(full); cols = []
        if a.match and not re.search(a.match, t):
            continue
        pk_cols = set()
        for part in split_top(find_block(text, m.end() - 1)):
            low = part.lower()
            if low.startswith(("primary key", "constraint", "unique", "check", "foreign key", "exclude")):
                pk = re.match(r"(?:constraint\s+\w+\s+)?primary\s+key\s*\(([^)]*)\)", low)
                if pk: pk_cols |= {c.strip().strip('"') for c in pk.group(1).split(",")}
                fk = re.search(r"foreign\s+key\s*\(([^)]*)\)\s*references\s+([\w\".]+)", part, re.I)
                if fk: rels.append((t, short(fk.group(2)), fk.group(1).split(",")[0].strip().strip('"')))
                continue
            cm = re.match(r'"?(\w+)"?\s+([\w\s\[\]\(\),.]+?)(?=\s+(?:primary|references|not|null|default|unique|check|generated|constraint|collate)\b|$)', part, re.I)
            if not cm: continue
            name, typ = cm.group(1), re.sub(r"\s+", "_", cm.group(2).strip().split("(")[0])
            key = []
            if re.search(r"\bprimary\s+key\b", low): key.append("PK")
            ref = re.search(r"\breferences\s+([\w\".]+)", part, re.I)
            if ref:
                key.append("FK"); rels.append((t, short(ref.group(1)), name))
            cols.append([typ or "text", name, key])
        for c in cols:
            if c[1] in pk_cols and "PK" not in c[2]: c[2].insert(0, "PK")
        tables[t] = cols
    for stmt in text.split(";"):   # 문장 단위로 끊어 다른 문장의 FK가 섞이지 않게
        am = re.match(r"\s*alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?([\w\".]+)", stmt, re.I)
        if not am: continue
        src = short(am.group(1))
        if src not in tables: continue
        for fk in re.finditer(r"foreign\s+key\s*\(([^)]*)\)\s*references\s+([\w\".]+)", stmt, re.I):
            rels.append((src, short(fk.group(2)), fk.group(1).split(",")[0].strip().strip('"')))
        for ac in re.finditer(r"add\s+column\s+(?:if\s+not\s+exists\s+)?\"?(\w+)\"?\s+([\w\[\]]+)[^,]*?references\s+([\w\".]+)", stmt, re.I):
            rels.append((src, short(ac.group(3)), ac.group(1)))
            if not any(c[1] == ac.group(1) for c in tables[src]): tables[src].append([ac.group(2), ac.group(1), ["FK"]])
    out = ["erDiagram"]
    for t, cols in tables.items():
        if a.no_columns or not cols:
            out.append(f"  {ident(t)} {{\n    string _\n  }}" if not cols else f"  {ident(t)}")
            continue
        out.append(f"  {ident(t)} {{")
        shown = [c for c in cols if c[2]] + [c for c in cols if not c[2]]
        for typ, name, key in shown[: a.max_cols]:
            k = (" " + ",".join(key)) if key else ""
            out.append(f"    {ident(typ)} {ident(name)}{k}")
        if len(cols) > a.max_cols:
            out.append(f"    string more_{len(cols) - a.max_cols}_cols")
        out.append("  }")
    seen = set()
    for src, dst, col in rels:
        if dst not in tables or (src, dst, col) in seen: continue
        seen.add((src, dst, col))
        out.append(f'  {ident(dst)} ||--o{{ {ident(src)} : "{col}"')
    result = "\n".join(out) + "\n"
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh: fh.write(result)
        print(f"✅ {a.out} — 테이블 {len(tables)}개, 관계 {len(seen)}개 (SQL 파일 {len(files)}개)")
        if len(tables) > 25:
            print("⚠️ 테이블 25개 초과 — 읽기 어렵다. --match 로 영역별 분할 권장")
    else:
        sys.stdout.write(result)

if __name__ == "__main__":
    main()
