"""Inspect reviewed worktree candidates, the COMPLETE index, or a commit tree.

No third-party dependencies. Reports never include matching secret text.
This guard prevents common accidental uploads; it is not a PII classifier.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

POLICY = "repository-policy.json"
PRIVATE_ROOTS = (
    "data/raw/", "data/ground_truth/", "datasets/", "environment/reports/",
    "environment/vendor/", "docs/evidence/", "docs/reviews/", "docs/references/",
    "research-tools/", "showcase/data/", "showcase/assets/", "backups/",
    "attachments/", ".codex-remote-attachments/", ".learnings/", ".ssh/",
    "collection/band9pro-probe/recordings/",
)
PRIVATE_SUFFIXES = {
    ".zip", ".7z", ".rar", ".apk", ".rpk", ".bag", ".db3", ".mcap",
    ".pcd", ".ply", ".las", ".laz", ".mp4", ".mov", ".avi", ".jpg",
    ".jpeg", ".pdf", ".pem", ".key", ".jks", ".keystore", ".p12", ".pfx",
    ".pt", ".pth", ".onnx", ".pkl", ".joblib", ".log", ".csv", ".jsonl",
}
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "private_endpoint": re.compile(r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"),
    "private_account_path": re.compile(r"(?:/home/(?:suan)(?:/|\b)|[CD]:[/\\]Users[/\\]Hello[/\\])", re.I),
}


def safe_path(name):
    parts = PurePosixPath(name).parts
    return (bool(name) and "\\" not in name and ":" not in name
            and not name.startswith("/") and all(p not in ("", ".", "..") for p in parts)
            and str(PurePosixPath(name)) == name
            and not any(ord(c) < 32 for c in name))


def private_path(name):
    lower = name.lower()
    parts = lower.split("/")
    return (lower.startswith(PRIVATE_ROOTS) or any(
        p in {".git", ".cache", ".gradle", "node_modules", "__pycache__", "build",
              "dist", "secrets", "sign", "output"} or p.startswith(".tmp") for p in parts)
        or PurePosixPath(lower).suffix in PRIVATE_SUFFIXES
        or any(p == ".env" or (p.startswith(".env.") and p != ".env.example") for p in parts)
        or lower.endswith(("/local.properties", ".tar.gz")))


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def tree_entries(root, revision):
    entries = {}
    if revision is None:
        raw = git(root, "ls-files", "--stage", "-z")
    else:
        raw = git(root, "ls-tree", "-rz", "--full-tree", revision)
    for item in raw.split(b"\0"):
        if not item:
            continue
        fields, raw_path = item.split(b"\t", 1)
        mode, middle, final = fields.decode("ascii").split()
        name = raw_path.decode("utf-8", errors="strict")
        if name in entries:
            raise ValueError("duplicate/unmerged index path")
        entries[name] = (mode, middle if revision is None else final,
                         final == "0" if revision is None else middle == "blob")
    return entries


def candidate_bytes(root, name):
    target = root / name
    current = target
    while current != root:
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise ValueError("link_or_reparse_point")
        current = current.parent
    if not target.is_file():
        raise ValueError("not_regular_file")
    if target.stat().st_size > 2_000_000:
        raise ValueError("oversized_file")
    return target.read_bytes()


def scan(root, mode, revision=None):
    report = {"schema_version": 1, "mode": mode, "revision": revision,
              "files": [], "findings": []}

    def finding(path, reason, line=None):
        item = {"path": path, "reason": reason}
        if line is not None:
            item["line"] = line
        report["findings"].append(item)

    entries = None if mode == "candidate" else tree_entries(root, revision)

    def read(name):
        if entries is None:
            return candidate_bytes(root, name)
        filemode, oid, normal = entries[name]
        if filemode not in ("100644", "100755") or not normal:
            raise ValueError("link_submodule_or_unmerged")
        size = int(git(root, "cat-file", "-s", oid))
        if size > 2_000_000:
            raise ValueError("oversized_file")
        return git(root, "cat-file", "blob", oid)

    policy_bytes = read(POLICY)
    policy = json.loads(policy_bytes.decode("utf-8-sig"))
    if policy.get("schema_version") != 1:
        raise ValueError("unsupported_policy")
    allowed = policy["allowed_files"]
    if not isinstance(allowed, list) or not allowed or any(not isinstance(p, str) for p in allowed):
        raise ValueError("invalid_allowlist")
    if len({p.casefold() for p in allowed}) != len(allowed):
        raise ValueError("duplicate_or_case_colliding_allowlist")
    report["policy_sha256"] = hashlib.sha256(policy_bytes).hexdigest()
    if entries is not None:
        for missing in sorted(set(allowed) - set(entries)):
            finding(missing, "allowlisted_file_missing_from_tree")
    names = allowed if entries is None else sorted(entries)
    for name in names:
        if not safe_path(name):
            finding(name, "unsafe_path")
            continue
        if name not in allowed:
            finding(name, "not_allowlisted")
            continue
        if private_path(name):
            finding(name, "private_path")
            continue
        try:
            content = read(name)
        except (OSError, ValueError, KeyError):
            finding(name, "unreadable_or_link")
            continue
        digest = hashlib.sha256(content).hexdigest()
        report["files"].append({"path": name, "bytes": len(content), "sha256": digest})
        binary_digest = policy.get("binary_sha256", {}).get(name)
        if binary_digest:
            if digest != binary_digest:
                finding(name, "binary_hash_mismatch")
            continue
        try:
            text = content.decode("utf-8-sig")
            if "\0" in text:
                raise UnicodeError("binary")
        except UnicodeError:
            finding(name, "unapproved_binary")
            continue
        # UTF-8 packaged archives/images are still binary by extension.
        if PurePosixPath(name).suffix.lower() in {".jar", ".png", ".exe", ".dll", ".bin"}:
            finding(name, "unapproved_binary")
        for category, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                finding(name, category, text.count("\n", 0, match.start()) + 1)
    report["passed"] = not report["findings"]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--candidate", action="store_true")
    modes.add_argument("--staged", action="store_true")
    modes.add_argument("--revision")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        mode = "candidate" if args.candidate else "staged" if args.staged else "revision"
        report = scan(args.root.resolve(), mode, args.revision)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        report = {"passed": False, "files": [], "findings": [{"reason": "scan_input_error"}]}
    output = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
