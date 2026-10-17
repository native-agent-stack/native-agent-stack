"""A static stylesheet cascade over one built page: which declarations reach an element, and which one wins.

The style tests of the harness atlas use it to check what the stylesheets actually do to the page's own elements,
not only how the selectors are spelled. It is test-only and stdlib-only: the CI interpreter carries no third-party
HTML or CSS package (.github/requirements-ci.txt), and the selector libraries screened would not supply the cascade.
soupsieve 3.0.3 matches selectors on Beautiful Soup 4 trees and cssselect 1.6.0 translates them to XPath for an engine
such as lxml (PyPI metadata, read 2026-10-17); neither parses a stylesheet or ranks declarations. The browser stays
the measured check.

Scope, kept to what the local-pages stylesheets use:
- Elements come from html.parser with their tag, attributes, classes, parent, element children and text. A page
  whose tree a browser would build differently (a block start tag inside an open <p>, a row directly in a <table>)
  or that carries a style attribute raises ValueError.
- Selectors: type, *, #id, .class, [attr], [attr="v"], [attr^="v"]; :root, :first-child, :last-child,
  :first-of-type, :nth-child(an+b), :not(), :is(), :where() and a one-compound :has(); the descendant, >, + and ~
  combinators. A user-action pseudo-class never matches a static element, and a rule with a pseudo-element styles
  that pseudo-element, not the element. Any other syntax raises ValueError, so a stylesheet that outgrows this
  helper fails its test instead of passing it.
- Specificity follows Selectors Level 4 section 17 (https://www.w3.org/TR/selectors-4/#specificity-rules): :is(),
  :not() and :has() count their most specific argument, :where() counts zero. All sheets are author sheets without
  layers, so the winner is the highest (importance, specificity, order of appearance), CSS Cascade Level 5 section
  6.1 (https://www.w3.org/TR/css-cascade-5/#cascade-sort).
- @media is evaluated against one environment: a medium, a viewport width in rem, the light scheme and no reduced
  motion. An @container rule that reaches an element raises, since no query container is evaluated.
- margin, padding and border, with their -block and -inline forms, and gap expand to longhands so that a shorthand
  and a longhand compete; values compare as written, with whitespace normalized.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re

VOID = frozenset("area base br col embed hr img input link meta source track wbr".split())
# Start tags that close an open <p> in a browser: the "in body" insertion mode of the HTML Living Standard,
# https://html.spec.whatwg.org/multipage/parsing.html#parsing-main-inbody
CLOSES_P = frozenset("address article aside blockquote center dd details dialog dir div dl dt fieldset figcaption figure footer form "
                     "h1 h2 h3 h4 h5 h6 header hgroup hr li listing main menu nav ol p pre search section summary table ul xmp".split())
USER_ACTION = frozenset({"hover", "focus", "focus-visible", "focus-within", "active"})
_COMBINATOR = re.compile(r"\s*([>+~])\s*|\s+")
_TOKEN = re.compile(r"\*|[a-zA-Z][\w-]*|#[\w-]+|\.[\w-]+|\[[^\]]*\]")
_ATTRIBUTE = re.compile(r"""\[\s*([\w-]+)\s*(?:(\^?=)\s*(?:"([^"]*)"|'([^']*)'|([\w-]+))\s*)?\]""")
_NTH = re.compile(r"([+-]?\d*)n([+-]\d+)?|([+-]?\d+)")
_WIDTH = re.compile(r"\((min|max)-width:\s*([\d.]+)rem\)")
_SIDES = ("top", "right", "bottom", "left")


class Element:
    __slots__ = ("tag", "attrs", "classes", "parent", "children", "text")

    def __init__(self, tag: str, attrs: dict, parent: "Element | None"):
        self.tag, self.attrs, self.parent, self.children, self.text = tag, attrs, parent, [], []
        self.classes = frozenset((attrs.get("class") or "").split())

    def label(self) -> str:
        ident = f'#{self.attrs["id"]}' if self.attrs.get("id") else ""
        return self.tag + ident + "".join("." + name for name in sorted(self.classes))


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.document = Element("#document", {}, None)
        self.open, self.elements = [self.document], []

    def handle_starttag(self, tag, attrs):
        if tag in CLOSES_P and any(element.tag == "p" for element in self.open):
            raise ValueError(f"<{tag}> inside an open <p>: a browser closes the <p> first")
        if tag == "tr" and self.open[-1].tag == "table":
            raise ValueError("<tr> directly inside <table>: a browser adds a <tbody>")
        element = Element(tag, {name: value or "" for name, value in attrs}, self.open[-1])
        self.open[-1].children.append(element)
        self.elements.append(element)
        if tag not in VOID:
            self.open.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.open) - 1, 0, -1):
            if self.open[index].tag == tag:
                del self.open[index:]
                return

    def handle_data(self, data):
        for element in self.open[1:]:
            element.text.append(data)


def _split(text: str, separator: str) -> list[str]:
    """Split on a separator outside parentheses, brackets and quotes."""
    parts, depth, quote, start = [], 0, "", 0
    for index, char in enumerate(text):
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == separator and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return [part.strip() for part in parts]


def _compound(text: str, index: int) -> tuple[tuple, int]:
    simples = []
    while index < len(text) and text[index] not in " >+~":
        if text[index] == ":":
            match = re.compile(r"::?([\w-]+)").match(text, index)
            if match is None:
                raise ValueError(f"unsupported selector syntax: {text!r}")
            name, index = match.group(1).lower(), match.end()
            if match.group(0).startswith("::"):
                simples.append(("pseudo-element", name, None))
            elif index < len(text) and text[index] == "(":
                depth, start = 1, index + 1
                index += 1
                while depth:
                    depth += {"(": 1, ")": -1}.get(text[index], 0)
                    index += 1
                simples.append(("function", name, text[start:index - 1].strip()))
            else:
                simples.append(("pseudo", name, None))
            continue
        match = _TOKEN.match(text, index)
        if match is None:
            raise ValueError(f"unsupported selector syntax: {text!r}")
        token, index = match.group(0), match.end()
        if token == "*":
            simples.append(("any", None, None))
        elif token[0] == "#":
            simples.append(("id", token[1:], None))
        elif token[0] == ".":
            simples.append(("class", token[1:], None))
        elif token[0] == "[":
            attribute = _ATTRIBUTE.fullmatch(token)
            if attribute is None:
                raise ValueError(f"unsupported attribute selector: {token!r}")
            value = next((group for group in attribute.group(3, 4, 5) if group is not None), None)
            simples.append(("attribute", attribute.group(1).lower(), (attribute.group(2), value)))
        else:
            simples.append(("type", token.lower(), None))
    if not simples:
        raise ValueError(f"unsupported selector syntax: {text!r}")
    return tuple(simples), index


def parse_selector(text: str) -> list:
    """'a > b c' as [compound, '>', compound, ' ', compound]."""
    text, parts, index = text.strip(), [], 0
    while True:
        compound, index = _compound(text, index)
        parts.append(compound)
        if index == len(text):
            return parts
        match = _COMBINATOR.match(text, index)
        parts.append(match.group(1) or " ")
        index = match.end()


def _relative(text: str) -> tuple[str, tuple]:
    """A :has() argument: an optional leading combinator and exactly one compound."""
    combinator = text[0] if text[:1] in (">", "+", "~") else " "
    parts = parse_selector(text[1:] if combinator != " " else text)
    if len(parts) != 1 or combinator not in (">", " "):
        raise ValueError(f"unsupported :has() argument: {text!r}")
    return combinator, parts[0]


def specificity(parts: list) -> tuple[int, int, int]:
    ids = classes = types = 0
    for compound in parts[::2]:
        for kind, name, argument in compound:
            if kind == "id":
                ids += 1
            elif kind in ("class", "attribute", "pseudo"):
                classes += 1
            elif kind in ("type", "pseudo-element"):
                types += 1
            elif kind == "function" and name == "nth-child":
                classes += 1
            elif kind == "function" and name != "where":
                inner = [specificity([_relative(part)[1]]) if name == "has" else specificity(parse_selector(part)) for part in _split(argument, ",")]
                most = max(inner)
                ids, classes, types = ids + most[0], classes + most[1], types + most[2]
    return ids, classes, types


def _nth(argument: str, position: int) -> bool:
    text = argument.replace(" ", "").lower()
    if text in ("odd", "even"):
        step, offset = 2, 1 if text == "odd" else 0
    else:
        match = _NTH.fullmatch(text)
        if match is None:
            raise ValueError(f"unsupported :nth-child() argument: {argument!r}")
        if match.group(3) is not None:
            step, offset = 0, int(match.group(3))
        else:
            coefficient = match.group(1)
            step = -1 if coefficient == "-" else 1 if coefficient in ("", "+") else int(coefficient)
            offset = int(match.group(2) or 0)
    if step == 0:
        return position == offset
    count, remainder = divmod(position - offset, step)
    return remainder == 0 and count >= 0


def _descendants(element: Element):
    for child in element.children:
        yield child
        yield from _descendants(child)


def _matches_compound(element: Element, compound: tuple) -> bool:
    siblings = element.parent.children if element.parent is not None else [element]
    for kind, name, argument in compound:
        if kind == "pseudo-element" or (kind == "pseudo" and name in USER_ACTION):
            return False
        if kind == "type":
            matched = element.tag == name
        elif kind == "any":
            matched = True
        elif kind == "id":
            matched = element.attrs.get("id") == name
        elif kind == "class":
            matched = name in element.classes
        elif kind == "attribute":
            operator, value = argument
            actual = element.attrs.get(name)
            matched = actual is not None and (operator is None or (actual == value if operator == "=" else actual.startswith(value)))
        elif kind == "pseudo" and name == "root":
            matched = element.tag == "html"
        elif kind == "pseudo" and name in ("first-child", "last-child"):
            matched = siblings[0 if name == "first-child" else -1] is element
        elif kind == "pseudo" and name == "first-of-type":
            matched = next(sibling for sibling in siblings if sibling.tag == element.tag) is element
        elif kind == "function" and name == "nth-child":
            matched = _nth(argument, siblings.index(element) + 1)
        elif kind == "function" and name in ("is", "where", "not"):
            any_match = any(matches(element, parse_selector(part)) for part in _split(argument, ","))
            matched = not any_match if name == "not" else any_match
        elif kind == "function" and name == "has":
            relations = [_relative(part) for part in _split(argument, ",")]
            matched = any(_matches_compound(other, inner) for combinator, inner in relations
                          for other in (element.children if combinator == ">" else _descendants(element)))
        else:
            raise ValueError(f"unsupported selector: {kind} {name}")
        if not matched:
            return False
    return True


def _matches_from(element: Element, parts: list, index: int) -> bool:
    if element.tag == "#document" or not _matches_compound(element, parts[index]):
        return False
    if index == 0:
        return True
    combinator, left = parts[index - 1], index - 2
    if combinator == ">":
        return element.parent is not None and _matches_from(element.parent, parts, left)
    if combinator == " ":
        ancestor = element.parent
        while ancestor is not None:
            if _matches_from(ancestor, parts, left):
                return True
            ancestor = ancestor.parent
        return False
    siblings = element.parent.children
    before = siblings[:siblings.index(element)]
    if combinator == "+":
        return bool(before) and _matches_from(before[-1], parts, left)
    return any(_matches_from(sibling, parts, left) for sibling in before)


def matches(element: Element, parts: list) -> bool:
    return _matches_from(element, parts, len(parts) - 1)


def _longhands(name: str, value: str) -> list[tuple[str, str]]:
    tokens = _split(value, " ") if "(" in value else value.split()
    family = name.split("-")[0]
    if name in ("margin", "padding") and 1 <= len(tokens) <= 4:
        sides = tokens * 4 if len(tokens) == 1 else tokens * 2 if len(tokens) == 2 else [*tokens, tokens[1]] if len(tokens) == 3 else tokens
        return [(f"{name}-{side}", part) for side, part in zip(_SIDES, sides)]
    if name in ("margin-block", "padding-block", "margin-inline", "padding-inline") and 1 <= len(tokens) <= 2:
        first, second = tokens[0], tokens[-1]
        sides = ("top", "bottom") if name.endswith("block") else ("left", "right")
        return [(f"{family}-{sides[0]}", first), (f"{family}-{sides[1]}", second)]
    if name == "border":
        return [(f"border-{side}", value) for side in _SIDES]
    if name in ("border-block", "border-inline"):
        return [(f"border-{side}", value) for side in (("top", "bottom") if name.endswith("block") else ("left", "right"))]
    if name == "gap" and 1 <= len(tokens) <= 2:
        return [("row-gap", tokens[0]), ("column-gap", tokens[-1])]
    return [(name, value)]


@dataclass(frozen=True)
class Declaration:
    property: str
    value: str
    important: bool
    sheet: str
    selector: str
    specificity: tuple
    order: tuple

    def rank(self) -> tuple:
        return self.important, self.specificity, self.order


@dataclass(frozen=True)
class Rule:
    sheet: str
    selector: str
    parts: list
    specificity: tuple
    media: tuple
    declarations: tuple
    order: tuple


def _declarations(body: str) -> list[tuple[str, str, bool]]:
    out = []
    for item in _split(body, ";"):
        if not item:
            continue
        name, colon, value = item.partition(":")
        if not colon:
            raise ValueError(f"unsupported declaration: {item!r}")
        value = " ".join(value.split())
        important = value.endswith("!important")
        value = value[:-len("!important")].strip() if important else value
        out.extend((longhand, part, important) for longhand, part in _longhands(name.strip().lower(), value))
    return out


def stylesheet(text: str, sheet: str, position: int) -> list[Rule]:
    text, rules = re.sub(r"/\*.*?\*/", "", text, flags=re.S), []

    def walk(body: str, media: tuple) -> None:
        index = 0
        while True:
            opening = body.find("{", index)
            if opening < 0:
                if body[index:].strip():
                    raise ValueError(f"unparsed stylesheet text in {sheet}: {body[index:].strip()[:60]!r}")
                return
            prelude, depth, closing = " ".join(body[index:opening].split()), 1, opening + 1
            while depth:
                depth += {"{": 1, "}": -1}.get(body[closing], 0)
                closing += 1
            inner = body[opening + 1:closing - 1]
            if prelude.startswith(("@media ", "@container ")):
                walk(inner, media + (prelude,))
            elif prelude.startswith("@"):
                raise ValueError(f"unsupported at-rule in {sheet}: {prelude}")
            else:
                declarations = tuple(_declarations(inner))
                for selector in _split(prelude, ","):
                    parts = parse_selector(selector)
                    rules.append(Rule(sheet, selector, parts, specificity(parts), media, declarations, (position, len(rules))))
            index = closing

    walk(text, ())
    return rules


def _media_holds(media: tuple, environment: tuple) -> bool:
    medium, width = environment
    for prelude in media:
        if prelude.startswith("@container"):
            continue
        query = prelude[len("@media"):].strip()
        if "," in query:
            raise ValueError(f"unsupported media query list: {query}")
        for condition in (part.strip() for part in query.split(" and ")):
            bound = _WIDTH.fullmatch(condition)
            if condition in ("screen", "print"):
                holds = condition == medium
            elif bound:
                holds = width >= float(bound.group(2)) if bound.group(1) == "min" else width <= float(bound.group(2))
            elif condition in ("(prefers-color-scheme: dark)", "(prefers-reduced-motion: reduce)"):
                holds = False
            else:
                raise ValueError(f"unsupported media condition: {condition}")
            if not holds:
                return False
    return True


class Cascade:
    """One built page and its stylesheets in document order, as (name, text) pairs."""

    def __init__(self, html: str, sheets: list[tuple[str, str]]):
        tree = _Tree()
        tree.feed(html)
        tree.close()
        self.elements = tree.elements
        styled = [element.label() for element in self.elements if "style" in element.attrs]
        if styled:
            raise ValueError(f"style attributes are not ranked here: {styled[:3]}")
        self.rules = [rule for position, (name, text) in enumerate(sheets) for rule in stylesheet(text, name, position)]
        self._index: dict[tuple, list[Rule]] = {}
        for rule in self.rules:
            subject = rule.parts[-1]
            key = next(((kind, name) for kind, name, _ in subject if kind in ("id", "class", "type")), ("any", None))
            self._index.setdefault(key, []).append(rule)

    def declarations(self, element: Element, environment: tuple) -> list[Declaration]:
        """Every declaration that reaches the element in the environment, in order of appearance."""
        keys = [("any", None), ("type", element.tag)] + [("class", name) for name in element.classes]
        if element.attrs.get("id"):
            keys.append(("id", element.attrs["id"]))
        candidates = sorted({id(rule): rule for key in keys for rule in self._index.get(key, ())}.values(), key=lambda rule: rule.order)
        out = []
        for rule in candidates:
            if not _media_holds(rule.media, environment) or not matches(element, rule.parts):
                continue
            if any(prelude.startswith("@container") for prelude in rule.media):
                raise ValueError(f"a container query reaches {element.label()}: {rule.selector}")
            out.extend(Declaration(name, value, important, rule.sheet, rule.selector, rule.specificity, rule.order + (index,))
                       for index, (name, value, important) in enumerate(rule.declarations))
        return out

    def winner(self, element: Element, name: str, environment: tuple) -> Declaration | None:
        found = [declaration for declaration in self.declarations(element, environment) if declaration.property == name]
        return max(found, key=Declaration.rank, default=None)
