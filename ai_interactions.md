# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agentic Workflow (SF8)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

I asked Claude Code to add 5 new attributes to the song dataset that weren't
already present (popularity, release_decade, explicit, vocal_type, and
detailed_mood_tags), update the CSV loading logic to parse each field to the
correct type, and add a new scoring component so the functional `score_song`
could reward songs whose popularity was close to an optional user-specified
target — without breaking any existing profile that doesn't specify one.

**Prompts used:**

```
I want to add 5 new attributes to my song dataset to deepen the recommender:
- popularity (integer, 0-100)
- release_decade (string, e.g., "1990s", "2000s", "2010s", "2020s")
- explicit (boolean, true/false)
- vocal_type (string: "male", "female", "instrumental", or "mixed")
- detailed_mood_tags (string, semicolon-separated list, e.g., "nostalgic;aggressive")

Add these as new columns to data/songs.csv, filling in realistic values for all 18
existing songs based on their existing genre/mood/era. Then update load_songs in
recommender.py to parse these new fields correctly (popularity as int, explicit as
bool, detailed_mood_tags as a list split on ";").

Also add a new scoring component to score_song/recommend_songs (functional path only):
+0.5 points if the song's popularity is within 20 points of a new optional
"target_popularity" key in user_prefs (skip this check if target_popularity isn't
provided, to keep backward compatibility with existing profiles).
```

**What did the agent generate or change?**

- **`data/songs.csv`** — added all 5 new columns to all 18 existing songs, with
  values chosen to be consistent with each song's existing genre/mood/era (e.g.,
  instrumental genres like lofi/ambient/classical/jazz got `vocal_type=instrumental`;
  rock/metal/hip-hop tracks got `explicit=true`; newer-sounding pop/EDM tracks got
  higher popularity scores and `release_decade=2020s`).
- **`load_songs`** — added parsing logic: `popularity` → `int`, `explicit` →
  `bool` (case-insensitive "true"/"false" string check), `detailed_mood_tags` →
  `list` (split on `;`, empty-safe so a blank cell returns `[]`).
- **`score_song`/`recommend_songs`** (functional path only) — added a new
  scoring branch that awards +0.5 points if `abs(song["popularity"] -
  user_prefs["target_popularity"]) <= 20`, but only if `target_popularity` is
  present in `user_prefs` at all, so any profile that doesn't specify it scores
  exactly as before.

**What did I verify or fix manually?**

I ran `pytest` first to confirm the existing OOP-path tests still passed
unmodified (they did — 2/2 passed, since the new fields don't touch the
`Song`/`UserProfile`/`Recommender` classes at all). Then I wrote a manual
verification script to check three things directly: (1) that all 5 new fields
parsed to the correct Python types on a real song row (confirmed: `popularity`
came back as `int`, `explicit` as `bool`, `detailed_mood_tags` as a `list`);
(2) that a profile with no `target_popularity` produced the exact same scores
as before my change (confirmed: Sunrise City still scored 4.38, unchanged);
and (3) that adding `target_popularity=80` correctly added the +0.5 bonus with
a matching explanation string (confirmed: Sunrise City rose to 4.88 with
`"popularity match (+0.5)"` appended).

One thing I chose *not* to have the agent do: wire `release_decade`, `explicit`,
`vocal_type`, and `detailed_mood_tags` into scoring as well, even though they're
now loaded. This mirrors a limitation I'd already found and documented in
`model_card.md` — that `tempo_bpm`, `valence`, and `danceability` are loaded but
never scored. Rather than scoring every new field just to use it, I left these
four as loaded-but-unscored on purpose, since forcing extra scoring logic in
without a clear justification would just be adding complexity for its own sake.

---

## Design Pattern (SF10)

> Document how AI helped you choose or implement a design pattern.

**Which design pattern did you use?**

The **Strategy pattern**, implemented as swappable weight-configuration profiles
rather than swappable code bodies. I built four ranking modes — Balanced,
Genre-First, Mood-First, and Energy-Focused — that a user selects via a single
`STRATEGY` constant in `main.py`.

**How did AI help you brainstory or implement it?**

I asked Claude Code to design multiple ranking strategies for the recommender
without duplicating the existing scoring logic. It identified the key insight
that made this possible without duplication: my three planned strategies don't
differ in *what* they check (genre match, mood match, energy closeness,
popularity) — they only differ in *how much* each component is worth. So rather
than writing a separate scoring function per strategy (which is what
`score_song_experimental` already was, from the Phase 4 weight-shift
experiment), the AI proposed keeping one `score_song` function body and passing
in a `weights` dictionary that the conditions read their point values from.
Each "strategy" then becomes a named entry in a `STRATEGIES` registry
(`{"genre": 2.0, "mood": 1.0, "energy": 1.5, "popularity": 0.5}` for Balanced,
etc.), and `recommend_songs` looks up the right weights by name.

**How does the pattern appear in your final code?**

In `recommender.py`: a `DEFAULT_WEIGHTS` dict (reproducing the original,
unchanged scoring), a `STRATEGIES` registry mapping strategy names to weight
dicts, a refactored `score_song(user_prefs, song, weights=None)` that reads
its point values from the weights dict instead of hardcoded numbers, and
`recommend_songs(..., strategy="Balanced")` which looks up the named strategy
and threads its weights through — raising a clear `ValueError` listing valid
options if an unknown strategy name is passed. In `main.py`, a single
`STRATEGY = "Balanced"` constant controls which mode the CLI runs in, and the
chosen strategy is echoed in the terminal output header.

I verified this didn't break anything by confirming all existing tests still
passed, and that calling `recommend_songs` with no `strategy` argument at all
produced byte-for-byte identical scores to before the refactor (Storm Runner:
4.484999999999999, unchanged). I then confirmed the four strategies produce
meaningfully different rankings on the same profile — Genre-First widens Storm
Runner's lead over Gym Hero (4.99 vs. 1.97), while Energy-Focused compresses
that same gap (4.97 vs. 3.91) and lifts an on-energy EDM track that Balanced
ranked lower.

I chose *not* to fold `score_song_experimental`/`recommend_songs_experimental`
into this new registry, even though the AI pointed out they're now redundant
with a strategy entry. Those functions are referenced directly in my Phase 4/5
`model_card.md` write-up as the artifacts of a specific documented experiment —
deleting them would break that trail of evidence for anyone reading the model
card and then checking the code.

---

## Diversity/Fairness Logic (Challenge 3)

I asked Claude Code to implement a diversity penalty so recommendations aren't
dominated by the same artist or genre — a direct response to a bias I'd already
documented in `model_card.md` (13 of 15 genres are singletons, so genre imbalance
gets amplified rather than corrected). The agent built a new `recommend_songs_diverse`
function using a greedy re-ranking approach: it picks the top song, then recomputes
every remaining candidate's score against the artists/genres already selected,
subtracting 0.75 for a repeated artist and 0.5 for a repeated genre, before picking
the next song. This is different from a one-shot sort, since the penalty has to be
recalculated relative to what's already been picked.

I verified this on the "Chill Lofi" profile, which I already knew was
lofi-dominated (Library Rain, Midnight Coding, and Focus Flow — all lofi — held
the top 3 spots). After the diversity penalty, Focus Flow (also LoRoom, the same
artist as Midnight Coding) dropped from 3rd to 4th, and Spacewalk Thoughts
(ambient) moved up to 3rd, breaking up the genre run. The score explanations now
show exactly which penalties applied (e.g., `"artist repeat (-0.75), genre repeat
(-0.5)"`), keeping the transparency principle from the original scoring intact. I
wired this into `main.py` behind a `DIVERSITY_MODE` toggle so the original
`recommend_songs` stays the default, byte-for-byte unchanged.

---

## Visual Summary Table (Challenge 4)

I asked Claude Code to improve CLI readability using the `tabulate` library,
displaying Rank/Title/Score/Reasons as a formatted table for each profile. The
agent checked whether `tabulate` was installed (it wasn't), added it to
`requirements.txt`, and wrote a guarded import so the CLI gracefully falls back
to the original plain-text format with an install hint if `tabulate` isn't
present, rather than crashing.

I verified this by setting up a proper virtual environment (`python3 -m venv
.venv`, then `pip install -r requirements.txt`) and confirming the tables
rendered correctly across all 7 test profiles, with scores matching the
original baseline exactly when diversity mode was off. One thing I checked
manually: the agent initially tried to install `tabulate` directly into the
system Python and correctly stopped when it hit a PEP 668 "externally managed
environment" error, rather than forcing an unsafe install — it verified the
feature worked in an isolated temp directory first, which I then confirmed for
real using a proper venv.

---

## Agentic Workflow Enhancement (Stretch Feature +2)

**What was built:** A genuine two-step reasoning chain was added to `src/agent.py`.
Step 1 (`critique_recommendations`) evaluates each recommendation and assigns a
confidence label. Step 2 (`decide_on_recommendations`) is a *separate, chained*
Claude API call that takes the Step 1 critiques as input and makes an explicit
decision per song: `keep`, `flag_for_review`, or `suggest_alternative` (naming
a better-fitting song already present in the recommendation list, if one exists).

**Why this is a genuine multi-step chain, not a single call restructured:** Step 2
never re-evaluates the raw song data — it reasons purely from Step 1's output
(the critique text and confidence label), meaning each step depends on the
previous one's result. A validation guardrail also downgrades any suggested
alternative that isn't actually present in the candidate list to
`flag_for_review`, preventing the model from inventing an unsupported suggestion.

**Full intermediate reasoning trace:** saved to [`logs/reasoning_trace.jsonl`](logs/reasoning_trace.jsonl),
containing both the raw `step_1_critiques` and `step_2_decisions` for every
critiqued profile, so the complete two-step chain is committed and inspectable.

**Sample chain output (High-Energy Pop profile, pop/happy/0.9):**

| Song | Step 1: Confidence | Step 2: Decision |
|---|---|---|
| Sunrise City | High | keep |
| Gym Hero | Medium | flag_for_review (mood mismatch masked by genre points) |
| Rooftop Lights | Medium | keep (indie pop close enough) |
| Neon Uprising | Low | suggest_alternative → Sunrise City |
| Storm Runner | Low | suggest_alternative → Sunrise City |

This demonstrates the agent isn't just labeling confidence — it's making an
actionable decision informed by its own prior reasoning step, and that decision
is logically consistent with the confidence label that produced it (every
"suggest_alternative" traces back to a "Low" confidence critique; every "keep"
traces back to "High" or a defensible "Medium").