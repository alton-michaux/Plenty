import pytest

from meal.ingredients import guess_aisle, normalize_name, parse_line
from meal.merge import Need, merge, scale
from meal.units import Amount, canonical, format_amount, format_quantity


@pytest.mark.parametrize(
    ("line", "qty", "unit", "name", "note"),
    [
        ("2 lb chicken thighs", 2, "lb", "chicken thighs", None),
        ("2 lbs. boneless chicken thighs, cut up", 2, "lb", "boneless chicken thighs", "cut up"),
        ("1 cup white rice", 1, "cup", "white rice", None),
        ("1 1/2 cups chicken broth", 1.5, "cup", "chicken broth", None),
        ("1½ cups milk", 1.5, "cup", "milk", None),
        ("½ tsp salt", 0.5, "tsp", "salt", None),
        ("3 cloves garlic, minced", 3, "clove", "garlic", "minced"),
        ("1 onion, diced", 1, None, "onion", "diced"),
        ("1 (15 oz) can black beans, drained", 1, "can", "black beans", "15 oz; drained"),
        ("2 Tbsp butter", 2, "tbsp", "butter", None),
        ("1 T olive oil", 1, "tbsp", "olive oil", None),
        ("1 t paprika", 1, "tsp", "paprika", None),
        ("2-3 tomatoes", 3, None, "tomatoes", None),
        ("a pinch of salt", 1, "pinch", "salt", None),
        ("salt and pepper to taste", None, None, "salt and pepper", "to taste"),
        ("fresh parsley", None, None, "fresh parsley", None),
        ("- 8 oz shredded cheese", 8, "oz", "shredded cheese", None),
        ("2 large eggs", 2, None, "large eggs", None),
        ("1 lemon (juiced)", 1, None, "lemon", "juiced"),
        ("12 fl oz beer", 12, "fl oz", "beer", None),
        ("2 cans", 2, None, "cans", None),  # a bare count word stays the item
        (".5 lb ground beef", 0.5, "lb", "ground beef", None),
    ],
)
def test_parse_line(line, qty, unit, name, note):
    p = parse_line(line)
    assert (p.quantity, p.unit, p.name, p.note) == (qty, unit, name, note)
    assert p.original == line


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("Fresh Roma Tomatoes (diced)", "roma tomato"),
        ("chicken thighs", "chicken thigh"),
        ("Large Eggs", "egg"),
        ("black beans", "black bean"),
        ("crushed tomatoes", "crushed tomato"),
        ("whole milk", "whole milk"),
        ("berries", "berry"),
        ("asparagus", "asparagus"),
        ("onion, diced", "onion"),
    ],
)
def test_normalize_name(raw, key):
    assert normalize_name(raw) == key


@pytest.mark.parametrize(
    ("name", "aisle"),
    [
        ("yellow onion", "Produce"),
        ("bell peppers", "Produce"),
        ("black pepper", "Spices & baking"),
        ("tomato paste", "Pantry"),
        ("chicken broth", "Pantry"),
        ("roma tomatoes", "Produce"),
        ("chicken thighs", "Meat & seafood"),
        ("shredded cheese", "Dairy & refrigerated"),
        ("frozen peas", "Frozen"),
        ("eggplant", "Other"),
    ],
)
def test_guess_aisle(name, aisle):
    assert guess_aisle(name) == aisle


def test_canonical_units():
    assert canonical("Tablespoons") == "tbsp"
    assert canonical("T") == "tbsp"
    assert canonical("t") == "tsp"
    assert canonical("lbs.") == "lb"
    assert canonical("each") is None
    assert canonical("handfulz") is None


@pytest.mark.parametrize(
    ("q", "s"),
    [(2, "2"), (1.5, "1 1/2"), (0.333, "1/3"), (0.66, "2/3"), (2.24, "2 1/4"), (12.4, "12")],
)
def test_format_quantity(q, s):
    assert format_quantity(q) == s


def test_format_amount_plurals():
    assert format_amount(Amount(2, "can")) == "2 cans"
    assert format_amount(Amount(1, "can")) == "1 can"
    assert format_amount(Amount(2, "lb")) == "2 lb"
    assert format_amount(Amount(3, None)) == "3"
    assert format_amount(Amount(None, "cup")) == ""


def test_scale():
    assert scale(2, 4, 1) == 0.5
    assert scale(2, None, 4) == 2
    assert scale(None, 4, 2) is None


def n(key, qty, unit, aisle="Pantry", source="r"):
    return Need(key=key, name=key, aisle=aisle, quantity=qty, unit=unit, source=source)


def test_merge_sums_within_dimension():
    [rice] = merge([n("rice", 1, "cup", source="A"), n("rice", 8, "fl oz", source="B")])
    assert rice.display == "2 cups"
    assert rice.sources == ["A", "B"]


def test_merge_converts_mass_to_friendly_units():
    [beef] = merge([n("beef", 12, "oz"), n("beef", 0.5, "lb")])
    assert beef.display == "1 1/4 lb"
    [cheese] = merge([n("cheese", 4, "oz"), n("cheese", 2, "oz")])
    assert cheese.display == "6 oz"


def test_merge_keeps_incompatible_amounts_apart():
    [beans] = merge([n("bean", 1, "can"), n("bean", 1, "cup"), n("bean", 1, "can")])
    assert beans.display == "1 cup + 2 cans"


def test_merge_unmeasured_only():
    [salt] = merge([n("salt", None, None)])
    assert salt.display == ""


def test_merge_orders_by_aisle_then_name():
    out = merge(
        [
            n("rice", 1, "cup", "Pantry"),
            n("onion", 2, None, "Produce"),
            n("chicken", 2, "lb", "Meat & seafood"),
            n("garlic", 3, "clove", "Produce"),
        ]
    )
    assert [m.key for m in out] == ["garlic", "onion", "chicken", "rice"]
