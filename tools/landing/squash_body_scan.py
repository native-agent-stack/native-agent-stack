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
  * an email address that is not a no-reply one. Every @ is judged, on its line, by CPython's RFC 5322 parser (`address_at`; #1027 round 3,
    on Claude's micro and the GPT family's verdict at 37e242c0: the parser finds the addresses as well as reads them, so none passes for
    want of a pattern that matches it): the local part before the @ and the domain after it are read as the parser reads an addr-spec, with quoted strings, comments and
    white space around the @, domain literals and domains of any form, and an @ inside a quoted string is judged inside it too. An @ with
    no local part before it (the start of a line, a special such as < or :, markup that wraps the name after it: the backticked
    `@file.md` import of an agent instruction file) or no domain after it is no address; text around an @ that the parser cannot read whole and without a defect is
    refused. An address passes only as one of the allowances below, compared whole after quotes and quoted pairs are undone (so "x"@<domain>
    is x@<domain>), and only when its local part holds no @ and neither a quote nor an @ follows its domain: the domain
    users.noreply.github.com (GitHub's documented ID+USERNAME and USERNAME forms) or a local part of exactly noreply or no-reply, public by
    construction (the vendor trailers `Co-Authored-By: ... <noreply@...>` are in nearly every squash body). Markup is no part of an address
    only when it wraps it (backticks, asterisks or quotes before it that close right after it), and `+` or `!` in front of a local part are
    part of it. Two things that the parser reads as addresses are not (the CC's ruling of 2026-10-12): a systemd unit instance,
    <name>@<instance>.<type> with a type of service, timer, socket, path or mount (systemd/systemd man/systemd.unit.xml: the unit name prefix
    is ASCII letters, digits and : - _ . only, and the instance goes between the @ and the type suffix) whose instance is not dotted like an
    address's domain, and the template unit <name>@.<type> itself; and an address of VENDOR_TRAILER_ADDRESSES, a short list of vendor
    co-author trailer addresses that are not no-reply ones, each with the vendor source it comes from. Two more are not, by the ruling on
    round 3: a source locator, <repository>@<object name> (this repository's repo@pin form: the whole domain is a git object name, 7 to
    64 hex digits), and the one address of REPOSITORY_TRAILER_ADDRESSES, the co-author address of this repository's synthetic scratch
    identity. A tag or a branch after an @ is refused, as every other domain without a dot is;
  * a name of the names file, case-insensitively, as a whole token: not inside a longer run of letters or digits (the host-name
    scanner's boundary rule, host_name_scan.py `boundary_filter`, which keeps `sam` out of `sample`). Hex and base64 spellings are not
    decoded. An entry equal to the running host's own name (socket.gethostname(), as `hostname` prints it, compared when the scan runs and
    never printed) is a warning, not a refusal (the CC's ruling: the host name is hygiene, never a blocker): its occurrences are counted.
The names file holds one assignment, LANDING_PROHIBITED_NAMES=<name>,<name>,... (an `export ` prefix and one pair of quotes are allowed),
the list the tests read from the environment under that name. It is parsed here, never sourced: no line of it runs, and no name reaches a
shell variable, an argument or the output. It must name at least one identity, and its value must be one that a shell reads as the same
list (read_names), or the scan fails closed.

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
NAMES_VALUE = re.compile(r"""'([^']*)'|"([^"$`\\]*)"|([^\s'"$`\\;&|<>()#]*)""")  # single-quoted, double-quoted or bare (read_names)
WSL_HOME = re.compile(r"\\{2,}wsl(?:\.localhost|\$)\\+[A-Za-z0-9_.-]+\\+home\\+(?!example(?:\\|\b))[A-Za-z0-9_.-]+", re.IGNORECASE)
# CPython v3.13.16 Lib/email/_header_value_parser.py at cbc944f4bc59, the RFC 5322 oracle of the CC's adjudication at e203d014 (rule 4),
# :83-97: the parser's own classes. An atom's text is any character that is neither a special nor white space (get_atext :1219-1233), so
# it takes letters of any script; a line end ends a line here, since the parser reads unfolded text (get_fws :1059-1069).
SPECIALS, WSP = _header_value_parser.SPECIALS, _header_value_parser.WSP
# The repository's own address shape (scripts/host_name_scan.py:174, `_config`): a domain with a dot and two letters or more after it. It
# no longer finds addresses (round 3); the unit allowance below uses it to tell an instance that is an address's domain.
DOMAIN = re.compile(r"[\w.-]+\.[A-Za-z]{2,}")
MARKUP = re.compile(r"[`*']+")  # a code span's backticks, emphasis or strong asterisks, quotes: presentation only when it also closes the address
NO_REPLY_DOMAIN = "users.noreply.github.com"
NO_REPLY_LOCAL_PARTS = ("noreply", "no-reply")
# systemd/systemd@c7a8e871de34 man/systemd.unit.xml:121-135: a unit name prefix is ASCII letters, digits and : - _ . (and \, which no address
# match holds), the type suffix one of eleven, and a template instance is formed by inserting the instance name between the @ and the suffix.
# The ruling named six of the types; the other five (device, automount, swap, slice, scope) stay refused, and so does `target` since #1027
# round 2 (the CC's adjudication at e203d014): it is a delegated top-level domain (IANA tlds-alpha-by-domain.txt, version 2026101200, lists
# TARGET and none of the five kept), so an address at <x>.target has the unit shape. A bare unit, with no @, is no address and needs nothing.
# A template unit "must have a single @ at the end of the unit name prefix (right before the type suffix)" (:130-135; getty@.service, :2404),
# which the parser cannot read as an address (no domain starts with a dot), so it is no address either.
UNIT_TYPES = ("service", "timer", "socket", "path", "mount")
UNIT_CHARACTERS = re.compile(r"[A-Za-z0-9:_.-]+")
TEMPLATE_SUFFIX = re.compile(r"\.(?:" + "|".join(UNIT_TYPES) + ")", re.IGNORECASE)
# Co-author trailer addresses of vendors that are not no-reply ones, each with the vendor source it comes from (the CC's ruling of
# 2026-10-12; #1002's email registry replaces this list). The vendor's current trailer is Codex <noreply@openai.com> (openai/codex@092d3acd6bec
# codex-rs/ext/git-attribution/src/world_state.rs:11 and :19), which passes as a no-reply address; the older one is in the vendor's own history.
VENDOR_TRAILER_ADDRESSES = {
    "codex@openai.com": "openai/codex@db22c91e61cc80defa5bbafc22bd8a8c7672e5e1, message line 38: Co-authored-by: Codex <codex@openai.com>",
}
# The co-author trailer address of this repository's own synthetic scratch identity, with its source in the repository (the CC's ruling of
# 2026-10-12 on #1027 round 3: one exact address, cited as the vendor list is). It names no person and no host: the scratch scripts commit
# with it, and 341 of main's last 600 commit messages at 5421e5d67017 carry it as a co-author trailer (measured 2026-10-12).
REPOSITORY_TRAILER_ADDRESSES = {
    "scout@local": "this repository, evidence/artifacts/omniroute-post-terminal-drain-20261005/scripts/build-drain.sh.txt:36: "
                   "the scratch commits' name Scout and address scout@local; in main's history as Co-authored-by: Scout <scout@local>",
}
# A source locator, <repository>@<object name>, is no address (the same ruling): this repository cites a source as repo@pin:path:line
# (CLAUDE.md:7), and the pin is a git object name, "the full SHA-1 object name (40-byte hexadecimal string), or a leading substring that
# is unique within the repository" (git/git@v2.53.0 Documentation/revisions.adoc:14-16). Git's own abbreviation has 7 hex digits or more
# (object-name.h:137 FALLBACK_DEFAULT_ABBREV, object-name.c:857-858; a shorter one, which core.abbrev allows, is refused here) and the
# longest name has 64 (hash.h:201-202, :208, SHA-256). The whole domain is the object name, so nothing of a host name's form passes, and
# the local part has only the characters of a repository's path. A tag, a branch and any other revision after the @ stay refused:
# nothing tells them from a host name.
OBJECT_NAME = re.compile(r"[0-9a-f]{7,64}")
REPOSITORY_PATH = re.compile(r"[A-Za-z0-9._/-]+")
CLASS_WSL_HOME = "WSL UNC home path"
CLASS_EMAIL = "email other than a no-reply address"
CLASS_NAME = "prohibited name"


def read_names(path):
    """The identities of the names file's last LANDING_PROHIBITED_NAMES assignment; ValueError when there is none, it names nobody, or its
    value is not one of the documented forms. The scan reads only a value that a shell reads as the same list, so no listed identity goes
    unchecked for text the two would read differently (#1027 round 3: Claude's P3-1 at e203d014, the GPT family's follow-up 2 at
    37e242c0): a list with no white space, quote or character that a shell treats as syntax, or a list in one pair of quotes (in double
    quotes, without $, ` or \\), white space after it allowed."""
    value = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        found = re.match(r"\s*(?:export\s+)?" + NAMES_VARIABLE + r"=(.*)$", line)
        if found:
            value = found.group(1).strip()
    if value is None:
        raise ValueError("no assignment")
    form = NAMES_VALUE.fullmatch(value)
    if form is None:
        raise ValueError("not a documented form")
    value = next(group for group in form.groups() if group is not None)
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


def atext(character):
    """True for a character of an atom's text (get_atext :1219-1233): neither a special, white space nor a line end."""
    return character not in SPECIALS and character not in WSP and character not in "\r\n"


def quoted_strings(line):
    """{index of each closing DQUOTE: index of its opening one} of a line, paired from left to right as get_bare_quoted_string (:1235-1275)
    reads a quoted string: from a DQUOTE to the next one that no backslash quotes (a quoted pair, _get_ptext_to_endchars :1027-1057). A
    DQUOTE that nothing after it closes opens nothing here."""
    found, start = {}, line.find('"')
    while start != -1:
        end = start + 1
        while end < len(line) and line[end] != '"':
            end += 2 if line[end] == "\\" else 1
        if end >= len(line):
            break
        found[end] = start
        start = line.find('"', end + 1)
    return found


def comments_of(line):
    """{index of each ")" that closes a comment: index of its "("} of a line, nested comments included, as get_comment (:1277-1300) reads
    them; in a comment a backslash quotes the character after it (get_qp_ctext :1187-1202). A "(" that nothing closes opens nothing here."""
    found, opened, index = {}, [], 0
    while index < len(line):
        if line[index] == "\\" and opened:
            index += 2
            continue
        if line[index] == "(":
            opened.append(index)
        elif line[index] == ")" and opened:
            found[index] = opened.pop()
        index += 1
    return found


def cfws_before(line, lo, end, comments):
    """Where the CFWS (white space and comments, get_cfws :1302-1313) that ends at index end of line[lo:] begins."""
    while end > lo:
        if line[end - 1] in WSP:
            end -= 1
        elif comments.get(end - 1, -1) >= lo:
            end = comments[end - 1]
        else:
            break
    return end


def cfws_after(line, start, hi, comments):
    """Where the CFWS that starts at index start of line[:hi] ends (comments maps each "(" to its ")" here)."""
    while start < hi:
        if line[start] in WSP:
            start += 1
        elif comments.get(start, hi) < hi:
            start = comments[start] + 1
        else:
            break
    return start


def local_start(line, lo, at, quoted, comments):
    """Where the local part that ends at the @ at index at of line[lo:] begins, read from right to left as get_local_part (:1486-1523) and
    get_obs_local_part (:1525-1575) read one from left to right: words (atoms, quoted strings :1315-1331, and a backslash, which the
    obsolete form keeps with a defect, :1539-1546) that touch each other or are joined by dots, with CFWS around them. A word that only white
    space or a comment joins to the next is prose, not part of the local part. at when nothing a local part ends with comes before the @;
    None when a DQUOTE that pairs with none touches the local part (the parser would read a quoted string from it to the line's end)."""
    index = start = cfws_before(line, lo, at, comments)
    if index == lo or not (line[index - 1] in '".\\' or atext(line[index - 1])):
        return at
    while index > lo:
        character = line[index - 1]
        if character == ".":
            start = index - 1
            index = cfws_before(line, lo, index - 1, comments)
            continue
        if character == '"':
            if quoted.get(index - 1, -1) < lo:
                return None
            index = quoted[index - 1]
        elif character == "\\":
            index -= 1
        elif atext(character):
            while index > lo and atext(line[index - 1]):
                index -= 1
        else:
            break
        start = index
        before = cfws_before(line, lo, index, comments)
        if before < index and not (before > lo and line[before - 1] == "."):
            break
        index = before
    return start


def domain_end(line, start, hi, opened):
    """Where the domain that starts at index start (just after an @) of line[:hi] ends, read as get_domain (:1644-1680) reads one: CFWS,
    then a domain literal (get_domain_literal :1605-1642) or the atoms and dots of a dot-atom or an obsolete domain, less the dots that end a
    sentence (an address at a.com-b is not one at a.com). start when no domain follows the @; None for a domain literal that does not
    close, which the parser reads with a defect. opened maps each "(" of a comment to its ")"."""
    index = cfws_after(line, start, hi, opened)
    if index < hi and line[index] == "[":
        end = index + 1
        while end < hi and line[end] != "]":
            end += 2 if line[end] == "\\" else 1
        return None if end >= hi else end + 1
    end = index
    while end < hi and (line[end] == "." or atext(line[end])):
        end += 1
    while end > index and line[end - 1] == ".":
        end -= 1
    return end if end > index else start


def address_at(line, lo, hi, at, quoted, comments, opened):
    """The address around the @ at index at of line[lo:hi] as CPython's RFC 5322 parser reads it: (local part, domain, the character
    after the domain) lower-cased; "" for no address, None for text the parser does not read whole and without a defect, which no allowance
    passes. The atext characters allow a backtick, an asterisk or a quote in a local part or a domain, so markup counts as outside the
    address only when it wraps it: a run of them before the local part that closes, reversed, at the end of the domain (a code span, bold,
    a quoted word). Any other character in front, `+` and `!` included, is part of the local part, which the allowances compare whole
    (Astra's P1 at e203d014). Markup that wraps the name after an @ leaves no local part: the backticked `@file.md` import of an agent
    instruction file. The
    parser undoes quotes and quoted pairs, so "x"@<domain> is the address x@<domain> (RFC 5322 3.2.4, rfc5322.txt:746-757: "quoted-string is
    identical to atom, semantically"); get_addr_spec :1682-1696, LocalPart.local_part :634-654, AddrSpec.domain :544-547; all_defects names
    each deviation, an obsolete form's included."""
    start, end = local_start(line, lo, at, quoted, comments), domain_end(line, at + 1, hi, opened)
    if start is None or end is None:
        return None
    local, domain = line[start:at], line[at + 1:end]
    markup = MARKUP.match(local)
    if markup and domain.endswith(markup.group()[::-1]):
        local, domain = local[markup.end():], domain[:-markup.end()].rstrip(".")
    elif markup and line.startswith(markup.group()[::-1], end, hi):  # after a domain literal, whose "]" ends it before any markup
        local, end = local[markup.end():], end + markup.end()
    if not local.strip(" \t") or not domain.strip(" \t"):
        return ""
    if TEMPLATE_SUFFIX.fullmatch(domain) and UNIT_CHARACTERS.fullmatch(local):
        return ""
    try:
        spec, rest = _header_value_parser.get_addr_spec(f"{local}@{domain}")
    except errors.HeaderParseError:
        return None
    if rest or spec.all_defects or spec.domain is None:
        return None
    return spec.local_part.lower(), spec.domain.lower(), line[end] if end < hi else ""


def mailbox(found):
    """True when found (see address_at) is an address that is not a no-reply one, a vendor or repository trailer address, a source locator
    or a systemd unit instance."""
    if found == "":
        return False
    if found is None:
        return True
    local, domain, following = found
    if "@" in local or following in ('"', "@"):
        # An allowance passes only a whole address that holds no other and that none touches (Claude's micro at 37e242c0, W1 and W2).
        # Each @ is also judged by itself (address_lines), so an address inside or beside an allowed one is refused there as well.
        return True
    if domain == NO_REPLY_DOMAIN or local in NO_REPLY_LOCAL_PARTS or f"{local}@{domain}" in VENDOR_TRAILER_ADDRESSES:
        return False
    if f"{local}@{domain}" in REPOSITORY_TRAILER_ADDRESSES:
        return False
    if OBJECT_NAME.fullmatch(domain) and REPOSITORY_PATH.fullmatch(local.lstrip("`*'")):
        return False  # markup in front may close after the locator's path, as in a code span of <repository>@<object name>:<path>
    instance, _, unit_type = domain.rpartition(".")
    if unit_type in UNIT_TYPES and UNIT_CHARACTERS.fullmatch(local) and UNIT_CHARACTERS.fullmatch(instance):
        # Claude's B1 at e203d014: <local>@<provider>.com.service had the unit shape. A unit is kept only when <local>@<instance> is no
        # address, that is when the instance does not start with an address's domain (any local part is one, quoted).
        return DOMAIN.match(instance) is not None
    return True


def address_lines(text):
    """The numbers of the lines of text that hold an @ the address rule refuses. Each @ outside a quoted string is judged on its line, and
    each @ inside one is judged inside it, the quotes bounding it as a line's ends do; a line stops being read at its first refusal."""
    refused = set()
    for number, whole in enumerate(text.split("\n"), 1):
        for line in whole.split("\r") if "@" in whole else ():
            quoted, comments = quoted_strings(line), comments_of(line)
            opened, inside = {start: end for end, start in comments.items()}, {}
            for end, start in quoted.items():
                inside.update(dict.fromkeys(range(start + 1, end), (start + 1, end)))
            for at in (index for index, character in enumerate(line) if character == "@"):
                lo, hi = inside.get(at, (0, len(line)))
                if mailbox(address_at(line, lo, hi, at, quoted if hi == len(line) else {}, comments, opened)):
                    refused.add(number)
                    break
    return refused


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
    found |= {(CLASS_EMAIL, number) for number in address_lines(text)}
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
