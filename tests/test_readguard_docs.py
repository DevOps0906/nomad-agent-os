import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RG = Path(__file__).resolve().parents[1] / "global/nomad/bin/py/readguard.py"


def doc_text(extra=""):
    body = ["# 제목", "소개 문단입니다."]
    body += [f"소개 {i}" for i in range(30)]
    body += ["## 둘째 장", "둘째 장 첫 줄"] + [f"둘째 {i}" for i in range(30)]
    body += ["```", "# 펜스 안 제목", "```", "## 셋째 장", "셋째 장 첫 줄" + extra] + [f"셋째 {i}" for i in range(30)]
    return "\n".join(body) + "\n"


class DocGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.doc = self.root / "plan.md"
        self.doc.write_text(doc_text(), encoding="utf-8")

    def run_hook(self, mode, tool, sess, env=None, **ti):
        d = {"tool_name": tool, "tool_input": {"file_path": str(self.doc), **ti}, "cwd": str(self.root), "session_id": sess}
        e = dict(os.environ, PYTHONIOENCODING="utf-8", **(env or {}))
        return subprocess.run([sys.executable, str(RG), mode], input=json.dumps(d), capture_output=True,
                              text=True, encoding="utf-8", env=e, cwd=str(self.root))

    def test_new_session_gets_toc_with_changed_section_first(self):
        self.assertEqual(self.run_hook("post", "Read", "s1").returncode, 0)
        self.assertTrue((self.root / ".nomad/read/docs.json").exists())
        self.doc.write_text(doc_text(" 수정됨"), encoding="utf-8")
        r = self.run_hook("pre", "Read", "s2")
        self.assertEqual(r.returncode, 2)
        self.assertIn("[바뀜]", r.stderr)
        self.assertIn("[변경 없음]", r.stderr)
        self.assertNotIn("펜스 안 제목", r.stderr)
        self.assertIn("먼저 이것만 offset/limit로", r.stderr)
        self.assertLess(len(r.stderr), 9100)
        # 같은 요청 두 번째는 허용
        self.assertEqual(self.run_hook("pre", "Read", "s2").returncode, 0)

    def test_ranged_read_allowed_and_marks_only_overlapping_sections(self):
        self.run_hook("post", "Read", "s1", offset=1, limit=32)
        r = self.run_hook("pre", "Read", "s2")
        self.assertEqual(r.returncode, 2)
        self.assertIn("[안 읽음]", r.stderr)
        self.assertIn("[변경 없음]", r.stderr)
        self.assertEqual(self.run_hook("pre", "Read", "s2", offset=40, limit=10).returncode, 0)

    def test_first_time_and_small_and_disabled_pass(self):
        self.assertEqual(self.run_hook("pre", "Read", "s1").returncode, 0)
        self.run_hook("post", "Read", "s1")
        self.assertEqual(self.run_hook("pre", "Read", "s2", env={"NOMAD_DOCGUARD": "0"}).returncode, 0)
        small = self.root / "small.md"; small.write_text("# a\nb\n", encoding="utf-8")
        self.doc = small
        self.run_hook("post", "Read", "s1")
        self.assertEqual(self.run_hook("pre", "Read", "s2").returncode, 0)

    def test_write_marks_all_seen(self):
        self.run_hook("post", "Write", "s1")
        self.assertEqual(self.run_hook("pre", "Read", "s2").returncode, 2)
        r = self.run_hook("pre", "Read", "s3")
        self.assertNotIn("[안 읽음]", r.stderr)

    def test_partial_overlap_does_not_mark_seen(self):
        self.run_hook("post", "Read", "s1", offset=1, limit=10)
        r = self.run_hook("pre", "Read", "s2")
        self.assertNotIn("[변경 없음]", r.stderr)

    def test_edit_marks_only_section_with_new_string(self):
        self.run_hook("post", "Read", "s1")
        self.doc.write_text(doc_text(" 수정됨").replace("둘째 3\n", "둘째 3 외부\n"), encoding="utf-8")
        self.run_hook("post", "Edit", "s1", new_string="셋째 장 첫 줄 수정됨")
        r = self.run_hook("pre", "Read", "s2")
        self.assertIn("[바뀜]", r.stderr)          # 외부에서 바뀐 둘째 장은 그대로
        self.assertEqual(r.stderr.count("[바뀜]"), 1)
        self.assertEqual(self.run_hook("post", "Edit", "s1", new_string="없는 문자열").returncode, 0)
        self.assertEqual(self.run_hook("pre", "Read", "s3").stderr.count("[바뀜]"), 1)

    def test_edit_without_docs_entry_records_nothing(self):
        self.run_hook("post", "Edit", "s1", new_string="셋째 장 첫 줄")
        self.assertFalse((self.root / ".nomad/read/docs.json").exists())

    def test_summary_skips_fence_and_tags(self):
        sys.path.insert(0, str(RG.parent))
        import readguard
        secs = readguard.split_sections(["## A", "", "```python", "<details>", "진짜 요지", "```", "## B", "### C", "x"])
        self.assertEqual(secs[0]["summary"], "진짜 요지")
        self.assertEqual(secs[1]["summary"], "")
        secs = readguard.split_sections(["## A", "<details>", "```", "본문"])
        self.assertEqual(secs[0]["summary"], "본문")

    def test_docmap_cli(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        run = lambda *a: subprocess.run([sys.executable, str(RG), "docmap", *a], capture_output=True, text=True,
                                        encoding="utf-8", env=env, cwd=str(self.root))
        self.assertIn("[안 읽음]", run(str(self.doc)).stdout)
        self.assertEqual(run("--mark", str(self.doc)).returncode, 0)
        out = run(str(self.doc)).stdout
        self.assertNotIn("[안 읽음]", out)
        self.assertIn("[변경 없음]", out)


if __name__ == "__main__":
    unittest.main()
