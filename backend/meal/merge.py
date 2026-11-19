"""Merge the week's recipe lines into one shopping list."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from meal.ingredients import AISLES
from meal.units import Amount, dimension, friendly, to_base


@dataclass(frozen=True)
class Need:
    """One recipe line, already scaled to the servings being cooked."""

    key: str  # what identifies the grocery item (an ingredient id or normalized name)
    name: str  # display name
    aisle: str
    quantity: float | None  # None: "to taste" or unknown amount
    unit: str | None  # canonical unit
    source: str = ""  # recipe title, for "used in"


@dataclass
class Merged:
    key: str
    name: str
    aisle: str
    amounts: list[Amount] = field(default_factory=list)  # one per dimension that can't combine
    sources: list[str] = field(default_factory=list)

    @property
    def display(self) -> str:
        """'2 lb', '1 cup + 2 cans', or '' when only unmeasured amounts were asked for."""
        return " + ".join(str(a) for a in self.amounts if a.quantity is not None)


def scale(
    quantity: float | None, recipe_servings: int | None, servings: int | None
) -> float | None:
    """Scale a line from the recipe's yield to the servings being cooked."""
    if quantity is None or not recipe_servings or not servings:
        return quantity
    return quantity * servings / recipe_servings


def merge(needs: Iterable[Need]) -> list[Merged]:
    """Add up the same item across recipes. Mass and volume each sum in their own dimension;
    counts ("2 cans", "3 cloves") only sum with the same unit. Sorted by aisle, then name."""
    totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    items: dict[str, Merged] = {}
    for n in needs:
        item = items.get(n.key)
        if item is None:
            item = items[n.key] = Merged(key=n.key, name=n.name, aisle=n.aisle)
        if n.source and n.source not in item.sources:
            item.sources.append(n.source)
        if n.quantity is not None and n.quantity > 0:
            totals[n.key][dimension(n.unit)] += to_base(n.quantity, n.unit)

    order = {a: i for i, a in enumerate(AISLES)}
    for key, item in items.items():
        dims = totals.get(key, {})
        # Stable order: mass, volume, then counts alphabetically
        rank = {"mass": "0", "volume": "1"}
        for dim in sorted(dims, key=lambda d: rank.get(d, "2" + d)):
            item.amounts.append(friendly(dim, dims[dim]))
    return sorted(items.values(), key=lambda m: (order.get(m.aisle, len(order)), m.name.lower()))
