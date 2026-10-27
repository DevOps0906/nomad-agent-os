"""modules.py / doctor.py 새 기능 테스트 (unittest 만). 실제 ~/.claude 는 건드리지 않는다."""
import json, os, shutil, subprocess, sys, tempfile, unittest, importlib.util

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PY = os.path.join(ROOT, "global", "nomad", "bin", "py")
MODULES = os.path.join(PY, "modules.py")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nomad-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home"); os.makedirs(self.home)
        self.repo = os.path.join(self.tmp, "repo"); os.makedirs(self.repo)   # 가짜 모듈 레포(루트에 module.json 없음)
        self.proj = os.path.join(self.tmp, "proj"); os.makedirs(self.proj)

    def mod(self, name, content=None, **man):
        d = os.path.join(self.repo, name); os.makedirs(d, exist_ok=True)
        man.setdefault("type", "blueprint"); man.setdefault("license", "MIT"); man.setdefault("version", "1.0.0")
        json.dump(man, open(os.path.join(d, "module.json"), "w"))
        for rel, txt in (content if content is not None else {"README.md": "# " + name}).items():
            p = os.path.join(d, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w", encoding="utf-8").write(txt)
        return d

    def run_mod(self, *args, frm=True):
        env = dict(os.environ, NOMAD_HOME=self.home, PYTHONIOENCODING="utf-8")
        cmd = [sys.executable, MODULES, *args]
        if frm: cmd += ["--from", self.repo]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, cwd=self.tmp)
        return r.returncode, r.stdout + r.stderr

    def add(self, name, *extra):
        return self.run_mod("add", name, self.proj, *extra)

    def lock(self):
        p = os.path.join(self.proj, "nomad-modules.json")
        return json.load(open(p, encoding="utf-8"))["modules"] if os.path.exists(p) else {}

    def exists(self, *rel):
        return os.path.exists(os.path.join(self.proj, *rel))


class DockerType(Base):
    FILES = {"Dockerfile": "FROM x", ".dockerignore": "node_modules", "Dockerfile.dockerignore": "**/.env", ".env.example": "A=1", "nginx.conf": "x", "README.md": "r"}

    def test_requires_allow_scripts(self):
        self.mod("dk", self.FILES, type="docker")
        code, out = self.add("dk")
        self.assertNotEqual(code, 0); self.assertIn("--allow-scripts", out)
        self.assertFalse(self.exists("infra", "dk"))

    def test_installs_with_allow_scripts(self):
        self.mod("dk", self.FILES, type="docker")
        code, out = self.add("dk", "--allow-scripts")
        self.assertEqual(code, 0, out)
        for f in self.FILES: self.assertTrue(self.exists("infra", "dk", f), f)
        self.assertEqual(self.lock()["dk"]["install_to"], "infra/dk")

    def test_blueprint_blocks_dockerfile(self):
        self.mod("bp", {"Dockerfile": "FROM x", "README.md": "r"}, type="blueprint")
        code, out = self.add("bp")
        self.assertNotEqual(code, 0); self.assertIn("Dockerfile", out)

    def test_blueprint_blocks_sh_without_allow_scripts(self):
        self.mod("bp", {"run.sh": "echo", "README.md": "r"}, type="blueprint")
        code, out = self.add("bp")
        self.assertNotEqual(code, 0); self.assertIn("run.sh", out)

    def test_docker_sh_rejected_even_with_allow_scripts(self):
        self.mod("dk", {"run.sh": "echo", "Dockerfile": "FROM x"}, type="docker")
        for extra in ((), ("--allow-scripts",)):
            code, out = self.add("dk", *extra)
            self.assertNotEqual(code, 0); self.assertFalse(self.exists("infra", "dk"))
        self.assertEqual(self.lock(), {})

    def test_docker_unknown_ext_rejected(self):
        self.mod("dk", {"Dockerfile": "FROM x", "a.bin": "x"}, type="docker")
        self.assertNotEqual(self.add("dk", "--allow-scripts")[0], 0)


class Security(Base):
    def test_requires_does_not_inherit_allow_scripts(self):
        self.mod("dk", {"Dockerfile": "FROM x"}, type="docker"); self.mod("a", requires=["dk"])
        code, out = self.add("a", "--allow-scripts")
        self.assertNotEqual(code, 0); self.assertIn("--allow-scripts", out)
        self.assertFalse(self.exists("docs")); self.assertFalse(self.exists("infra")); self.assertEqual(self.lock(), {})
        self.assertFalse(self.exists("nomad-modules.json"))

    def test_requires_bad_names_rejected(self):
        for bad in ("https://x.invalid/r", "../x", "Upper", "nonexistent"):
            self.mod("a", requires=[bad])
            code, out = self.add("a")
            self.assertNotEqual(code, 0, bad); self.assertFalse(self.exists("nomad-modules.json"), bad)
            self.assertFalse(self.exists("docs"), bad)

    def test_install_to_outside_types_top_rejected(self):
        for bad in ("src/x", "../out", "docs", "security/x", ".git/hooks", "docs/.github/x", "docs/.vscode"):
            self.mod("a", install_to=bad)         # blueprint 는 docs/ 아래만
            code, out = self.add("a")
            self.assertNotEqual(code, 0, bad); self.assertFalse(self.exists("nomad-modules.json"), bad)
        self.mod("a", install_to="docs/custom/a")
        self.assertEqual(self.add("a")[0], 0)
        self.assertTrue(self.exists("docs", "custom", "a", "README.md"))

    def test_forbidden_dir_in_files_rejected(self):
        self.mod("a", {"README.md": "r", ".github/workflows/x.yml": "x"})
        code, out = self.add("a")
        self.assertNotEqual(code, 0); self.assertFalse(self.exists("docs"))

    def test_preflight_nothing_installed_if_one_requires_fails(self):
        self.mod("b"); self.mod("c", {"run.sh": "echo"}); self.mod("a", requires=["b", "c"])
        code, out = self.add("a")
        self.assertNotEqual(code, 0)
        self.assertFalse(self.exists("docs")); self.assertFalse(self.exists("nomad-modules.json"))

    def test_depth_limit(self):
        for i in range(9): self.mod(f"m{i}", requires=[f"m{i+1}"] if i < 8 else [])
        code, out = self.add("m0")
        self.assertNotEqual(code, 0); self.assertIn("깊", out)
        self.assertFalse(self.exists("nomad-modules.json"))
        code, out = self.add("m1")          # 8단계는 허용
        self.assertEqual(code, 0, out); self.assertEqual(len(self.lock()), 8)

    def test_lock_records_requires_and_remove_uses_lock(self):
        self.mod("b"); self.mod("a", requires=["b"])
        self.assertEqual(self.add("a")[0], 0)
        self.assertEqual(self.lock()["a"]["requires"], ["b"])
        # lock 에서 requires 를 지우면(예전 항목) 소스를 보지 않으므로 경고 없음
        p = os.path.join(self.proj, "nomad-modules.json"); d = json.load(open(p, encoding="utf-8"))
        d["modules"]["a"].pop("requires"); json.dump(d, open(p, "w", encoding="utf-8"))
        code, out = self.run_mod("remove", "b", self.proj, frm=False)
        self.assertEqual(code, 0, out); self.assertNotIn("requires 로 사용 중", out)

    def test_intermediate_symlink_rejected(self):
        outside = os.path.join(self.tmp, "outside"); os.makedirs(outside)
        open(os.path.join(outside, "x.md"), "w").write("secret")
        d = self.mod("a", {"README.md": "r"}, files=["README.md", "link/x.md"])
        try: os.symlink(outside, os.path.join(d, "link"), target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError): self.skipTest("심볼릭 링크 생성 불가")
        code, out = self.add("a")
        self.assertNotEqual(code, 0); self.assertFalse(self.exists("docs"))


class Requires(Base):
    def test_recursive_chain(self):
        self.mod("a", requires=["b"]); self.mod("b", requires=["c"]); self.mod("c")
        code, out = self.add("a")
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(self.lock()), ["a", "b", "c"])
        for n in "abc": self.assertTrue(self.exists("docs", "blueprints", n, "README.md"))

    def test_skips_installed(self):
        self.mod("b"); self.mod("a", requires=["b"])
        self.assertEqual(self.add("b")[0], 0)
        code, out = self.add("a")
        self.assertEqual(code, 0, out)
        self.assertNotIn("함께 설치(requires)", out)
        self.assertEqual(sorted(self.lock()), ["a", "b"])

    def test_cycle_fails(self):
        self.mod("a", requires=["b"]); self.mod("b", requires=["a"])
        code, out = self.add("a")
        self.assertNotEqual(code, 0); self.assertIn("순환", out)

    def test_update_installs_only_new_requires(self):
        self.mod("b"); self.mod("c"); self.mod("a", requires=["b"])
        self.assertEqual(self.add("a")[0], 0)
        self.assertEqual(sorted(self.lock()), ["a", "b"])
        self.mod("a", requires=["b", "c"])
        code, out = self.run_mod("update", "a", self.proj, frm=False)
        self.assertEqual(code, 0, out)
        self.assertIn("함께 설치(requires): c", out)
        self.assertEqual(sorted(self.lock()), ["a", "b", "c"])


class Integrates(Base):
    def test_integrates_line(self):
        self.mod("b"); self.mod("a", integrates=["b", "zz"])
        self.assertEqual(self.add("b")[0], 0)
        code, out = self.add("a")
        self.assertEqual(code, 0, out)
        self.assertIn("함께 쓰면 연결: b(설치됨) · zz(미설치)", out)


class Remove(Base):
    def test_remove_warns_dependents(self):
        self.mod("b"); self.mod("a", requires=["b"])
        self.assertEqual(self.add("a")[0], 0)
        code, out = self.run_mod("remove", "b", self.proj, frm=False)
        self.assertEqual(code, 0, out)
        self.assertIn("a 모듈이 b 을(를) requires 로 사용 중", out)
        self.assertFalse(self.exists("docs", "blueprints", "b", "README.md"))

    def test_remove_no_warning_when_unused(self):
        self.mod("b")
        self.assertEqual(self.add("b")[0], 0)
        code, out = self.run_mod("remove", "b", self.proj, frm=False)
        self.assertEqual(code, 0); self.assertNotIn("requires 로 사용 중", out)

    def test_remove_not_installed_fails(self):
        code, out = self.run_mod("remove", "nope", self.proj, frm=False)
        self.assertNotEqual(code, 0)


class ListOrder(Base):
    def test_category_order(self):
        order = ["core", "foundation", "domain", "ai", "infra", "security", "zzz"]
        reg = {f"t-{c}": {"repo": "https://example.invalid/x", "type": "blueprint", "category": c} for c in reversed(order)}
        json.dump({"modules": reg}, open(os.path.join(self.home, "modules.local.json"), "w"))
        code, out = self.run_mod("list", self.proj, frm=False)
        self.assertEqual(code, 0, out)
        heads = [f"({c})" for c in order[:-1]] + ["기타 (other)"]
        pos = [out.find("■ ") if False else out.find("■ " + h) if False else out.find(h) for h in heads]
        self.assertTrue(all(p >= 0 for p in pos), (pos, out))
        self.assertEqual(pos, sorted(pos))
        npos = [out.find(f"| t-{c} |") for c in order]
        self.assertTrue(all(p >= 0 for p in npos)); self.assertEqual(npos, sorted(npos))


class Doctor(unittest.TestCase):
    def load(self, tag):
        spec = importlib.util.spec_from_file_location("doctor_" + tag, os.path.join(PY, "doctor.py"))
        d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
        return d

    def setup_dirs(self, d):
        tmp = tempfile.mkdtemp(prefix="nomad-doc-"); self.addCleanup(shutil.rmtree, tmp, True)
        repo, cl = os.path.join(tmp, "repo"), os.path.join(tmp, "cl")
        os.makedirs(os.path.join(cl, "nomad")); os.makedirs(repo)
        d.CL = cl; d.ROWS.clear(); d.FIX.clear()
        return repo, cl

    def row(self, d):
        return [r for r in d.ROWS if r[1] == "모듈 등록부"]

    def test_registry_diff_warns_and_fix(self):
        d = self.load("a"); repo, cl = self.setup_dirs(d)
        open(os.path.join(repo, "modules.json"), "w").write('{"modules":{}}')
        open(os.path.join(cl, "nomad", "modules.json"), "w").write('{"modules":{"x":{}}}')
        d.check_global(repo)
        self.assertEqual(len(self.row(d)), 1); self.assertEqual(self.row(d)[0][2], "⚠️"); self.assertIn("global", d.FIX)

    def test_registry_same_ok_ignoring_crlf(self):
        d = self.load("b"); repo, cl = self.setup_dirs(d)
        open(os.path.join(repo, "modules.json"), "wb").write(b'{"a":1}\n')
        open(os.path.join(cl, "nomad", "modules.json"), "wb").write(b'{"a":1}\r\n')
        d.check_global(repo)
        self.assertEqual(self.row(d)[0][2], "✅")

    def test_registry_missing_installed_warns(self):
        d = self.load("c"); repo, cl = self.setup_dirs(d)
        open(os.path.join(repo, "modules.json"), "w").write("{}")
        d.check_global(repo)
        self.assertEqual(self.row(d)[0][2], "⚠️")


if __name__ == "__main__":
    unittest.main()
