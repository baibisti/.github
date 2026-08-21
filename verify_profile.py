#!/usr/bin/env python3
"""Verify standalone Bisti GitHub organization-profile handoff."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from build_motto_catalog import (
    BLOCKED_REVIEW_STATUS,
    EXPECTED_CODES,
    REVIEW_STATUS,
    SOURCE_TEXT,
    load_entries,
    markdown_escape,
    render_outputs,
)


ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / "profile"
README = PROFILE / "README.md"
ASSETS = PROFILE / "assets"
MANIFEST = ASSETS / "manifest.json"
MOTTO_JSON = PROFILE / "motto-translations.json"
MOTTO_MARKDOWN = PROFILE / "MOTTO_TRANSLATIONS.md"
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
    if not all(path.is_file() for path in (README, MANIFEST, MOTTO_JSON, MOTTO_MARKDOWN)):
        raise SystemExit("GitHub profile README, manifest, or motto catalog missing")
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
    if SOURCE_TEXT not in source or "./MOTTO_TRANSLATIONS.md" not in source:
        raise SystemExit("Approved motto or translation-catalog link missing from profile README")
    alt = re.search(r'<img\s+[^>]*alt="([^"]+)"', source, re.IGNORECASE)
    if alt is None or len(alt.group(1).strip()) < 40:
        raise SystemExit("Profile image alternative text incomplete")
    if re.search(r'src(?:set)?="https?://', source, re.IGNORECASE):
        raise SystemExit("Remote profile media forbidden")

    expected_json, expected_markdown = render_outputs(load_entries())
    actual_json = MOTTO_JSON.read_text(encoding="utf-8")
    actual_markdown = MOTTO_MARKDOWN.read_text(encoding="utf-8")
    if actual_json != expected_json or actual_markdown != expected_markdown:
        raise SystemExit("Generated motto catalog drift; run python3 build_motto_catalog.py")
    if markdown_escape(r"x\|y") != r"x\\\|y":
        raise SystemExit("Motto Markdown escaping contract failed")
    motto = json.loads(actual_json)
    if motto.get("sourceLocale") != "en" or motto.get("sourceText") != SOURCE_TEXT or motto.get("status") != REVIEW_STATUS:
        raise SystemExit("Motto catalog identity or review status drift")
    scope = motto.get("scope", {})
    if (
        scope.get("standard") != "ISO 639-1"
        or scope.get("count") != len(EXPECTED_CODES)
        or scope.get("draftExpressions") != len(EXPECTED_CODES) - 1
        or scope.get("blockedExpressions") != 1
    ):
        raise SystemExit("Motto catalog scope drift")
    translations = motto.get("translations")
    if not isinstance(translations, list) or len(translations) != len(EXPECTED_CODES):
        raise SystemExit("Motto translation count mismatch")
    codes = [entry.get("code") for entry in translations if isinstance(entry, dict)]
    if codes != EXPECTED_CODES or len(codes) != len(set(codes)):
        raise SystemExit("Motto ISO 639-1 ordering, coverage, or uniqueness mismatch")
    blocked = []
    for entry in translations:
        status = entry.get("reviewStatus")
        confidence = entry.get("confidence")
        if status == BLOCKED_REVIEW_STATUS:
            if confidence != "blocked" or entry.get("translation") is not None or entry.get("transliteration") is not None:
                raise SystemExit(f"Motto blocked-entry contract failed: {entry.get('code')}")
            blocked.append(entry.get("code"))
        elif status != REVIEW_STATUS or confidence not in {"high", "medium", "low"}:
            raise SystemExit(f"Motto translation improperly certified: {entry.get('code')}")
        elif not isinstance(entry.get("translation"), str) or not entry["translation"].strip():
            raise SystemExit(f"Motto translation missing: {entry.get('code')}")
        for field in ("locale", "language", "nativeName", "confidence", "note"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise SystemExit(f"Motto translation field missing: {entry.get('code')}: {field}")
    if blocked != ["nv"]:
        raise SystemExit(f"Unexpected blocked motto entries: {blocked}")
    markdown = actual_markdown
    data_rows = [line for line in markdown.splitlines() if re.match(r"^\| [a-z]{2} \|", line)]
    if len(data_rows) != len(EXPECTED_CODES) or SOURCE_TEXT not in markdown:
        raise SystemExit("Human-readable motto catalog coverage drift")

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
        "mottoEntries": len(translations),
        "mottoDraftExpressions": len(translations) - len(blocked),
        "mottoBlocked": blocked,
    }, indent=2))


if __name__ == "__main__":
    main()
