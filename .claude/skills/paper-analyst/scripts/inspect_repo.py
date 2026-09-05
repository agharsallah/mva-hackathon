#!/usr/bin/env python3
"""Inspect a code repository linked from a paper.

Reports: repo health (stars, forks, licence, last push, archived, open issues),
issues mentioning reproduction problems, README, file tree, detected
dependency/train/eval/weights/results evidence (ML Code Completeness Checklist),
CITATION.cff, containers, tests, notebooks, and a rough language mix.
Optionally shallow-clones the repo for reading the code.

Usage:
  python inspect_repo.py https://github.com/org/repo --out repo.json
  python inspect_repo.py https://github.com/org/repo --clone work/src --out repo.json
  python inspect_repo.py https://gitlab.com/org/repo --clone work/src   # clone only, API unsupported

Set GITHUB_TOKEN to raise the API rate limit (60/h anonymous -> 5000/h).
Never crashes on network failure; see result["errors"] and result["fallback_urls"].
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "paper-analyst-skill/1.0"

DEP_FILES = [
    "requirements.txt",
    "requirements-dev.txt",
    "environment.yml",
    "environment.yaml",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "poetry.lock",
    "conda.yml",
    "Dockerfile",
    "docker-compose.yml",
    "package.json",
    "renv.lock",
    "DESCRIPTION",
    "Project.toml",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Snakefile",
    "nextflow.config",
    "main.nf",
    "flake.nix",
    "shell.nix",
]
CONTAINER_FILES = [
    "Dockerfile",
    "docker-compose.yml",
    "Singularity",
    "Singularity.def",
    "apptainer.def",
    ".devcontainer/devcontainer.json",
]
WEIGHT_EXT = (
    ".pt",
    ".pth",
    ".ckpt",
    ".safetensors",
    ".h5",
    ".hdf5",
    ".pkl",
    ".pickle",
    ".joblib",
    ".onnx",
    ".bin",
    ".npz",
    ".params",
    ".tflite",
    ".rds",
    ".RData",
)
WEIGHT_WORDS = re.compile(
    r"\b(pretrained|pre-trained|checkpoints?|weights|model zoo|download the model|trained models?)\b",
    re.IGNORECASE,
)
WEIGHT_HOSTS = re.compile(
    r"(huggingface\.co|drive\.google\.com|zenodo\.org|dropbox\.com|s3\.amazonaws\.com|storage\.googleapis\.com|figshare\.com|osf\.io|box\.com|onedrive|mega\.nz|dl\.fbaipublicfiles\.com)",
    re.IGNORECASE,
)
REPRO_ISSUE_WORDS = re.compile(
    r"\b(reproduc|replicat|cannot get|can't get|different (results|numbers|score)|mismatch|lower than (paper|reported)|not match|doesn't match|does not match|worse than|missing (file|weights|checkpoint|data)|pretrained|checkpoint|dataset (link|download)|broken link|404)\b",
    re.IGNORECASE,
)


def get(url, timeout=20, headers=None):
    hdrs = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        hdrs["Authorization"] = f"Bearer {tok}"
    if headers:
        hdrs.update(headers)
    try:
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read().decode("utf-8", errors="replace")
            try:
                return json.loads(data), None
            except json.JSONDecodeError:
                return data, None
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        if e.code == 403 and "rate limit" in body.lower():
            return None, f"HTTP 403 rate limited ({url}); set GITHUB_TOKEN"
        return None, f"HTTP {e.code} for {url} {body}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e} for {url}"


def parse_repo(url):
    url = url.strip().rstrip("/")
    url = re.sub(r"\.git$", "", url)
    m = re.match(
        r"(?:https?://)?(?:www\.)?(github\.com|gitlab\.com|bitbucket\.org|codeberg\.org)/([^/\s]+)/([^/\s#?]+)(?:/(?:tree|blob|-/tree)/([^/\s]+))?",
        url,
    )
    if not m:
        return None
    host, owner, repo, ref = m.groups()
    return {
        "host": host,
        "owner": owner,
        "repo": repo,
        "ref": ref,
        "clone_url": f"https://{host}/{owner}/{repo}.git",
        "web_url": f"https://{host}/{owner}/{repo}",
    }


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("url")
    ap.add_argument("--out")
    ap.add_argument("--clone", metavar="DIR", help="shallow clone into DIR for reading the code")
    ap.add_argument("--issues", type=int, default=40, help="how many recent open issues to scan")
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()

    info = parse_repo(args.url)
    result = {
        "input_url": args.url,
        "repo": info,
        "errors": [],
        "fallback_urls": [],
        "warnings": [],
    }
    if not info:
        result["errors"].append(
            "Could not parse a github/gitlab/bitbucket/codeberg repository URL."
        )
        print(json.dumps(result, indent=2))
        sys.exit(1)

    T = args.timeout
    tree_paths = []
    readme = ""

    if info["host"] == "github.com":
        api = f"https://api.github.com/repos/{info['owner']}/{info['repo']}"
        meta, err = get(api, T)
        if meta:
            lic = meta.get("license") or {}
            result["health"] = {
                "full_name": meta.get("full_name"),
                "description": meta.get("description"),
                "homepage": meta.get("homepage"),
                "stars": meta.get("stargazers_count"),
                "forks": meta.get("forks_count"),
                "watchers": meta.get("subscribers_count"),
                "open_issues_and_prs": meta.get("open_issues_count"),
                "license": lic.get("spdx_id") or lic.get("name"),
                "license_note": None,
                "created_at": meta.get("created_at"),
                "pushed_at": meta.get("pushed_at"),
                "archived": meta.get("archived"),
                "disabled": meta.get("disabled"),
                "is_fork": meta.get("fork"),
                "parent": (meta.get("parent") or {}).get("full_name"),
                "default_branch": meta.get("default_branch"),
                "primary_language": meta.get("language"),
                "topics": meta.get("topics"),
                "size_kb": meta.get("size"),
            }
            if meta.get("fork"):
                result["warnings"].append(
                    f"This is a FORK of {result['health']['parent']}; check whether the parent is the official repo."
                )
            if not lic:
                result["health"]["license_note"] = (
                    "NO LICENSE detected: all rights reserved by default; reuse is not permitted without permission."
                )
            elif lic.get("spdx_id") in ("GPL-3.0", "GPL-2.0", "AGPL-3.0", "LGPL-3.0"):
                result["health"]["license_note"] = (
                    "Copyleft licence: derivative works must be released under the same terms."
                )
            elif lic.get("spdx_id") == "NOASSERTION":
                result["health"]["license_note"] = (
                    "Custom/unrecognised licence: read LICENSE file; may be research-only or non-commercial."
                )
            try:
                pushed = time.strptime(meta.get("pushed_at", "")[:10], "%Y-%m-%d")
                days = (time.time() - time.mktime(pushed)) / 86400
                result["health"]["days_since_push"] = int(days)
                if days > 730:
                    result["warnings"].append("No push in over two years: expect dependency rot.")
            except Exception:
                pass
            ref = info["ref"] or meta.get("default_branch") or "main"

            # languages
            langs, lerr = get(f"{api}/languages", T)
            if isinstance(langs, dict):
                total = sum(langs.values()) or 1
                result["languages"] = {
                    k: round(100 * v / total, 1)
                    for k, v in sorted(langs.items(), key=lambda kv: -kv[1])[:8]
                }

            # tree
            tree, terr = get(f"{api}/git/trees/{urllib.parse.quote(ref)}?recursive=1", T)
            if tree and tree.get("tree"):
                tree_paths = [t["path"] for t in tree["tree"] if t.get("type") == "blob"]
                result["tree_truncated"] = bool(tree.get("truncated"))
                result["n_files"] = len(tree_paths)
            else:
                result["errors"].append(terr or "tree fetch failed")

            # readme
            rd, rerr = get(f"{api}/readme", T)
            if rd and rd.get("content"):
                try:
                    readme = base64.b64decode(rd["content"]).decode("utf-8", errors="replace")
                    result["readme_path"] = rd.get("path")
                except Exception as e:
                    result["errors"].append(f"readme decode failed: {e}")
            else:
                result["warnings"].append("No README found via API.")

            # issues (open, most recent), filter out PRs
            iss, ierr = get(
                f"{api}/issues?state=open&per_page={min(args.issues, 100)}&sort=updated", T
            )
            if isinstance(iss, list):
                issues = [i for i in iss if "pull_request" not in i]
                flagged = [
                    {
                        "number": i.get("number"),
                        "title": i.get("title"),
                        "comments": i.get("comments"),
                        "created_at": (i.get("created_at") or "")[:10],
                        "url": i.get("html_url"),
                    }
                    for i in issues
                    if REPRO_ISSUE_WORDS.search(i.get("title") or "")
                ]
                result["issues"] = {
                    "open_scanned": len(issues),
                    "reproduction_related": flagged,
                    "recent_titles": [i.get("title") for i in issues[:15]],
                }
                if len(flagged) >= 3:
                    result["warnings"].append(
                        f"{len(flagged)} open issues mention reproduction problems; read them before trusting reported numbers."
                    )
            else:
                result["errors"].append(ierr or "issues fetch failed")

            # latest release / tags
            rel, _ = get(f"{api}/releases/latest", T)
            if isinstance(rel, dict) and rel.get("tag_name"):
                result["latest_release"] = {
                    "tag": rel.get("tag_name"),
                    "published_at": rel.get("published_at"),
                    "assets": [a.get("name") for a in (rel.get("assets") or [])][:10],
                }
        else:
            result["errors"].append(err)
            result["fallback_urls"].append(api)
    else:
        result["warnings"].append(
            f"API inspection implemented for github.com only; {info['host']} needs --clone for analysis."
        )

    # ---------- clone ----------
    if args.clone:
        if shutil.which("git") is None:
            result["errors"].append("git not available; cannot clone")
        else:
            dest = args.clone
            if os.path.exists(dest) and os.listdir(dest):
                result["warnings"].append(f"{dest} exists and is non-empty; using it as-is.")
            else:
                cmd = ["git", "clone", "--depth", "1"]
                if info["ref"]:
                    cmd += ["--branch", info["ref"]]
                cmd += [info["clone_url"], dest]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if r.returncode != 0:
                    result["errors"].append(f"git clone failed: {r.stderr.strip()[:300]}")
            if os.path.isdir(dest):
                result["clone_dir"] = os.path.abspath(dest)
                if not tree_paths:
                    for root, dirs, files in os.walk(dest):
                        dirs[:] = [
                            d for d in dirs if d not in (".git", "node_modules", "__pycache__")
                        ]
                        for f in files:
                            tree_paths.append(os.path.relpath(os.path.join(root, f), dest))
                    result["n_files"] = len(tree_paths)
                if not readme:
                    for cand in ("README.md", "README.rst", "README.txt", "README", "readme.md"):
                        p = os.path.join(dest, cand)
                        if os.path.exists(p):
                            with open(p, encoding="utf-8", errors="replace") as f:
                                readme = f.read()
                            result["readme_path"] = cand
                            break
                # git log date
                r = subprocess.run(
                    ["git", "-C", dest, "log", "-1", "--format=%cI %h %s"],
                    capture_output=True,
                    text=True,
                )
                if r.returncode == 0:
                    result["head_commit"] = r.stdout.strip()

    # ---------- completeness checklist ----------
    low_paths = [p.lower() for p in tree_paths]
    basenames = [os.path.basename(p) for p in tree_paths]

    def find(pred):
        return [p for p in tree_paths if pred(p.lower())]

    deps = [p for p in tree_paths if os.path.basename(p) in DEP_FILES]
    containers = [
        p for p in tree_paths if os.path.basename(p) in CONTAINER_FILES or p in CONTAINER_FILES
    ]
    train = find(
        lambda p: (
            re.search(
                r"(^|/)(train|training|fit|pretrain|finetune|fine_tune|run_train)[\w\-]*\.(py|sh|r|jl|ipynb)$",
                p,
            )
            or ("/train" in p and p.endswith((".py", ".sh")))
        )
    )
    evals = find(
        lambda p: (
            re.search(
                r"(^|/)(eval|evaluate|evaluation|test|benchmark|inference|predict|score|metrics)[\w\-]*\.(py|sh|r|jl|ipynb)$",
                p,
            )
            and "/tests/" not in p
            and not p.startswith("tests/")
        )
    )
    tests = find(
        lambda p: (
            p.startswith("tests/")
            or "/tests/" in p
            or re.search(r"(^|/)test_[\w\-]+\.py$", p)
            or p.startswith("test/")
        )
    )
    notebooks = find(lambda p: p.endswith(".ipynb"))
    configs = find(
        lambda p: (
            re.search(r"(^|/)(configs?|conf|hparams|hyperparams)(/|$)", p)
            or (
                re.search(r"\.(yaml|yml|json|toml|cfg|ini)$", p)
                and re.search(r"config|hparam|setting", p)
            )
        )
    )
    weight_files = find(
        lambda p: p.endswith(tuple(e.lower() for e in WEIGHT_EXT)) and "test" not in p
    )
    citation = [
        p
        for p in tree_paths
        if os.path.basename(p) in ("CITATION.cff", "CITATION.bib", "CITATION", "citation.bib")
    ]
    license_files = [
        p
        for p in tree_paths
        if os.path.basename(p).upper().startswith("LICENSE")
        or os.path.basename(p).upper().startswith("COPYING")
    ]
    data_scripts = find(
        lambda p: re.search(
            r"(download|prepare|preprocess|get_data|make_dataset)[\w\-]*\.(py|sh)$", p
        )
    )
    lockfiles = [
        p
        for p in tree_paths
        if os.path.basename(p)
        in (
            "poetry.lock",
            "Pipfile.lock",
            "conda-lock.yml",
            "renv.lock",
            "package-lock.json",
            "yarn.lock",
            "uv.lock",
            "requirements.lock",
        )
    ]

    rd_low = readme.lower()
    readme_has_install = bool(
        re.search(
            r"(pip install|conda (create|env|install)|docker (build|pull|run)|poetry install|npm install|requirements)",
            rd_low,
        )
    )
    readme_has_train_cmd = bool(
        re.search(r"(python\s+\S*train\S*|\btrain(ing)?\b.*```|--train|\bfit\b)", rd_low)
    )
    readme_has_eval_cmd = bool(
        re.search(r"(python\s+\S*(eval|test|infer|predict)\S*|\bevaluat(e|ion)\b|--eval)", rd_low)
    )
    readme_weights = bool(WEIGHT_WORDS.search(readme)) and bool(
        WEIGHT_HOSTS.search(readme) or weight_files or re.search(r"\bdownload\b", rd_low)
    )
    readme_results_table = bool(
        re.search(r"^\s*\|.*\|\s*$\n\s*\|[\s:\-|]+\|\s*$", readme, re.MULTILINE)
    ) and bool(re.search(r"\d+\.\d+", readme))
    readme_results_heading = bool(
        re.search(
            r"^#+\s*(results|benchmarks?|performance|leaderboard|model zoo)",
            readme,
            re.MULTILINE | re.IGNORECASE,
        )
    )
    readme_paper_link = bool(
        re.search(
            r"(arxiv\.org|doi\.org|openreview\.net|aclanthology|proceedings|neurips|icml|iclr|cvpr|nature\.com|biorxiv|@inproceedings|@article)",
            rd_low,
        )
    )
    pinned = False
    if args.clone and result.get("clone_dir"):
        for dep in deps:
            if os.path.basename(dep) in ("requirements.txt", "environment.yml", "environment.yaml"):
                try:
                    with open(
                        os.path.join(result["clone_dir"], dep), encoding="utf-8", errors="replace"
                    ) as f:
                        content = f.read()
                    if re.search(r"==\s*\d", content):
                        pinned = True
                except Exception:
                    pass

    def status(files, readme_flag, partial_ok=True):
        if files and readme_flag:
            return "yes"
        if files or readme_flag:
            return "partial" if partial_ok else "yes"
        return "no"

    checklist = {
        "dependencies": {
            "status": status(deps, readme_has_install),
            "files": deps[:10],
            "lockfiles": lockfiles,
            "containers": containers,
            "pinned_versions": pinned if args.clone else "unknown (use --clone)",
            "readme_install_instructions": readme_has_install,
        },
        "training_script": {
            "status": status(train, readme_has_train_cmd),
            "files": train[:10],
            "readme_train_command": readme_has_train_cmd,
        },
        "evaluation_script": {
            "status": status(evals, readme_has_eval_cmd),
            "files": evals[:10],
            "readme_eval_command": readme_has_eval_cmd,
        },
        "pretrained_models": {
            "status": "yes" if readme_weights else ("partial" if weight_files else "no"),
            "weight_files_in_repo": weight_files[:10],
            "readme_mentions_weights": bool(WEIGHT_WORDS.search(readme)),
            "external_host_mentioned": bool(WEIGHT_HOSTS.search(readme)),
        },
        "results_table": {
            "status": "yes" if (readme_results_table or readme_results_heading) else "no",
            "readme_has_markdown_table_with_numbers": readme_results_table,
            "readme_results_heading": readme_results_heading,
        },
    }
    score = sum(
        1 if v["status"] == "yes" else 0.5 if v["status"] == "partial" else 0
        for v in checklist.values()
    )
    result["completeness_checklist"] = checklist
    result["completeness_score"] = f"{score}/5"
    result["completeness_note"] = (
        "Heuristic from file names and README; confirm by opening the files. 'partial' = evidence in files or README but not both."
    )

    result["structure"] = {
        "tests": tests[:10],
        "n_tests": len(tests),
        "notebooks": notebooks[:10],
        "config_files": configs[:15],
        "data_scripts": data_scripts[:10],
        "citation_file": citation,
        "license_files": license_files,
        "top_level": sorted({p.split("/")[0] for p in tree_paths})[:40],
        "readme_links_paper": readme_paper_link,
    }
    result["readme_excerpt"] = readme[:4000] if readme else None
    result["readme_chars"] = len(readme)

    if not readme_paper_link and readme:
        result["warnings"].append(
            "README does not link to a paper; verify this is the official implementation."
        )
    if not tests:
        result["warnings"].append("No tests detected.")
    if not license_files and result.get("health", {}).get("license") in (None, "NOASSERTION"):
        result["warnings"].append(
            "No LICENSE file: reuse is not legally permitted without author permission."
        )

    result["next_steps"] = [
        "Open the config and main train/eval files to check paper-to-code consistency (hyperparameters, model size, datasets, metric).",
        "If dependencies look installable, attempt the dry run protocol in references/code-and-data-assessment.md (time-boxed).",
        "Read the reproduction-related issues; they are the most honest reproducibility signal.",
    ]
    result["errors"] = [e for e in result["errors"] if e]

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        compact = {k: v for k, v in result.items() if k not in ("readme_excerpt",)}
        compact["saved_to"] = args.out
        print(json.dumps(compact, indent=2, ensure_ascii=False))
    else:
        print(text)


if __name__ == "__main__":
    main()
