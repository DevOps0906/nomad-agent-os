#!/usr/bin/env python3
"""secscan — SBOM 생성 · 취약점 우선순위 · 라이선스 점검 · 보안 설정 파일 생성 (모델 토큰 0).

사용: secscan [all|sbom|vuln|license|setup] [프로젝트=.] [--kev] [--ci] [--top N] [--offline]
  all      SBOM → 취약점 → 라이선스 → "먼저 고칠 것" (기본)
  sbom     CycloneDX JSON → .nomad/sbom/sbom.cdx.json   (syft 있으면 syft, 없으면 lockfile 직접 해석)
  vuln     취약점 조회 (osv-scanner 있으면 그것, 없으면 OSV 공개 API) — --kev: CISA KEV · FIRST EPSS 반영
  license  라이선스를 정책(기본값 또는 security/policy.json)과 대조
  setup    .github/dependabot.yml(실제 매니페스트만) · SECURITY.md 생성, --ci: .github/workflows/sbom.yml 도 생성
원칙: 외부 도구·네트워크가 없어도 실패로 끝내지 않는다(안내 후 exit 0). 기존 파일은 덮어쓰지 않는다.
"""
import argparse, json, math, os, re, shutil, subprocess, sys, time, uuid
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

try:  # 한국어 Windows(cp949) 콘솔에서도 출력이 죽지 않게
    sys.stdout.reconfigure(encoding="utf-8", errors="replace"); sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SKIP_DIRS = {".git", "node_modules", ".next", "dist", "build", "out", ".venv", "venv", "env", "__pycache__",
             ".nomad", ".dart_tool", "coverage", "target", "vendor", ".turbo", ".cache"}
UA = {"User-Agent": "nomad-secscan/1"}

# ---------- 라이선스 정책 (기본값, security/policy.json 으로 덮어쓰기) ----------
ALLOW = {"MIT", "MIT-0", "APACHE-2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "ISC", "0BSD", "UNLICENSE", "CC0-1.0",
         "ZLIB", "PYTHON-2.0", "PSF-2.0", "BLUEOAK-1.0.0", "CC-BY-4.0", "CC-BY-3.0", "WTFPL", "BSL-1.0"}
REVIEW_PREFIX = ("LGPL", "MPL", "EPL", "CDDL", "CC-BY-SA", "ARTISTIC", "OFL", "EUPL")
DENY_PREFIX = ("GPL", "AGPL", "SSPL", "BUSL", "COMMONS-CLAUSE", "CC-BY-NC", "ELASTIC")
RANK = {"allow": 0, "review": 1, "deny": 2}


def log(msg=""):
    print(msg, flush=True)


# ---------- 탐색 ----------
def walk(root, max_depth=5):
    root = os.path.abspath(root)
    for d, dirs, files in os.walk(root):
        rel = os.path.relpath(d, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not (x.startswith(".") and x != ".github")]
        if depth >= max_depth:
            dirs[:] = []
        yield d, files


def read(p):
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


# ---------- lockfile 해석 → 컴포넌트 ----------
def purl(eco, name, ver):
    if eco == "npm":
        n = name.replace("@", "%40", 1) if name.startswith("@") else name
        return f"pkg:npm/{n}@{ver}" if ver else f"pkg:npm/{n}"
    if eco == "pypi":
        n = re.sub(r"[-_.]+", "-", name).lower()
        return f"pkg:pypi/{n}@{ver}" if ver else f"pkg:pypi/{n}"
    t = {"pub": "pub", "go": "golang", "cargo": "cargo"}[eco]
    return f"pkg:{t}/{name}@{ver}" if ver else f"pkg:{t}/{name}"


def comp(eco, name, ver, lic=None, dev=False, src=""):
    return {"eco": eco, "name": name, "version": ver or "", "purl": purl(eco, name, ver),
            "licenses": [lic] if isinstance(lic, str) and lic else (lic or []), "dev": bool(dev), "source": src}


def split_at(spec):  # "name@1.2.3" / "@scope/name@1.2.3" → (name, ver)
    i = spec.rfind("@")
    return (spec[:i], spec[i + 1:]) if i > 0 else (spec, "")


def p_npm_lock(path, rel):
    data = json.loads(read(path)); out = []
    if "packages" in data:
        for key, v in data["packages"].items():
            if not key or "node_modules/" not in key or v.get("link"):
                continue
            name = v.get("name") or key.rsplit("node_modules/", 1)[1]
            lic = v.get("license")
            if isinstance(lic, dict): lic = lic.get("type")
            out.append(comp("npm", name, v.get("version"), lic, v.get("dev") or v.get("devOptional"), rel))
    else:  # lockfileVersion 1
        def rec(deps):
            for name, v in (deps or {}).items():
                out.append(comp("npm", name, v.get("version"), None, v.get("dev"), rel)); rec(v.get("dependencies"))
        rec(data.get("dependencies"))
    return out


def p_pnpm_lock(path, rel):
    out, sect, cur = [], None, None
    for line in read(path).splitlines():
        if line and not line.startswith(" "):
            sect = line.rstrip(":").strip(); cur = None; continue
        if sect != "packages":
            continue
        m = re.match(r"^  (\S.*):\s*$", line)
        if m:
            key = m.group(1).strip("'\"").lstrip("/")
            key = re.sub(r"\(.*$", "", key)              # peer 접미사 제거
            if "@" in key[1:]:
                name, ver = split_at(key)
            else:                                        # v5: name/1.2.3
                name, ver = key.rsplit("/", 1) if "/" in key else (key, "")
            cur = comp("npm", name, ver, None, False, rel); out.append(cur)
        elif cur is not None and re.match(r"^    dev:\s*true", line):
            cur["dev"] = True
    seen, uniq = set(), []
    for c in out:
        if c["purl"] not in seen: seen.add(c["purl"]); uniq.append(c)
    return uniq


def p_yarn_lock(path, rel):
    out, names = [], None
    for line in read(path).splitlines():
        if line and not line.startswith((" ", "#")) and line.rstrip().endswith(":"):
            first = line.rstrip().rstrip(":").split(",")[0].strip().strip('"')
            # v1: name@^1.2 / berry: name@npm:^1.2 — 마지막 '@' 앞이 이름. workspace·patch 항목은 제외
            names = None if first.startswith("__metadata") or "@workspace:" in first or "@patch:" in first else split_at(first)[0]
        elif names:
            m = re.match(r'^\s+version:?\s+"?([^"\s]+)"?', line)
            if m:
                out.append(comp("npm", names, m.group(1), None, False, rel)); names = None
    return out


def p_requirements(path, rel):
    out = []
    for line in read(path).splitlines():
        line = line.split("#", 1)[0].split(";", 1)[0].strip()
        if not line or line.startswith(("-", "git+", "http")):
            continue
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*(==|===)\s*([^\s,]+)", line)
        if m:
            out.append(comp("pypi", m.group(1), m.group(4), None, "dev" in os.path.basename(path).lower(), rel))
        else:
            m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", line)
            if m: out.append(comp("pypi", m.group(1), "", None, False, rel))
    return out


def p_toml_lock(path, rel, eco):  # poetry.lock · uv.lock · Cargo.lock 공통 [[package]] 블록
    out = []
    for blk in read(path).split("[[package]]")[1:]:
        n = re.search(r'^name\s*=\s*"([^"]+)"', blk, re.M); v = re.search(r'^version\s*=\s*"([^"]+)"', blk, re.M)
        if not n: continue
        if re.search(r'^source\s*=\s*\{\s*(editable|virtual)', blk, re.M): continue   # uv 루트 프로젝트
        if eco == "cargo" and not re.search(r"^source\s*=", blk, re.M): continue      # cargo 로컬 크레이트
        dev = bool(re.search(r'^category\s*=\s*"dev"', blk, re.M))
        out.append(comp(eco, n.group(1), v.group(1) if v else "", None, dev, rel))
    return out


def p_pipfile_lock(path, rel):
    data = json.loads(read(path)); out = []
    for sect, dev in (("default", False), ("develop", True)):
        for name, v in (data.get(sect) or {}).items():
            out.append(comp("pypi", name, (v.get("version") or "").lstrip("="), None, dev, rel))
    return out


def p_pubspec_lock(path, rel):
    out, cur = [], None
    for line in read(path).splitlines():
        m = re.match(r"^  ([A-Za-z0-9_]+):\s*$", line)
        if m:
            cur = comp("pub", m.group(1), "", None, False, rel); out.append(cur); continue
        if cur is not None:
            m = re.match(r'^    version:\s*"?([^"\s]+)"?', line)
            if m: cur["version"] = m.group(1); cur["purl"] = purl("pub", cur["name"], cur["version"])
            if re.match(r'^    dependency:\s*"?direct dev', line): cur["dev"] = True
    return out


def p_go_mod(path, rel):
    out, block = [], False
    for line in read(path).splitlines():
        s = line.split("//", 1)[0].strip()
        if s.startswith("require ("): block = True; continue
        if block and s == ")": block = False; continue
        m = re.match(r"^(?:require\s+)?(\S+)\s+(v\S+)$", s) if (block or s.startswith("require ")) else None
        if m: out.append(comp("go", m.group(1), m.group(2), None, False, rel))
    return out


PARSERS = [("package-lock.json", p_npm_lock), ("npm-shrinkwrap.json", p_npm_lock), ("pnpm-lock.yaml", p_pnpm_lock),
           ("yarn.lock", p_yarn_lock), ("poetry.lock", lambda p, r: p_toml_lock(p, r, "pypi")),
           ("uv.lock", lambda p, r: p_toml_lock(p, r, "pypi")), ("Pipfile.lock", p_pipfile_lock),
           ("pubspec.lock", p_pubspec_lock), ("go.mod", p_go_mod), ("Cargo.lock", lambda p, r: p_toml_lock(p, r, "cargo"))]


def collect(root):
    comps, sources, notes = [], {}, []
    for d, files in walk(root):
        fs = set(files)
        has_py_lock = fs & {"poetry.lock", "uv.lock", "Pipfile.lock"}
        for fname, fn in PARSERS:
            if fname in fs:
                p = os.path.join(d, fname); rel = os.path.relpath(p, root).replace("\\", "/")
                try:
                    got = fn(p, rel); comps += got; sources[rel] = len(got)
                except Exception as e:
                    notes.append(f"{rel} 해석 실패: {e.__class__.__name__}")
        if not has_py_lock:
            for f in sorted(fs):
                if re.match(r"^requirements.*\.txt$", f):
                    p = os.path.join(d, f); rel = os.path.relpath(p, root).replace("\\", "/")
                    got = p_requirements(p, rel); comps += got; sources[rel] = len(got)
    npm_locks = [k for k in sources if k.endswith(("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "npm-shrinkwrap.json"))]
    if os.path.exists(os.path.join(root, "package.json")) and not npm_locks:
        notes.append("package.json 은 있는데 lockfile 이 없습니다 → 설치 후 lockfile 커밋 (정확한 버전 확인 불가)")
    seen, uniq = set(), []
    for c in comps:
        k = (c["purl"], c["source"])
        if k not in seen: seen.add(k); uniq.append(c)
    return uniq, sources, notes


# ---------- SBOM ----------
def run(cmd, timeout=600):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, "", str(e)


def sbom_syft(root):
    exe = shutil.which("syft")
    if not exe: return None
    for cmd in ([exe, "scan", f"dir:{root}", "-o", "cyclonedx-json", "-q"], [exe, f"dir:{root}", "-o", "cyclonedx-json", "-q"]):
        code, out, _ = run(cmd)
        if code == 0 and out.strip().startswith("{"):
            try: return json.loads(out)
            except ValueError: pass
    return None


def lic_entry(l):
    u = l.upper()
    return {"license": {"id": l}} if (u in ALLOW or re.match(r"^(A?GPL|LGPL|MPL|EPL)-[0-9.]+(-only|-or-later)?$", u)) \
        else ({"expression": l} if re.search(r"\s(OR|AND|WITH)\s", l) else {"license": {"name": l}})


def to_cdx(root, comps):
    return {"bomFormat": "CycloneDX", "specVersion": "1.5", "serialNumber": f"urn:uuid:{uuid.uuid4()}", "version": 1,
            "metadata": {"timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "tools": {"components": [{"type": "application", "name": "nomad-secscan", "version": "1"}]},
                         "component": {"type": "application", "name": os.path.basename(os.path.abspath(root)),
                                       "bom-ref": "root"}},
            "components": [{"type": "library", "bom-ref": f"{c['purl']}#{i}", "name": c["name"], "version": c["version"],
                            "purl": c["purl"], **({"licenses": [lic_entry(l) for l in c["licenses"]]} if c["licenses"] else {}),
                            **({"scope": "optional"} if c["dev"] else {}),
                            "properties": [{"name": "nomad:source", "value": c["source"]}]}
                           for i, c in enumerate(comps)]}


def from_cdx(doc):
    out = []
    for c in doc.get("components", []):
        p = c.get("purl") or ""
        m = re.match(r"^pkg:([^/]+)/", p)
        eco = {"npm": "npm", "pypi": "pypi", "pub": "pub", "golang": "go", "cargo": "cargo"}.get(m.group(1) if m else "", "other")
        lics = []
        for l in c.get("licenses", []) or []:
            lics.append(l.get("expression") or (l.get("license") or {}).get("id") or (l.get("license") or {}).get("name") or "")
        out.append({"eco": eco, "name": c.get("name", ""), "version": c.get("version", ""), "purl": p,
                    "licenses": [x for x in lics if x], "dev": c.get("scope") == "optional", "source": "syft"})
    return out


def do_sbom(root, outdir):
    comps, sources, notes = collect(root)
    doc, gen = sbom_syft(root), "syft"
    if doc:
        syft_comps = [c for c in from_cdx(doc) if c["purl"]]
        dev_map = {c["purl"]: c["dev"] for c in comps}
        for c in syft_comps: c["dev"] = dev_map.get(c["purl"], False)
        comps = syft_comps or comps
    else:
        gen = "nomad-secscan (lockfile 해석)"; doc = to_cdx(root, comps)
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "sbom.cdx.json")
    with open(path, "w", encoding="utf-8") as f: json.dump(doc, f, ensure_ascii=False, indent=1)
    return {"path": path, "generator": gen, "components": comps, "sources": sources, "notes": notes}


# ---------- 취약점 ----------
def http_json(url, body=None, timeout=25):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={**UA, **({"Content-Type": "application/json"} if data else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def cvss3_score(vec):
    m = dict(p.split(":", 1) for p in vec.split("/")[1:] if ":" in p)
    try:
        s = m["S"]; av = {"N": .85, "A": .62, "L": .55, "P": .2}[m["AV"]]; ac = {"L": .77, "H": .44}[m["AC"]]
        pr = {"N": .85, "L": .68 if s == "C" else .62, "H": .5 if s == "C" else .27}[m["PR"]]
        ui = {"N": .85, "R": .62}[m["UI"]]; cia = {"H": .56, "L": .22, "N": 0}
        iss = 1 - (1 - cia[m["C"]]) * (1 - cia[m["I"]]) * (1 - cia[m["A"]])
        imp = 6.42 * iss if s == "U" else 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
        if imp <= 0: return 0.0
        raw = min(imp + 8.22 * av * ac * pr * ui, 10) if s == "U" else min(1.08 * (imp + 8.22 * av * ac * pr * ui), 10)
        i = round(raw * 100000)
        return i / 100000.0 if i % 10000 == 0 else (math.floor(i / 10000) + 1) / 10.0
    except (KeyError, ValueError):
        return None


def sev_of(v):
    label = ((v.get("database_specific") or {}).get("severity") or "").upper()
    score = None
    for s in v.get("severity") or []:
        if str(s.get("type", "")).startswith("CVSS_V3") and str(s.get("score", "")).startswith("CVSS:3"):
            score = cvss3_score(s["score"])
    if not label and score is not None:
        label = "CRITICAL" if score >= 9 else "HIGH" if score >= 7 else "MODERATE" if score >= 4 else "LOW"
    return (label.replace("MEDIUM", "MODERATE") or "?"), score


def vkey(s):  # "4.17.21" → (4, 17, 21) 비교용 (숫자 아닌 꼬리는 무시)
    return tuple(int(x) for x in re.findall(r"\d+", str(s).split("-")[0])[:4])


def fixed_of(v, name, cur):
    """현재 버전보다 높은 수정 버전 중 가장 가까운 것 (여러 브랜치에 각각 수정이 있는 경우)."""
    fixes = []
    for a in v.get("affected") or []:
        if (a.get("package") or {}).get("name", "").lower() != name.lower(): continue
        for r in a.get("ranges") or []:
            if r.get("type") == "GIT": continue          # 커밋 해시는 설치 가능한 버전이 아니다
            fixes += [e["fixed"] for e in r.get("events") or [] if "fixed" in e]
    above = [f for f in fixes if vkey(f) > vkey(cur)] if cur else fixes
    return min(above, key=vkey) if above else ""


def vulns_osv_scanner(root):
    exe = shutil.which("osv-scanner")
    if not exe: return None
    for cmd in ([exe, "scan", "source", "-r", "--format", "json", root], [exe, "--format", "json", "-r", root]):
        code, out, _ = run(cmd, timeout=900)
        if code in (0, 1) and out.strip().startswith("{"):
            try: data = json.loads(out)
            except ValueError: continue
            found = []
            for res in data.get("results", []):
                for pk in res.get("packages", []):
                    p = pk.get("package", {})
                    for v in pk.get("vulnerabilities", []):
                        found.append((p.get("name", ""), p.get("version", ""), p.get("ecosystem", ""), v))
            return found
    return None


def vulns_osv_api(comps):
    q = [c for c in comps if c["version"] and c["eco"] in ("npm", "pypi", "pub", "go", "cargo")]
    uniq = list({c["purl"]: c for c in q}.values())
    hits = []  # (comp, vuln_id)
    for i in range(0, len(uniq), 500):
        chunk = uniq[i:i + 500]
        res = http_json("https://api.osv.dev/v1/querybatch", {"queries": [{"package": {"purl": c["purl"]}} for c in chunk]})
        for c, r in zip(chunk, res.get("results", [])):
            for v in r.get("vulns", []) or []:
                hits.append((c, v["id"]))
    ids = sorted({h[1] for h in hits})[:150]
    details = {}
    def get(i):
        try: details[i] = http_json(f"https://api.osv.dev/v1/vulns/{i}")
        except Exception: details[i] = {"id": i}
    with ThreadPoolExecutor(8) as ex: list(ex.map(get, ids))
    return [(c["name"], c["version"], c["eco"], details.get(i, {"id": i})) for c, i in hits if i in details]


def load_kev(cache_dir):
    os.makedirs(cache_dir, exist_ok=True); p = os.path.join(cache_dir, "kev.json")
    if not (os.path.exists(p) and time.time() - os.path.getmtime(p) < 86400):
        data = http_json("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", timeout=40)
        with open(p, "w", encoding="utf-8") as f: json.dump([x["cveID"] for x in data.get("vulnerabilities", [])], f)
    with open(p, encoding="utf-8") as f: return set(json.load(f))


def load_epss(cves):
    out, cves = {}, sorted(cves)
    for i in range(0, len(cves), 80):
        data = http_json("https://api.first.org/data/v1/epss?cve=" + ",".join(cves[i:i + 80]))
        for row in data.get("data", []):
            try: out[row["cve"]] = float(row["epss"])
            except (KeyError, ValueError): pass
    return out


SEV_RANK = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "LOW": 1, "?": 0}


def do_vuln(root, comps, kev=False, offline=False, cache_dir=""):
    notes, engine = [], "osv-scanner"
    raw = vulns_osv_scanner(root)
    if raw is None:
        engine = "OSV API"
        if offline:
            return {"engine": "미실행", "items": [], "notes": ["--offline: 취약점 조회를 건너뜀"]}
        try:
            raw = vulns_osv_api(comps)
        except Exception as e:
            return {"engine": "미실행", "items": [], "notes": [f"OSV API 연결 실패({e.__class__.__name__}) — 네트워크 확인 또는 osv-scanner 설치: https://google.github.io/osv-scanner/"]}
    dev = {(c["name"].lower(), c["version"]): c["dev"] for c in comps}
    by_key = {}  # 같은 CVE가 여러 DB(GHSA·PYSEC 등)에서 오면 하나로 합친다
    for name, ver, eco, v in raw:
        vid = v.get("id", "?")
        cves = [a for a in ([vid] + (v.get("aliases") or [])) if a.startswith("CVE-")]
        label, score = sev_of(v)
        it = {"package": name, "version": ver, "eco": eco, "id": vid, "cve": cves[0] if cves else "",
              "severity": label, "cvss": score, "summary": (v.get("summary") or "")[:90],
              "fixed": fixed_of(v, name, ver), "dev": dev.get((name.lower(), ver), False), "kev": False, "epss": None}
        k = (name.lower(), ver, it["cve"] or vid)
        old = by_key.get(k)
        if old is None:
            by_key[k] = it; continue
        if old["severity"] == "?" and label != "?": old["severity"], old["cvss"] = label, score
        if old["cvss"] is None and score is not None: old["cvss"] = score
        if not old["fixed"]: old["fixed"] = it["fixed"]
    items = list(by_key.values())
    if kev and items:
        try:
            k = load_kev(cache_dir)
            for it in items: it["kev"] = it["cve"] in k
        except Exception as e:
            notes.append(f"KEV 조회 실패({e.__class__.__name__}) — 우선순위에서 제외")
        try:
            ep = load_epss({it["cve"] for it in items if it["cve"]})
            for it in items: it["epss"] = ep.get(it["cve"])
        except Exception as e:
            notes.append(f"EPSS 조회 실패({e.__class__.__name__}) — 우선순위에서 제외")
    items.sort(key=lambda it: (not it["kev"], it["dev"], -(it["epss"] or 0), -SEV_RANK.get(it["severity"], 0), -(it["cvss"] or 0)))
    return {"engine": engine, "items": items, "notes": notes}


# ---------- 라이선스 ----------
def load_policy(root):
    p = os.path.join(root, "security", "policy.json")
    pol = {"allow": set(), "deny": set(), "exceptions": []}
    if os.path.exists(p):
        try:
            d = json.loads(read(p))
            pol["allow"] = {x.upper() for x in d.get("allow", [])}; pol["deny"] = {x.upper() for x in d.get("deny", [])}
            pol["exceptions"] = d.get("exceptions", [])
        except ValueError:
            log(f"  ⚠️ {p} JSON 오류 — 기본 정책 사용")
    return pol


def classify_one(l, pol):
    u = l.strip().strip("()").upper()
    if not u or u in ("UNKNOWN", "NOASSERTION", "NONE") or u.startswith("SEE LICENSE"): return "review"
    if u in pol["deny"]: return "deny"
    if u in pol["allow"] or u in ALLOW: return "allow"
    if u.startswith(REVIEW_PREFIX): return "review"
    if u.startswith(DENY_PREFIX): return "deny"
    return "review"


def classify(expr, pol):
    best = 2
    for alt in re.split(r"\s+OR\s+", expr.replace("/", " OR "), flags=re.I):
        worst = max(RANK[classify_one(re.sub(r"\s+WITH\s+.*$", "", part, flags=re.I), pol)]
                    for part in re.split(r"\s+AND\s+", alt, flags=re.I))
        best = min(best, worst)
    return {0: "allow", 1: "review", 2: "deny"}[best]


def do_license(root, comps):
    pol = load_policy(root)
    res = {"deny": [], "review": [], "allow": 0, "unknown": 0, "excepted": 0}
    for c in comps:
        def hit(e):  # purl 전체 일치, 버전 없는 purl(pkg:npm/x)이면 모든 버전, 또는 이름 일치 — 앞부분 일치(x-extra)는 제외
            p = str(e.get("package", ""))
            return bool(p) and (c["purl"] == p or c["purl"].startswith(p + "@") or c["name"] == p)
        if any(hit(e) for e in pol["exceptions"]):
            res["excepted"] += 1; continue
        if not c["licenses"]:
            res["unknown"] += 1; continue
        cls = max((classify(l, pol) for l in c["licenses"]), key=lambda x: RANK[x])
        if cls == "allow": res["allow"] += 1
        else: res[cls].append({"package": c["name"], "version": c["version"], "license": " / ".join(c["licenses"]), "dev": c["dev"]})
    return res


# ---------- setup ----------
DEPENDABOT_HEAD = "# Dependabot — `secscan setup` 이 실제 매니페스트를 보고 생성 (없는 생태계는 넣지 않음)\nversion: 2\nupdates:\n"
SECURITY_MD = """# 보안 정책 (Security Policy)

## 취약점 신고
- 공개 이슈로 올리지 말고 **GitHub 비공개 취약점 신고**(Security 탭 → Report a vulnerability)를 사용해 주세요.
- 재현 방법 · 영향 범위 · 확인한 버전을 함께 알려 주시면 빠르게 확인합니다.

## 대응
- 접수 후 3영업일 안에 확인 회신합니다.
- 실제 악용 중(KEV)이거나 인터넷에 노출된 경로에서 도달 가능한 취약점을 먼저 처리합니다.

## 지원 버전
- 최신 `main` 브랜치와 최신 릴리스만 보안 수정을 제공합니다.
"""
SBOM_WORKFLOW = """# SBOM 생성 + 취약점 스캔 — `secscan setup --ci` 가 생성. 액션 버전은 Dependabot(github-actions)이 갱신한다.
name: sbom
on:
  push:
    branches: [main]
  release:
    types: [published]
  workflow_dispatch:
permissions:
  contents: read
jobs:
  sbom:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: SBOM 생성 (CycloneDX)
        uses: anchore/sbom-action@v0
        with:
          path: .
          format: cyclonedx-json
          output-file: sbom.cdx.json
          upload-artifact: false
      - name: 취약점 스캔 (리포트만, 빌드는 막지 않음)
        uses: anchore/scan-action@v6
        with:
          sbom: sbom.cdx.json
          fail-build: false
          severity-cutoff: high
          output-format: table
      - name: SBOM 보관
        uses: actions/upload-artifact@v4
        with:
          name: sbom-${{ github.sha }}
          path: sbom.cdx.json
          retention-days: 90
"""


def detect_ecosystems(root):
    found = {}  # eco → set(dirs)
    def add(eco, d):
        rel = os.path.relpath(d, root).replace("\\", "/")
        found.setdefault(eco, set()).add("/" if rel == "." else "/" + rel)
    npm_lock_dirs = []
    for d, files in walk(root, 4):
        fs = set(files)
        if fs & {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "npm-shrinkwrap.json"}: npm_lock_dirs.append(d); add("npm", d)
        if fs & {"pyproject.toml", "Pipfile"} or any(re.match(r"^requirements.*\.txt$", f) for f in fs): add("pip", d)
        if "pubspec.yaml" in fs: add("pub", d)
        if "go.mod" in fs: add("gomod", d)
        if "Cargo.toml" in fs: add("cargo", d)
        if any(f == "Dockerfile" or f.endswith(".Dockerfile") for f in fs): add("docker", d)
    if not npm_lock_dirs and os.path.exists(os.path.join(root, "package.json")): add("npm", root)
    if os.path.isdir(os.path.join(root, ".github", "workflows")): found.setdefault("github-actions", set()).add("/")
    return found


def write_new(path, text, made, root):
    rel = os.path.relpath(path, root).replace("\\", "/")
    if os.path.exists(path):
        log(f"  · 유지  {rel} (이미 있음 — 덮어쓰지 않음)"); return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f: f.write(text)
    log(f"  + 생성  {rel}"); made.append(rel)


def do_setup(root, ci):
    eco = detect_ecosystems(root)
    if ci: eco.setdefault("github-actions", set()).add("/")
    made = []
    log(f"■ secscan setup → {root}")
    if not eco:
        log("  · 매니페스트(package.json · requirements.txt · pyproject.toml · pubspec.yaml · go.mod · Cargo.toml)가 아직 없습니다.")
        log("    코드가 생긴 뒤 다시 실행하세요. (빈 dependabot.yml 은 Dependabot 오류를 내므로 만들지 않음)")
    else:
        body = DEPENDABOT_HEAD
        for e in sorted(eco):
            for d in sorted(eco[e]):
                body += (f'  - package-ecosystem: "{e}"\n    directory: "{d}"\n    schedule:\n      interval: "weekly"\n'
                         f"    open-pull-requests-limit: 5\n    groups:\n      minor-and-patch:\n"
                         f'        update-types: ["minor", "patch"]\n')
        log("  생태계: " + ", ".join(f"{e}({len(v)})" for e, v in sorted(eco.items())))
        write_new(os.path.join(root, ".github", "dependabot.yml"), body, made, root)
    write_new(os.path.join(root, "SECURITY.md"), SECURITY_MD, made, root)
    if ci: write_new(os.path.join(root, ".github", "workflows", "sbom.yml"), SBOM_WORKFLOW, made, root)
    log("■ GitHub 저장소 설정 (사람이 한 번 — Settings → Code security):")
    log("  Dependency graph · Dependabot alerts · Secret scanning(+Push protection) · Private vulnerability reporting 켜기")
    log("  gh 로 하려면: gh api -X PUT repos/<계정>/<저장소>/vulnerability-alerts")
    log("               gh api -X PUT repos/<계정>/<저장소>/private-vulnerability-reporting")
    return made


# ---------- 출력 ----------
def print_vulns(v, top):
    items = v["items"]
    log(f"■ 취약점 ({v['engine']}): {len(items)}건" + (f" — KEV {sum(i['kev'] for i in items)}" if items else ""))
    for n in v["notes"]: log(f"  ⚠️ {n}")
    if not items: return
    log("  | # | 패키지@버전 | 취약점 | 심각도 | KEV | EPSS | 범위 | 수정 버전 |")
    log("  |---|---|---|---|---|---|---|---|")
    for i, it in enumerate(items[:top], 1):
        ep = f"{it['epss']:.2f}" if it["epss"] is not None else "-"
        log(f"  | {i} | {it['package']}@{it['version']} | {it['cve'] or it['id']} | {it['severity']}"
            f"{'' if it['cvss'] is None else ' ' + str(it['cvss'])} | {'🔴' if it['kev'] else '-'} | {ep} | "
            f"{'개발' if it['dev'] else '운영'} | {it['fixed'] or '?'} |")
    if len(items) > top: log(f"  … 외 {len(items) - top}건 (전체: .nomad/sbom/report.json)")


def print_license(r, total):
    log(f"■ 라이선스: 허용 {r['allow']} · 검토 {len(r['review'])} · 거부 {len(r['deny'])} · 정보 없음 {r['unknown']}"
        + (f" · 예외 {r['excepted']}" if r["excepted"] else ""))
    for x in r["deny"][:10]: log(f"  🔴 거부  {x['package']}@{x['version']} — {x['license']}{' (개발)' if x['dev'] else ''}")
    for x in r["review"][:5]: log(f"  🟡 검토  {x['package']}@{x['version']} — {x['license']}")
    if total and r["unknown"] > total / 2:
        log("  ⚠️ 라이선스 정보가 lockfile 에 없습니다(pnpm·yarn·pip 등) → syft 설치 후 다시: https://github.com/anchore/syft")


def first_fixes(v, lic):
    out = []
    for x in lic["deny"]:
        if not x["dev"]: out.append(f"라이선스 거부 {x['package']}@{x['version']} ({x['license']}) → 대체 패키지 또는 사용자 승인 후 security/policy.json 예외")
    groups = {}  # 패키지별로 묶어 모든 취약점을 덮는 가장 높은 수정 버전 하나만 권한다
    for it in v["items"]:
        if it["kev"] or (not it["dev"] and SEV_RANK.get(it["severity"], 0) >= 3):
            g = groups.setdefault((it["package"], it["version"]), {"ids": [], "kev": False, "sev": it["severity"]})
            g["ids"].append(it["cve"] or it["id"]); g["kev"] |= it["kev"]
    for (pkg, ver), g in groups.items():
        fixes = [it["fixed"] for it in v["items"] if it["package"] == pkg and it["version"] == ver and it["fixed"]]
        best = max(fixes, key=vkey) if fixes else ""
        ids = ", ".join(g["ids"][:2]) + (f" 외 {len(g['ids']) - 2}건" if len(g["ids"]) > 2 else "")
        major = " (메이저 버전 변경 — 호환성 확인)" if best and vkey(best)[:1] != vkey(ver)[:1] else ""
        out.append(f"{pkg}@{ver} — {ids} ({'KEV ' if g['kev'] else ''}{g['sev']}) → {best + ' 이상으로 업데이트' + major if best else '수정 버전 확인'}")
    return out[:3]


def main():
    ap = argparse.ArgumentParser(prog="secscan", description="SBOM · 취약점 · 라이선스 · 보안 설정 (NOMAD)")
    ap.add_argument("cmd", nargs="?", default="all", choices=["all", "sbom", "vuln", "license", "setup"])
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--kev", action="store_true", help="CISA KEV · FIRST EPSS 반영 (네트워크)")
    ap.add_argument("--ci", action="store_true", help="setup 때 .github/workflows/sbom.yml 도 생성")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--offline", action="store_true", help="네트워크 조회 생략")
    a = ap.parse_args()
    root = os.path.abspath(a.path)
    if not os.path.isdir(root):
        log(f"❌ 폴더가 없습니다: {root}"); return 2
    if a.cmd == "setup":
        do_setup(root, a.ci); return 0

    outdir = os.path.join(root, ".nomad", "sbom")
    log(f"■ secscan {a.cmd} → {root}")
    sb = do_sbom(root, outdir)
    comps = sb["components"]
    if sb["sources"]: log("  해석: " + " · ".join(f"{k}({n})" for k, n in sb["sources"].items()))
    for n in sb["notes"]: log(f"  ⚠️ {n}")
    if not comps:
        log("  · 의존성을 찾지 못했습니다 (lockfile 없음). 코드·lockfile 이 생긴 뒤 다시 실행하세요.")
        if not shutil.which("syft"): log("    더 넓게 보려면 syft 설치: https://github.com/anchore/syft")
        return 0
    if a.cmd in ("all", "sbom"):
        log(f"■ SBOM: {os.path.relpath(sb['path'], root)} — 컴포넌트 {len(comps)}개 (생성: {sb['generator']})")
    unpinned = [c["name"] for c in comps if not c["version"]]
    if unpinned:
        log(f"  ⚠️ 버전 고정 안 됨 {len(unpinned)}개 (취약점 조회 불가): {', '.join(unpinned[:5])} → lockfile 또는 == 로 고정")
    report = {"generated": datetime.now(timezone.utc).isoformat(), "sbom": sb["path"], "generator": sb["generator"]}
    v, lic = {"engine": "-", "items": [], "notes": []}, {"deny": [], "review": [], "allow": 0, "unknown": 0, "excepted": 0}
    if a.cmd in ("all", "vuln"):
        v = do_vuln(root, comps, a.kev, a.offline, os.path.join(root, ".nomad", "cache")); print_vulns(v, a.top)
        report["vulns"] = v
    if a.cmd in ("all", "license"):
        lic = do_license(root, comps); print_license(lic, len(comps)); report["license"] = lic
    if a.cmd == "all":
        fixes = first_fixes(v, lic)
        if not fixes and v["engine"] == "미실행":
            log("■ 먼저 고칠 것: 라이선스는 문제 없음, **취약점은 확인하지 못함** (위 ⚠️ 참고)")
        else:
            log("■ 먼저 고칠 것" + ("" if fixes else ": 없음 ✅ (KEV·운영 high 이상·거부 라이선스 없음)"))
        for i, f in enumerate(fixes, 1): log(f"  {i}. {f}")
        if not a.kev and v["items"]: log("  (실제 악용 여부까지 보려면: secscan vuln --kev)")
    with open(os.path.join(outdir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1, default=list)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
