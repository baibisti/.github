#!/usr/bin/env python3
"""Build Bisti's deterministic ISO 639-1 motto catalog from reviewed parts."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PARTS = ROOT / "profile/i18n/parts"
JSON_OUTPUT = ROOT / "profile/motto-translations.json"
MARKDOWN_OUTPUT = ROOT / "profile/MOTTO_TRANSLATIONS.md"
SOURCE_TEXT = "Style you wear. Culture you carry."
REVIEW_STATUS = "native-review-required"
BLOCKED_REVIEW_STATUS = "blocked-native-copy-required"
EXPECTED_CODES = """
aa ab af ak sq am ar an hy as av ae ay az ba bm eu be bn bi bs br bg my ca ch ce zh cu cv kw
co cr cs da dv nl dz en eo et ee fo fj fi fr fy ff ka de gd ga gl gv el gn gu ht ha he hz hi
ho hr hu ig is io ii iu ie ia id ik it jv ja kl kn ks kr kk km ki rw ky kv kg ko kj ku lo la
lv li ln lt lb lu lg mk mh ml mi mr ms mg mt mn na nv nr nd ng ne nn nb no ny oc oj or om os
pa fa pi pl pt ps qu rm ro rn ru sg sa si sk sl se sm sn sd so st es sc sr ss su sw sv ty ta
tt te tg tl th bo ti to tn ts tk tr tw ug uk ur uz ve vi vo cy wa wo xh yi yo za zu
""".split()
REQUIRED_FIELDS = {
    "code",
    "locale",
    "language",
    "nativeName",
    "translation",
    "transliteration",
    "confidence",
    "reviewStatus",
    "note",
}
LOCALE_PATTERN = re.compile(
    r"^(?P<language>[a-z]{2})(?:-(?P<script>[A-Z][a-z]{3}))?(?:-(?P<region>[A-Z]{2}|[0-9]{3}))?$"
)
REGISTERED_SCRIPTS = {
    "Arab",
    "Avst",
    "Cans",
    "Cyrl",
    "Deva",
    "Ethi",
    "Geor",
    "Grek",
    "Gujr",
    "Guru",
    "Hans",
    "Hebr",
    "Latn",
    "Mlym",
    "Orya",
    "Thaa",
    "Tibt",
    "Yiii",
}
REGISTERED_REGIONS = {"PT"}


def fail(message: str) -> None:
    raise SystemExit(message)


def clean_text(value: object, field: str, code: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        fail(f"{code}: {field} must be non-empty text")
    cleaned = value.strip()
    if "\ufffd" in cleaned or any(ord(character) < 32 for character in cleaned):
        fail(f"{code}: {field} contains invalid Unicode/control characters")
    return cleaned


def load_entries() -> list[dict]:
    files = sorted(PARTS.glob("*.json"))
    if len(files) != 6:
        fail(f"Expected six translation parts, found {len(files)}")
    by_code: dict[str, dict] = {}
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"Invalid translation part {path.name}: {exc}")
        entries = payload.get("entries") if isinstance(payload, dict) else None
        if not isinstance(entries, list) or not entries:
            fail(f"{path.name}: entries must be a non-empty list")
        for raw in entries:
            if not isinstance(raw, dict) or set(raw) != REQUIRED_FIELDS:
                fail(f"{path.name}: entry fields must equal {sorted(REQUIRED_FIELDS)}")
            code = clean_text(raw["code"], "code", path.name)
            if code not in EXPECTED_CODES:
                fail(f"{path.name}: unexpected ISO 639-1 code {code}")
            if code in by_code:
                fail(f"Duplicate ISO 639-1 code: {code}")
            confidence = clean_text(raw["confidence"], "confidence", code)
            if confidence not in {"high", "medium", "low", "blocked"}:
                fail(f"{code}: invalid confidence {confidence}")
            status = clean_text(raw["reviewStatus"], "reviewStatus", code)
            if status not in {REVIEW_STATUS, BLOCKED_REVIEW_STATUS}:
                fail(f"{code}: unsupported review status {status}")
            locale = clean_text(raw["locale"], "locale", code)
            match = LOCALE_PATTERN.fullmatch(locale)
            if match is None or match.group("language") != code:
                fail(f"{code}: locale must be its ISO code with optional registered script: {locale}")
            script = match.group("script")
            if script is not None and script not in REGISTERED_SCRIPTS:
                fail(f"{code}: unregistered or unsupported script subtag: {script}")
            region = match.group("region")
            if region is not None and region not in REGISTERED_REGIONS:
                fail(f"{code}: unregistered or unsupported region subtag: {region}")
            if confidence == "blocked":
                if status != BLOCKED_REVIEW_STATUS or raw["translation"] is not None or raw["transliteration"] is not None:
                    fail(f"{code}: blocked entry must have null expression/transliteration and blocked review status")
                translation = None
            else:
                if status != REVIEW_STATUS:
                    fail(f"{code}: draft expression must retain native-review-required status")
                translation = clean_text(raw["translation"], "translation", code)
            entry = {
                "code": code,
                "locale": locale,
                "language": clean_text(raw["language"], "language", code),
                "nativeName": clean_text(raw["nativeName"], "nativeName", code),
                "translation": translation,
                "transliteration": clean_text(raw["transliteration"], "transliteration", code, nullable=True),
                "confidence": confidence,
                "reviewStatus": status,
                "note": clean_text(raw["note"], "note", code),
            }
            by_code[code] = entry
    missing = [code for code in EXPECTED_CODES if code not in by_code]
    extra = sorted(set(by_code) - set(EXPECTED_CODES))
    if missing or extra or len(by_code) != 183:
        fail(f"ISO 639-1 coverage mismatch; missing={missing}; extra={extra}")
    if by_code["en"]["translation"] != SOURCE_TEXT:
        fail("English catalog entry must equal approved source motto")
    return [by_code[code] for code in EXPECTED_CODES]


def markdown_escape(value: str | None) -> str:
    if value is None:
        return "—"
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def build_payload(entries: list[dict]) -> dict:
    blocked = sum(entry["translation"] is None for entry in entries)
    return {
        "schemaVersion": "1.0.0",
        "brand": "Bisti",
        "sourceLocale": "en",
        "sourceText": SOURCE_TEXT,
        "status": REVIEW_STATUS,
        "scope": {
            "standard": "ISO 639-1",
            "count": len(entries),
            "draftExpressions": len(entries) - blocked,
            "blockedExpressions": blocked,
            "definition": "Every current alpha-2 entry represented in the Library of Congress ISO 639 table.",
            "source": "https://www.loc.gov/standards/iso639-2/ISO-639-2_utf-8.txt",
            "accessed": "2026-08-21",
            "limitation": "ISO 639-1 is not every human language and does not resolve every dialect or script.",
        },
        "editorialContract": {
            "meaning": "Style is personal expression worn through clothing; culture is lived identity carried with the person.",
            "syntax": "Prefer two short balanced native clauses; adapt word order and ellipsis when required by the language.",
            "publication": "This catalog may be public only as a visibly labeled working draft. No localized line is approved brand copy until a native copywriter records target-market approval.",
        },
        "translations": entries,
    }


def render_json(entries: list[dict]) -> str:
    return json.dumps(build_payload(entries), ensure_ascii=False, indent=2) + "\n"


def render_markdown(entries: list[dict]) -> str:
    lines = [
        "# Bisti motto — 183-language ISO 639-1 catalog",
        "",
        f"> **{SOURCE_TEXT}**",
        "",
        "Status: **public working draft · no localized line is approved brand copy**.",
        "",
        "Scope means every current ISO 639-1 alpha-2 entry—not every human language, dialect, or script. "
        "Translations preserve intent and native syntax over word-for-word structure. Macrolanguage and script choices appear in notes.",
        "",
        "| ISO | Language | Native name | Native expression | Transliteration | Confidence | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in entries:
        translation = entry["translation"] if entry["translation"] is not None else "**BLOCKED — native copy required**"
        lines.append(
            "| "
            + " | ".join(
                markdown_escape(value)
                for value in (
                    entry["code"],
                    entry["language"],
                    entry["nativeName"],
                    translation,
                    entry["transliteration"],
                    entry["confidence"],
                    entry["note"],
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Publication rule",
            "",
            "Public visibility documents the work; it does not approve any translation for campaign use. "
            "Treat `high`, `medium`, and `low` as editorial confidence—not native certification. "
            "Before using any localized motto in product, campaign, packaging, or clothing, record native-copy review, locale, script, market, and approval date.",
            "",
            "## Scope source",
            "",
            "Language-code universe: [Library of Congress ISO 639 table](https://www.loc.gov/standards/iso639-2/ISO-639-2_utf-8.txt), accessed 2026-08-21.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_outputs(entries: list[dict]) -> tuple[str, str]:
    return render_json(entries), render_markdown(entries)


def write_outputs(entries: list[dict]) -> None:
    rendered_json, rendered_markdown = render_outputs(entries)
    JSON_OUTPUT.write_text(rendered_json, encoding="utf-8")
    MARKDOWN_OUTPUT.write_text(rendered_markdown, encoding="utf-8")


def main() -> None:
    entries = load_entries()
    write_outputs(entries)
    print(json.dumps({"ok": True, "translations": len(entries), "json": str(JSON_OUTPUT), "markdown": str(MARKDOWN_OUTPUT)}, indent=2))


if __name__ == "__main__":
    main()
