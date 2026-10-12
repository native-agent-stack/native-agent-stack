#!/usr/bin/env python3
r"""Publication scan of a squash commit body, for the CC landing scripts (#1027, Astra's P1 at d6be1b02, 2026-10-12).

usage: squash_body_scan.py <body file> <scripts/validate.py> <names file>   (the landing scripts run it as python3 -E -s -B)

The squash body becomes the commit message on main for good, and `gh pr merge --body-file` sends whatever bytes the file holds when the
merge call starts (cli/cli v2.102.0 pkg/cmd/pr/merge/merge.go:146-153 reads it, :292-293 and http.go:72-75 send it as the mutation's
CommitBody; pkg/cmdutil/file_input.go:8-16). nas_land.sh and uet_land.sh copy the file once to a private snapshot, run this scan on the
snapshot, and give gh that same snapshot. The scan reads the text, and its percent-decoded form, for:
  * every pattern of PRIVATE_CONTENT in the given scripts/validate.py, the repository's own table for published text (home paths, the
    dash-encoded and graph-id forms, Windows user paths, tokens, session identifiers);
  * a WSL UNC home path, \\wsl.localhost\<distro>\home\<user> or the older \\wsl$\<distro>\home\<user>, which PRIVATE_CONTENT does not
    match (it knows the forward-slash forms); any run of backslashes counts for one, since Markdown and JSON double them;
  * an email address that is not a no-reply one: the domain users.noreply.github.com (GitHub's documented ID+USERNAME and USERNAME forms)
    or a local part of exactly noreply or no-reply is public by construction and passes; the vendor trailers `Co-Authored-By: ... <noreply@...>`
    are in nearly every squash body. The address shape is the repository's own native private-email rule (host_name_scan.py, `_config`:
    the RFC 5322 atext characters before the @), with a lookbehind so that a long run of such characters costs one pass, and a local part
    may also hold quoted strings ("x"@<domain>, RFC 5322 3.2.4; #1027 round 2). Each address is read as CPython's RFC 5322 parser reads it
    (`address`): quotes and quoted pairs undone, the whole local part and the whole domain kept, so an allowance below compares the complete
    address; markup is no part of it only when it wraps it (backticks, asterisks or quotes before it that close right after it), and `+`
    or `!` in front of a local part are part of it. Two things that have the shape are not addresses (the CC's ruling of 2026-10-12): a
    systemd unit instance, <name>@<instance>.<type> with a type of service, timer, socket, path or mount (systemd/systemd
    man/systemd.unit.xml: the unit name prefix is ASCII letters, digits and : - _ . only, and the instance goes between the @ and the type
    suffix) whose <name>@<instance> is not itself an address, and an address of VENDOR_TRAILER_ADDRESSES, a short list of vendor co-author
    trailer addresses that are not no-reply ones, each with the vendor source it comes from;
  * a name of the names file, case-insensitively, as a whole token: not inside a longer run of letters or digits (the host-name
    scanner's boundary rule, host_name_scan.py `boundary_filter`, which keeps `sam` out of `sample`). Hex and base64 spellings are not
    decoded. An entry equal to the running host's own name (socket.gethostname(), as `hostname` prints it, compared when the scan runs and
    never printed) is a warning, not a refusal (the CC's ruling: the host name is hygiene, never a blocker): its occurrences are counted.
The names file holds one assignment, LANDING_PROHIBITED_NAMES=<name>,<name>,... (an `export ` prefix and one pair of quotes are allowed),
the list the tests read from the environment under that name. It is parsed here, never sourced: no line of it runs, and no name reaches a
shell variable, an argument or the output. It must name at least one identity, or the scan fails closed.

Exit codes and the one line printed: 0 `squash body scan: clean (names_checked=<n>[, warnings=<k>])`, the warnings being the occurrences of the
host's own name, a count and nothing more; 1 `squash body scan: refused: <class> (line <n>)[; ...][ (warnings=<k>)]`, the classes from the
closed vocabulary above, with line numbers and never the matched text; 2 `squash body scan: could not run` (a file that cannot be read, a
names file without an identity, a validate.py that cannot be loaded or whose table is not (description, pattern) pairs, any exception: no
traceback, which would print paths). The landing scripts show none of this output but the warning count.
"""
import importlib.util
import re
import socket
import sys
from email import _header_value_parser, errors
from pathlib import Path
from urllib.parse import unquote

STATUS = "squash body scan: "
NAMES_VARIABLE = "LANDING_PROHIBITED_NAMES"
WSL_HOME = re.compile(r"\\{2,}wsl(?:\.localhost|\$)\\+[A-Za-z0-9_.-]+\\+home\\+(?!example(?:\\|\b))[A-Za-z0-9_.-]+", re.IGNORECASE)
LOCAL_PART = r"[\w.!#$%&'*+/=?^`{|}~-]"
# RFC 5322 (rfc-editor.org rfc5322.txt, sha256 cb459acc...) 3.4.1, :961: local-part = dot-atom / quoted-string / obs-local-part; 3.2.4,
# :735-744: a quoted-string is qtext or quoted pairs between two DQUOTEs, here on one line. Astra's P1 at e203d014: "x"@<provider> is a valid
# address that a run of atext alone never matches, so quoted strings and atext mix in the run (obs-local-part, :1939, words joined by dots).
# A run can start again after each quote, so text that runs letters and quotes together costs more: 15 KB of a"b repeated took 1.5 s
# (measured 2026-10-12); prose, with its spaces, does not.
QUOTED_STRING = r'"(?:[^"\\\r\n]|\\[^\r\n])*"'
DOMAIN = re.compile(r"[\w.-]+\.[A-Za-z]{2,}")  # the shape's domain: a dot and two letters or more after it
EMAIL = re.compile(r"(?<!" + LOCAL_PART + r")((?:" + QUOTED_STRING + "|" + LOCAL_PART + r")+)@(" + DOMAIN.pattern + ")")
DOMAIN_TEXT = re.compile(LOCAL_PART + "*")  # the domain after an @ as RFC 5322 reads it, atext and dots, which the shape's domain may stop short of
MARKUP = re.compile(r"[`*']+")  # a code span's backticks, emphasis or strong asterisks, quotes: presentation only when it also closes the address
NO_REPLY_DOMAIN = "users.noreply.github.com"
NO_REPLY_LOCAL_PARTS = ("noreply", "no-reply")
# systemd/systemd@c7a8e871de34 man/systemd.unit.xml:121-135: a unit name prefix is ASCII letters, digits and : - _ . (and \, which no address
# match holds), the type suffix one of eleven, and a template instance is formed by inserting the instance name between the @ and the suffix.
# The ruling named six of the types; the other five (device, automount, swap, slice, scope) stay refused, and so does `target` since #1027
# round 2 (the CC's adjudication at e203d014): it is a delegated top-level domain (IANA tlds-alpha-by-domain.txt, version 2026101200, lists
# TARGET and none of the five kept), so an address at <x>.target has the unit shape. A bare unit, with no @, is no address and needs nothing.
UNIT_TYPES = ("service", "timer", "socket", "path", "mount")
UNIT_CHARACTERS = re.compile(r"[A-Za-z0-9:_.-]+")
# Co-author trailer addresses of vendors that are not no-reply ones, each with the vendor source it comes from (the CC's ruling of
# 2026-10-12; #1002's email registry replaces this list). The vendor's current trailer is Codex <noreply@openai.com> (openai/codex@092d3acd6bec
# codex-rs/ext/git-attribution/src/world_state.rs:11 and :19), which passes as a no-reply address; the older one is in the vendor's own history.
VENDOR_TRAILER_ADDRESSES = {
    "codex@openai.com": "openai/codex@db22c91e61cc80defa5bbafc22bd8a8c7672e5e1, message line 38: Co-authored-by: Codex <codex@openai.com>",
}
CLASS_WSL_HOME = "WSL UNC home path"
CLASS_EMAIL = "email other than a no-reply address"
CLASS_NAME = "prohibited name"


def read_names(path):
    """The identities of the names file's last LANDING_PROHIBITED_NAMES assignment; ValueError when there is none or it names nobody."""
    value = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        found = re.match(r"\s*(?:export\s+)?" + NAMES_VARIABLE + r"=(.*)$", line)
        if found:
            value = found.group(1).strip()
    if value is None:
        raise ValueError("no assignment")
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    names = [name.strip() for name in value.split(",") if name.strip()]
    if not names:
        raise ValueError("no identity")
    return names


def read_table(validate_py):
    """PRIVATE_CONTENT, the (description, pattern) pairs of the given scripts/validate.py; ValueError when it is not that."""
    spec = importlib.util.spec_from_file_location("landing_validate", validate_py)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    table = tuple(module.PRIVATE_CONTENT)
    if not table or any(not isinstance(description, str) or not hasattr(pattern, "search") for description, pattern in table):
        raise ValueError("PRIVATE_CONTENT is not a table of patterns")
    return table


def line_of(text, match):
    return text.count("\n", 0, match.start()) + 1


def address(text, match):
    """The address of an EMAIL match in text as CPython's RFC 5322 parser reads it, (local part, domain) lower-cased; "" for no address, None
    for one the parser does not read whole and without a defect, which no allowance passes.

    The local part is the match's run before the @, the domain the atext and dots after it less a final dot (an address at a.com-b is not
    one at a.com). The atext characters allow a backtick, an asterisk or a quote in a local part or a domain, so markup counts as outside the
    address only when it wraps it: a run of them before the local part that closes, reversed, at the end of the domain (a code span, bold, a
    quoted word). Any other character in front, `+` and `!` included, is part of the local part, which the allowances compare whole (Astra's
    P1 at e203d014: the old strip of every leading non-word character read +codex@<vendor> as the vendor's address). Nothing but such markup
    before the @ is no address: the backticked `@file.md` import of an agent instruction file. The parser undoes quotes and quoted pairs, so
    "x"@<domain> is the address x@<domain> (RFC 5322 3.2.4, rfc5322.txt:746-757: "quoted-string is identical to atom, semantically").
    CPython v3.13.16 Lib/email/_header_value_parser.py at cbc944f4bc59: get_addr_spec :1682-1696, get_local_part :1486-1523,
    get_obs_local_part :1525-1575, get_bare_quoted_string :1235-1275, get_domain :1644-1680, LocalPart.local_part :634-654 and
    AddrSpec.domain :544-547; all_defects names each deviation, an obsolete form's included."""
    local, domain = match.group(1), DOMAIN_TEXT.match(text, match.start(2)).group().rstrip(".")
    markup = MARKUP.match(local)
    if markup and domain.endswith(markup.group()[::-1]):
        local, domain = local[markup.end():], domain[:-markup.end()].rstrip(".")
    if not local:
        return ""
    try:
        spec, rest = _header_value_parser.get_addr_spec(f"{local}@{domain}")
    except errors.HeaderParseError:
        return None
    if rest or spec.all_defects or spec.domain is None:
        return None
    return spec.local_part.lower(), spec.domain.lower()


def mailbox(found):
    """True when found (see address) is an address that is not a no-reply one, a vendor trailer address or a systemd unit instance."""
    if found == "":
        return False
    if found is None:
        return True
    local, domain = found
    if domain == NO_REPLY_DOMAIN or local in NO_REPLY_LOCAL_PARTS or f"{local}@{domain}" in VENDOR_TRAILER_ADDRESSES:
        return False
    instance, _, unit_type = domain.rpartition(".")
    if unit_type in UNIT_TYPES and UNIT_CHARACTERS.fullmatch(local) and UNIT_CHARACTERS.fullmatch(instance):
        # Claude's B1 at e203d014: <local>@<provider>.com.service had the unit shape. A unit is kept only when <local>@<instance> is no
        # address, that is when the instance does not start with an address's domain (any local part is one, quoted).
        return DOMAIN.match(instance) is not None
    return True


def hits(text, table, name_patterns):
    """The {(class, line)} of every refused item in text: the first match of each PRIVATE_CONTENT pattern and of the UNC form, every
    address that is not a no-reply one (see mailbox) and every name. Classes only, never the matched text."""
    found = set()
    for description, pattern in table:
        match = pattern.search(text)
        if match:
            found.add((description, line_of(text, match)))
    match = WSL_HOME.search(text)
    if match:
        found.add((CLASS_WSL_HOME, line_of(text, match)))
    for match in EMAIL.finditer(text):
        if mailbox(address(text, match)):
            found.add((CLASS_EMAIL, line_of(text, match)))
    for pattern in name_patterns:
        for match in pattern.finditer(text):
            found.add((CLASS_NAME, line_of(text, match)))
    return found


def token(name):
    """A name as a whole token, in any letter case: not inside a longer run of letters or digits."""
    return re.compile(r"(?<![^\W_])" + re.escape(name) + r"(?![^\W_])", re.IGNORECASE)


def scan(raw, table, names, host=""):
    """(the refusal text for a body, or None when it is clean; the number of occurrences of the host's own name). A name equal to host,
    compared without regard to case, is counted and never refused; host is empty when there is none. A hit in the percent-decoded text counts
    when its class has none in the text itself (its line would be the decoded text's)."""
    own = [token(name) for name in names if host and name.casefold() == host.casefold()]
    others = [token(name) for name in names if not (host and name.casefold() == host.casefold())]
    found = hits(raw, table, others)
    decoded = unquote(raw)
    warnings = sum(len(pattern.findall(raw)) for pattern in own)
    if decoded != raw:
        classes = {description for description, _ in found}
        found |= {(description, 0) for description, _ in hits(decoded, table, others) if description not in classes}
        warnings = max(warnings, sum(len(pattern.findall(decoded)) for pattern in own))
    if not found:
        return None, warnings
    return "; ".join(f"{description} (line {line})" if line else f"{description} (percent-encoded)" for description, line in sorted(found)), warnings


def run(argv):
    try:
        if len(argv) != 4:
            raise ValueError("usage")
        data = Path(argv[1]).read_bytes()
        try:
            raw = data.decode("utf-8")
        except UnicodeError:
            raw = data.decode("latin-1")
        names = read_names(argv[3])
        refusal, warnings = scan(raw, read_table(argv[2]), names, socket.gethostname())
    except (Exception, SystemExit):  # one fixed line and no traceback, which would print paths; an exit while loading validate.py is no clean line
        print(STATUS + "could not run")
        return 2
    if refusal:
        print(f"{STATUS}refused: {refusal}" + (f" (warnings={warnings})" if warnings else ""))
        return 1
    print(f"{STATUS}clean (names_checked={len(names)}" + (f", warnings={warnings}" if warnings else "") + ")")
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv))
