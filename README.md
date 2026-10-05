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

A user types one plain-language request for a secondhand find — "vintage
graphic tee under $30" or "platform sneakers size 8". FitFindr pulls a
description, a size and a price ceiling out of that sentence, searches 40 mock
thrift listings for matches, picks the best one, asks the model how to wear it
with the clothes already in the user's wardrobe, and then writes a short
caption they could post about the find. What comes back is three things: the
listing itself (title, price, platform), an outfit built from pieces they
already own, and the caption. If nothing in the data matches, it stops after
the search and says which of the three filters to loosen, rather than styling
an item it never found.

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

**One full query**

```
$ python app.py ask 'vintage graphic tee under $30'

[1] parse_query
      in:  vintage graphic tee under $30
      out: dict with keys: description, size, max_price
[2] search_listings
      in:  dict with keys: description, size, max_price
      out: 10 items: Y2K Baby Tee — Butterfly Print, Graphic Tee — 2003 Tour Bootleg Style, Vintage Band Tee — Faded Grey … +7 more
[3] select_item
      in:  10 results
      out: Y2K Baby Tee — Butterfly Print ($18.0, depop)
      →    branch: results found, continuing to suggest_outfit
[4] suggest_outfit
      in:  Y2K Baby Tee — Butterfly Print ($18.0, depop)
      out: Pair the butterfly baby tee with the baggy straight-leg dark wash jeans to balance the fitted crop length, add…
[5] create_fit_card
      in:  Y2K Baby Tee — Butterfly Print ($18.0, depop)
      out: My inner early 2000s pop star is currently screaming because I tracked down the ultimate butterfly baby tee on…

  Found:    Y2K Baby Tee — Butterfly Print — $18.0 on depop

  Outfit:   Pair the butterfly baby tee with the baggy straight-leg dark wash jeans to balance the fitted crop length, adding the brown leather belt and chunky white sneakers for an effortless Y2K streetwear look. For a slightly edgier vibe when the weather cools, layer the black cropped zip hoodie unzipped over the tee, keeping the same baggy jeans and finishing the outfit with the black combat boots.

  Fit card: My inner early 2000s pop star is currently screaming because I tracked down the ultimate butterfly baby tee on depop. It is giving major mall tour energy and I only had to shell out $18 for it. Honestly, nobody else is going to look this effortlessly nostalgic today.

1 model calls this session, 1 served from cache, 310 prompt + 60 output tokens
```

**The same loop on a query the data cannot match** — it stops at step 3, where
the happy path keeps going to step 5:

```
$ python app.py ask 'designer ballgown size XXS under $5'

[1] parse_query
      in:  designer ballgown size XXS under $5
      out: dict with keys: description, size, max_price
[2] search_listings
      in:  dict with keys: description, size, max_price
      out: [] (empty)
[3] branch
      in:  len(session['search_results']) == 0
      out: Stopped before styling anything: nothing matched "designer ballgown" with the filters I read out of your query…
      →    branch: empty, stopping before suggest_outfit

  Stopped before styling anything: nothing matched "designer ballgown" with the filters I read out of your query. To get results, raise the $5 ceiling; or drop or widen size XXS; or try the words that are on the listings themselves — the data is tagged vintage, y2k, grunge, streetwear, denim, graphic tee, cargo, flannel, slip dress, platform.

0 model calls this session
```

Zero model calls on that path, which is the branch working: it stopped before
`suggest_outfit`, not after it.

**The three tools, tested one at a time**

```
$ python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"

[{'id': 'lst_006', 'title': 'Graphic Tee — 2003 Tour Bootleg Style', 'description':
'Vintage-style bootleg tee with faded graphic. Slightly boxy fit. 100% cotton, soft
and worn-in.', 'category': 'tops', 'style_tags': ['graphic tee', 'vintage', 'grunge',
'streetwear', 'band tee'], 'size': 'L', 'condition': 'good', 'price': 24.0, 'colors':
['black'], 'brand': None, 'platform': 'depop'}, {'id': 'lst_002', 'title': 'Y2K Baby
Tee — Butterfly Print', ... }]
                                            (6 listings, all priced at or under $30)

$ python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"

[]
```

```
$ python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"

Tuck the white ribbed tank top into the vintage Levi's 501 jeans, cinched at the
waist with the brown leather belt. Layer the oversized grey crewneck sweatshirt
casually over your shoulders and finish the look with the chunky white sneakers for
an effortless, classic daytime street style. For cooler weather, wear the black
cropped zip hoodie under the vintage black denim jacket, paired directly with the
Levi's and the black combat boots to create a textured, edgy silhouette.
```

Every garment it names is in `data/wardrobe_schema.json` — it isn't inventing
pieces.

```
$ python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"

Scored these vintage medium wash Levi 501s on depop for just $38 and they fit like
an absolute dream. The lived-in fade at the knees gives them that effortless
Saturday morning coffee run energy. Paired with my crispest white sneakers, this is
officially my uniform for the foreseeable future.

$ python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('   ', load_listings()[0]))"

No outfit suggestion to write a card from — suggest_outfit returned nothing.
```

Run three times on the same item, the card comes back different each time
(`TEMPERATURE = 0.9`, and the tool passes `cache=False`). Three consecutive
opening sentences:

```
run 1:  Finally cracked the code on finding true vintage denim that actually fits…
run 2:  Everyone keeps asking me how I find denim that actually hugs the waist…
run 3:  Some days you just manifest the exact vintage wash you have been hunting for.
```

---

## How I Used AI

**Moment 1 — the size filter**

- *What I asked for:* I pasted my `search_listings` spec into Claude with the
  list of every distinct size string in `data/listings.json` and asked whether
  a case-insensitive substring test would satisfy the spec line "a request for
  M should match S/M".
- *What came back:* It pointed out two cases from that list that break it:
  `"s" in "us 9"` is `True`, so asking for a small top returns shoes, and
  `"l" in "xl"` is `True`, so asking for large returns extra-large. It also
  flagged `"W30 L30"`, where the `L30` is an inseam and would match a request
  for size L.
- *What I changed:* I threw out the substring test and wrote `_size_tokens()`
  in `tools.py`, which splits a size string into whole tokens, drops
  parentheticals like `(oversized)`, ignores an `L<number>` inseam, and treats
  anything containing "One Size" as matching everything. Then I wrote the rule
  into my Tool Inventory, because what counts as a size match is part of the
  spec and not an implementation detail. `search_listings('platform sneakers',
  size='8')` now returns exactly the platform sneakers, and
  `_size_matches('US 9', 'M')` is `False`.

**Moment 2 — attacking my own acceptance criteria**

- *What I asked for:* I pasted all five criteria from `criteria.md` in and
  asked the question the brief suggests — for each one, tell me exactly how
  you would test it using only what the sentence says, and don't suggest
  improvements.
- *What came back:* It produced a concrete procedure for criteria 1, 2, 3 and
  5. On criterion 4 it stopped at my phrase "mentions the price": it said it
  could not tell whether a card reading "snagged it for eighteen dollars"
  counts, because the number is there but not as a number, so it did not know
  whether to write the check as a regex for the digits or as a human judgement.
- *What I changed:* Two things. I made the criterion say "contains the item's
  price as a number", so the check is a regex and nothing else. Then I ran my
  own card tool and discovered the ambiguity was real and not hypothetical —
  it had actually written "eighteen dollars" for the $18 baby tee, which my own
  regex would have scored as a miss. So I added one clause to the prompt in
  `create_fit_card`: write the price as a numeral with a dollar sign, not
  spelled out in words. The criterion got checkable and the tool got fixed, and
  I would not have found the second one without tightening the first.

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
