"""Read a recipe out of a web page: schema.org Recipe data when the site has it, otherwise the
page's title and description (where TikTok/Instagram put the caption). No network here."""

import json
import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser


@dataclass
class PageRecipe:
    title: str = ""
    servings: int | None = None
    minutes: int | None = None
    ingredients: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)


@dataclass
class Page:
    title: str = ""
    description: str = ""
    recipe: PageRecipe | None = None  # from schema.org data, when present


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ld: list[str] = []
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in_ld = self._in_title = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_ld, self._buf = True, []
        elif tag == "title":
            self._in_title, self._buf = True, []
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key in ("og:title", "og:description", "description", "twitter:description"):
                self.meta.setdefault(key, a.get("content", ""))

    def handle_data(self, data):
        if self._in_ld or self._in_title:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_ld:
            self.ld.append("".join(self._buf))
            self._in_ld = False
        elif tag == "title" and self._in_title:
            self.title = "".join(self._buf).strip()
            self._in_title = False


def _walk(node):
    """Every dict in a JSON-LD tree (handles @graph, lists, nesting)."""
    if isinstance(node, list):
        for x in node:
            yield from _walk(x)
    elif isinstance(node, dict):
        yield node
        for v in node.values():
            if isinstance(v, dict | list):
                yield from _walk(v)


def _is_recipe(d: dict) -> bool:
    t = d.get("@type")
    return t == "Recipe" or (isinstance(t, list) and "Recipe" in t)


def _text(v) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", str(v))).split())


def _duration_minutes(v) -> int | None:
    """ISO 8601 durations: PT1H30M -> 90."""
    if not isinstance(v, str):
        return None
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:\d+S)?", v.strip())
    if not m or not any(m.groups()):
        return None
    d, h, mins = (int(x or 0) for x in m.groups())
    return d * 1440 + h * 60 + mins or None


def _servings(v) -> int | None:
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, int | float):
        return int(v) or None
    if isinstance(v, str) and (m := re.search(r"\d+", v)):
        return int(m[0]) or None
    return None


def _steps(v) -> list[str]:
    out: list[str] = []
    if isinstance(v, str):
        out += [s for s in (_text(x) for x in re.split(r"\n+", v)) if s]
    elif isinstance(v, list):
        for x in v:
            out += _steps(x)
    elif isinstance(v, dict):
        if "itemListElement" in v:  # HowToSection
            out += _steps(v["itemListElement"])
        elif v.get("text"):
            out.append(_text(v["text"]))
    return out


def parse_page(html: str) -> Page:
    c = _Collector()
    c.feed(html)
    page = Page(
        title=_text(c.meta.get("og:title") or c.title),
        description=_text(
            c.meta.get("og:description")
            or c.meta.get("description")
            or c.meta.get("twitter:description")
            or ""
        ),
    )
    for block in c.ld:
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for d in _walk(data):
            if not _is_recipe(d):
                continue
            ingredients = [_text(x) for x in d.get("recipeIngredient") or [] if _text(x)]
            if not ingredients:
                continue
            page.recipe = PageRecipe(
                title=_text(d.get("name") or page.title),
                servings=_servings(d.get("recipeYield")),
                minutes=_duration_minutes(d.get("totalTime"))
                or _duration_minutes(d.get("cookTime")),
                ingredients=ingredients,
                steps=_steps(d.get("recipeInstructions")),
            )
            return page
    return page
