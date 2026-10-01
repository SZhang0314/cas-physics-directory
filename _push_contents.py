#!/usr/bin/env python3
"""Push local files to GitHub via the Contents API (works on empty repos)."""
import base64
import json
import subprocess
from pathlib import Path

OWNER = "SZhang0314"
REPO = "cas-physics-directory"
BRANCH = "main"
SKIP_DIRS = {".git", "data/raw", "__pycache__"}
root = Path(".")


def gh(method, endpoint, payload=None):
    args = ["gh", "api", "-X", method, endpoint]
    if payload is not None:
        args += ["--input", "-"]
    proc = subprocess.run(args,
                          input=(json.dumps(payload) if payload is not None else None),
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
        if any(rel == s or rel.startswith(s + "/") for s in SKIP_DIRS) or rel.startswith(".git/"):
            continue
        out.append(rel)
    return out


def main():
    files = collect()
    # order: put a small file first so the empty-repo case gets seeded
    files.sort(key=lambda f: Path(f).stat().st_size)
    print(f"uploading {len(files)} files via Contents API ...")
    for rel in files:
        data = Path(rel).read_bytes()
        b64 = base64.b64encode(data).decode()
        payload = {"message": f"Add {rel}", "content": b64, "branch": BRANCH}
        # if file already exists, need its sha
        try:
            existing = gh("GET", f"repos/{OWNER}/{REPO}/contents/{rel}?ref={BRANCH}")
            if isinstance(existing, dict) and existing.get("sha"):
                payload["sha"] = existing["sha"]
        except Exception:
            pass
        r = gh("PUT", f"repos/{OWNER}/{REPO}/contents/{rel}", payload)
        sha = (r.get("commit") or {}).get("sha", "")[:8]
        print(f"  {rel} -> commit {sha}")


if __name__ == "__main__":
    main()
