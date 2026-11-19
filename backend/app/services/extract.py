"""Read recipes out of free text (captions, pasted text, a page's recipe data) and screenshots
with Claude. Every call is logged to meal.extraction with its token usage and cost, and the
same input returns the cached result instead of calling the model again."""

import base64
import hashlib
import json
import logging
from typing import Literal

import anthropic
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import config
from meal.ingredients import AISLES

log = logging.getLogger(__name__)

# Bump when the prompt or schema changes, so cached results from the old prompt aren't reused.
PROMPT_VERSION = 1

# Dollars per million tokens: (input, output). Unknown models are logged at Opus rates.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}

Unit = Literal[
    "g", "kg", "oz", "lb", "ml", "l", "tsp", "tbsp", "fl oz", "cup", "pint", "quart", "gallon",
    "can", "jar", "bottle", "box", "bag", "package", "packet", "clove", "head", "bunch", "stalk",
    "sprig", "slice", "stick", "piece", "fillet", "breast", "pinch", "dash", "handful", "dozen",
]  # fmt: skip
Aisle = Literal[AISLES]  # type: ignore[valid-type]


class ExtractedLine(BaseModel):
    original: str = Field(description="The ingredient line as written in the source.")
    quantity: float | None = Field(
        description="Amount as a number (1/2 -> 0.5; a range -> the larger end). Null if none."
    )
    unit: Unit | None = Field(description="Unit of the amount. Null for whole items (2 onions).")
    item: str = Field(
        description=(
            "The grocery item as it would appear on a shopping list: generic, lowercase, "
            "singular, no prep words or brand. e.g. 'chicken thigh', 'yellow onion', "
            "'black beans', 'shredded cheddar', 'garlic'."
        )
    )
    note: str | None = Field(description="Prep or detail from the line: 'diced', '15 oz can'.")
    aisle: Aisle = Field(description="Where it's found in a US grocery store.")
    problem: str | None = Field(
        description=(
            "Only when the source clearly meant an amount you couldn't read: a short note like "
            "\"couldn't read the amount\". Null for 'to taste' and anything readable."
        )
    )


class ExtractedRecipe(BaseModel):
    is_recipe: bool = Field(description="False when the input has no recipe in it.")
    title: str
    servings: int | None = Field(description="How many it serves, if stated or clear.")
    minutes: int | None = Field(description="Total time in minutes, if stated or clear.")
    ingredients: list[ExtractedLine]
    steps: list[str] = Field(description="Short steps in order, as written. Empty if none.")


SYSTEM = """You read recipes for a family's grocery-list app. Input is a social media caption, \
pasted text, a recipe web page's data, or a photo/screenshot of a recipe.

Extract the recipe exactly as given. Don't invent ingredients, amounts, or steps that aren't \
there; if an ingredient is named without an amount, leave quantity null. Ignore hashtags, \
emojis, sponsor text and calls to follow. If the source has no recipe, set is_recipe false and \
return no ingredients."""


class ExtractionError(Exception):
    """A message safe to show the user."""


def available() -> bool:
    return bool(config.anthropic_api_key)


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=config.anthropic_api_key, max_retries=2, timeout=90)


def _cost_micros(model: str, usage) -> int:
    price_in, price_out = PRICES.get(model, PRICES["claude-opus-5-5"])
    tokens_in = (usage.input_tokens or 0) + (usage.cache_creation_input_tokens or 0) * 1.25
    tokens_in += (usage.cache_read_input_tokens or 0) * 0.1
    return round(tokens_in * price_in + (usage.output_tokens or 0) * price_out)


def call_model(content: list[dict]) -> tuple[ExtractedRecipe | None, dict]:
    """One model call. Returns (parsed result or None on refusal, usage metadata).
    Tests replace this function."""
    response = _client().beta.messages.parse(
        model=config.anthropic_model,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": content}],
        output_format=ExtractedRecipe,
        output_config={"effort": "low"},
        # If a request is declined, the API retries it on a fallback model in the same call.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    meta = {
        "model": response.model,
        "request_id": response._request_id,
        "input_tokens": response.usage.input_tokens or 0,
        "output_tokens": response.usage.output_tokens or 0,
        "cost_micros": _cost_micros(response.model, response.usage),
    }
    if response.stop_reason == "refusal":
        return None, meta
    if response.stop_reason == "max_tokens":
        raise ExtractionError("That recipe was too long to read in one go.")
    return response.parsed_output, meta


def _run(db: Session, user_id: int, kind: str, content: list[dict], key: bytes) -> ExtractedRecipe:
    input_hash = hashlib.sha256(
        f"{kind}:{config.anthropic_model}:{PROMPT_VERSION}:".encode() + key
    ).hexdigest()
    cached = db.scalar(
        select(models.Extraction)
        .where(models.Extraction.input_hash == input_hash, models.Extraction.result.is_not(None))
        .order_by(models.Extraction.id.desc())
        .limit(1)
    )
    if cached:
        return ExtractedRecipe.model_validate(cached.result)
    if not available():
        raise ExtractionError("Reading captions and screenshots isn't set up on this server.")

    row = models.Extraction(
        user_id=user_id, input_hash=input_hash, kind=kind, model=config.anthropic_model
    )
    try:
        parsed, meta = call_model(content)
    except ExtractionError as e:
        row.error = str(e)
        db.add(row)
        db.commit()
        raise
    except anthropic.RateLimitError:
        raise ExtractionError("Too many imports at once. Try again in a minute.") from None
    except (anthropic.APIConnectionError, anthropic.InternalServerError):
        raise ExtractionError("Couldn't reach the recipe reader. Try again.") from None
    except anthropic.APIStatusError as e:
        log.error("Extraction failed: %s %s", e.status_code, e.message)
        raise ExtractionError("The recipe reader had a problem with that one.") from None

    for k, v in meta.items():
        setattr(row, k, v)
    if parsed is None:
        row.error = "refused"
        db.add(row)
        db.commit()
        raise ExtractionError("The recipe reader declined that one. Try pasting the text.")
    row.result = parsed.model_dump(mode="json")
    db.add(row)
    db.commit()
    return parsed


def from_text(db: Session, user_id: int, text: str) -> ExtractedRecipe:
    text = text.strip()[:30_000]
    return _run(db, user_id, "recipe_text", [{"type": "text", "text": text}], text.encode())


def from_image(db: Session, user_id: int, data: bytes, media_type: str) -> ExtractedRecipe:
    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.standard_b64encode(data).decode(),
            },
        },
        {"type": "text", "text": "Read the recipe in this image."},
    ]
    return _run(db, user_id, "recipe_image", content, hashlib.sha256(data).digest())


def page_text(title: str, ingredients: list[str], steps: list[str], extra: str = "") -> str:
    """Flatten a page's recipe data into text for the model."""
    return json.dumps(
        {"title": title, "ingredients": ingredients, "steps": steps, "notes": extra},
        ensure_ascii=False,
    )
