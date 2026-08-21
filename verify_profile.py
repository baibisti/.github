#!/usr/bin/env python3
"""Verify standalone Bisti GitHub organization-profile handoff."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / "profile"
README = PROFILE / "README.md"
ASSETS = PROFILE / "assets"
MANIFEST = ASSETS / "manifest.json"
EXPECTED_ORIGINS = {
    "https://github.com/baibisti/.github.git",
    "git@github.com:baibisti/.github.git",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_output(*arguments: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def main() -> None:
    if not README.is_file() or not MANIFEST.is_file():
        raise SystemExit("GitHub profile README or asset manifest missing")
    source = README.read_text(encoding="utf-8")
    if len(source.encode("utf-8")) >= 500_000:
        raise SystemExit("Profile README exceeds safe GitHub rendering budget")
    required = (
        "<picture>",
        'media="(prefers-reduced-motion: reduce)"',
        'srcset="./assets/bisti-chromatic-wardrobe-poster.png"',
        'src="./assets/bisti-chromatic-wardrobe.gif"',
    )
    for token in required:
        if token not in source:
            raise SystemExit(f"Profile README contract missing: {token}")
    alt = re.search(r'<img\s+[^>]*alt="([^"]+)"', source, re.IGNORECASE)
    if alt is None or len(alt.group(1).strip()) < 40:
        raise SystemExit("Profile image alternative text incomplete")
    if re.search(r'src(?:set)?="https?://', source, re.IGNORECASE):
        raise SystemExit("Remote profile media forbidden")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("motion") != "finite one-shot" or manifest.get("reducedMotion") != "static poster":
        raise SystemExit("Profile motion contract drift")
    records = manifest.get("assets")
    if not isinstance(records, list) or len(records) != 2:
        raise SystemExit("Profile asset manifest incomplete")
    for record in records:
        delivered = record.get("delivered", "")
        prefix = ".github/profile/assets/"
        if not delivered.startswith(prefix):
            raise SystemExit(f"Unexpected delivered asset path: {delivered}")
        path = ROOT / delivered.removeprefix(".github/")
        if not path.is_file() or path.stat().st_size != record.get("bytes") or sha256(path) != record.get("sha256"):
            raise SystemExit(f"Profile asset mismatch: {delivered}")

    worktree = git_output("rev-parse", "--is-inside-work-tree") == "true"
    origin = git_output("remote", "get-url", "origin")
    valid_checkout = worktree and origin in EXPECTED_ORIGINS
    remote_main = git_output("ls-remote", "--exit-code", "origin", "refs/heads/main")
    visibility = subprocess.run(
        ["gh", "repo", "view", "baibisti/.github", "--json", "visibility", "--jq", ".visibility"],
        check=False,
        capture_output=True,
        text=True,
    ) if valid_checkout else None
    published = valid_checkout and remote_main is not None and visibility is not None and visibility.returncode == 0 and visibility.stdout.strip() == "PUBLIC"
    archive_mode = os.environ.get("BISTI_PROFILE_ARCHIVE_MODE") == "1"
    status = manifest.get("status")
    if status == "approved-github-profile-delivery" and not valid_checkout and not archive_mode:
        raise SystemExit("Approved profile status requires expected baibisti/.github checkout")
    if not valid_checkout and not archive_mode and status != "ready-for-github-repository-staging":
        raise SystemExit("Unpublished profile must remain explicitly staged")
    if status not in {"ready-for-github-repository-staging", "approved-github-profile-delivery"}:
        raise SystemExit(f"Unknown profile status: {status}")
    publication = manifest.get("publication")
    if publication == "published-public-github-organization-profile" and not published and not archive_mode:
        raise SystemExit("Published status requires public baibisti/.github remote main")
    if published and publication != "published-public-github-organization-profile":
        raise SystemExit("Public GitHub profile exists but publication manifest is stale")

    print(json.dumps({
        "ok": True,
        "status": status,
        "publication": "portable archive; remote proof not rerun" if archive_mode else "published public organization profile" if published else "repository checkout verified; push not proven" if valid_checkout else "staged; not published",
        "origin": origin,
        "assets": len(records),
    }, indent=2))


if __name__ == "__main__":
    main()
