"""Ingredient lines: parse "2 lb chicken thighs, cut up" into parts, and normalize item names
so the same grocery item from different recipes (and later, receipts) lands on one key."""

import re
from dataclasses import dataclass
from fractions import Fraction

from meal.units import canonical

AISLES = (
    "Produce",
    "Meat & seafood",
    "Dairy & refrigerated",
    "Bakery",
    "Pantry",
    "Spices & baking",
    "Frozen",
    "Other",
)

_UNICODE_FRACTIONS = {
    "½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4", "⅕": "1/5", "⅖": "2/5",
    "⅗": "3/5", "⅘": "4/5", "⅙": "1/6", "⅚": "5/6", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8",
    "⅞": "7/8",
}  # fmt: skip
_WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "half": 0.5,
}  # fmt: skip

_NUM = r"\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?|\.\d+"
_QTY = re.compile(rf"^(?P<q1>{_NUM})(?:\s*(?:-|–|—|to|or)\s*(?P<q2>{_NUM}))?(?=[\s(a-zA-Z]|$)\s*")
_WORD_QTY = re.compile(r"^(?P<w>" + "|".join(_WORD_NUMBERS) + r")\b\s*", re.I)
_PAREN = re.compile(r"^\(([^)]*)\)\s*")
_BULLET = re.compile(r"^[\s\-–•*·▢□☐◦‣⁃]+")
_TO_TASTE = re.compile(r",?\s*\b(to taste|as needed|for serving|for garnish|optional)\b\.?", re.I)


@dataclass(frozen=True)
class ParsedLine:
    original: str
    quantity: float | None
    unit: str | None  # canonical unit (see meal.units), None = each / none
    name: str  # what's left: "chicken thighs"
    note: str | None  # prep and extras: "cut up", "15 oz", "to taste"


def _to_float(s: str) -> float:
    s = s.strip()
    total = Fraction(0)
    for part in s.split():
        total += Fraction(part)
    return float(total)


def parse_line(text: str) -> ParsedLine:
    original = " ".join(text.split())
    s = _BULLET.sub("", original)
    for u, ascii_frac in _UNICODE_FRACTIONS.items():
        s = re.sub(rf"(\d)\s*{u}", rf"\1 {ascii_frac}", s)
        s = s.replace(u, ascii_frac)

    notes: list[str] = []
    quantity: float | None = None
    if m := _QTY.match(s):
        try:
            quantity = _to_float(m["q2"] or m["q1"])  # ranges: buy for the top of the range
        except (ValueError, ZeroDivisionError):
            quantity = None
        s = s[m.end() :]
    elif m := _WORD_QTY.match(s):
        rest = s[m.end() :]
        # "a pinch", "two cloves", "an onion"; but not "a" in "a few" / "half-and-half"
        if not rest.lower().startswith(("few", "couple", "-")):
            quantity = float(_WORD_NUMBERS[m["w"].lower()])
            s = rest

    if m := _PAREN.match(s):  # "1 (15 oz) can beans"
        notes.append(m[1].strip())
        s = s[m.end() :]

    unit = None
    if quantity is not None or s.lower().startswith(("pinch", "dash", "handful")):
        words = s.split()
        for n in (2, 1):
            if len(words) >= n:
                candidate = " ".join(words[:n])
                if (u := canonical(candidate)) and (n == 1 or u == "fl oz"):
                    # A bare count word with nothing after it is the item: "2 heads" alone stays
                    if len(words) > n:
                        unit = u
                        s = " ".join(words[n:])
                    break
        if unit is not None and quantity is None:
            quantity = 1.0
        s = re.sub(r"^of\s+", "", s, flags=re.I)

    s = _TO_TASTE.sub(lambda m: notes.append(m[1].lower()) or "", s)
    # Trailing parenthetical -> note: "onion (about 1 cup)"
    while m := re.search(r"\s*\(([^)]*)\)\s*$", s):
        notes.append(m[1].strip())
        s = s[: m.start()]
    if "," in s:
        s, prep = s.split(",", 1)
        if prep.strip():
            notes.append(prep.strip())

    name = s.strip(" ,.;:-")
    return ParsedLine(
        original=original,
        quantity=quantity,
        unit=unit,
        name=name,
        note="; ".join(n for n in notes if n) or None,
    )


# --- Names ---------------------------------------------------------------------------------

_DROP_WORDS = frozenset(
    """fresh freshly large small medium extra-large jumbo chopped diced minced sliced grated
    finely roughly coarsely thinly thickly peeled seeded softened melted cubed halved
    quartered trimmed rinsed drained packed divided optional about heaping level good
    quality organic ripe room temperature""".split()
)
_NO_SINGULAR = frozenset(
    """molasses hummus asparagus couscous swiss greens grits oats brussels bass citrus lettuce
    floss cress hibiscus octopus""".split()
)


def _singular(word: str) -> str:
    if word in _NO_SINGULAR or len(word) <= 3 or word.endswith(("ss", "us", "is")):
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("oes"):
        return word[:-2]
    if word.endswith("ves") and word not in ("olives", "chives", "cloves"):
        return word[:-3] + "f"
    if word.endswith(("ches", "shes", "xes", "sses")):
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def normalize_name(name: str) -> str:
    """'Fresh Roma Tomatoes (diced)' -> 'roma tomato'. A stable key, not a display name."""
    s = re.sub(r"\([^)]*\)", " ", name.lower())
    s = s.split(",", 1)[0]
    s = re.sub(r"[^a-z0-9&' -]", " ", s).replace("'", "")
    words = [w for w in s.split() if w not in _DROP_WORDS]
    if not words:
        return " ".join(s.split())
    words[-1] = _singular(words[-1])
    return " ".join(words)


# --- Aisle guess (used when the model isn't available and nothing is saved yet) -------------

_AISLE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Frozen", ("frozen",)),
    ("Spices & baking", (
        "salt", "red pepper flake", "black pepper", "pepper", "paprika", "cumin", "oregano",
        "chili powder",
        "cinnamon", "garlic powder", "onion powder", "baking", "flour", "sugar", "vanilla",
        "yeast", "cornstarch", "bay leaf", "thyme dried", "seasoning", "nutmeg", "cocoa",
    )),
    ("Meat & seafood", (
        "chicken", "beef", "pork", "turkey", "sausage", "bacon", "ham", "steak", "shrimp",
        "salmon", "tilapia", "fish", "lamb", "chorizo", "ground meat", "hot dog",
    )),
    ("Dairy & refrigerated", (
        "milk", "butter", "cheese", "cheddar", "mozzarella", "parmesan", "yogurt", "cream",
        "egg", "sour cream", "tortilla", "half-and-half", "shredded cheese",
    )),
    ("Bakery", ("bread", "bun", "roll", "bagel", "pita", "naan")),
    ("Produce", (
        "onion", "garlic", "tomato", "potato", "carrot", "celery", "lettuce",
        "spinach", "broccoli", "cilantro", "parsley", "basil", "lime", "lemon", "apple",
        "banana", "avocado", "cucumber", "zucchini", "mushroom", "ginger", "scallion",
        "green onion", "cabbage", "kale", "corn on the cob", "jalapeno", "squash", "green bean",
        "strawberry", "blueberry", "grape", "orange", "romaine", "bell pepper",
    )),
    ("Pantry", (
        "rice", "pasta", "noodle", "spaghetti", "bean", "broth", "stock", "oil", "vinegar",
        "sauce", "canned", "tuna", "lentil", "oat", "cereal", "peanut butter", "honey",
        "salsa", "ketchup", "mustard", "mayo", "soy sauce", "tomato paste", "crushed tomato",
        "tomato sauce", "black bean", "pinto bean", "kidney bean", "olive oil",
    )),
)  # fmt: skip


def guess_aisle(name: str) -> str:
    """The aisle of the longest keyword found, so "tomato paste" beats "tomato"."""
    key = normalize_name(name)
    best, best_len = "Other", 0
    for aisle, words in _AISLE_KEYWORDS:
        for w in words:
            if len(w) > best_len and re.search(rf"\b{re.escape(w)}\b", key):
                best, best_len = aisle, len(w)
    return best
