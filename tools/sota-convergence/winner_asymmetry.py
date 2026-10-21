"""Operator-only identity-binding audit; never imported by the blind exporter.

Candidates and prior roles enter only through restored operator packets. Findings
contain private candidate keys and must not be written to a lane-visible readset.
This auditor imports neither the redactor nor its classification or exceptions.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import cache
import json
from pathlib import Path
import posixpath
import re

from export_isolation_check import load_packets, winner_keys

LINK = re.compile(r"\]\(([^)\s]+)\)|`([^`\s]+/[^`\s]+)`|(?<![\w/.-])((?:[\w.-]+/)+[\w.-]+\.(?:json|jsonl|md|txt|ya?ml|py|sh|csv))")
SLOT = re.compile(r"^[^/\s]+/[^\n]+$")
IDENTITY_FIELDS = frozenset({
    "slot", "slot_id", "repository", "repo", "name", "component", "component_id",
    "owner", "owner_default", "default", "pin", "current_pin", "package", "decided_by",
    "interim", "installed", "label", "claude", "gpt", "upstream", "upstream_source",
    "tool", "tool_name",
})
SELECTION_FIELDS = frozenset({
    "default", "owner_default", "interim", "decided_by", "alternatives",
    "canonical", "primary", "selected", "chosen", "winner", "winners", "choice",
    "selection", "installed_owner", "current_owner",
})
COLLECTIONS = frozenset({
    "slots", "add_rows", "amend_rows", "owner_defaults", "owners", "interim_rows",
    "current_owner_pin_amendments", "pinned_requirements",
})
CHOICE_CONTEXT = re.compile(
    r"\b(?:installed\s+(?:stack|owner)|"
    r"installs?\b[^.!?\n]{0,180}\b(?:owner\s+defaults?|core\s+row)|"
    r"(?:stays?|remains?|is)\s+the\s+(?:selection|baseline)|"
    r"(?:owner's\s+(?:order\s+)?(?:installs?|adds?|uses?|keeps?)|owner\s+(?:installs?|adds?|uses?))|"
    r"interim\b[^.!?\n/]{0,60}\b(?:installs|adds|uses|keeps)|"
    r"(?:owns?|serves)\s+(?:symbols|references|the\s+(?:slot|layer))|"
    r"remain\s+(?:workload-specific|conditional)\s+alternatives|"
    r"core\s+row|selected\s+(?:v?\d[\w.]*|(?-i:[A-Z])[\w.-]*(?:/[\w.-]+)?))\b", re.I)
INSTALL = re.compile(
    r"\b(?:run_slot|if\s+selected)\b|"
    r"\b(?:npm\s+(?:install|pack)|npx\s|uv\s+(?:tool|pip)\s+install|pip\s+install|"
    r"apt-get\s+install|cargo\s+install|go\s+install|install-hooks)\b", re.I)


@dataclass(frozen=True, slots=True)
class Binding:
    pointer: str
    kind: str
    text: str


def strings(node):
    """Read strings including JSON embedded inside returned tool text."""
    if isinstance(node, dict):
        for name, value in node.items():
            yield name
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)
    elif isinstance(node, str):
        yield node
        if node.lstrip().startswith(("{", "[")):
            try:
                inner = json.loads(node)
            except ValueError:
                return
            if isinstance(inner, (dict, list)):
                yield from strings(inner)


def bindings(node, pointer="", container="", installer=False, layer_owned=False):
    """Find identity-binding contexts by shape, not by a list of reviewed files."""
    if isinstance(node, dict):
        own_layer = bool(node.get("layer_id") or node.get("layer"))
        named_slot = any(isinstance(node.get(k), str) and SLOT.fullmatch(node[k])
                         for k in ("slot", "slot_id"))
        slot = named_slot or bool(node.get("slot_id") and
                                  set(node) & (IDENTITY_FIELDS - {"slot_id"}))
        collection = container in COLLECTIONS and bool(set(node) & IDENTITY_FIELDS)
        membership = own_layer and any(node.get(k) for k in ("owns", "uses", "owner", "default"))
        layer_component = (layer_owned or container == "pinned_requirements") and bool(
            node.get("name") or node.get("package") or node.get("repository"))
        owner = bool(node.get("owner") and set(node) & {"installed", "repository", "route", "slot", "layer"})
        if slot or collection or membership or layer_component or owner:
            selected = {k: v for k, v in node.items()
                        if k in IDENTITY_FIELDS or k in ("owns", "uses")}
            yield Binding(pointer, "slot" if slot else "owner" if owner else
                          "layer-component" if layer_component else "collection", json.dumps(selected))
        for name, value in node.items():
            child = pointer + "/" + name.replace("~", "~0").replace("/", "~1")
            data_selection = (name in ("choice", "selection") and isinstance(value, str)
                              and re.search(r"\b(?:modelBreakdowns|lastActivity|timestamps?|"
                                            r"session totals|unfiltered|daily row)\b", value, re.I))
            if name in SELECTION_FIELDS and value and not data_selection:
                yield Binding(child, name, json.dumps(value))
            yield from bindings(value, child, name, installer,
                                layer_owned or container == "pinned_requirements")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from bindings(value, pointer + "/" + str(index), container, installer, layer_owned)
    elif isinstance(node, str):
        if node.lstrip().startswith(("{", "[")):
            try:
                inner = json.loads(node)
            except ValueError:
                inner = None
            if isinstance(inner, (dict, list)):
                yield from bindings(inner, pointer + "/@json", container, installer, layer_owned)
                return
        # Paragraphs retain subject/context across sentences, as in an interim
        # amendment followed by the installed package's dependency requirements.
        for index, paragraph in enumerate(re.split(r"\n\s*\n", node)):
            # A cue in one table row never binds identities in neighboring rows.
            units = (paragraph.splitlines() if installer or paragraph.lstrip().startswith("|")
                     else re.split(r"\n(?=\s*(?:[-*] |#+ ))", paragraph))
            for unit_index, unit in enumerate(units):
                match = CHOICE_CONTEXT.search(unit)
                function = re.match(r"\s*([\w.-]+)\s*\(\)\s*\{", unit) if installer else None
                if match or function or (installer and INSTALL.search(unit)):
                    # A selected data-row key is not the software named elsewhere
                    # in its measurement paragraph. Bind only the selected name.
                    context = (function.group(1) if function else
                               match.group() if match and match.group().lower().startswith("selected ") else unit)
                    yield Binding(pointer + "/@text/" + str(index) + "/" + str(unit_index),
                                  "installer" if installer else "prose", context)


@cache
def normalize(value):
    return re.sub(r"[^a-z0-9@.+/-]+", "-", value.lower()).strip("-")


def identity_tokens(candidate):
    """Collect names, repositories, IDs, pins and package/CLI specs from one candidate."""
    tokens = set()
    for name in ("name", "component_id", "repository", "slot_id", "package", "package_name",
                 "install_function", "cli", "owner"):
        value = candidate.get(name)
        if not isinstance(value, str) or not value:
            continue
        value = re.sub(r"^https?://(?:www\.)?(?:github.com|huggingface.co)/", "", value).removesuffix(".git")
        tokens.add(normalize(value))
        if "/" in value:
            tokens.add(normalize(value.rsplit("/", 1)[-1]))
        for prefix in ("foundation-", "data-"):
            if value.startswith(prefix):
                tokens.add(normalize(value[len(prefix):]))
    # A version without a name is not an identity. Keep named package/pin specs.
    pin = candidate.get("pin") or candidate.get("current_pin")
    if isinstance(pin, str):
        tokens.add(normalize(pin))
        for token in tuple(tokens):
            tokens.add(token + "@" + pin)
    return {token for token in tokens if len(token) > 2}


@cache
def token_pattern(tokens):
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(t) for t in sorted(tokens, key=len, reverse=True)) +
                      r")(?![a-z0-9])") if tokens else re.compile(r"(?!)")


def named(text, tokens):
    return token_pattern(frozenset(tokens)).search(normalize(text)) is not None


def closure(packet, root, files):
    """Direct references, directories, all path strings and one JSON/string/link level."""
    directories = defaultdict(set)
    for relative in files:
        parts = relative.split("/")
        for count in range(1, len(parts)):
            directories["/".join(parts[:count])].add(relative)

    def resolve(value, parent=""):
        raw = re.split(r"\s+\(", value, maxsplit=1)[0].split("#")[0].split("?")[0].strip("`")
        if re.match(r"[a-z]+://", raw):
            return set()
        choices = {raw, posixpath.normpath(posixpath.join(parent, raw))}
        result = set()
        for choice in choices:
            choice = choice.removeprefix("./").rstrip("/")
            if choice in files:
                result.add(choice)
            result.update(directories.get(choice, ()))
        return result

    direct = set()
    for value in strings(packet):
        direct.update(resolve(value))
        for match in LINK.finditer(value):
            direct.update(resolve(next(g for g in match.groups() if g)))
    found = set(direct)
    for relative in direct:
        text = (root / relative).read_text(encoding="utf-8", errors="replace")
        try:
            values = list(strings(json.loads(text)))
        except ValueError:
            values = [text]
        for value in values:
            found.update(resolve(value, posixpath.dirname(relative)))
            for match in LINK.finditer(value):
                found.update(resolve(next(g for g in match.groups() if g), posixpath.dirname(relative)))
    return found


def scan_files(root, files):
    """Read every actual export file once, retaining independent structural contexts."""
    result = {}
    for relative in sorted(files):
        raw = (root / relative).read_bytes()
        if b"\0" in raw:
            continue
        text = raw.decode("utf-8", errors="replace")
        try:
            node = json.loads(text)
        except ValueError:
            node = text
        found = list(bindings(node, installer=relative.endswith((".sh", ".bash"))))
        if found:
            result[relative] = found
    return result


def audit_layer(adopted, winners, contexts, cited):
    """Report both separation and unequal role incidence, including reverse signals."""
    win = winner_keys(adopted, winners)
    other = {c["key"] for c in adopted} - win
    hits = {}
    for candidate in adopted:
        tokens = identity_tokens(candidate)
        hits[candidate["key"]] = [
            {"path": path, "pointer": item.pointer, "kind": item.kind}
            for path in sorted(cited & contexts.keys()) for item in contexts[path]
            if named(item.text, tokens)]
    marked = {key for key, found in hits.items() if found}
    w, n = len(marked & win), len(marked & other)
    separating = bool(win and other and ((w and not n) or (n and not w)))
    correlating = bool(win and other and w * len(other) != n * len(win))
    # Equal presence can still hide a per-candidate density signal.
    wd = sum(len(hits[key]) for key in win)
    nd = sum(len(hits[key]) for key in other)
    density = bool(win and other and wd * len(other) != nd * len(win))
    return {"scored": bool(win), "winners": len(win), "nonwinners": len(other),
            "winner_marked": w, "nonwinner_marked": n, "winner_bindings": wd, "nonwinner_bindings": nd,
            "separating": separating, "correlating": correlating or density, "hits": hits}


def audit_export(root, packets, winners, keys):
    """Return operator-only layer results; this function writes no file."""
    files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    contexts = scan_files(root, files)
    result = {}
    for layer, adopted in load_packets(packets, keys).items():
        packet = json.loads((packets / (layer.replace("::", "__", 1) + ".json")).read_text())
        cited = closure(packet, root, files)
        result[layer] = audit_layer(adopted, winners.get(layer) or [], contexts, cited)
    return result
