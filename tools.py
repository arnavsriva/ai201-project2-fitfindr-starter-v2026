"""
The three FitFindr tools.

Each one is a standalone function you can call and test on its own.

    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str

The spec for all three — inputs with types, the exact return value, and what
each returns when it has nothing — is in the Tool Inventory section of
README.md. This file implements that spec and nothing more.
"""

import re

import config
from generate import generate
from utils.data_loader import load_listings


# ── size handling ─────────────────────────────────────────────────────────────
#
# A plain substring test is wrong on this data: `"s" in "us 9"` is True and
# `"l" in "xl"` is True, so asking for a small top returns shoes. Sizes are
# tokenised instead, and a match has to be a whole token.

_LETTER_SIZES = {"XXS", "XS", "S", "M", "L", "XL", "XXL"}

_WORD_SIZES = {
    "extra small": "XS",
    "small": "S",
    "medium": "M",
    "large": "L",
    "extra large": "XL",
}

_ONE_SIZE = "ONE SIZE"


def _size_tokens(raw: str) -> set[str]:
    """
    Break a size string into whole tokens that can be compared.

        "S/M"              → {"S", "M"}
        "XL (oversized)"   → {"XL"}          parentheticals are notes, not sizes
        "W30 L30"          → {"W30"}         L30 is the inseam, not a size
        "US 8.5"           → {"US 8.5"}
        "One Size / Oversized" → {"ONE SIZE"}  matches anything
        "medium"           → {"M"}
    """
    if not raw:
        return set()

    text = re.sub(r"\(.*?\)", " ", str(raw)).strip()
    if "one size" in text.lower():
        return {_ONE_SIZE}

    lowered = text.lower()
    for word, letter in _WORD_SIZES.items():
        if re.search(rf"\b{word}\b", lowered):
            return {letter}

    tokens: set[str] = set()
    for part in re.split(r"[\s/,]+", text.upper()):
        if not part:
            continue
        if part in _LETTER_SIZES:
            tokens.add(part)
        elif re.fullmatch(r"W\d+", part):           # waist
            tokens.add(part)
        elif re.fullmatch(r"L\d+", part):           # inseam — not a size
            continue
        elif re.fullmatch(r"\d+(\.\d+)?", part):    # shoe size, with or without "US"
            tokens.add(f"US {part.rstrip('0').rstrip('.') if '.' in part else part}")
    return tokens


def _size_matches(listing_size: str, wanted: str) -> bool:
    """True when a listing's size satisfies the requested size."""
    want = _size_tokens(wanted)
    if not want:                 # unparseable request — don't filter on it
        return True
    have = _size_tokens(listing_size)
    if _ONE_SIZE in have or _ONE_SIZE in want:
        return True
    return bool(have & want)


# ── keyword scoring ───────────────────────────────────────────────────────────

_STOPWORDS = {
    "a", "an", "and", "any", "are", "as", "at", "be", "find", "for",
    "from", "i", "im", "in", "is", "it", "looking", "me", "my", "of", "on",
    "or", "please", "something", "that", "the", "to", "under", "want", "with",
    "would", "size", "sz",
}


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9']+", str(text).lower()) if w]


def _query_terms(description: str) -> list[str]:
    return [w for w in _words(description) if w not in _STOPWORDS and len(w) > 1]


def _score(listing: dict, terms: list[str]) -> int:
    """
    Keyword overlap, weighted by where the word was found. Title and style tags
    are what someone is actually searching on; the free-text description is
    weaker evidence because it is long enough to contain anything.
    """
    title = set(_words(listing.get("title", "")))
    tags = set()
    for tag in listing.get("style_tags") or []:
        tags |= set(_words(tag))
    tags |= set(_words(listing.get("category", "")))
    colors = set()
    for color in listing.get("colors") or []:
        colors |= set(_words(color))
    brand = set(_words(listing.get("brand") or ""))      # brand is None most of the time
    body = set(_words(listing.get("description", "")))

    total = 0
    for term in terms:
        if term in title:
            total += 3
        if term in tags:
            total += 3
        if term in brand:
            total += 3
        if term in colors:
            total += 2
        if term in body:
            total += 1

    # Phrases people actually type, which the per-word pass splits apart.
    haystack = " ".join(
        [str(listing.get("title", "")), str(listing.get("description", ""))]
        + list(listing.get("style_tags") or [])
    ).lower()
    joined = " ".join(terms)
    for i in range(len(terms) - 1):
        phrase = f"{terms[i]} {terms[i + 1]}"
        if phrase in haystack:
            total += 2
    if joined and joined in haystack:
        total += 2

    return total


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the listings data for items matching a description, and optionally a
    size and a price ceiling.

    Args:
        description: keywords describing what the user wants.
        size:        a size string to filter by, or None to skip size
                     filtering. Matched on whole tokens — see _size_matches.
        max_price:   maximum price, inclusive, or None to skip price filtering.

    Returns:
        A list of whole listing dicts, best match first, ties broken by lower
        price, at most config.SEARCH_RESULT_LIMIT of them. Returns an empty
        list when nothing matches — not None, not an exception.

    Test it from a terminal:
        python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
    """
    listings = load_listings()
    terms = _query_terms(description or "")

    scored: list[tuple[int, float, dict]] = []
    for listing in listings:
        if max_price is not None and listing.get("price", 0.0) > float(max_price):
            continue
        if size is not None and not _size_matches(listing.get("size", ""), size):
            continue
        score = _score(listing, terms)
        if score <= 0:
            continue
        scored.append((score, listing.get("price", 0.0), listing))

    scored.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in scored[: config.SEARCH_RESULT_LIMIT]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

_OUTFIT_SYSTEM = (
    "You are a thrift stylist. Suggest how to wear one secondhand find. "
    "Be concrete about garments, lengths and shoes. Plain prose, no lists, no "
    "headings, no markdown. Keep it under 90 words."
)


def _money(price) -> str:
    """$38.0 reads like a bug in a caption. 38 and 24.5 read like prices."""
    try:
        value = float(price)
    except (TypeError, ValueError):
        return str(price)
    return f"{value:g}"


def _describe_item(item: dict) -> str:
    """One compact block of item facts for a prompt. Brand is often None."""
    lines = [
        f"Title: {item.get('title')}",
        f"Category: {item.get('category')}",
        f"Size: {item.get('size')}",
        f"Condition: {item.get('condition')}",
        f"Price: ${_money(item.get('price'))}",
        f"Platform: {item.get('platform')}",
        f"Colors: {', '.join(item.get('colors') or []) or 'unlisted'}",
        f"Style tags: {', '.join(item.get('style_tags') or []) or 'none'}",
        f"Description: {item.get('description')}",
    ]
    if item.get("brand"):
        lines.insert(1, f"Brand: {item['brand']}")
    return "\n".join(lines)


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest one or two outfits.

    Args:
        new_item: a listing dict — the item the user is considering.
        wardrobe: a wardrobe dict with an 'items' key holding a list of items.
                  It may be empty.

    Returns:
        A non-empty string with outfit suggestions. With an empty wardrobe it
        returns general styling advice instead of naming owned pieces. Returns
        "" only when new_item is falsy.

    Test it from a terminal:
        python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
    """
    if not new_item:
        return ""

    items = (wardrobe or {}).get("items") or []

    if not items:
        prompt = (
            "Someone is considering this secondhand item but has not told us "
            "anything about what they already own.\n\n"
            f"{_describe_item(new_item)}\n\n"
            "Give one or two outfit ideas in general terms — the kind of "
            "bottom, shoe and layer that work with it, and the colours to "
            "reach for. Do not pretend to know what they own, and say in one "
            "short clause that this is general advice because their wardrobe "
            "is empty."
        )
    else:
        owned = "\n".join(
            f"- {it.get('name')} ({it.get('category')}; "
            f"{', '.join(it.get('colors') or []) or 'colour unlisted'}; "
            f"{', '.join(it.get('style_tags') or []) or 'no tags'})"
            for it in items
        )
        prompt = (
            "Someone is considering this secondhand item:\n\n"
            f"{_describe_item(new_item)}\n\n"
            "Here is everything already in their wardrobe:\n\n"
            f"{owned}\n\n"
            "Give one or two outfit ideas that each name specific pieces from "
            "that wardrobe by name. Do not invent pieces they do not own."
        )

    return generate(prompt, system=_OUTFIT_SYSTEM).strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

_CARD_SYSTEM = (
    "You write short social captions about thrift finds. Two to four "
    "sentences, first person, the voice of someone pleased with themselves. "
    "No hashtags, no lists, no markdown, no quotation marks around the whole "
    "caption. Mention the price once and the platform once, naturally."
)

NO_OUTFIT_MESSAGE = (
    "No outfit suggestion to write a card from — suggest_outfit returned nothing."
)


def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a short caption someone would actually post about the find.

    Args:
        outfit:   the outfit suggestion string from suggest_outfit().
        new_item: the listing dict for the item.

    Returns:
        A two-to-four sentence caption. If `outfit` is empty or whitespace,
        returns NO_OUTFIT_MESSAGE and makes no model call.

    cache=False is passed deliberately: the brief asks for three runs on the
    same item to differ, and a cached answer would hand back the same words.

    Test it from a terminal:
        python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
    """
    if not outfit or not str(outfit).strip():
        return NO_OUTFIT_MESSAGE
    if not new_item:
        return NO_OUTFIT_MESSAGE

    prompt = (
        "Write the caption for this thrift find.\n\n"
        f"{_describe_item(new_item)}\n\n"
        "How it's being styled:\n"
        f"{str(outfit).strip()}\n\n"
        f"The caption must say the price (${_money(new_item.get('price'))}) "
        f"once, written as a numeral with a dollar sign (not spelled out in "
        f"words), and say it was found/bought on {new_item.get('platform')} once "
        f"— that is where it came from, not somewhere it is being resold. "
        "Be specific "
        "about the vibe rather than describing the garment like a product "
        "listing."
    )

    return generate(prompt, system=_CARD_SYSTEM, cache=False).strip()
