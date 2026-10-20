"""Independent, content-based audit of every file in an exported blind readset.

This module deliberately imports neither the redactor nor its classification.
Its data exceptions bind independently reviewed paragraphs/rows/JSON keys and
strings to a path and digest. Unknown choice cues fail closed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

RULES = Path(__file__).with_name("readset-audit-data.json")
CHOICE = re.compile(
    r"\b(?:current\s+(?:choice|selection|destination|default)|incumbents?|winners?|won)\b|"
    r"\b(?:is|remains?)\s+(?:the\s+)?(?:default|winner|incumbent)\b|"
    r"\bwe\s+(?:keep|retain|adopt)\b|"
    r"\b(?:gave|gives|goes|takes?|took)\s+the\s+slot\b|"
    r"\b(?:keep|retain|adopt)\s+(?:the\s+)?(?:current|native|catalog|installed)\b|"
    r"\b(?:selected|chosen|adopted|retained|accepted)\s+(?:destination|choice|stack|engine|runtime|component|candidate|executable)\b|"
    r"\b(?:existing\s+selected|accepted\s+upstream|quality\s+default|keeps?\s+.{0,50}\s+as\s+the)\b|"
    r"\bselected\s+(?:\[|path\b)|\bremains?\s+the\s+frozen\s+historical\s+comparator\b|"
    r"\bselection\s+(?:remains?|of\s+record\b|moves?|stays?)\b|"
    r"\bselected\s+(?:(?-i:[A-Z][\w-]*)|source\s+remains?\b)|"
    r"\(\s*selected\b|\bfor\s+this\s+selection\b|"
    r"\bits\s+interim\b[^.!?\n]{0,120}\badds?\b",
    re.I)


def text_content(data: bytes) -> str | None:
    """Decode text by its bytes, including UTF-16 BOMs, not by its filename."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            return None
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
        controls = sum(not (character.isprintable() or character in "\n\r\t\b\x1b")
                       for character in text)
        return text if controls / max(1, len(text)) < 0.01 else None


def units(text: str):
    """Read JSON keys and strings, otherwise paragraphs and individual table rows."""
    try:
        document = json.loads(text)
    except ValueError:
        document = None
    if isinstance(document, dict):
        for name, value in document.items():
            yield name
            if isinstance(value, str):
                yield from units(value)
            elif isinstance(value, (dict, list)):
                yield from units(json.dumps(value, ensure_ascii=False))
    elif isinstance(document, list):
        for value in document:
            if isinstance(value, str):
                yield from units(value)
            elif isinstance(value, (dict, list)):
                yield from units(json.dumps(value, ensure_ascii=False))
    else:
        for paragraph in re.split(r"\n\s*\n", text):
            if paragraph.lstrip().startswith("|"):
                yield from (row.strip() for row in paragraph.splitlines() if row.strip())
            elif paragraph.strip():
                yield " ".join(paragraph.split())


def audit_readset(root: Path, files) -> dict:
    """Return findings and a complete text/binary accounting for the supplied files."""
    reviewed = json.loads(RULES.read_text(encoding="utf-8"))
    exceptions = {(item["path"], item["sha256"]) for item in reviewed["data"]}
    findings = []
    text_files = []
    binary_files = []
    exempted = []
    for relative in sorted(files):
        path = root / relative
        text = text_content(path.read_bytes())
        if text is None:
            binary_files.append(relative)
            continue
        text_files.append(relative)
        for unit in units(text):
            plain = re.sub(r"[`*]", "", unit).replace("_", " ")
            plain = " ".join(plain.split())
            match = CHOICE.search(plain)
            if match is None:
                continue
            sha = hashlib.sha256(unit.encode("utf-8")).hexdigest()
            if (relative, sha) in exceptions:
                exempted.append({"path": relative, "sha256": sha})
            else:
                findings.append({"path": relative, "sha256": sha, "excerpt": unit[:60]})
    return {"files": len(text_files) + len(binary_files), "text_files": text_files,
            "binary_files": binary_files, "exempted": exempted, "findings": findings}
