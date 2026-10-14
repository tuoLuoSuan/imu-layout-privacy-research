"""Integration checks use isolated temporary repositories; no research data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

GUARD = Path(__file__).resolve().parents[1] / "repository_guard.py"


class RepositoryGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        (self.root / "hello.md").write_text("Reviewed source\n", encoding="utf-8")
        self.policy(["hello.md", "repository-policy.json"])

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args])

    def policy(self, files, **extra):
        (self.root / "repository-policy.json").write_text(
            json.dumps({"schema_version": 1, "allowed_files": files,
                        "binary_sha256": {}, **extra}), encoding="utf-8")

    def scan(self, mode="--candidate", *args):
        result = subprocess.run([sys.executable, str(GUARD), "--root", str(self.root),
                                 mode, *args], capture_output=True, text=True, encoding="utf-8")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_reviewed_utf8_source_passes(self):
        code, report = self.scan()
        self.assertEqual(code, 0, report)
        self.assertEqual(len(report["files"]), 2)

    def test_staged_secret_is_caught_even_when_worktree_is_clean(self):
        (self.root / "hello.md").write_text("-----BEGIN " + "PRIVATE KEY-----\n", encoding="utf-8")
        self.git("add", "hello.md", "repository-policy.json")
        (self.root / "hello.md").write_text("Clean worktree\n", encoding="utf-8")
        code, report = self.scan("--staged")
        self.assertEqual(code, 1)
        self.assertIn("private_key", str(report))

    def test_unlisted_staged_file_blocks_entire_index(self):
        (self.root / "extra.md").write_text("unreviewed", encoding="utf-8")
        self.git("add", "hello.md", "extra.md", "repository-policy.json")
        code, report = self.scan("--staged")
        self.assertEqual(code, 1)
        self.assertIn("not_allowlisted", str(report))

    def test_policy_cannot_allow_raw_recordings_or_archives(self):
        for name in ("data/raw/phone.csv", "session.zip", "secret.pem"):
            with self.subTest(name=name):
                self.policy([name, "repository-policy.json"])
                target = self.root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("should never be staged", encoding="utf-8")
                code, report = self.scan()
                self.assertEqual(code, 1)
                self.assertIn("private_path", str(report))

    def test_unsafe_policy_path_fails_closed(self):
        self.policy(["../outside.md"])
        code, report = self.scan()
        self.assertEqual(code, 1)
        self.assertIn("unsafe_path", str(report))

    def test_allowlist_tree_mismatch_blocks_incomplete_backup(self):
        self.git("add", "repository-policy.json")
        code, report = self.scan("--staged")
        self.assertEqual(code, 1)
        self.assertIn("allowlisted_file_missing_from_tree", str(report))

    @unittest.skipUnless(sys.platform == "win32", "Windows junction check")
    def test_junction_parent_is_rejected(self):
        target = self.root / "target"
        target.mkdir()
        (target / "item.md").write_text("safe", encoding="utf-8")
        junction = self.root / "linked"
        # Both resolved targets stay inside this named temporary repository.
        self.assertTrue(target.resolve().is_relative_to(self.root.resolve()))
        result = subprocess.run([
            "powershell", "-NoProfile", "-Command",
            "New-Item -ItemType Junction -Path $env:IMU_TEST_JUNCTION -Target $env:IMU_TEST_TARGET | Out-Null"],
            env={**os.environ, "IMU_TEST_JUNCTION": str(junction), "IMU_TEST_TARGET": str(target)},
            capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.policy(["linked/item.md", "repository-policy.json"])
        code, report = self.scan()
        self.assertEqual(code, 1)
        self.assertIn("unreadable_or_link", str(report))

    def test_unapproved_binary_and_modified_binary_fail(self):
        import hashlib
        content = b"\x00\xffknown tool"
        (self.root / "tool.jar").write_bytes(content)
        files = ["tool.jar", "repository-policy.json"]
        self.policy(files)
        self.assertEqual(self.scan()[0], 1)
        self.policy(files, binary_sha256={"tool.jar": hashlib.sha256(content).hexdigest()})
        self.assertEqual(self.scan()[0], 0)
        (self.root / "tool.jar").write_bytes(content + b"changed")
        self.assertEqual(self.scan()[0], 1)

    def test_private_endpoint_blocks_without_echoing_value(self):
        endpoint = ".".join(("192", "168", "60", "135"))
        (self.root / "hello.md").write_text(endpoint, encoding="utf-8")
        code, report = self.scan()
        self.assertEqual(code, 1)
        self.assertIn("private_endpoint", str(report))
        self.assertNotIn(endpoint, str(report))

    def test_missing_candidate_fails(self):
        self.policy(["missing.md", "repository-policy.json"])
        code, report = self.scan()
        self.assertEqual(code, 1)
        self.assertIn("unreadable", str(report))

    def test_symlink_is_not_dereferenced(self):
        link = self.root / "link.md"
        try:
            link.symlink_to(self.root / "hello.md")
        except OSError:
            self.skipTest("Symlink creation privilege unavailable")
        self.policy(["link.md", "repository-policy.json"])
        self.assertEqual(self.scan()[0], 1)
        self.git("add", "link.md", "repository-policy.json")
        self.assertEqual(self.scan("--staged")[0], 1)

    def test_revision_is_scanned_independently_of_worktree(self):
        self.git("add", "hello.md", "repository-policy.json")
        self.git("commit", "-qm", "fixture")
        (self.root / "hello.md").write_bytes(b"\x00bad worktree")
        self.assertEqual(self.scan("--revision", "HEAD")[0], 0)


if __name__ == "__main__":
    unittest.main()
