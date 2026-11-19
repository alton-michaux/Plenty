"""Units: aliases, conversion within a dimension, and friendly display amounts.

Three kinds of unit:
- mass (base: grams) and volume (base: millilitres) convert freely within their dimension;
- every other unit ("can", "clove", "bunch", or no unit at all, meaning "each") is its own
  count and only adds up with the same unit.
"""

from dataclasses import dataclass
from fractions import Fraction

MASS = {"g": 1.0, "kg": 1000.0, "oz": 28.349523125, "lb": 453.59237}
VOLUME = {
    "ml": 1.0,
    "l": 1000.0,
    "tsp": 4.92892159375,
    "tbsp": 14.78676478125,
    "fl oz": 29.5735295625,
    "cup": 236.5882365,
    "pint": 473.176473,
    "quart": 946.352946,
    "gallon": 3785.411784,
}

# Lowercased spellings -> canonical unit. "T" and "t" are handled case-sensitively in `canonical`.
_ALIASES = {
    **{u: u for u in (*MASS, *VOLUME)},
    "gram": "g",
    "grams": "g",
    "gr": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "kgs": "kg",
    "ounce": "oz",
    "ounces": "oz",
    "pound": "lb",
    "pounds": "lb",
    "lbs": "lb",
    "#": "lb",
    "milliliter": "ml",
    "milliliters": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
    "mls": "ml",
    "liter": "l",
    "liters": "l",
    "litre": "l",
    "litres": "l",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tsps": "tsp",
    "tspn": "tsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tbsps": "tbsp",
    "tbs": "tbsp",
    "tbl": "tbsp",
    "tblsp": "tbsp",
    "fluid ounce": "fl oz",
    "fluid ounces": "fl oz",
    "fl. oz": "fl oz",
    "floz": "fl oz",
    "c": "cup",
    "cups": "cup",
    "pints": "pint",
    "pt": "pint",
    "quarts": "quart",
    "qt": "quart",
    "qts": "quart",
    "gallons": "gallon",
    "gal": "gallon",
    # Counts: singular canonical names
    "can": "can",
    "cans": "can",
    "tin": "can",
    "tins": "can",
    "jar": "jar",
    "jars": "jar",
    "bottle": "bottle",
    "bottles": "bottle",
    "box": "box",
    "boxes": "box",
    "bag": "bag",
    "bags": "bag",
    "package": "package",
    "packages": "package",
    "pkg": "package",
    "pkgs": "package",
    "packet": "packet",
    "packets": "packet",
    "clove": "clove",
    "cloves": "clove",
    "head": "head",
    "heads": "head",
    "bunch": "bunch",
    "bunches": "bunch",
    "stalk": "stalk",
    "stalks": "stalk",
    "rib": "stalk",
    "ribs": "stalk",
    "sprig": "sprig",
    "sprigs": "sprig",
    "slice": "slice",
    "slices": "slice",
    "stick": "stick",
    "sticks": "stick",
    "piece": "piece",
    "pieces": "piece",
    "fillet": "fillet",
    "fillets": "fillet",
    "breast": "breast",
    "breasts": "breast",
    "pinch": "pinch",
    "pinches": "pinch",
    "dash": "dash",
    "dashes": "dash",
    "handful": "handful",
    "handfuls": "handful",
    "dozen": "dozen",
    "each": "each",
    "ea": "each",
    "whole": "each",
}

# Units that are their own count (no conversion): "can", "clove", "bunch", ...
COUNT_UNITS = frozenset(v for v in _ALIASES.values() if v not in MASS and v not in VOLUME)


def canonical(unit: str | None) -> str | None:
    """'Tablespoons' -> 'tbsp', 'T' -> 'tbsp', 't' -> 'tsp', '' -> None. Unknown -> None."""
    if unit is None:
        return None
    u = unit.strip().rstrip(".")
    if u == "T":
        return "tbsp"
    if u == "t":
        return "tsp"
    u = u.lower()
    if u in ("", "each"):
        return None
    return _ALIASES.get(u)


def dimension(unit: str | None) -> str:
    """'mass', 'volume', or the count unit itself ('can', 'clove', 'each' for none)."""
    if unit in MASS:
        return "mass"
    if unit in VOLUME:
        return "volume"
    return unit or "each"


def to_base(quantity: float, unit: str | None) -> float:
    if unit in MASS:
        return quantity * MASS[unit]
    if unit in VOLUME:
        return quantity * VOLUME[unit]
    if unit == "dozen":
        return quantity  # kept as dozens; it's its own count
    return quantity


@dataclass(frozen=True)
class Amount:
    quantity: float | None  # None = "to taste" / unreadable
    unit: str | None  # canonical unit, None = each

    def __str__(self) -> str:
        return format_amount(self)


def friendly(dim: str, base: float) -> Amount:
    """Express a summed base amount in the unit a US shopper would use."""
    if dim == "mass":
        lb = base / MASS["lb"]
        if lb >= 1:
            return Amount(lb, "lb")
        return Amount(base / MASS["oz"], "oz")
    if dim == "volume":
        cups = base / VOLUME["cup"]
        if cups >= 4:
            return Amount(base / VOLUME["quart"], "quart")
        if cups >= 0.25:
            return Amount(cups, "cup")
        tbsp = base / VOLUME["tbsp"]
        if tbsp >= 1:
            return Amount(tbsp, "tbsp")
        return Amount(base / VOLUME["tsp"], "tsp")
    return Amount(base, None if dim == "each" else dim)


_PLURAL = {"box": "boxes", "bunch": "bunches", "dash": "dashes", "pinch": "pinches", "each": "each"}
_NO_PLURAL = {"g", "kg", "oz", "lb", "ml", "l", "tsp", "tbsp", "fl oz", "dozen"}


def format_quantity(q: float) -> str:
    """1.5 -> '1 1/2', 0.333 -> '1/3', 2.0 -> '2'. Rounds to the nearest 1/8 (or 1/3)."""
    if q >= 10:
        return f"{round(q):g}"
    best = min(
        (Fraction(round(q * d), d) for d in (8, 3)),
        key=lambda f: abs(float(f) - q),
    )
    if best == 0:
        best = Fraction(1, 8)
    whole, frac = divmod(best, 1)
    if frac == 0:
        return str(int(whole))
    frac_s = f"{frac.numerator}/{frac.denominator}"
    return f"{int(whole)} {frac_s}" if whole else frac_s


def format_amount(a: Amount) -> str:
    if a.quantity is None:
        return ""
    q = format_quantity(a.quantity)
    if a.unit is None:
        return q
    unit = a.unit
    if unit not in _NO_PLURAL and a.quantity > 1:
        unit = _PLURAL.get(unit, unit + "s")
    return f"{q} {unit}"
