"""
Your MCP server. ← UNIT 4, MILESTONE 1

Right now your tools only exist inside your own program. Nothing else can reach
them. MCP is an agreed shape you wrap a tool in so that anything speaking the
same protocol can call it — your agent today, a different agent tomorrow,
someone else's app after that.

**You're moving one tool. Not three.** The point is to see the seam.
`search_listings` is the one to move: it doesn't call the model, so nothing is
slow and nothing changes between runs while you're learning the shape.

    python mcp_server.py        starts the server (it will just sit there — that's right)
    python mcp_client.py        asks the server what it offers

─────────────────────────────────────────────────────────────────────────────
TODO — register one tool.

Uncomment the block below and fill it in. Three things matter:

  1. **The name.** Exactly what your agent will ask for.

  2. **The description.** This is the part that isn't code and matters most.
     Write it before you look at the example. You are not writing it for your
     agent — you're writing it for an agent someone else builds, that will
     never see your implementation. That isn't hypothetical; it's what every
     MCP server on the registry is.

     Two things to get right: name units and types ("price" is ambiguous,
     "max_price, in whole dollars" isn't), and state the empty case. Last unit
     the empty case was on your spec sheet for your loop's benefit. Here it's
     part of a published contract.

  3. **The typed inputs.** These come straight from your Tool Inventory. If the
     types here don't match your README, one of the two is wrong — fix it.

Then point your agent at it. In `run_agent()`, swap the direct call:

    results = search_listings(description, size, max_price)

for the MCP one:

    from mcp_client import call_tool
    results = call_tool("search_listings", {
        "description": description,
        "size": size,
        "max_price": max_price,
    })

**What comes back should not change.** If it does, that difference is your
first clue about what your tool was really returning before.

🛑 Stop rule: if this isn't connecting after 40 minutes, stop. Keep your direct
call, and write down in your README exactly where it broke — the error text and
the last thing that worked. Then carry on to Milestone 2. Everything after this
works with a direct call, and **a documented failure earns the point in full.**
─────────────────────────────────────────────────────────────────────────────
"""

from mcp.server.fastmcp import FastMCP

from tools import search_listings as _search_listings_impl  # noqa: F401 — you'll use this below

# log_level="WARNING" keeps the server from printing an INFO line for every
# request. Without it your terminal fills with "Processing request of type
# CallToolRequest" and the output you actually care about scrolls away.
mcp = FastMCP("fitfindr", log_level="WARNING")


# ── registered tool ──────────────────────────────────────────────────────────

@mcp.tool()
def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search a fixed catalogue of 40 secondhand clothing listings and return the
    ones matching a plain-language description, ranked best match first.

    `description` is free text and is required — keywords such as "vintage
    graphic tee" or "90s track jacket"; it is scored by word overlap against
    each listing's title, style tags, category, colours, brand and description
    text, and there is no synonym expansion, so words that appear on the
    listings themselves work best. `size` is optional and is matched on whole
    size tokens, not substrings: "M" matches the listing sizes "M", "M/L",
    "S/M" and "One Size", and does not match "XL" or "US 9"; shoe sizes are
    given as a bare number ("8", "8.5") and waist sizes as "W30". `max_price`
    is optional and is an inclusive ceiling in whole or fractional US dollars
    (30 means $30.00, not 3000 cents); listings priced above it are removed.

    Returns a list of at most 10 listing objects, each with the keys id, title,
    description, category, style_tags (list of strings), size, condition,
    price (a number in US dollars), colors (list of strings), brand (a string
    or null — most listings have no brand) and platform (one of depop, thredUp,
    poshmark). **When nothing matches it returns an empty list.** It does not
    return null and it does not raise; an empty list is the normal, expected
    answer for a query the catalogue cannot satisfy, and a caller should treat
    it as "stop and ask the user to loosen something" rather than as an error.
    """
    return _search_listings_impl(description, size, max_price)


if __name__ == "__main__":
    mcp.run()
