"""Prepare independent GRAMM variants from the pinned public upstream commit."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
VARIANTS = {
    "baseline": ("warnings", "work/build/baseline_clean", None),
    "pressure": ("pressure", "build/pressure", "0002_pressure.patch"),
    "tdma": ("tdma", "build/tdma", "0003_tdma.patch"),
    "radiation": ("radiation", "qa/radiation/build", "0004_radiation.patch"),
    "scalar_tdma": ("scalar_tdma", "build/scalar_tdma", "0005_scalar_tdma.patch"),
}


def command(args, cwd, timeout=300):
    print("RUN", subprocess.list2cmdline([str(x) for x in args]), flush=True)
    subprocess.run([str(x) for x in args], cwd=cwd, check=True, timeout=timeout)


def git_output(repo, *args):
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def prepare(root, repository, dotnet, skip_build):
    manifest = json.loads((HERE / "staging_manifest.json").read_text(encoding="utf-8"))
    base = manifest["upstream_commit"]
    root = root.resolve()
    if root != HERE:
        if root.exists() and any(root.iterdir()):
            raise RuntimeError("Choose an empty reproduction workspace: " + str(root))
        root.mkdir(parents=True, exist_ok=True)
        for folder in ("work", "qa", "patches"):
            shutil.copytree(HERE / folder, root / folder)
        shutil.copy2(HERE / "staging_manifest.json", root / "staging_manifest.json")
        for name in ("README.md", "prepare_sources.py", "run_components.py"):
            shutil.copy2(HERE / name, root / name)
    work = root / "work"
    upstream = work / "upstream"
    if upstream.exists() or any((work / folder).exists() for folder, _, _ in VARIANTS.values()):
        raise RuntimeError("Source worktrees already exist. Choose a fresh workspace to preserve prior runs.")
    for entry in manifest["patches"]:
        path = root / entry["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError("Patch hash mismatch: " + str(path))
    command(["git", "clone", "--filter=blob:none", "--no-checkout", repository, upstream], work)
    present = subprocess.run(["git", "cat-file", "-e", base + "^{commit}"], cwd=upstream, capture_output=True)
    if present.returncode:
        command(["git", "fetch", "origin", base], upstream)
    command(["git", "checkout", "--detach", base], upstream)
    if git_output(upstream, "rev-parse", "HEAD") != base:
        raise RuntimeError("Upstream commit mismatch")
    records = []
    for variant, (folder, output, topic_patch) in VARIANTS.items():
        repo = work / folder
        command(["git", "worktree", "add", "--detach", repo, base], upstream)
        patch_names = ["0001_warnings.patch"] + ([topic_patch] if topic_patch else [])
        for name in patch_names:
            patch = root / "patches" / name
            command(["git", "apply", "--check", patch], repo)
            command(["git", "apply", patch], repo)
        command(["git", "add", "src"], repo)
        command(["git", "-c", "user.name=GRAMM validation", "-c", "user.email=validation@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-m", "Prepare " + variant + " validation source"], repo)
        tree = git_output(repo, "rev-parse", "HEAD:src")
        expected = manifest["source_trees"][variant]
        if tree != expected:
            raise RuntimeError(f"Source tree mismatch for {variant}: {tree} != {expected}")
        record = {"variant": variant, "source_commit": git_output(repo, "rev-parse", "HEAD"),
                  "source_tree": tree, "source_tree_matches_reviewed": True, "output": output,
                  "build": "skipped" if skip_build else "pending"}
        if not skip_build:
            obj = root / "build" / ("native_" + variant + "_obj")
            command([dotnet, "build", repo / "src/GRAMM.csproj", "-c", "Release",
                     "-p:TreatWarningsAsErrors=true", "-p:BaseIntermediateOutputPath=" + str(obj) + os.sep,
                     "-o", root / output, "--nologo"], repo, timeout=180)
            record["build"] = "pass"
        records.append(record)
        (root / "preparation_result.json").write_text(json.dumps({"upstream": base, "variants": records}, indent=2), encoding="utf-8")
    print("Prepared", root, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=HERE, help="Empty reproduction directory; defaults to this bundle")
    parser.add_argument("--repository", default="https://github.com/GralDispersionModel/GRAMM.git", help="Public upstream URL or a local mirror")
    parser.add_argument("--dotnet", default=os.environ.get("GRAMM_TEST_DOTNET", shutil.which("dotnet") or "dotnet"))
    parser.add_argument("--skip-build", action="store_true", help="Fetch sources, apply patches and verify source trees only")
    args = parser.parse_args()
    prepare(args.workspace, args.repository, args.dotnet, args.skip_build)
