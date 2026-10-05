# FitFindr

> ### 👋 Start here
>
> **New to this repo? Read [RUNNING.md](RUNNING.md) first** — setup, every
> command, and what to do when something breaks.
>
> ```bash
> python app.py listings --full -n 6      # read the data
> python app.py fields                    # what you can filter on
> python app.py ask 'vintage graphic tee under $30'
> ```

---

<!-- ═══════════════════════ UNIT 3 — THE BUILD ═══════════════════════ -->

## What This Does

PLACEHOLDER_WHAT

---

## Tool Inventory

### `search_listings`

- **What it does:** Filters the 40 mock thrift listings down to the ones that
  match a plain-language description, and optionally a size and a price
  ceiling, ranked best match first.
- **Inputs:**
  - `description` (`str`) — keywords, e.g. `"vintage graphic tee"`. Required.
  - `size` (`str | None`) — a size string such as `"M"`, `"8"`, `"W30"`, or
    `None` to skip size filtering.
  - `max_price` (`float | None`) — inclusive price ceiling, or `None` to skip
    price filtering.
- **Returns:** A `list[dict]` of at most `config.SEARCH_RESULT_LIMIT` (10)
  listing dicts, sorted by keyword score descending, ties broken by lower
  price. Every dict is a whole listing record, unmodified, with the keys
  `id` (str), `title` (str), `description` (str), `category` (str),
  `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float),
  `colors` (list[str]), `brand` (str **or None**), `platform` (str).
- **When it has nothing:** Returns `[]` — an empty list. Never `None`, never a
  raise. This is the value the loop branches on.

**My size-match rule** (part of the spec, because a plain substring test is
wrong on this data — `"s" in "us 9"` is `True` and `"l" in "xl"` is `True`):
each size string is split into tokens, and a listing matches only on a whole
token. `"S/M"` → `{S, M}`; `"XL (oversized)"` → `{XL}` (parentheticals are
dropped); `"W30 L30"` → `{W30}` (the inseam is ignored); `"US 8.5"` →
`{US 8.5}`; anything containing `"One Size"` → `{ONE SIZE}`, which matches any
requested size. A request for `M` therefore matches `M`, `M/L`, `S/M` and
`One Size`, and does **not** match `XL` or `US 9`.

### `suggest_outfit`

- **What it does:** Asks the model how to wear one thrifted item, naming pieces
  the user already owns when it can.
- **Inputs:**
  - `new_item` (`dict`) — one listing dict, the shape above.
  - `wardrobe` (`dict`) — a wardrobe dict with an `items` key holding a
    `list[dict]`; each item has `id`, `name`, `category`, `colors`,
    `style_tags`, `notes`. The list may be empty.
- **Returns:** A non-empty `str` — one or two outfit ideas, plain prose, each
  naming specific garments.
- **When it has nothing:** If `wardrobe["items"]` is empty, it still returns a
  non-empty `str`: general styling advice for the item (what kind of bottom,
  shoe and layer to pair it with) instead of named wardrobe pieces. If
  `new_item` is falsy it returns `""` and the caller must not proceed. If the
  model cannot be reached, `generate()` raises `ModelUnavailable`, which
  `run_agent` catches.

### `create_fit_card`

- **What it does:** Turns the outfit suggestion into a short caption someone
  would actually post about the find.
- **Inputs:**
  - `outfit` (`str`) — the string `suggest_outfit` returned.
  - `new_item` (`dict`) — the same listing dict.
- **Returns:** A `str` of two to four sentences that names the item, its price
  once and its platform once, and varies between runs (`TEMPERATURE = 0.9`,
  and the tool passes `cache=False` so repeat runs are real calls).
- **When it has nothing:** If `outfit` is empty or whitespace-only, it returns
  the fixed string
  `"No outfit suggestion to write a card from — suggest_outfit returned nothing."`
  rather than raising, and makes no model call.

---

## Planning Loop

**Branch rule:** If `search_listings` returns an empty list, put a message in
`session["error"]` naming what the user could change — the price ceiling, the
size, or the words — and return the session immediately, leaving
`session["fit_card"]` as `None`. Otherwise take the first result, put it in
`session["selected_item"]`, and go on to `suggest_outfit`.

**Where it lives:** `agent.py::run_agent`

**How the query is parsed:** regex, in `agent.py::parse_query`. One pattern
pulls a price ceiling (`under $30`, `below 30`, `$30 or less`, a bare `$30`),
one pulls a size (`size M`, `size 8`, `in a medium`, `sz L`), and the matched
spans are stripped out of the string; what is left, minus a few filler words
(`looking`, `for`, `a`, `in`), becomes the description.

**What moves through the session:** in this order —
`query` → `parsed` (`{description, size, max_price}`) → `search_results`
(the list from `search_listings`) → `selected_item` (`search_results[0]`) →
`outfit_suggestion` → `fit_card`. Each step writes its result into the session
and the next step reads its input back **out** of the session; no value is
passed directly from one call to the next. `error` is set only when the run
ends early.

---

## Sample Run

PLACEHOLDER_SAMPLE

---

## How I Used AI

PLACEHOLDER_AI

<!-- ═══════════════════════ UNIT 4 — THE TEST ═══════════════════════

     Don't fill these in during unit 3.
     ═══════════════════════════════════════════════════════════════════ -->

---

## Run Log — Before

<!-- Five criteria, five tries each, in this exact format.

     Five, because your criteria are written out of five. Mark each try PASS
     or FAIL, count the passes, and read that count against your target — a
     row targeting 4 of 5 with three PASS cells is MISSED (3/5).

     `python run_eval.py --label before` runs everything and writes the table
     into results/. Paste it here and fill in the verdicts. -->

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |  |  |
| 2.  |  |  |  |  |  |  |  |
| 3.  |  |  |  |  |  |  |  |
| 4.  |  |  |  |  |  |  |  |
| 5.  |  |  |  |  |  |  |  |

**Real output from one try**, pasted as text, naming the file and function
that produced it:

```

```

---

## Verdicts and Diagnoses

<!-- MET or MISSED per criterion against LAST UNIT's target, plus a sentence on
     how you decided.

     Then, for every miss: which of the four places it happened — a tool, the
     loop's branch, the session, or the model's output — AND the mechanism.

     Not a diagnosis:  "The fit card was bad."
     A diagnosis:      "The fit card criterion missed on 2 of 5 items. Both had
                        an empty brand field. My prompt puts the brand in the
                        first sentence, so the card opened with a blank and read
                        like a fragment. The tool worked; the prompt assumed a
                        field that isn't always there."

     Look for a pattern. Three misses on the same tool is one problem, not
     three. -->

| # | Criterion | Target | Verdict | How I decided |
|---|---|---|---|---|
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |
| 4 |  |  |  |  |
| 5 |  |  |  |  |

**Diagnoses**



---

## Loop Trace

<!-- One full run, printed step by step, with the MCP call visible in it.

     `python app.py ask '...' --trace` once you've added the trace.step()
     calls in Milestone 2.

     Worth pasting BOTH the happy path and the empty-search path. The empty
     one should be visibly shorter, because it stops. If your two traces are
     the same length, your branch isn't working — and this is the fastest way
     anyone will ever find that out. -->

**Happy path**

```

```

**Empty search**

```

```

**On the MCP move:** <!-- what changed in your code, and whether anything
behaved differently afterwards. If the rewire didn't work, say exactly where it
broke — the error text and the last thing that worked. That earns the point in
full. -->



---

## The Improvement

<!-- What you changed, why your diagnosis pointed at it, and the after-run in
     the same table format. One change, measured properly.

     `python run_eval.py --label after` -->

**What I changed:**

**Which failure it was meant to fix:**

### Run Log — After

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |  |  |
| 2.  |  |  |  |  |  |  |  |
| 3.  |  |  |  |  |  |  |  |
| 4.  |  |  |  |  |  |  |  |
| 5.  |  |  |  |  |  |  |  |

**Did it help, and how do I know:**

<!-- If it made things worse, say that. Honestly reported, that earns full
     credit and is more interesting than one that worked. -->



---

## What's Still Broken

<!-- For each criterion still missed: what you'd do, and why you stopped where
     you did. "I ran out of time" is fine if it's true. Pretending nothing is
     left is not. -->



<!-- ═════════════════════════════════════════════════════════════════════

     SUBMISSION CHECKLIST — unit 3

       [ ] criteria.md has five numbered criteria, each with a target
       [ ] Each criterion has a reason underneath it
       [ ] All five unit 3 sections above have real content
       [ ] Tool Inventory: all three tools, inputs WITH TYPES, a specific
           return value, and the empty case
       [ ] Planning Loop names the branch rule and agent.py::run_agent
       [ ] Sample Run: one full query plus the three per-tool tests, as text
       [ ] At least four new commits
       [ ] Repository URL submitted — WRITE IT DOWN, you submit the same one
           next unit

     SUBMISSION CHECKLIST — unit 4

       [ ] mcp_server.py exists with one tool registered
           (or a written record of exactly where the rewire broke)
       [ ] Run Log — Before, five criteria, five tries each
       [ ] Real output pasted underneath, naming file and function
       [ ] A verdict on every criterion
       [ ] A diagnosis for every miss, naming a place AND a mechanism
       [ ] Loop Trace, with the MCP call visible in it
       [ ] All three failure modes triggered and handled
       [ ] One improvement, with Run Log — After in the same format
       [ ] What's Still Broken
       [ ] At least four new commits
       [ ] The SAME repository URL as last unit

     Do not delete and recreate this repository. Your commit history is what
     shows your criteria existed before your results did.
     ═════════════════════════════════════════════════════════════════════ -->

---

📖 **How to run this project: [RUNNING.md](RUNNING.md)**
