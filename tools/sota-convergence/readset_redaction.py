"""Pinned, path-scoped choice statements with keyed redaction.

Classification is by exact normalized statement digest, not by candidate identity.
The public classification contains hashes and locators, never private evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

CLASSIFICATION = Path(__file__).with_name("readset-choice-classification.json")
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


def classification(relative=None):
    document = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    labels = {item["sha256"]: item["disposition"] for item in document["statements"]
              if relative is None or item["path"] == relative}
    labels.update({"paragraph/" + item["sha256"]: item["disposition"]
                   for item in document.get("paragraphs", [])
                   if relative is None or item["path"] == relative})
    return labels


def redact_tables(text, relative, stripped, key):
    """Redact selection columns, retaining the table's other evidence columns."""
    from blind_checkout import hmac_sha256_of
    document = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    tables = document.get("tables", {})
    if relative not in tables:
        return text
    columns = []
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            columns = []
            continue
        if index + 1 < len(lines) and re.fullmatch(
                r"\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*", lines[index + 1]):
            columns = tables[relative].get(digest(line), [])
            # Identify selection columns from the original header, then mask separately reviewed
            # header adjectives without withholding their measurement/provenance body cells.
        elif re.fullmatch(r"[\s|:-]+", line):
            continue
        spans = {item["sha256"]: item for item in document["spans"] if item["path"] == relative}
        line = redact_text(line, relative, "", stripped, key, {}, spans)
        cells = line.rstrip("\n").split("|")
        for column in columns:
            if column < len(cells) and cells[column].strip() != "[withheld]":
                stripped.append({"path": f"{relative}/@table/{index + 1}/{column}",
                                 "old_sha256": hmac_sha256_of(cells[column], key)})
                # The replacement is also used in header cells. Naming a choice there would
                # turn every retained measurement row back into a selection statement.
                cells[column] = " [withheld] "
        lines[index] = "|".join(cells) + ("\n" if line.endswith("\n") else "")
    return "".join(lines)


def redact_text(text, relative, pointer, stripped, key, labels, spans):
    from blind_checkout import hmac_sha256_of
    edits = []
    for line in re.finditer(r"[^\n]+", text):
        value = line.group()
        fragment = spans.get(digest(value))
        if fragment and fragment.get("unit") == "line" and fragment["path"] == relative and hashlib.sha256(
                value.encode()).hexdigest() == fragment["source_sha256"]:
            for start, end in fragment["ranges"]:
                edits.append((line.start() + start, line.start() + end, value[start:end],
                              fragment.get("replacement", "")))
    for paragraph in re.finditer(r"\S[^\n]*(?:\n(?!\s*\n)[^\n]*)*", text):
        value = paragraph.group()
        fragment = spans.get(digest(value))
        if fragment and fragment.get("unit") == "paragraph" and fragment["path"] == relative and hashlib.sha256(
                value.encode()).hexdigest() == fragment["source_sha256"]:
            for start, end in fragment.get("ranges", [[fragment["start"], fragment["end"]]]):
                edits.append((paragraph.start() + start, paragraph.start() + end, value[start:end],
                              fragment.get("replacement", "")))
        elif labels.get("paragraph/" + digest(value)) == "choice":
            edits.append((paragraph.start(), paragraph.end(), paragraph.group(), ""))
    for start, end, value in statements(text):
        # An exact reviewed span takes precedence over a coarser sentence classification.
        # Applying both would delete measured bytes or apply the same edit twice.
        if any(first < end and start < last for first, last, _, _ in edits):
            continue
        sha = digest(value)
        if sha in spans and spans[sha]["path"] == relative and hashlib.sha256(
                value.encode()).hexdigest() == spans[sha]["source_sha256"]:
            fragment = spans[sha]
            if fragment.get("unit") in ("paragraph", "line"):
                continue
            # Require the exact reviewed spacing before applying byte-positioned spans.
            offset = text[start:end].find(value)
            for first, last in fragment.get("ranges", [[fragment["start"], fragment["end"]]]):
                edits.append((start + offset + first, start + offset + last, value[first:last],
                              fragment.get("replacement", "")))
        elif labels.get(sha) == "choice":
            edits.append((start, end, value, ""))
    for start, end, value, replacement in sorted(edits, reverse=True):
        stripped.append({"path": f"{relative}{pointer}/@text/{start}",
                         "old_sha256": hmac_sha256_of(value, key)})
        left, right = text[:start], text[end:]
        if not right or right.startswith(("\n", ",", ".", ";", ":")):
            left = left.rstrip(" \t")
        if not left or left.endswith("\n"):
            right = right.lstrip(" \t")
        if left.endswith((" ", "\t")) and right.startswith((" ", "\t")):
            right = right.lstrip(" \t")
        text = left + replacement + right
    return redact_text(text, relative, pointer, stripped, key, labels, spans) if edits else text


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
                after = redact_text(value, relative, child, stripped, key, labels, spans)
                node[name] = re.sub(r"[ \t]{2,}", " ", after).strip() if after != value else value
                if after != value and not node[name]:
                    del node[name]
            else:
                had_content = bool(value)
                redact_document(value, relative, child, stripped, key, labels, fields, spans)
                if had_content and isinstance(value, dict) and not value and name != "measurement":
                    del node[name]
    elif isinstance(node, list):
        emptied = []
        for index, value in enumerate(node):
            child = pointer + "/" + str(index)
            if relative + child in fields and (fields[relative + child] is None or fields[relative + child] ==
                    hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()):
                stripped.append({"path": relative + child, "old_sha256": hmac_sha256_of(value, key)})
                emptied.append(index)
            elif isinstance(value, str):
                after = redact_text(value, relative, child, stripped, key, labels, spans)
                node[index] = re.sub(r"[ \t]{2,}", " ", after).strip() if after != value else value
                if after != value and not node[index]:
                    emptied.append(index)
            else:
                had_content = bool(value)
                redact_document(value, relative, child, stripped, key, labels, fields, spans)
                if had_content and not value:
                    emptied.append(index)
        for index in reversed(emptied):
            del node[index]


def redact_readset(root, stripped, key):
    """Remove reviewed choice spans; reference routes belong only in the operator manifest."""
    document = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    fields = {item["path"] + item["pointer"]: item["sha256"] for item in document["fields"]}
    reviewed_spans = document["spans"]
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or ".git" in path.parts or path.name == "BLIND-MANIFEST.json":
            continue
        relative = path.relative_to(root).as_posix()
        spans = {item["sha256"]: item for item in reviewed_spans if item["path"] == relative}
        data = path.read_bytes()
        if b"\0" in data:
            continue
        try:
            before = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        labels = classification(relative)
        try:
            document = json.loads(before)
        except ValueError:
            document = None
        count = len(stripped)
        if document is not None:
            redact_document(document, relative, "", stripped, key, labels, fields, spans)
            after = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        else:
            after = redact_text(redact_tables(before, relative, stripped, key),
                                relative, "", stripped, key, labels, spans)
        if len(stripped) != count:
            path.write_text(after, encoding="utf-8")


def content_findings(root, files):
    """Compatibility entry point for the separately implemented content audit."""
    from readset_audit import audit_readset
    return audit_readset(root, files)["findings"]
