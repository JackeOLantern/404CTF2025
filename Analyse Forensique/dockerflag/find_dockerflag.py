#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dockerflag history – automated solver
-------------------------------------
Reproduces the forensic approach described in the "Dockerflag history" steps:
 1) Load / inspect image (optional)
 2) Extract layers from docker save tar (or OCI-like bundle)
 3) Hunt for .git repos left behind despite "RUN rm -rf .git"
 4) Walk commit history to recover a .env file that contains the flag
 5) Fallback searches (grep-like): 404CTF, SECRET=, dotenv patterns

USAGE
-----
  python3 find_dockerflag.py /path/to/dockerflag.tar

OPTIONS
-------
  --use-docker        : attempt `docker load` and `docker history` like in the manual steps
  --workdir DIR       : extraction working directory (default: ./dockerflag_extracted)
  --max-bytes N       : limit for content previews
  --print-greps       : also print grep-like hits (SECRET=, dotenv lines)

NOTES
-----
* No `git` binary is required. The script reads the .git object database directly
  (zlib-inflated loose objects) and walks first-parent history to locate `.env`.
* If Docker is present and `--use-docker` is set, the script will try to mimic:
    docker load < dockerflag.tar
    docker history <image>
  to help the analyst see the "RUN rm -rf .git" layer hint.
"""

import argparse
import base64
import binascii
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import zlib
from typing import Dict, List, Optional, Tuple

# ----------------------------
# Pretty printing helpers
# ----------------------------
def info(msg): print(f"[i] {msg}")
def ok(msg):   print(f"[+] {msg}")
def warn(msg): print(f"[!] {msg}")
def err(msg):  print(f"[x] {msg}", file=sys.stderr)

# ----------------------------
# Docker helpers (optional)
# ----------------------------
def try_docker_load(image_tar: str) -> Optional[List[str]]:
    """Try `docker load` and return repo tags for the loaded image, if any."""
    try:
        p = subprocess.run(["docker", "load", "-i", image_tar], capture_output=True, text=True, check=False)
        if p.returncode != 0:
            warn(f"docker load failed: {p.stderr.strip()}")
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        tags = []
        for line in out.splitlines():
            # Typical: "Loaded image: repo/name:tag"
            if "Loaded image:" in line:
                t = line.split("Loaded image:",1)[1].strip()
                if t: tags.append(t)
        if tags:
            ok(f"Docker loaded with tags: {tags}")
            return tags
        else:
            warn("No repo tags found from docker load output.")
            return None
    except FileNotFoundError:
        warn("Docker binary not found; skipping docker load.")
        return None

def try_docker_history(image_ref: str):
    """Try `docker history` like the manual approach, non-fatal on errors."""
    try:
        info(f"docker history {image_ref}")
        p = subprocess.run(["docker", "history", image_ref], capture_output=True, text=True, check=False)
        print(p.stdout)
        if p.returncode != 0:
            warn(p.stderr.strip())
    except FileNotFoundError:
        warn("Docker binary not found; cannot run docker history.")

# ----------------------------
# TAR / layers extraction
# ----------------------------
def safe_extract_all(tar_path: str, out_dir: str):
    with tarfile.open(tar_path, "r:*") as tf:
        def is_within_directory(directory, target):
            abs_directory = os.path.abspath(directory)
            abs_target = os.path.abspath(target)
            prefix = os.path.commonprefix([abs_directory, abs_target])
            return prefix == abs_directory
        for m in tf.getmembers():
            target = os.path.join(out_dir, m.name)
            if not is_within_directory(out_dir, target):
                raise Exception("Path traversal risk in tar file")
        tf.extractall(out_dir)

def extract_image_top(tar_path: str, workdir: str) -> Dict[str, str]:
    """
    Extract the docker save / OCI-like tar to workdir.
    Return a dict with keys:
      - manifest
      - layer_archives (list)
    Accepts files named like <digest>.tar.gz as well as standard docker-save layout.
    """
    os.makedirs(workdir, exist_ok=True)
    info(f"Extracting top-level tar to {workdir} ...")
    safe_extract_all(tar_path, workdir)
    # Collect potential layer archives
    layer_archives = []
    manifest_path = None
    for root, dirs, files in os.walk(workdir):
        for f in files:
            p = os.path.join(root, f)
            if f == "manifest.json" and manifest_path is None:
                manifest_path = p
            if f.endswith(".tar") or f.endswith(".tar.gz") or f.endswith(".tgz"):
                layer_archives.append(p)
    if manifest_path:
        ok(f"Found manifest.json at {manifest_path}")
    else:
        warn("No manifest.json found; will process all tar/tar.gz as layers (OCI-like bundle?)")
    info(f"Found {len(layer_archives)} potential layer archives.")
    return {"manifest": manifest_path or "", "layers": layer_archives}

def extract_layers(layer_archives: List[str], out_root: str) -> List[str]:
    """Extract each layer tar[.gz] to its own folder and return the list of extraction dirs."""
    os.makedirs(out_root, exist_ok=True)
    extracted_dirs = []
    for arc in layer_archives:
        base = os.path.basename(arc).replace(".tar.gz","").replace(".tgz","").replace(".tar","")
        out_dir = os.path.join(out_root, base)
        os.makedirs(out_dir, exist_ok=True)
        try:
            with tarfile.open(arc, "r:*") as tf:
                tf.extractall(out_dir)
            extracted_dirs.append(out_dir)
            info(f"Extracted layer {os.path.basename(arc)} -> {out_dir}")
        except Exception as e:
            warn(f"Failed to extract {arc}: {e}")
    ok(f"Extracted {len(extracted_dirs)} layer directories.")
    return extracted_dirs

# ----------------------------
# Grep-like scanning
# ----------------------------
DOTENV_RE = re.compile(rb"(?im)^[A-Z0-9_]{2,40}=[^\r\n]{1,200}$")
FLAG_RE   = re.compile(rb"404CTF\{[^}\r\n]{0,200}\}")
KEYWORDS  = [b"404CTF", b"SECRET", b"secret", b"FLAG", b"flag", b"password", b"PASSWORD", b"token", b"API_KEY", b"dotenv"]

def scan_bytes_for_hits(b: bytes):
    hits = {}
    m = FLAG_RE.findall(b)
    if m: hits["flag"] = [x.decode("utf-8","ignore") for x in m]
    envs = DOTENV_RE.findall(b)
    if envs: hits["dotenv"] = [x.decode("utf-8","ignore") for x in envs[:50]]
    for kw in KEYWORDS:
        if kw in b:
            ctx = re.findall(rb".{0,48}"+re.escape(kw)+rb".{0,48}", b)
            if ctx:
                hits.setdefault("keywords", []).extend([x.decode("utf-8","ignore") for x in ctx[:10]])
    return hits

def grep_layers(layer_dirs: List[str], print_greps: bool=False) -> Dict[str, List[Dict]]:
    results = {"flags": [], "dotenvs": [], "keyword_hits": []}
    for d in layer_dirs:
        for root, _, files in os.walk(d):
            for fn in files:
                p = os.path.join(root, fn)
                try:
                    with open(p, "rb") as fh: b = fh.read()
                except Exception:
                    continue
                h = scan_bytes_for_hits(b)
                if "flag" in h:
                    ok(f"[FLAG] direct in {p}: {h['flag'][:1]}")
                    results["flags"].append({"file": p, "flag": h["flag"][0]})
                if "dotenv" in h:
                    results["dotenvs"].append({"file": p, "lines": h["dotenv"]})
                    if print_greps:
                        info(f"[.env-like] {p}")
                if "keywords" in h and print_greps:
                    results["keyword_hits"].append({"file": p, "samples": h["keywords"]})
    return results

# ----------------------------
# Minimal Git object reader
# ----------------------------
def git_read_loose_object(repo: str, sha: str) -> Tuple[str, int, bytes]:
    obj = os.path.join(repo, "objects", sha[:2], sha[2:])
    with open(obj, "rb") as f:
        raw = zlib.decompress(f.read())
    i = raw.find(b" ")
    type_name = raw[:i].decode()
    j = raw.find(b"\x00", i+1)
    size = int(raw[i+1:j])
    data = raw[j+1:]
    return type_name, size, data

def git_parse_commit(data: bytes) -> Tuple[Dict[str, List[str]], str]:
    lines = data.split(b"\n")
    meta = {}
    msg_idx = 0
    for i, line in enumerate(lines):
        if line == b"":
            msg_idx = i+1
            break
        k, v = line.split(b" ", 1)
        meta.setdefault(k.decode(), []).append(v.decode("utf-8", "ignore"))
    message = b"\n".join(lines[msg_idx:]).decode("utf-8", "ignore")
    return meta, message

def git_parse_tree(data: bytes) -> List[Tuple[str, str, str]]:
    i = 0
    out = []
    while i < len(data):
        j = data.find(b" ", i)
        mode = data[i:j].decode()
        k = data.find(b"\x00", j+1)
        name = data[j+1:k].decode()
        sha = binascii.hexlify(data[k+1:k+21]).decode()
        out.append((mode, name, sha))
        i = k+21
    return out

def git_find_branches(repo: str) -> List[str]:
    heads = os.path.join(repo, "refs", "heads")
    found = []
    for root, _, files in os.walk(heads):
        for fn in files:
            found.append(os.path.join(root, fn))
    return found

def git_read_ref(repo: str, ref_path: str) -> Optional[str]:
    try:
        with open(ref_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None

def git_walk_history_for_env(repo: str, start_sha: str, max_steps: int=200) -> Optional[Tuple[str, str]]:
    """Walk first-parent history to find a .env blob. Return (commit_sha, env_text) or None."""
    seen = set()
    cur = start_sha
    for _ in range(max_steps):
        if not cur or cur in seen:
            break
        seen.add(cur)
        t, sz, data = git_read_loose_object(repo, cur)
        meta, msg = git_parse_commit(data)
        tree_sha = meta["tree"][0]
        # scan the tree for '.env'
        stack = [("", tree_sha)]
        while stack:
            prefix, tsha = stack.pop()
            tt, tsz, tdata = git_read_loose_object(repo, tsha)
            for mode, name, sha in git_parse_tree(tdata):
                if mode.startswith("040000"):
                    stack.append((prefix + name + "/", sha))
                else:
                    if name == ".env":
                        bt, bsz, bdata = git_read_loose_object(repo, sha)
                        try:
                            env_txt = bdata.decode("utf-8", "ignore")
                        except Exception:
                            env_txt = ""
                        return cur, env_txt
        parents = meta.get("parent", [])
        cur = parents[0] if parents else None
    return None

def hunt_git_and_flag(layer_dirs: List[str], print_greps: bool=False) -> Optional[str]:
    """Find .git repos in extracted layers, and try to recover .env from history."""
    found_flag = None
    for d in layer_dirs:
        for root, dirs, files in os.walk(d):
            if ".git" in dirs:
                repo = os.path.join(root, ".git")
                ok(f"Found Git repo: {repo}")
                # prefer HEAD if present; else try refs/heads/main or master
                head_path = os.path.join(repo, "HEAD")
                start_sha = None
                if os.path.isfile(head_path):
                    try:
                        content = open(head_path,"r",encoding="utf-8").read().strip()
                        if content.startswith("ref:"):
                            ref = content.split(" ",1)[1].strip()
                            start_sha = git_read_ref(repo, os.path.join(repo, ref))
                        else:
                            start_sha = content
                    except Exception:
                        start_sha = None
                if not start_sha:
                    # fallback: scan heads
                    heads = git_find_branches(repo)
                    # prioritize 'main', then 'master', else first
                    prefer = [h for h in heads if h.endswith("/main")] or [h for h in heads if h.endswith("/master")] or heads
                    if not prefer:
                        warn("No git heads found in repo.")
                        continue
                    start_sha = git_read_ref(repo, prefer[0])
                    info(f"Using branch: {prefer[0].split(os.sep)[-1]} -> {start_sha}")
                if not start_sha:
                    warn("Unable to resolve start commit for repo.")
                    continue
                res = git_walk_history_for_env(repo, start_sha)
                if res:
                    commit_sha, env_text = res
                    ok(f".env recovered from commit {commit_sha}")
                    print("----- .env -----")
                    print(env_text.strip())
                    print("----------------")
                    m = FLAG_RE.search(env_text.encode("utf-8", "ignore"))
                    if m:
                        found_flag = m.group(0).decode("utf-8", "ignore")
                        ok(f"FLAG recovered: {found_flag}")
                        return found_flag
                else:
                    warn("No .env found in git history (first-parent scan).")
    return found_flag

# ----------------------------
# Main
# ----------------------------
def main():
    ap = argparse.ArgumentParser(description="Dockerflag history – automated solver")
    ap.add_argument("image_tar", help="Path to docker save tar (dockerflag.tar)")
    ap.add_argument("--use-docker", action="store_true", help="Try docker load/history like the manual steps")
    ap.add_argument("--workdir", default="dockerflag_extracted", help="Extraction working directory")
    ap.add_argument("--max-bytes", type=int, default=120, help="Preview size for prints")
    ap.add_argument("--print-greps", action="store_true", help="Also print grep-like hits")
    args = ap.parse_args()

    # 1) Optional: use Docker like the manual history
    repo_tags = None
    if args.use_docker:
        repo_tags = try_docker_load(args.image_tar)
        if repo_tags:
            for tag in repo_tags:
                try_docker_history(tag)
        else:
            warn("No tags loaded; cannot run docker history with a reference.")

    # 2) Extract top-level tar
    layout = extract_image_top(args.image_tar, args.workdir)

    # 3) Extract layers
    layers_root = os.path.join(args.workdir, "layers")
    layer_dirs = extract_layers(layout["layers"], layers_root)

    # 4) Quick grep-like scans (optional prints)
    scans = grep_layers(layer_dirs, print_greps=args.print_greps)

    # 5) Hunt for .git and recover .env from history
    flag = hunt_git_and_flag(layer_dirs, print_greps=args.print_greps)

    print("==== SUMMARY ====")
    print(f"Layers extracted: {len(layer_dirs)}")
    print(f"Direct flag hits: {len(scans['flags'])}")
    print(f".env-like files:  {len(scans['dotenvs'])}")
    print(f"FLAG (history):   {flag or 'not found'}")

    if not flag:
        warn("No flag via git history; you may want to inspect grep hits (`--print-greps`) or check non-first-parent merges.")

if __name__ == "__main__":
    main()
