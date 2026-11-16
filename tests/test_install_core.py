"""install.sh add_core 갱신 로직 테스트. 함수만 잘라 임시 HOME에서 실행(실제 ~/.claude·~/.codex 불변)."""
import os, re, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
S, E = "<!-- NOMAD CORE START -->", "<!-- NOMAD CORE END -->"


def posix(p):
    return p.replace("\\", "/")


class AddCore(unittest.TestCase):
    def setUp(self):
        self.bash = next((b for b in (r"C:\Program Files\Git\bin\bash.exe", shutil.which("bash")) if b and os.path.exists(b)), None)
        if not self.bash:
            self.skipTest("bash 없음")
        self.tmp = tempfile.mkdtemp(prefix="nomad-core-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cl = os.path.join(self.tmp, "claude"); os.makedirs(os.path.join(self.cl, "nomad"))
        self.bk = os.path.join(self.tmp, "bk")
        self.f = os.path.join(self.tmp, "codex", "AGENTS.md")
        src = open(os.path.join(ROOT, "install.sh"), encoding="utf-8").read()
        m = re.search(r"^add_core\(\) \{.*?^\}\n", src, re.S | re.M)
        self.assertTrue(m, "add_core 함수를 찾지 못함")
        self.func = m.group(0)
        self.set_core("# NOMAD CORE v1\n\n## 규칙\n- 하나\n")

    def set_core(self, txt):
        open(os.path.join(self.cl, "nomad", "CORE.md"), "w", encoding="utf-8", newline="").write(txt)

    def run_core(self):
        env = os.environ.copy()   # WSL bash 는 환경변수를 안 넘기므로 스크립트 안에서 지정
        script = 'CL="%s"; BK="%s"; PY="%s"\n' % (posix(self.cl), posix(self.bk), posix(sys.executable)) + self.func + '\nadd_core "%s" Test\n' % posix(self.f)
        sh = os.path.join(self.tmp, "run.sh")
        open(sh, "w", encoding="utf-8", newline="\n").write(script)
        r = subprocess.run([self.bash, "run.sh"], cwd=self.tmp, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def read(self):
        return open(self.f, encoding="utf-8", newline="").read()

    def write(self, txt):
        os.makedirs(os.path.dirname(self.f), exist_ok=True)
        open(self.f, "w", encoding="utf-8", newline="").write(txt)

    def test_add_new_and_idempotent(self):
        self.assertIn("+", self.run_core())
        t = self.read()
        self.assertTrue(t.startswith(S) and t.rstrip().endswith(E))
        self.assertIn("유지", self.run_core())
        self.assertEqual(self.read(), t)

    def test_add_preserves_user_content(self):
        self.write("# 내 규칙\n- 유지\n")
        self.run_core()
        t = self.read()
        self.assertTrue(t.startswith("# 내 규칙\n- 유지\n"))
        self.assertIn(S, t)

    def test_legacy_replaced_up_to_next_h1(self):
        self.write("# 앞\nA\n\n# NOMAD CORE 구버전\n\n## 옛\n- 옛것\n\n# 뒤\nB\n")
        out = self.run_core()
        self.assertIn("갱신", out)
        t = self.read()
        self.assertNotIn("옛것", t)
        self.assertTrue(t.startswith("# 앞\nA\n\n" + S))
        self.assertTrue(t.endswith(E + "\n\n# 뒤\nB\n"))
        self.assertEqual(t.count("# NOMAD CORE"), 1)
        self.assertTrue(os.path.isdir(self.bk) and os.listdir(self.bk))
        self.assertIn("유지", self.run_core())

    def test_legacy_to_end(self):
        self.write("# 앞\nA\n\n# NOMAD CORE\n- 옛것\n")
        self.run_core()
        t = self.read()
        self.assertTrue(t.startswith("# 앞\nA\n\n" + S) and t.endswith(E + "\n"))

    def test_markers_replaced(self):
        self.run_core()
        self.write("위\n" + self.read() + "\n# 아래\nC\n")
        self.set_core("# NOMAD CORE v2\n\n## 규칙\n- 둘\n")
        self.assertIn("갱신", self.run_core())
        t = self.read()
        self.assertIn("v2", t)
        self.assertNotIn("v1", t)
        self.assertTrue(t.startswith("위\n" + S) and t.endswith("\n# 아래\nC\n"))
        self.assertIn("유지", self.run_core())


if __name__ == "__main__":
    unittest.main()
