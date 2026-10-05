"""
The FitFindr planning loop.

This is the file that makes FitFindr an agent rather than a script. It decides
which tool to run next based on what the last one returned.

If your loop calls all three tools no matter what comes back, you have a list
of function calls. A loop looks at the last result before it picks the next
step. **That branch is the graded part of this unit.**

Build and test your three tools in `tools.py` first. Then come here.

    python agent.py          runs both example paths below
"""

import re

import config
import trace
from tools import search_listings, suggest_outfit, create_fit_card
from generate import ModelUnavailable


# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """
    A fresh session for one user interaction.

    The session is the single source of truth for a run. Every tool result goes
    in here, and the next tool reads it back out.
    """
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price pulled out of it
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one chosen — goes into suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "fit_card": None,            # what create_fit_card returned
        "error": None,               # set when the run ended early
        # The id of the item actually handed to each model tool. This is what
        # criterion 3 in criteria.md compares against selected_item, so a state
        # mix-up shows up as a mismatched string instead of a confusing caption.
        "handoff_ids": {},
    }


# ── query parsing ─────────────────────────────────────────────────────────────
#
# Regex, not the model. The query shapes this app sees are narrow enough that a
# pattern covers them, and a parse that makes no network call cannot fail
# halfway through a run.

_PRICE_PATTERNS = [
    r"\b(?:under|below|less than|cheaper than|max|up to)\s*\$?\s*(\d+(?:\.\d+)?)",
    r"\$\s*(\d+(?:\.\d+)?)\s*(?:or less|or under|and under|max)",
    r"\$\s*(\d+(?:\.\d+)?)",
]

_SIZE_PATTERNS = [
    r"\b(?:size|sz)\s*[:\-]?\s*(xxs|xs|s|m|l|xl|xxl|\d+(?:\.\d+)?|w\d+)\b",
    r"\bin\s+an?\s+(extra small|small|medium|large|extra large)\b",
    r"\b(?:us\s*)(\d+(?:\.\d+)?)\b",
]

_FILLER = r"\b(?:looking|searching|hunting|for|a|an|the|in|some|please|want|need|me|i|im|i'm)\b"


def parse_query(query: str) -> dict:
    """
    Pull a description, a size and a price ceiling out of a plain-language query.

    Returns:
        {"description": str, "size": str | None, "max_price": float | None}.
        size and max_price are None when the query did not mention them;
        description is whatever text is left, and is never empty — it falls
        back to the whole query.
    """
    text = query or ""
    remaining = text

    max_price = None
    for pattern in _PRICE_PATTERNS:
        match = re.search(pattern, remaining, flags=re.IGNORECASE)
        if match:
            max_price = float(match.group(1))
            remaining = remaining[: match.start()] + " " + remaining[match.end() :]
            break

    size = None
    for pattern in _SIZE_PATTERNS:
        match = re.search(pattern, remaining, flags=re.IGNORECASE)
        if match:
            size = match.group(1).strip()
            remaining = remaining[: match.start()] + " " + remaining[match.end() :]
            break

    description = re.sub(_FILLER, " ", remaining, flags=re.IGNORECASE)
    description = re.sub(r"[,;]", " ", description)
    description = re.sub(r"\s+", " ", description).strip()

    return {
        "description": description or text.strip(),
        "size": size,
        "max_price": max_price,
    }


def _no_results_message(parsed: dict) -> str:
    """
    What the user could change. "No results" is not that message, so this names
    the three things that were actually applied as filters.
    """
    parts = [f'nothing matched "{parsed["description"]}"']
    knobs = []
    if parsed["max_price"] is not None:
        knobs.append(f"raise the ${parsed['max_price']:.0f} ceiling")
    if parsed["size"]:
        knobs.append(f"drop or widen size {parsed['size']}")
    knobs.append(
        "try the words that are on the listings themselves — the data is tagged "
        "vintage, y2k, grunge, streetwear, denim, graphic tee, cargo, flannel, "
        "slip dress, platform"
    )
    return (
        f"Stopped before styling anything: {parts[0]}"
        + (f" with the filters I read out of your query." if (parsed["max_price"] is not None or parsed["size"]) else ".")
        + " To get results, "
        + "; or ".join(knobs)
        + "."
    )


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the loop once and return the finished session.

    Args:
        query:    what the user asked for, in plain language.
        wardrobe: a wardrobe dict — get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py.

    Returns:
        The session dict. Check session["error"] first — if it isn't None, the
        run ended early and the later fields will still be None.

    The branch rule, as stated in README.md:

        If search_listings returns an empty list, put a message in
        session["error"] naming what the user could change and return the
        session. Otherwise take the first result, put it in
        session["selected_item"], and go on to suggest_outfit.

    Every step writes its result into the session, and the next step reads its
    input back out of the session. Nothing is passed directly from one call to
    the next — that is what makes the state testable.
    """
    session = new_session(query, wardrobe)
    steps = 0

    try:
        # ── step 1: parse ─────────────────────────────────────────────────────
        steps += 1
        trace.check_iterations(steps)
        session["parsed"] = parse_query(query)
        trace.step(
            "parse_query",
            inputs=session["query"],
            returned=session["parsed"],
        )

        # ── step 2: search ────────────────────────────────────────────────────
        steps += 1
        trace.check_iterations(steps)
        parsed = session["parsed"]
        session["search_results"] = search_listings(
            description=parsed["description"],
            size=parsed["size"],
            max_price=parsed["max_price"],
        )
        trace.step(
            "search_listings",
            inputs=parsed,
            returned=session["search_results"],
        )

        # ── THE BRANCH ────────────────────────────────────────────────────────
        if not session["search_results"]:
            session["error"] = _no_results_message(session["parsed"])
            trace.step(
                "branch",
                inputs="len(session['search_results']) == 0",
                returned=session["error"],
                note="branch: empty, stopping before suggest_outfit",
            )
            return session

        # ── step 3: select ────────────────────────────────────────────────────
        steps += 1
        trace.check_iterations(steps)
        session["selected_item"] = session["search_results"][0]
        trace.step(
            "select_item",
            inputs=f"{len(session['search_results'])} results",
            returned=session["selected_item"],
            note="branch: results found, continuing to suggest_outfit",
        )

        # ── step 4: suggest_outfit ────────────────────────────────────────────
        steps += 1
        trace.check_iterations(steps)
        item = session["selected_item"]          # read back OUT of the session
        session["handoff_ids"]["suggest_outfit"] = item.get("id")
        session["outfit_suggestion"] = suggest_outfit(item, session["wardrobe"])
        trace.step(
            "suggest_outfit",
            inputs=item,
            returned=session["outfit_suggestion"],
        )

        # ── step 5: create_fit_card ───────────────────────────────────────────
        steps += 1
        trace.check_iterations(steps)
        outfit = session["outfit_suggestion"]    # read back OUT of the session
        item = session["selected_item"]
        session["handoff_ids"]["create_fit_card"] = item.get("id")
        session["fit_card"] = create_fit_card(outfit, item)
        trace.step(
            "create_fit_card",
            inputs=item,
            returned=session["fit_card"],
        )

    except ModelUnavailable as exc:
        session["error"] = (
            f"The model couldn't be reached, so I stopped after the search. "
            f"{exc} Your search results are still in the session; re-run once "
            f"the key or the network is sorted."
        )
        trace.step("ModelUnavailable", returned=str(exc), note="stopped, no fit card")

    return session


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    if session["error"]:
        print(f"  stopped: {session['error']}")
        print(f"  fit_card is {session['fit_card']!r} — it should still be None here")
        return

    item = session["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    print(f"  outfit:   {session['outfit_suggestion']}")
    print(f"  fit card: {session['fit_card']}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== A query the data can match ===")
    _show(run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    ))

    print("\n=== A query it can't ===")
    _show(run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    ))

    print(
        "\nThe second one should stop before the fit card. If both paths look "
        "the same,\nthe branch isn't doing anything yet."
    )
