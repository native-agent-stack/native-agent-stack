"""Pinned choice statements, with keyed redaction and an independent readset audit.

Classification is by exact normalized statement digest, not by candidate identity.
The public classification contains hashes and locators, never private evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

CLASSIFICATION = Path(__file__).with_name("readset-choice-classification.json")
TEXT_SUFFIXES = frozenset({".md", ".txt", ".log", ".yaml", ".yml", ".toml", ".jsonl"})
CHOICE_CUE = re.compile(
    r"\b(?:incumbents?|winners?|current (?:choice|selection|destination|default)|"
    r"(?:selected|chosen|adopted|retained|accepted) (?:destination|choice|stack|engine|runtime|component|candidate|executable)|"
    r"(?:gave|gives|goes|takes?|took|take) the slot|(?:retain|keep|adopt) (?:the )?(?:current|native|catalog|installed)\b)",
    re.I)


def statements(text):
    """Offsets of sentences, table rows and wrapped-line fragments, preserving all untouched bytes."""
    for line in re.finditer(r"[^\n]+", text):
        for unit in re.finditer(r".+?(?:[.!?;](?=\s)|$)", line.group()):
            value = unit.group().strip()
            if value:
                yield line.start() + unit.start(), line.start() + unit.end(), value


def digest(text):
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def classification():
    document = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    return {item["sha256"]: item["disposition"] for item in document["statements"]}


def redact_tables(text, relative, stripped, key):
    """Redact selection columns, retaining the table's other evidence columns."""
    from blind_checkout import hmac_sha256_of
    columns = []
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            columns = []
            continue
        cells = line.rstrip("\n").split("|")
        if index + 1 < len(lines) and re.fullmatch(r"[\s|:-]+", lines[index + 1]) and any(
                re.search(r"\b(?:selected|current choice|retained choice)\b", cell, re.I) for cell in cells):
            columns = [i for i, cell in enumerate(cells)
                       if re.search(r"\b(?:selected|current choice|retained choice|decision)\b", cell, re.I)]
        elif re.fullmatch(r"[\s|:-]+", line):
            continue
        for column in columns:
            if column < len(cells) and cells[column].strip() != "[withheld choice]":
                stripped.append({"path": f"{relative}/@table/{index + 1}/{column}",
                                 "old_sha256": hmac_sha256_of(cells[column], key)})
                cells[column] = " [withheld choice] "
        lines[index] = "|".join(cells) + ("\n" if line.endswith("\n") else "")
    return "".join(lines)


def redact_text(text, relative, pointer, stripped, key, labels, spans):
    from blind_checkout import hmac_sha256_of
    edits = []
    for start, end, value in statements(text):
        sha = digest(value)
        if sha in spans and hashlib.sha256(value.encode()).hexdigest() == spans[sha]["source_sha256"]:
            fragment = spans[sha]
            # Require the exact reviewed spacing before applying byte-positioned spans.
            offset = text[start:end].find(value)
            edits.append((start + offset + fragment["start"], start + offset + fragment["end"],
                          value[fragment["start"]:fragment["end"]]))
        elif labels.get(sha) == "choice":
            edits.append((start, end, value))
    for start, end, value in reversed(edits):
        stripped.append({"path": f"{relative}{pointer}/@text/{start}",
                         "old_sha256": hmac_sha256_of(value, key)})
        text = text[:start] + text[end:]
    return text


def redact_document(node, relative, pointer, stripped, key, labels, fields, spans):
    from blind_checkout import hmac_sha256_of
    if isinstance(node, dict):
        for name, value in list(node.items()):
            child = pointer + "/" + name.replace("~", "~0").replace("/", "~1")
            if relative + child in fields and (fields[relative + child] is None or fields[relative + child] ==
                    hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()):
                stripped.append({"path": relative + child, "old_sha256": hmac_sha256_of(value, key)})
                del node[name]
                continue
            if isinstance(value, str):
                node[name] = redact_text(value, relative, child, stripped, key, labels, spans)
            else:
                redact_document(value, relative, child, stripped, key, labels, fields, spans)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            child = pointer + "/" + str(index)
            if relative + child in fields and (fields[relative + child] is None or fields[relative + child] ==
                    hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()):
                stripped.append({"path": relative + child, "old_sha256": hmac_sha256_of(value, key)})
                node[index] = ""
            elif isinstance(value, str):
                node[index] = redact_text(value, relative, child, stripped, key, labels, spans)
            else:
                redact_document(value, relative, child, stripped, key, labels, fields, spans)


def redact_readset(root, stripped, key):
    """Keep evidence files and reference routes; remove only reviewed choice statement spans."""
    from blind_checkout import TRANSITIVE_PREFIXES, _string_values, bare_reference
    labels = classification()
    document = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    fields = {item["path"] + item["pointer"]: item["sha256"] for item in document["fields"]}
    spans = {item["sha256"]: item for item in document["spans"]}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or ".git" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        if path.suffix != ".json" and path.suffix not in TEXT_SUFFIXES:
            continue
        before = path.read_text(encoding="utf-8", errors="replace")
        try:
            document = json.loads(before) if path.suffix == ".json" or path.name.endswith(".json.source.txt") else None
        except ValueError:
            document = None
        count = len(stripped)
        if document is not None:
            before_refs = {bare_reference(value) for value in _string_values(document)}
            redact_document(document, relative, "", stripped, key, labels, fields, spans)
            if isinstance(document, dict):
                after_refs = {bare_reference(value) for value in _string_values(document)}
                retained = sorted(reference for reference in before_refs - after_refs
                                  if reference and reference.startswith(TRANSITIVE_PREFIXES))
                if retained:
                    document["withheld_choice_evidence_refs"] = retained
            after = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        else:
            after = redact_text(redact_tables(before, relative, stripped, key),
                                relative, "", stripped, key, labels, spans)
        if len(stripped) != count:
            path.write_text(after, encoding="utf-8")


def content_findings(root, files):
    """Fail closed on known choices or unclassified choice cues in the complete one-level readset."""
    from blind_checkout import _string_values
    labels = classification()
    findings = []
    for relative in sorted(files):
        path = root / relative
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix != ".json" and path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            values = list(_string_values(json.loads(text))) if (
                path.suffix == ".json" or path.name.endswith(".json.source.txt")) else [text]
        except ValueError:
            values = [text]
        for value in values:
            for _start, _end, statement in statements(value):
                sha = digest(statement)
                disposition = labels.get(sha)
                if disposition == "choice" or (CHOICE_CUE.search(statement) and disposition != "data"):
                    findings.append({"path": relative, "sha256": sha, "excerpt": statement[:60]})
    return findings
