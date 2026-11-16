import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("codex_team", ROOT / "global/nomad/bin/py/codex_team.py")
team = importlib.util.module_from_spec(spec); spec.loader.exec_module(team)

class CodexTeam(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_initializes_native_roles_and_checks(self):
        result = team.initialize(self.root, "gpt-6-luna")
        self.assertEqual(result["primary_model"], "gpt-6.1-sol")
        self.assertEqual(len(result["roles"]), 5)
        self.assertFalse(result["availability_verified"])
        self.assertEqual(team.check(self.root)["issues"], [])

    def test_preserves_sandbox_and_unrelated_tables(self):
        config = self.root / ".codex/config.toml"; config.parent.mkdir()
        original = 'approval_policy = "on-request"\nsandbox_mode = "read-only"\n\n[mcp_servers.example]\nurl = "https://example.com/mcp"\n'
        config.write_text(original, encoding="utf-8")
        team.initialize(self.root, "custom-supported-worker")
        text = config.read_text(encoding="utf-8")
        self.assertIn('sandbox_mode = "read-only"', text)
        self.assertIn('[mcp_servers.example]', text)
        self.assertEqual(config.with_name("config.toml.nomad-backup").read_text(encoding="utf-8"), original)

    def test_repeat_is_idempotent_and_updates_all_models(self):
        team.initialize(self.root, "worker-a")
        config = self.root / ".codex/config.toml"; once = config.read_text(encoding="utf-8")
        team.initialize(self.root, "worker-a")
        self.assertEqual(once, config.read_text(encoding="utf-8"))
        team.initialize(self.root, "worker-b")
        self.assertEqual(team.check(self.root)["worker_model"], "worker-b")
        self.assertEqual(team.check(self.root)["issues"], [])

    def test_conflicting_custom_role_prevents_partial_config_write(self):
        role = self.root / ".codex/agents/nomad_builder.toml"; role.parent.mkdir(parents=True)
        role.write_text('name = "my-builder"', encoding="utf-8")
        with self.assertRaises(ValueError): team.initialize(self.root, "worker")
        self.assertFalse((self.root / ".codex/config.toml").exists())
        self.assertEqual(role.read_text(encoding="utf-8"), 'name = "my-builder"')

    def test_invalid_model_does_not_write(self):
        with self.assertRaises(ValueError): team.initialize(self.root, 'bad"\nmodel="other')
        self.assertFalse((self.root / ".codex").exists())

    def test_check_detects_missing_role(self):
        team.initialize(self.root, "worker")
        (self.root / ".codex/agents/nomad_tester.toml").unlink()
        self.assertTrue(team.check(self.root)["issues"])

if __name__ == "__main__": unittest.main()
