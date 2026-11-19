"""Map recipe text to canonical ingredients, remembering every confirmed match."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from meal.ingredients import AISLES, guess_aisle, normalize_name, parse_line


def find(db: Session, user_id: int, *texts: str) -> models.Ingredient | None:
    """The saved ingredient for any of these texts: a remembered alias first, then a name match."""
    keys = [k for k in dict.fromkeys(normalize_name(t) for t in texts if t) if k]
    if not keys:
        return None
    alias = db.scalar(
        select(models.IngredientAlias).where(
            models.IngredientAlias.user_id == user_id, models.IngredientAlias.text.in_(keys)
        )
    )
    if alias:
        return db.get(models.Ingredient, alias.ingredient_id)
    found = db.scalars(
        select(models.Ingredient).where(
            models.Ingredient.user_id == user_id, models.Ingredient.key.in_(keys)
        )
    ).all()
    by_key = {i.key: i for i in found}
    return next((by_key[k] for k in keys if k in by_key), None)


def get_or_create(db: Session, user_id: int, name: str, aisle: str | None) -> models.Ingredient:
    name = " ".join(name.split())[:120]
    key = normalize_name(name)
    ing = db.scalar(
        select(models.Ingredient).where(
            models.Ingredient.user_id == user_id, models.Ingredient.key == key
        )
    )
    if ing is None:
        ing = models.Ingredient(
            user_id=user_id,
            name=name,
            key=key,
            aisle=aisle if aisle in AISLES else guess_aisle(name),
        )
        db.add(ing)
        db.flush()
    elif aisle in AISLES and aisle != ing.aisle:
        ing.aisle = aisle  # the user moved it; every list uses the new aisle from now on
    return ing


def remember(db: Session, user_id: int, original: str, ing: models.Ingredient) -> None:
    """Map the recipe line's own wording to the confirmed ingredient, so it matches next time."""
    text = normalize_name(parse_line(original).name)[:200]
    if not text or text == ing.key:
        return
    alias = db.scalar(
        select(models.IngredientAlias).where(
            models.IngredientAlias.user_id == user_id, models.IngredientAlias.text == text
        )
    )
    if alias is None:
        db.add(models.IngredientAlias(user_id=user_id, text=text, ingredient_id=ing.id))
    else:
        alias.ingredient_id = ing.id
