# Acceptance criteria — FitFindr

Five criteria that say what "working" means for this agent, written in unit 3
**before** any results existed.

---

## 1. A matching query completes all three tools

Given a query that matches at least one listing, the agent completes all three
tool calls and returns a fit card — in at least 4 of 5 tries.

**Why this target:** My search is keyword overlap against the title,
description, style tags, category and colors — there is no synonym handling at
all. "Tee" scores against the `graphic tee` style tag, but a phrasing like
"band shirt" or "going-out top" has no token in common with anything in the
file, so some reasonable queries return `[]` and stop at the branch. 4 of 5
leaves room for one phrasing my tokenizer cannot reach. I did not go to 3 of 5
because the five queries `python app.py examples` prints are all phrased with
words that do appear in the data, so most of them should land.

---

## 2. An impossible query stops before the second tool

Given a query that matches no listings, the agent stops before calling
`suggest_outfit` and returns a message naming what to change — 5 of 5 tries.

**Why this target:** This path touches no model at all. `search_listings` is
pure Python over a 40-row JSON file, the branch is one `if not
session["search_results"]`, and the message is a formatted string built from
the parsed query. Nothing in it can vary between runs — no temperature, no
network, no cache. A deterministic path that fails even once is a logic bug,
not variance, so anything below 5 of 5 would mean the branch is simply wrong.

---

## 3. Something about state

For 5 different matching queries, `session["selected_item"]["id"]` equals the
`id` of the item that `suggest_outfit` actually received, and that same `id`
appears in `session["search_results"][0]` — 5 of 5 tries. I check it by having
`run_agent` record the `id` of the dict it hands to each model tool in
`session["handoff_ids"]`, then comparing the three ids after the run:
`search_results[0]["id"]`, `selected_item["id"]`, and
`handoff_ids["suggest_outfit"]` must be the same string.

**Why this target:** This is a pure-Python identity check on dictionary keys,
so there is nothing to be probabilistic about — either the loop reads the item
back out of the session or it doesn't. 5 of 5. The reason it is worth writing
down at all is that a state mix-up does not look like a state bug: if the loop
re-sorted or re-searched between steps, the fit card would simply describe a
different jacket than the one printed as "Found:", and I would spend an hour
blaming the prompt. Recording the handoff id makes the failure visible in one
comparison.

---

## 4. Something about the fit card

Across 5 runs of `create_fit_card` on the **same** item with caching off, all
5 cards (a) contain the item's price as a number and the platform name, (b) are
between 2 and 4 sentences, and (c) have 5 distinct opening sentences. I will
accept 5 of 5 on (a) and (b), and 4 of 5 distinct on (c).

**Why this target:** (a) and (b) are things I put in the prompt as explicit
instructions and can check with a regex and a sentence split, so a miss is a
prompt problem I can fix — I hold those at 5 of 5. (c) is the part I cannot
control: at `TEMPERATURE = 0.9` the model is free to open two of five cards the
same way, especially on a short caption where "Found this" is an obvious first
move. Demanding 5 distinct openings would be demanding something about the
model's sampling rather than about my code, so I allow one collision. If two
*different* items ever produced the same opening sentence I would call that a
template and a real failure, which is why the criterion is about the same item
— the harder case.

---

## 5. Your choice — the price ceiling is never violated

For every query containing a price ceiling, every listing in
`session["search_results"]` has `price <= max_price`, and `max_price` as parsed
matches the number the user typed — across 5 queries with ceilings of $20,
$30, $40, $50 and $25, that's 5 of 5 queries with zero over-ceiling results.

**Why this target:** This is the one failure a user would notice immediately
and never forgive — being shown a $120 coat after asking for one under $50
makes the whole thing untrustworthy, in a way that a mediocre caption does not.
It is also two deterministic pieces: a regex that extracts the number, and one
`<=` comparison in the filter. Both are testable without the model, so 5 of 5
is the only honest target. I included the parse in the criterion rather than
only the filter because the quiet failure here is not a broken comparison —
it's `max_price` coming back as `None` because my regex missed the phrasing,
and then the filter correctly applies no ceiling at all and every result looks
fine.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 4 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 4. Something about the fit card

         The fit card is different every time.

         **Why this target:** ...

         > **Revised in unit 4:** For 5 different items, the 5 fit cards share
         > no opening sentence.
         >
         > **Why revised:** "different" wasn't checkable — two cards that
         > differed by one word still counted. The new version is something I
         > can actually score.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said the empty search stops it 5 of 5 times, but I got 3 of 5,
            so 3 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->
