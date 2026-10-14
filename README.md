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

**Where the search runs (unit 4):** the loop no longer imports
`search_listings` for its own use — `agent.py::_search_over_mcp` calls it
through the MCP server registered in `mcp_server.py::search_listings`, and
records `"mcp"` or the reason it fell back in `session["search_transport"]`.
The direct import is kept as the fallback path.

**How the query is parsed:** regex, in `agent.py::parse_query`. One pattern
pulls a price ceiling (`under $30`, `below 30`, `$30 or less`, a bare `$30`),
one pulls a size (`size M`, `size 8`, `in a medium`, `sz L`), and the matched
spans are stripped out of the string; what is left, minus a few filler words
(`looking`, `for`, `a`, `in`), becomes the description.

**What moves through the session:** in this order —
`query` → `parsed` (`{description, size, max_price}`) → `search_results`
(the list from `search_listings`) → `selected_item` (`search_results[0]`) →
`outfit_suggestion` → `fit_card`, with `handoff_ids` recording which item id
each model tool actually received. Each step writes its result into the session
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

<!-- ═══════════════════════ UNIT 4 — THE TEST ═══════════════════════ -->

---

## Run Log — Before

Produced by `run_eval.py::main`, caching off, temperature 0.9, five tries per
scenario. Full output: [`results/run_2026-10-13_2339_before.md`](results/run_2026-10-13_2339_before.md).
The per-try counts below were read out of that file with `score.py`, which
counts the evidence lines and decides nothing.

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1. A matching query completes all three tools | ≥4 of 5 | PASS | PASS | PASS | PASS | PASS | **MET (5/5)** |
| 2. An impossible query stops before the second tool | 5 of 5 | PASS | PASS | PASS | PASS | PASS | **MET (5/5)** |
| 3. The item handed on is the item that was found | 5 of 5 | PASS | PASS | PASS | PASS | PASS | **MET (5/5)** |
| 4. Fit card: price as a numeral, 2–4 sentences, distinct openings | 5 of 5 on price and length; 4 of 5 distinct openings | FAIL | PASS | PASS | FAIL | PASS | **MISSED (3/5)** |
| 5. The price ceiling is never violated | 5 of 5 | PASS | PASS | PASS | PASS | PASS | **MET (5/5)** |

How each row was counted:

- **1** — `stopped_early=0/5`, a fit card on all five tries.
- **2** — `stopped_early=5/5`, every try's error naming the $5 ceiling, size
  XXS and the tags in the data; `0 model calls` on that scenario, which is the
  branch proving it stopped *before* `suggest_outfit` rather than after it.
- **3** — all five tries printed
  `search_results[0]=lst_004 selected_item=lst_004 handoff_ids={'suggest_outfit': 'lst_004', 'create_fit_card': 'lst_004'}`.
  Three sources, one id, five times.
- **4** — the FAILs are the price condition, not the length or the openings:
  `price_as_numeral=['False', 'True', 'True', 'False', 'True']`. Sentence
  counts were `[3,3,3,3,3]` and all five openings were distinct, so (b) and
  (c) passed; (a) went 3 of 5 against a target of 5 of 5, and a criterion with
  three conditions is missed if any is.
- **5** — `max_price=50.0` parsed from "under $50" on all five tries,
  `over_ceiling=0` on all five, with `highest_price=45.0` out of 7 results.
  Four listings in the data are priced above $50 and none appeared.

**Real output from one try**, produced by `agent.py::run_agent` with the
search running through `mcp_server.py::search_listings`, the caption by
`tools.py::create_fit_card` — this is try 1 of criterion 4's scenario, one of
the two misses:

```
- stopped early: no
- selected_item: 90s Silk Slip Dress — Floral, Midi Length ($30.0, depop)
- search_results: 5
- search_transport: mcp
- parsed: {'description': 'silk slip dress midi length', 'size': None, 'max_price': 40.0}
- ids: search_results[0]=lst_013 selected_item=lst_013 handoff_ids={'suggest_outfit': 'lst_013', 'create_fit_card': 'lst_013'}
- ceiling: max_price=40.0 results=5 highest_price=30.0 over_ceiling=0
- card: sentences=3 price_as_numeral=False platform_named=True

Fit card:

I scored this dreamy floral slip dress on depop and honestly, nobody touch me.
It has that perfect grungy romance that usually takes three hours of digging to
find, but I got it for thirty dollars. Pairing it with heavy combat boots makes
me look effortlessly cool instead of delicate, and I am obsessed.
```

Everything about that try is right except three words: `thirty dollars`.

---

## Verdicts and Diagnoses

| # | Criterion | Target | Verdict | How I decided |
|---|---|---|---|---|
| 1 | A matching query completes all three tools | ≥4 of 5 | **MET (5/5)** | `stopped_early=0/5` and a non-empty `fit_card` on every try |
| 2 | An impossible query stops before `suggest_outfit` | 5 of 5 | **MET (5/5)** | Every try set `error` and left `fit_card` as `None`; the scenario made 0 model calls, so nothing downstream ran |
| 3 | The item handed on is the item that was found | 5 of 5 | **MET (5/5)** | `search_results[0]["id"]`, `selected_item["id"]` and `handoff_ids["suggest_outfit"]` were the same string on all five tries |
| 4 | Fit card: price as a numeral, 2–4 sentences, 4/5 distinct openings | 5 of 5 / 5 of 5 / 4 of 5 | **MISSED (3/5)** | `price_as_numeral` was False on tries 1 and 4; length and openings both passed |
| 5 | The price ceiling is never violated | 5 of 5 | **MET (5/5)** | `max_price=50.0` parsed correctly and `over_ceiling=0` on all five tries |

**Diagnoses**

**Criterion 4 — the one miss. Where: the tool, specifically the prompt in
`tools.py::create_fit_card`. Not the loop, not the session, not the search.**

The mechanism: I had the price rule in two places that disagreed with each
other. `_CARD_SYSTEM` said to mention the price "once and the platform once,
*naturally*", and the numeral requirement was one clause buried at the end of a
long user prompt, after the nine-line item block and the whole outfit
paragraph. When the model followed "naturally" it wrote prose — "I got it for
thirty dollars", "dropping forty-two dollars felt justified" — which is a
perfectly good caption and a failed criterion. So the failure was not the model
ignoring an instruction; it was the model obeying the stronger of two
instructions I had given it.

The miss rate is the other half of the diagnosis. Five of the six scenarios produce a
card (the impossible query produces none), so the before run wrote 25 cards,
and 22 had the numeral — three misses: criterion 4 tries 1 and 4, and
criterion 5 try 3. So this was never "the prompt doesn't work", it was a leak
running at 3 in 25, which is exactly the kind of thing
one run would have hidden from me. Criterion 4's scenario drew two of the three
by chance; had it drawn none, I would have called the criterion met and shipped
the leak.

**Why nothing else is diagnosed:** criteria 1, 2, 3 and 5 are all deterministic
paths — a keyword filter, one `if`, dictionary-key comparisons and a `<=` — and
all four came back 5 of 5, which is what I predicted in `criteria.md` for
exactly that reason. The only criterion that touched the nondeterministic part
of the system is the only one that missed, and the two conditions in it that I
could state as hard rules (sentence count, distinct openings) passed, while the
one I had stated twice and inconsistently failed.

**One thing worth recording that was not a miss:** an earlier before-run (the
same five scenarios, discarded only because it predated the evidence lines
`score.py` reads) had criterion 4 try 4 fail differently — the service returned
`503 UNAVAILABLE` and the run ended at `create_fit_card` with no card at all.
That is handled, not crashed: the handler in `agent.py::run_agent` turned it
into a message naming the stage. But it is a second, independent way criterion
4 can miss, and it is not something a prompt fix can touch — `generate.py`
retries 429s and raises on everything else, so a transient 503 ends the run.
See **What's Still Broken**.

---

## Loop Trace

Both traces come from `agent.py::run_agent` via `trace.step()`, captured in the
after run. Step 2 is the MCP call.

**Happy path**

```
[1] parse_query
      in:  vintage graphic tee under $30
      out: dict with keys: description, size, max_price
[2] search_listings via mcp
      in:  dict with keys: description, size, max_price
      out: 10 items: Y2K Baby Tee — Butterfly Print, Graphic Tee — 2003 Tour Bootleg Style, Vintage Band Tee — Faded Grey … +7 more
      →    MCP tool call — mcp_server.py::search_listings
[3] select_item
      in:  10 results
      out: Y2K Baby Tee — Butterfly Print ($18.0, depop)
      →    branch: results found, continuing to suggest_outfit
[4] suggest_outfit
      in:  Y2K Baby Tee — Butterfly Print ($18.0, depop)
      out: Pair the Y2K baby tee with your baggy straight-leg jeans in dark wash, letting the cropped hem show. Add the v…
[5] create_fit_card
      in:  Y2K Baby Tee — Butterfly Print ($18.0, depop)
      out: Scored this absolute dream of a butterfly baby tee on depop. It hugs in all the exact right places and looks l…
```

**Empty search**

```
[1] parse_query
      in:  designer ballgown size XXS under $5
      out: dict with keys: description, size, max_price
[2] search_listings via mcp
      in:  dict with keys: description, size, max_price
      out: [] (empty)
      →    MCP tool call — mcp_server.py::search_listings
[3] branch
      in:  len(session['search_results']) == 0
      out: Stopped before styling anything: nothing matched "designer ballgown" with the filters I read out of your query…
      →    branch: empty, stopping before suggest_outfit
```

Three steps against five, and `0 model calls this session` on that scenario —
the branch stops the run before either model tool, rather than calling them and
discarding the result.

**On the MCP move:** `mcp_server.py` registers one tool, `search_listings`,
with the typed inputs taken straight from the Tool Inventory
(`description: str` required, `size: str | None`, `max_price: float | None`) and
a description written for a client that cannot see my code — it gives the unit
for `max_price` ("an inclusive ceiling in whole or fractional US dollars; 30
means $30.00, not 3000 cents"), states the whole-token size rule with examples
of what does *not* match, and spells out that an empty list is the normal
answer rather than an error. In `agent.py::run_agent` the direct call became
`call_tool("search_listings", {...})`, wrapped in `_search_over_mcp()`.

What `python mcp_client.py` reports back:

```
  search_listings
    Search a fixed catalogue of 40 secondhand clothing listings and return the
    ones matching a plain-language description, ranked best match first.
    …
    - description: string
    - size: string  (optional)
    - max_price: number  (optional)
```

Nothing behaved differently afterwards, which is the result I wanted and I
checked it rather than assuming it:

```
$ python -c "
from tools import search_listings
from mcp_client import call_tool
d = search_listings('vintage graphic tee', max_price=30)
m = call_tool('search_listings', {'description': 'vintage graphic tee', 'size': None, 'max_price': 30})
print(type(m), len(m), d == m)"

<class 'list'> 10 True
```

Same type, same length, equal element by element — and `[]` still arrives as
`[]` over the wire, which matters because that is the value the branch tests.
`_search_over_mcp()` also asserts `isinstance(results, list)` and falls back to
the direct call if the server is unreachable, recording which transport ran in
`session["search_transport"]` so the trace can never claim MCP when it was the
fallback. Every try in both run logs says `search_transport: mcp`.

**The three failure modes, triggered on purpose**

**1. Nothing matches** — `python app.py ask 'designer ballgown size XXS under $5'`

```
  Stopped before styling anything: nothing matched "designer ballgown" with the
  filters I read out of your query. To get results, raise the $5 ceiling; or
  drop or widen size XXS; or try the words that are on the listings themselves
  — the data is tagged vintage, y2k, grunge, streetwear, denim, graphic tee,
  cargo, flannel, slip dress, platform.

0 model calls this session
```

Handled in `agent.py::run_agent` at the branch. The message names all three
filters it applied, because the user cannot tell which one was the problem.

**2. Empty wardrobe** — `python app.py ask 'denim jacket under $50' --empty-wardrobe`

```
  Outfit:   Since your wardrobe is currently empty, here is general styling
  advice starting with the jacket as your foundation. Layer the cropped light
  wash Wrangler jacket over an oversized charcoal grey cotton hoodie to play
  with proportions. Pair it with black wide leg pleat front trousers that pool
  slightly over chunky black leather loafers.

  Fit card: Scored this cropped Wrangler jacket on Poshmark for just $42 and my
  street style game is officially unlocked. …
```

Handled in `tools.py::suggest_outfit`, which branches on
`wardrobe["items"]` being empty and switches prompts — general advice, with the
reason stated, rather than a failure or an invented wardrobe. The run completes
all three tools; `empty wardrobe` scored 5/5 completions in both run logs.

**3. The model can't be reached** —
`GEMINI_API_KEY=AIzaBROKEN AI201_CACHE=0 python app.py ask 'vintage graphic tee under $30'`

```
[5] ModelUnavailable
      in:  stage=suggest_outfit
      out: The model rejected your API key. Check GEMINI_API_KEY in your .env file, or create a fresh key at aistudio.goo…
      →    handled: message instead of a stack trace, fit_card stays None

  The model couldn't be reached, so I stopped at suggest_outfit. The model
  rejected your API key. Check GEMINI_API_KEY in your .env file, or create a
  fresh key at aistudio.google.com. Everything finished before that is still in
  the session (search_results, selected_item); re-run once the key or the
  network is sorted.
```

Handled by the `except ModelUnavailable` clause in `agent.py::run_agent`. It
names the stage it died at and lists what survived in the session, so the
message distinguishes "died before any styling" from "died with the outfit
already written" — with the cache left on, the same broken key stops at
`create_fit_card` instead, and the message says so.

**A fourth one I got for free, because MCP added a new way to fail:** the
server not starting. Simulated by making `call_tool` raise:

```
  [mcp] unreachable, falling back to the direct call: simulated: server exited before responding
[2] search_listings via direct (mcp failed)
transport: direct (mcp failed) | results: 7
```

The run completes on the in-process tool and the session records that MCP was
not what ran.

---

## The Improvement

**What I changed:** one thing — where the price-format rule lives. In
`tools.py::create_fit_card` I removed the word "naturally" from the price
sentence in `_CARD_SYSTEM`, put the rule in the system instruction as a hard
constraint ("THE PRICE IS ALWAYS WRITTEN AS DIGITS WITH A DOLLAR SIGN — $18,
$42 — never spelled out in words"), and changed the user prompt from describing
the format to asking for one exact string (`contain the exact string "$30"
once`). No change to the loop, the search, the session or the other tool.

**Which failure it was meant to fix:** criterion 4's two FAILs — the 3-in-30
cards that wrote the price in words. The diagnosis said the model was obeying
the stronger of two conflicting instructions, so the fix was to stop giving it
two.

### Run Log — After

Produced by `run_eval.py::main`, same six scenarios, same five tries, caching
off. Full output: [`results/run_2026-10-13_2342_after.md`](results/run_2026-10-13_2342_after.md).

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1. A matching query completes all three tools | ≥4 of 5 | PASS | PASS | PASS | PASS | PASS | **MET (5/5)** |
| 2. An impossible query stops before the second tool | 5 of 5 | PASS | PASS | PASS | PASS | PASS | **MET (5/5)** |
| 3. The item handed on is the item that was found | 5 of 5 | PASS | PASS | PASS | PASS | PASS | **MET (5/5)** |
| 4. Fit card: price as a numeral, 2–4 sentences, distinct openings | 5 of 5 / 5 of 5 / 4 of 5 | PASS | PASS | PASS | PASS | PASS | **MET (5/5)** |
| 5. The price ceiling is never violated | 5 of 5 | PASS | PASS | PASS | PASS | PASS | **MET (5/5)** |

**Did it help, and how do I know:** yes, and the number I trust is not
criterion 4's row — it's the whole-run count, because the row is only five
samples of a leak that was running at about 12%.

| | Cards with the price as a numeral | Criterion 4's row |
|---|---|---|
| Before | 22 of 25 | 3 of 5 — MISSED |
| After | 25 of 25 | 5 of 5 — MET |

Every other measurement held still, which is what I wanted from a one-line
change: sentence counts stayed inside 2–4 (one card came back at 2 sentences in
each run, which is in range), all five openings stayed distinct in every
scenario, `over_ceiling` stayed 0 across both logs, and the handoff ids stayed
identical. Nothing regressed to buy the fix.

The honest limit on that claim: 25 cards cannot distinguish "fixed" from
"reduced below 1 in 25". A leak that now fires at 2% looks exactly like this.
What I can say is that the mechanism I named is gone — there is no longer an
instruction telling the model to write the price naturally — and that the
before/after difference is in the direction and the place the diagnosis
predicted.

---

## What's Still Broken

**A transient 503 from the model service ends the run, and it counts as a
criterion 4 miss.** This is the failure from the discarded first before-run: the
service returned `503 UNAVAILABLE` mid-run, `generate.py` retries 429s and
raises `ModelUnavailable` on everything else, and my handler correctly turned it
into a message — but a run with no fit card fails criterion 4 regardless of how
gracefully it stopped. The fix is one retry at the loop level for a transient
error, distinguished from a permanent one like a bad key, which means telling
them apart by the text of the exception. I stopped short of it because the unit
asks for **one** change measured properly, and I had already chosen the one my
diagnosis pointed at. Spending my single change on a failure I had seen once
would have left the 12% leak in place, and the leak was the one I could measure
before and after.

**My search still has no synonyms, and criterion 1's 4-of-5 target was never
really tested.** It passed 5 of 5 — but with one query, phrased in words that
are literally in the data. The criterion says "a query that matches at least
one listing", and the queries that would actually threaten it are the ones where
a human would say a listing matches and my tokeniser disagrees: "band shirt"
for the band tee, "going-out top" for the mesh long-sleeve. `search_listings`
scores raw word overlap, so both return `[]` and the run stops with a message
telling the user to use different words. That is a defensible product decision
and an undefended criterion; a fair test of it needs a scenario list of five
*differently phrased* queries, not one query five times.

**Criterion 4 measures one item, and the shared-template failure is the one I
actually care about.** I wrote it about five cards for the same item because
that is the harder test of variance, and I stand by the reasoning — but what
would genuinely embarrass this app is two *different* finds opening with the
same sentence, and nothing in my five criteria checks that. Across the before
run's 25 cards the openings repeat a form heavily — 7 of the 25 begin with the
word "Scored" — while being distinct strings, so my check passes on output a reader
would call samey. I would make this a sixth criterion rather than revise the
fourth, since the fourth measures what it says it measures.

**The MCP fallback hides a real failure behind a working run.** If the server
stops starting, `_search_over_mcp()` degrades to the direct call and the user
sees a normal result; only `session["search_transport"]` and one line on stderr
record that the protocol path is broken. For a class project that is the right
trade — the stop rule in the brief says keep the direct call working. In
anything real it should be a loud failure or a counted metric, because a
fallback nobody notices is a fallback that is always on.

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
