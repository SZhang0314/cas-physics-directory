#!/usr/bin/env python3
"""Push the local directory to GitHub via the API (bypasses git-over-https).

Creates blobs, a tree, a commit, and updates refs/heads/main.
"""
import base64
import json
import subprocess
import sys
from pathlib import Path

OWNER = "SZhang0314"
REPO = "cas-physics-directory"
BRANCH = "main"

# Files to include (relative paths); skip .git and data/raw
SKIP_DIRS = {".git", "data/raw", "__pycache__"}
root = Path(".")


def gh(method, endpoint, payload=None):
    args = ["gh", "api", "-X", method, endpoint]
    if payload is not None:
        args += ["--input", "-"]
    proc = subprocess.run(args, input=(json.dumps(payload) if payload is not None else None),
                          capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"gh api {method} {endpoint} failed:\n{proc.stderr}\n{proc.stdout}")
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def collect():
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.as_posix()
        if any(rel == s or rel.startswith(s + "/") for s in SKIP_DIRS):
            continue
        if rel.startswith(".git/"):
            continue
        out.append(rel)
    return out


def main():
    files = collect()
    print(f"uploading {len(files)} files ...")
    tree = []
    for rel in files:
        data = Path(rel).read_bytes()
        b64 = base64.b64encode(data).decode()
        r = gh("POST", f"repos/{OWNER}/{REPO}/git/blobs",
               {"content": b64, "encoding": "base64"})
        tree.append({"path": rel, "mode": "100644", "type": "blob", "sha": r["sha"]})
        print(f"  blob {rel} -> {r['sha'][:8]}")

    # base tree (allow empty repo)
    base = None
    try:
        ref = gh("GET", f"repos/{OWNER}/{REPO}/git/ref/heads/{BRANCH}")
        base = ref["object"]["sha"]
    except Exception:
        base = None

    t = gh("POST", f"repos/{OWNER}/{REPO}/git/trees", {"tree": tree})
    commit_payload = {
        "message": "Add CAS physics institutes faculty directory (6 institutes, 1490 researchers)",
        "tree": t["sha"],
        "parents": [base] if base else [],
    }
    c = gh("POST", f"repos/{OWNER}/{REPO}/git/commits", commit_payload)
    print("commit:", c["sha"])

    if base:
        gh("PATCH", f"repos/{OWNER}/{REPO}/git/refs/heads/{BRANCH}",
           {"sha": c["sha"], "force": True})
    else:
        gh("POST", f"repos/{OWNER}/{REPO}/git/refs",
           {"ref": f"refs/heads/{BRANCH}", "sha": c["sha"]})
    print("pushed to refs/heads/" + BRANCH)


if __name__ == "__main__":
    main()
