from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import MEAL_SCHEMA, Base

# --- Auth: same tables and names as Buoy's, in the public schema. On a merge, Buoy's win. ---


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lowercased
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Session(Base):
    """A login. Only a SHA-256 of the cookie token is stored, so a leaked DB can't log anyone in."""

    __tablename__ = "session"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


# --- Meal tables: everything below lives in the `meal` schema. ---


def _user_fk(**kw) -> Mapped[int]:
    return mapped_column(ForeignKey("user.id", ondelete="CASCADE"), **kw)


class Household(Base):
    """Who eats when, the food budget and its pay period, and where the shopping happens."""

    __tablename__ = "household"
    __table_args__ = {"schema": MEAL_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk(unique=True)
    # All food, groceries and eating out together, per pay period.
    budget_cents: Mapped[int]
    anchor_payday: Mapped[date] = mapped_column(Date)  # any known payday
    period_days: Mapped[int] = mapped_column(default=14)
    stores: Mapped[list[str]] = mapped_column(ARRAY(String(60)))
    # Kids' weekly window, both ends included. Weekdays follow date.weekday() (Mon=0).
    kids: Mapped[int] = mapped_column(default=0)
    kids_from_day: Mapped[int] = mapped_column(default=2)
    kids_from_slot: Mapped[str] = mapped_column(String(10), default="dinner")
    kids_to_day: Mapped[int] = mapped_column(default=5)
    kids_to_slot: Mapped[str] = mapped_column(String(10), default="lunch")


class Ingredient(Base):
    """A canonical grocery item ("chicken thigh"). Recipe lines (and, in phase 2, receipt lines)
    point here, so the same thing adds up on one list line and carries one price."""

    __tablename__ = "ingredient"
    __table_args__ = (UniqueConstraint("user_id", "key"), {"schema": MEAL_SCHEMA})

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk(index=True)
    name: Mapped[str] = mapped_column(String(120))  # display name
    key: Mapped[str] = mapped_column(String(120))  # meal.ingredients.normalize_name(name)
    aisle: Mapped[str] = mapped_column(String(40))


class IngredientAlias(Base):
    """Recipe text (normalized) -> the ingredient it was confirmed as. Reused on import."""

    __tablename__ = "ingredient_alias"
    __table_args__ = (UniqueConstraint("user_id", "text"), {"schema": MEAL_SCHEMA})

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    text: Mapped[str] = mapped_column(String(200))
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey(f"{MEAL_SCHEMA}.ingredient.id", ondelete="CASCADE")
    )


class Upload(Base):
    """A recipe screenshot or photo (later: receipts). Postgres bytea for now."""

    __tablename__ = "upload"
    __table_args__ = {"schema": MEAL_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk(index=True)
    content_type: Mapped[str] = mapped_column(String(60))
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Recipe(Base):
    __tablename__ = "recipe"
    __table_args__ = {"schema": MEAL_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk(index=True)
    title: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(2000))
    source_kind: Mapped[str] = mapped_column(String(10))  # link | text | image | manual
    servings: Mapped[int | None]
    minutes: Mapped[int | None]
    steps: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    rating: Mapped[int | None]  # 1-5, set in Review (phase 2)
    image_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{MEAL_SCHEMA}.upload.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe",
        order_by="RecipeIngredient.position",
        cascade="all, delete-orphan",
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredient"
    __table_args__ = {"schema": MEAL_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey(f"{MEAL_SCHEMA}.recipe.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey(f"{MEAL_SCHEMA}.ingredient.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[float | None]
    unit: Mapped[str | None] = mapped_column(String(20))  # canonical (meal.units)
    note: Mapped[str | None] = mapped_column(String(200))
    original: Mapped[str] = mapped_column(String(300))

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")
    ingredient: Mapped[Ingredient] = relationship(lazy="joined")


class PlanEntry(Base):
    """One planned meal: a recipe, a night out, or leftovers."""

    __tablename__ = "plan_entry"
    __table_args__ = (UniqueConstraint("user_id", "day", "slot"), {"schema": MEAL_SCHEMA})

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    day: Mapped[date] = mapped_column(Date)
    slot: Mapped[str] = mapped_column(String(10))  # breakfast | lunch | dinner
    kind: Mapped[str] = mapped_column(String(10))  # recipe | out | leftovers
    recipe_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{MEAL_SCHEMA}.recipe.id", ondelete="CASCADE")
    )
    servings: Mapped[int]
    amount_cents: Mapped[int | None]  # planned spend for a night out

    recipe: Mapped[Recipe | None] = relationship(lazy="joined")


class PantryItem(Base):
    """Something on hand. Staples are always on hand and stay off the list."""

    __tablename__ = "pantry_item"
    __table_args__ = (UniqueConstraint("user_id", "ingredient_id"), {"schema": MEAL_SCHEMA})

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey(f"{MEAL_SCHEMA}.ingredient.id", ondelete="CASCADE")
    )
    staple: Mapped[bool] = mapped_column(default=True)

    ingredient: Mapped[Ingredient] = relationship(lazy="joined")


class GroceryList(Base):
    """The list for one Wed-Tue week (one trip)."""

    __tablename__ = "grocery_list"
    __table_args__ = (UniqueConstraint("user_id", "week_start"), {"schema": MEAL_SCHEMA})

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    week_start: Mapped[date] = mapped_column(Date)
    built_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Bumped by plan changes, so the list can say it's out of date
    plan_changed_at: Mapped[datetime | None] = mapped_column(DateTime)

    items: Mapped[list["GroceryListItem"]] = relationship(
        back_populates="list",
        order_by="GroceryListItem.position",
        cascade="all, delete-orphan",
    )


class GroceryListItem(Base):
    __tablename__ = "grocery_list_item"
    __table_args__ = {"schema": MEAL_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(
        ForeignKey(f"{MEAL_SCHEMA}.grocery_list.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    ingredient_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{MEAL_SCHEMA}.ingredient.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(120))
    aisle: Mapped[str] = mapped_column(String(40))
    amount: Mapped[str] = mapped_column(String(80))  # "2 lb", "1 cup + 2 cans", ""
    used_in: Mapped[list[str]] = mapped_column(ARRAY(String(200)), default=list)
    manual: Mapped[bool] = mapped_column(default=False)  # added by hand, not from the plan
    in_pantry: Mapped[bool] = mapped_column(default=False)  # have it already this week
    checked: Mapped[bool] = mapped_column(default=False)  # in the cart

    list: Mapped[GroceryList] = relationship(back_populates="items")


class Extraction(Base):
    """Every model call: what it cost and what it returned. Doubles as the cache."""

    __tablename__ = "extraction"
    __table_args__ = {"schema": MEAL_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), index=True
    )
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # recipe_text | recipe_image
    model: Mapped[str] = mapped_column(String(60))
    request_id: Mapped[str | None] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cost_micros: Mapped[int] = mapped_column(default=0)  # millionths of a dollar
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
