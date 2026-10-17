"""A static stylesheet cascade over one built page: which declarations reach an element, and which one wins.

The style tests of the harness atlas use it to check what the stylesheets actually do to the page's own elements,
not only how the selectors are spelled. It is test-only. The browser stays the measured check.

Parsing and selector matching are upstream's. tinycss2 1.5.1 parses the stylesheets into rules and declarations and
cssselect2 0.10.1 compiles each selector and matches it with its specificity (Matcher.match returns sorted
(specificity, order, pseudo, payload) tuples: by specificity, then by order of addition); both are hash-pinned in
.github/requirements-ci.txt. They are imported when a Cascade is built, so a missing package fails the style tests
alone. Screened 2026-10-17 from PyPI metadata, each package's documentation and its source at the pin: on the built
atlas page, 756 selectors compiled and 9,905 element-by-setting pairs gave the same matching rules and the same
specificity as the stdlib helper this replaced (design-plan.md "CSS cascade helper").

What neither package ships stays here, and each part is small:
- The tree. cssselect2 matches ElementTree-like trees and reads each node's tag, attributes, children, text and
  tail (:empty tests children and text). html.parser builds that tree, with the text before an element's first
  child as its text and the text after a child as that child's tail, and the helper's own Element keeps classes,
  parent, element children and the text of its whole subtree. A pseudo-class that needs state or data a static page
  lacks (:hover, :focus, :target and the like) never matches, as cssselect2 compiles it. A page whose tree a browser would build differently (a block start tag
  inside an open <p>, a row directly in a <table>) or that carries a style attribute raises ValueError.
- @media and @container. Neither package evaluates a media query. @media is evaluated against one environment: a
  medium, a viewport width in rem, the light scheme and no reduced motion. An @container rule that reaches an element
  raises, since no query container is evaluated. Any other at-rule raises.
- Shorthands. margin, padding and border, with their -block and -inline forms, and gap expand to longhands so that a
  shorthand and a longhand compete; values compare as written, with whitespace normalized. Every other property
  compares by its own name only.
- The cascade order. All sheets are author sheets without layers, so the winner is the highest (importance,
  specificity, order of appearance), CSS Cascade Level 5 section 6.1 (https://www.w3.org/TR/css-cascade-5/#cascade-sort).
  A user-action pseudo-class never matches a static element, and a rule with a pseudo-element styles that
  pseudo-element, not the element.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
import xml.etree.ElementTree as ET

VOID = frozenset("area base br col embed hr img input link meta source track wbr".split())
# Start tags that close an open <p> in a browser: the "in body" insertion mode of the HTML Living Standard,
# https://html.spec.whatwg.org/multipage/parsing.html#parsing-main-inbody
CLOSES_P = frozenset("address article aside blockquote center dd details dialog dir div dl dt fieldset figcaption figure footer form "
                     "h1 h2 h3 h4 h5 h6 header hgroup hr li listing main menu nav ol p pre search section summary table ul xmp".split())
_WIDTH = re.compile(r"\((min|max)-width:\s*([\d.]+)rem\)")
_SIDES = ("top", "right", "bottom", "left")


def _libraries():
    """The two upstream packages, imported when a Cascade is built so that only the style tests need them."""
    import cssselect2
    import tinycss2
    return cssselect2, tinycss2


class Element:
    __slots__ = ("tag", "attrs", "classes", "parent", "children", "text", "etree")

    def __init__(self, tag: str, attrs: dict, parent: "Element | None"):
        self.tag, self.attrs, self.parent, self.children, self.text = tag, attrs, parent, [], []
        self.classes = frozenset((attrs.get("class") or "").split())
        self.etree = None

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
        parent = self.open[-1]
        if parent is self.document:
            if self.document.children:
                raise ValueError("a page has one root element")
            element.etree = ET.Element(tag, element.attrs)
        else:
            element.etree = ET.SubElement(parent.etree, tag, element.attrs)
        parent.children.append(element)
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
        node = self.open[-1].etree
        if node is not None:
            # ElementTree keeps text before the first child in .text and later text in the previous child's .tail.
            if len(node):
                node[-1].tail = (node[-1].tail or "") + data
            else:
                node.text = (node.text or "") + data


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
    compiled: object
    specificity: tuple
    media: tuple
    declarations: tuple
    order: tuple


def _text(tokens) -> str:
    """Tokens as one whitespace-normalized string."""
    _, tinycss2 = _libraries()
    return " ".join(tinycss2.serialize(tokens).split())


def _declarations(content) -> list[tuple[str, str, bool]]:
    _, tinycss2 = _libraries()
    out = []
    for item in tinycss2.parse_blocks_contents(content, skip_comments=True, skip_whitespace=True):
        if item.type != "declaration":
            raise ValueError(f"unsupported declaration block item: {item.type}")
        out.extend((longhand, part, item.important) for longhand, part in _longhands(item.lower_name, _text(item.value)))
    return out


def _selectors(prelude) -> list[str]:
    """The comma-separated selectors of a rule's prelude, each as normalized text."""
    parts, current = [], []
    for token in prelude:
        if token.type == "literal" and token.value == ",":
            parts.append(current)
            current = []
        else:
            current.append(token)
    parts.append(current)
    return [_text(part) for part in parts]


def stylesheet(text: str, sheet: str, position: int) -> list[Rule]:
    cssselect2, tinycss2 = _libraries()
    rules: list[Rule] = []

    def walk(items, media: tuple) -> None:
        for item in items:
            if item.type == "error":
                raise ValueError(f"unparsed stylesheet text in {sheet}: {item.message}")
            if item.type == "at-rule" and item.lower_at_keyword in ("media", "container"):
                inner = tinycss2.parse_rule_list(item.content or [], skip_comments=True, skip_whitespace=True)
                walk(inner, media + (f"@{item.lower_at_keyword} {_text(item.prelude)}",))
            elif item.type == "at-rule":
                raise ValueError(f"unsupported at-rule in {sheet}: @{item.at_keyword}")
            else:
                declarations = tuple(_declarations(item.content))
                for selector in _selectors(item.prelude):
                    (compiled,) = cssselect2.compile_selector_list(selector)
                    rules.append(Rule(sheet, selector, compiled, compiled.specificity, media, declarations, (position, len(rules))))

    walk(tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True), ())
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
        cssselect2, _ = _libraries()
        tree = _Tree()
        tree.feed(html)
        tree.close()
        self.elements = tree.elements
        styled = [element.label() for element in self.elements if "style" in element.attrs]
        if styled:
            raise ValueError(f"style attributes are not ranked here: {styled[:3]}")
        self.rules = [rule for position, (name, text) in enumerate(sheets) for rule in stylesheet(text, name, position)]
        self._wrappers: dict[int, object] = {}

        def wrap(wrapper) -> None:
            self._wrappers[id(wrapper.etree_element)] = wrapper
            for child in wrapper.iter_children():
                wrap(child)

        wrap(cssselect2.ElementWrapper.from_html_root(tree.document.children[0].etree))
        self._matchers: dict[tuple, object] = {}

    def _matcher(self, environment: tuple):
        """The environment's rules in cssselect2's Matcher, each selector with its rule as the payload."""
        if environment not in self._matchers:
            cssselect2, _ = _libraries()
            matcher = cssselect2.Matcher()
            for rule in self.rules:
                if _media_holds(rule.media, environment):
                    matcher.add_selector(rule.compiled, rule)
            self._matchers[environment] = matcher
        return self._matchers[environment]

    def declarations(self, element: Element, environment: tuple) -> list[Declaration]:
        """Every declaration that reaches the element in the environment, in order of appearance."""
        hits = [rule for _, _, pseudo, rule in self._matcher(environment).match(self._wrappers[id(element.etree)]) if pseudo is None]
        out = []
        for rule in sorted(hits, key=lambda rule: rule.order):
            if any(prelude.startswith("@container") for prelude in rule.media):
                raise ValueError(f"a container query reaches {element.label()}: {rule.selector}")
            out.extend(Declaration(name, value, important, rule.sheet, rule.selector, rule.specificity, rule.order + (index,))
                       for index, (name, value, important) in enumerate(rule.declarations))
        return out

    def winner(self, element: Element, name: str, environment: tuple) -> Declaration | None:
        found = [declaration for declaration in self.declarations(element, environment) if declaration.property == name]
        return max(found, key=Declaration.rank, default=None)
