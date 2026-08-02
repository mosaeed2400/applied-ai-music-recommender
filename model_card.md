# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name

**VibeFinder 1.0**

---

## 2. Intended Use

This recommender is designed to suggest songs from a small catalog based on a listener's stated taste profile — favorite genre, favorite mood, and a target energy level. It's a content-based system: it only looks at the attributes of the songs themselves (genre, mood, energy, and in the OOP version, acousticness preference), not at what other users have listened to or liked.

It assumes the user can articulate their taste as a simple, single-valued profile (one favorite genre, one favorite mood, one energy target) — it does not support multiple genres, ranges of preference, or preferences that shift by context (e.g., "upbeat in the morning, chill at night").

This is a **classroom exploration project**, not a production recommender. It's meant to demonstrate and reason about how a basic content-based scoring system works, including where it breaks down — not to serve real listeners at scale.

**Non-intended use:** This system should not be used to make real purchasing or subscription decisions, deployed as an actual product feature, or treated as representative of how production recommenders (which use far more data and users) actually behave.

---

## 3. How the Model Works

Imagine every song has a short profile card: what genre it is, what mood it captures, and how energetic it feels on a scale from calm to intense. A listener fills out a similar card describing what they're in the mood for. The recommender compares the listener's card to every song's card and hands out points for each thing that matches:

- If a song's genre matches exactly what the listener asked for, it earns a big bonus.
- If the mood matches too, it earns a smaller bonus.
- Then, instead of just rewarding "high energy" or "low energy" outright, the system checks how *close* the song's energy is to what the listener wants — a listener who wants a mellow, low-energy song gets rewarded for finding mellow songs, not penalized for not being intense.

Once every song in the catalog has been given a score this way, the system sorts them from highest to lowest and hands back the top few, along with a plain-language list of exactly why each one scored the way it did (e.g., "genre match," "energy close to target").

**What changed from the starter logic:** The starter file had empty placeholder functions. I built out real scoring logic for both an object-oriented version (`Recommender` class, used by the test suite) and a simpler dictionary-based version (used by the command-line tool). Along the way, testing against real data revealed that a straightforward "reward high energy" formula wasn't good enough — it needed to reward *closeness* to a target, not just raw magnitude, so a listener wanting something calm wouldn't be unfairly penalized.

---

## 4. Data

The catalog contains **18 songs**, expanded from an original starter set of 10 using AI-assisted generation to diversify genre and mood coverage.

**Genres represented:** pop, lofi, rock, ambient, jazz, synthwave, indie pop, hip-hop, classical, folk, EDM, R&B, metal, country, reggae (15 genres across 18 songs — meaning most genres appear only once or twice).

**Moods represented:** happy, chill, intense, relaxed, moody, focused, nostalgic, melancholic, dreamy, triumphant, bittersweet, angry, peaceful, hopeful (14 distinct moods across 18 songs).

**What's missing:** With only 18 songs spread across 15 genres, most genres have just one representative song — there's no way to tell whether a listener likes "pop" in general or just happens to like that one specific pop song. The dataset also has no representation of tempo variation within a genre, no lyrical content or language data, and no way to represent a listener who enjoys a blend of styles rather than one dominant genre/mood.

---

## 5. Strengths

- For listeners with a clear, single dominant preference (e.g., "High-Energy Pop," "Chill Lofi," "Deep Intense Rock"), the system reliably surfaces a sensible top pick — in every standard test, the highest-scoring song was a genuine match on genre, mood, and energy simultaneously.
- The plain-language "reasons" output makes the system's logic fully transparent — a non-technical user can see exactly why a song was recommended, which is a meaningful strength over a black-box recommender.
- The energy-closeness formula correctly handles both ends of the spectrum — it rewards a "Chill Lofi" listener for low-energy matches just as well as it rewards a "High-Energy Pop" listener for high-energy matches, rather than assuming higher is always better.

---

## 6. Limitations and Bias

Stress-testing with adversarial profiles surfaced several real weaknesses:

- **Genre/mood strings fail silently when they don't exist in the data.** A profile asking for mood `"sad"` (which appears nowhere in the dataset) is silently ignored rather than flagged — the system still confidently returns results, but the "sad" preference contributed nothing to the ranking, and a listener wouldn't know their preference was effectively dropped.
- **The system can produce negative scores with no floor or validation.** Passing an out-of-range energy value (e.g., `2.0`, outside the intended 0.0–1.0 scale) causes the energy term to go negative for every song, and the reason string even renders a broken-looking double sign (e.g., `"energy close to target (+-0.1)"`). There is no input validation to catch this.
- **A profile with no genre or mood matches anywhere in the catalog degrades to pure energy-nearest-neighbor matching**, with every recommended song sharing the identical explanation string ("energy close to target") — the system gives no signal to the user that their stated genre/mood preferences matched nothing at all.
- **Genre acts as a flat, binary "cliff" worth more than any continuous signal.** Genre match is worth a full +2.0 with no partial credit, while energy similarity — even a near-perfect match — maxes out at +1.5. This means a song that's a near-identical fit on mood and energy can still lose decisively to a worse-fitting song purely because it carries the "right" genre label (confirmed directly: Gym Hero, an almost-perfect mood/energy match for a "Deep Intense Rock" listener, lost to Storm Runner by a 2.0-point margin — exactly the size of the genre bonus, even though the two songs were within 0.03 points of each other on mood + energy combined).
- **Genre has no concept of similarity between categories.** "Pop" vs. "rock" scores exactly the same zero as "pop" vs. "polka," even though pop and rock are much closer neighbors musically. A genre-adjacency or embedding-based approach would capture this; the current flat exact-match does not.
- **The energy-gap formula treats users at different points on the scale unequally.** Because energy scoring is a distance from the user's target, a user near the middle of the 0–1 range (~0.5) barely gets differentiated by energy at all — genre and mood end up deciding their results almost entirely. A user near either extreme (close to 0.0 or 1.0) instead gets results dominated by energy, drowning out genre and mood. Worse, the catalog itself has a real gap between energy 0.60 and 0.75 with almost no songs in that range, so a listener targeting that exact zone has no good matches available regardless of weighting — a data-coverage problem, not just a scoring one.
- **The scoring amplifies the dataset's own genre imbalance rather than compensating for it.** 13 of the catalog's 15 genres appear only once. A lofi or pop fan (2–3 songs) can receive a genre-coherent set of recommendations; a rock, jazz, classical, or country fan (1 song each) structurally cannot — at most one result can ever be a genre match, and the remaining slots are necessarily filled with genre-mismatched songs. No amount of reweighting fixes this, since it's a coverage problem inherited from the data, not something the scoring formula itself causes.
- **Some listener preferences are structurally impossible to satisfy, no matter how the weights are tuned.** Every acoustic song in the catalog (acousticness > 0.6) is also low-energy — there are zero high-energy acoustic songs. A listener who wants both loud/energetic *and* acoustic music is asking for a combination the catalog simply cannot produce. Separately, `tempo_bpm`, `valence`, and `danceability` are all loaded from the CSV but never actually scored in either the OOP or functional path — a listener who cares about danceability has no way to express that preference at all, even though the underlying data already exists in the catalog.
- With genre coverage this thin (15 genres across 18 songs), the system can't reliably distinguish "I like this genre" from "I like this one song" — a filter-bubble risk in miniature, since there's rarely more than one song to actually reinforce a genre preference.

---

## 7. Evaluation

I tested the recommender with three standard user profiles representing distinct, clear tastes — "High-Energy Pop," "Chill Lofi," and "Deep Intense Rock" — plus four adversarial profiles designed to probe for weaknesses: a profile with a genre/mood combination requesting a mood ("sad") that doesn't exist in the dataset, a "ghost" profile with a genre and mood that match nothing at all, a profile with an out-of-range energy value (2.0), and a profile isolating genre match against a strong competing mood+energy match.

**What I expected vs. what happened:**
- "High-Energy Pop" and "Chill Lofi" behaved exactly as expected — Sunrise City (pop, happy, high energy) topped the pop list, and Library Rain / Midnight Coding (both lofi, chill, low energy) topped the lofi list. This confirmed the core scoring logic works correctly for well-formed preferences.
- "Deep Intense Rock" correctly surfaced Storm Runner (rock, intense, high energy) as the top pick, but Gym Hero — a pop song — ranked second purely on mood + energy match, despite not being rock at all. This was a useful, mildly surprising result: it shows the system can recommend cross-genre songs when mood and energy align strongly, which could be a feature or a bug depending on intent.
- The **biggest surprise** was the "Overclocked" adversarial test: passing an energy value outside the valid 0–1 range didn't just produce inaccurate results, it produced literal negative scores and a broken-looking explanation string. I hadn't anticipated the system had zero input validation until I saw this in the actual terminal output.
- The "Ghost Profile" test was also revealing: I expected the system to somehow flag that nothing matched, but instead it confidently returned five results with identical, uninformative explanations — a clear example of a system that can't tell the difference between "I found your ideal match" and "I found nothing relevant and defaulted to energy similarity."

**Profile comparison notes:**
- *High-Energy Pop vs. Chill Lofi:* the Pop profile favors fast, upbeat, high-energy tracks (Sunrise City, Gym Hero), while the Lofi profile shifts entirely toward calm, low-tempo tracks (Library Rain, Midnight Coding) — makes sense, since these two profiles are near-opposites on the energy scale and the scoring correctly flips which songs come out on top.
- *Deep Intense Rock vs. Sad But Hyper:* both profiles requested high energy, but Deep Intense Rock correctly surfaced Storm Runner (genuine rock/intense match) at the top, while Sad But Hyper — which paired high energy with a nonexistent "sad" mood — surfaced Gym Hero (pop) instead, since there was no real mood signal to work with. This shows the mood field is doing real work when it matches something, and silently doing nothing when it doesn't.
- *Wrong Energy Right Genre vs. Deep Intense Rock:* asking for "classical" genre with "intense" mood and energy 1.0 did NOT push a classical song (Autumn Sonata, genuinely low-energy) to the top — instead, non-classical songs with a mood match won out, since Autumn Sonata's actual energy (0.20) was far from the requested 1.0 despite its genre match. In plain language: if a listener says "I want the *feeling* of classical music but at maximum intensity," the system doesn't know those two things conflict — it just does its best with mismatched signals and the result ends up being neither purely classical nor purely intense.

**Root-cause check on the Deep Intense Rock surprise:** I asked my AI coding assistant to walk through the exact arithmetic behind Gym Hero's score (2.46) versus Storm Runner's (4.48). The math confirmed both songs are nearly tied on mood (+1.0 each) and energy (1.455 vs. 1.485 — a gap of only 0.03), and the entire 2.0-point difference between them comes from the genre bonus alone. This confirmed the "genre as a flat cliff" issue is a real structural property of the weights, not a coincidence or a bug in the code — the arithmetic is doing exactly what the recipe specifies, but the recipe itself has a blind spot.

**Dataset-level bias check:** I also asked my AI coding assistant to analyze the scoring logic together with the actual song catalog (rather than one profile at a time) to look for systemic bias. This surfaced three findings not visible from individual stress tests alone: (1) users targeting moderate energy (~0.5) get results driven mostly by genre/mood, while users at energy extremes get results driven mostly by energy — the same weights behave very differently depending on where a listener sits on the scale; (2) because 13 of 15 genres in the catalog appear only once, fans of those niche genres can never receive more than one genre-matched recommendation, no matter how the weights are tuned — this is a data coverage problem the scoring formula inherits and cannot fix on its own; and (3) some preference combinations are simply impossible to satisfy — every acoustic song in the catalog is also low-energy, so a listener wanting both loud and acoustic music is asking for something that doesn't exist in the data.

In plain language for a non-programmer: the system is like a matchmaker who's very good at finding someone who checks the boxes you listed, but doesn't notice if the boxes you listed don't make sense together (like "I want someone very tall" and "I want someone under 5 feet"). It will still confidently set you up with someone — it just won't tell you your requirements didn't add up, or that its dating pool only had one person who matched your favorite hobby in the first place.

---

## Appendix: Raw Stress Test Output

### High-Energy Pop
```
Sunrise City - Score: 4.38
Because: genre match (+2.0), mood match (+1.0), energy close to target (+1.4)

Gym Hero - Score: 3.46
Because: genre match (+2.0), energy close to target (+1.5)

Rooftop Lights - Score: 2.29
Because: mood match (+1.0), energy close to target (+1.3)

Neon Uprising - Score: 1.50
Because: energy close to target (+1.5)

Storm Runner - Score: 1.48
Because: energy close to target (+1.5)
```

### Chill Lofi
```
Library Rain - Score: 4.42
Because: genre match (+2.0), mood match (+1.0), energy close to target (+1.4)

Midnight Coding - Score: 4.32
Because: genre match (+2.0), mood match (+1.0), energy close to target (+1.3)

Focus Flow - Score: 3.35
Because: genre match (+2.0), energy close to target (+1.3)

Spacewalk Thoughts - Score: 2.47
Because: mood match (+1.0), energy close to target (+1.5)

Dust Road Home - Score: 1.42
Because: energy close to target (+1.4)
```

### Deep Intense Rock
```
Storm Runner - Score: 4.48
Because: genre match (+2.0), mood match (+1.0), energy close to target (+1.5)

Gym Hero - Score: 2.46
Because: mood match (+1.0), energy close to target (+1.5)

Neon Uprising - Score: 1.50
Because: energy close to target (+1.5)

Iron Verdict - Score: 1.43
Because: energy close to target (+1.4)

Sunrise City - Score: 1.38
Because: energy close to target (+1.4)
```

### Adversarial: Sad But Hyper (genre=pop, mood=sad, energy=0.95)
```
Gym Hero - Score: 3.47
Because: genre match (+2.0), energy close to target (+1.5)

Sunrise City - Score: 3.30
Because: genre match (+2.0), energy close to target (+1.3)

Iron Verdict - Score: 1.50
Because: energy close to target (+1.5)

Storm Runner - Score: 1.44
Because: energy close to target (+1.4)

Neon Uprising - Score: 1.43
Because: energy close to target (+1.4)
```

### Adversarial: Ghost Profile (genre=polka, mood=euphoric, energy=0.5)
```
Golden Horizon - Score: 1.50
Because: energy close to target (+1.5)

Concrete Bloom - Score: 1.38
Because: energy close to target (+1.4)

Midnight Coding - Score: 1.38
Because: energy close to target (+1.4)

Focus Flow - Score: 1.35
Because: energy close to target (+1.4)

Velvet Static - Score: 1.35
Because: energy close to target (+1.4)
```

### Adversarial: Overclocked (genre=rock, mood=intense, energy=2.0)
```
Storm Runner - Score: 2.87
Because: genre match (+2.0), mood match (+1.0), energy close to target (+-0.1)

Gym Hero - Score: 0.90
Because: mood match (+1.0), energy close to target (+-0.1)

Iron Verdict - Score: -0.08
Because: energy close to target (+-0.1)

Neon Uprising - Score: -0.15
Because: energy close to target (+-0.2)

Sunrise City - Score: -0.27
Because: energy close to target (+-0.3)
```

### Adversarial: Wrong Energy Right Genre (genre=classical, mood=intense, energy=1.0)
```
Gym Hero - Score: 2.40
Because: mood match (+1.0), energy close to target (+1.4)

Storm Runner - Score: 2.37
Because: mood match (+1.0), energy close to target (+1.4)

Autumn Sonata - Score: 2.30
Because: genre match (+2.0), energy close to target (+0.3)

Iron Verdict - Score: 1.42
Because: energy close to target (+1.4)

Neon Uprising - Score: 1.35
Because: energy close to target (+1.4)
```

---

## Experiment: Weight Shift (Genre 2.0→1.0, Energy 1.5→3.0)

To test the system's sensitivity to its weighting scheme, I halved the genre match bonus (2.0 → 1.0) and doubled the maximum energy-similarity bonus (1.5 → 3.0), keeping mood match unchanged at 1.0. I implemented this as separate experimental functions (`score_song_experimental`, `recommend_songs_experimental`) so the original scoring remained untouched and comparable side by side.

**Result across all 7 test profiles:**
- In 5 of 7 profiles, the reweighting compressed score margins but did **not** change the top-5 ordering.
- In 2 profiles, the ordering actually changed:
  - **Chill Lofi:** Spacewalk Thoughts (ambient, exact mood match, closer energy) overtook Focus Flow (lofi, genre match, worse mood/energy fit) — the reweighting correctly favored the better overall fit over the genre label.
  - **Wrong Energy Right Genre:** Autumn Sonata (the only true classical song) dropped out of the top 5 entirely, since halving its genre bonus while doubling its energy penalty erased its one advantage.

**Conclusion: the reweighting made results different, not simply "more accurate."** It fixed the specific problem we set out to test — genre no longer completely buries a strong mood/energy match (e.g., Gym Hero's gap to Storm Runner shrank from 2.02 points to 1.06) — but it introduced a new tradeoff: a song that's genuinely the right genre can now lose out entirely if its other attributes are a poor match, even though genre correctness is arguably still meaningful to a real listener. Whether the original or experimental weighting is "better" depends on what a listener values more: strict genre fidelity, or overall vibe similarity regardless of genre label.

**One unrelated finding surfaced by this experiment:** the "Overclocked" adversarial profile (energy=2.0, outside the valid range) got measurably worse under the new weights — several songs' scores went further negative. This isn't a flaw in the reweighting itself; it's a pre-existing lack of input validation (energy is never clamped to [0.0, 1.0]) that the doubled multiplier simply made more visible. I've noted this as a limitation in Section 6 rather than silently patching it here, to keep the weight-shift experiment isolated and comparable.

---

## 8. Future Work

- Add input validation to clamp energy values to the 0.0–1.0 range and reject/flag genre or mood strings that don't exist anywhere in the dataset
- Add a diversity penalty so the top 5 recommendations aren't dominated by the same artist or overly similar songs
- Expand the dataset so each genre has multiple songs, making it possible to distinguish "likes this genre" from "likes this one song"
- Explore genre-adjacency or embedding-based similarity instead of exact-match, so related genres (pop/rock) score better than unrelated ones (pop/polka)
- Either score `tempo_bpm`, `valence`, and `danceability`, or remove them from the dataset entirely — right now they're loaded but silently unused, which misleads a reader into thinking they influence recommendations
- Add a "low confidence" flag when a user's top result scores below some minimum threshold, so the system can signal "the catalog doesn't have a good match for you" instead of confidently returning a weak result

---

## 9. Personal Reflection

My biggest learning moment was realizing that a scoring system can be completely
"correct" by its own math and still produce results that feel wrong — like when
Gym Hero nearly tied Storm Runner on mood and energy, but lost by exactly the size
of the genre bonus. The code wasn't broken; the recipe itself just had a blind spot
I hadn't noticed until I saw real numbers.

AI tools were genuinely useful for catching things I wouldn't have thought to test —
the adversarial profiles (a "sad but hyper" listener, an out-of-range energy value,
a genre/mood combination that doesn't exist anywhere in the data) all came from
asking my AI assistant to actively try to break my own logic, which is a different
mindset than just building forward. But I also learned to double-check its claims
rather than accept them outright — one early analysis claimed "genre always
dominates the ranking," and running the actual numbers showed that wasn't quite
true; a strong mood + energy match could still outrank a genre-only match in some
cases. The AI's instinct was directionally useful, but the specific claim needed
verification against real output before I trusted it.

What surprised me most is how much a simple weighted sum can *feel* like genuine
taste-matching, right up until you push on its edges. For clean, well-formed
preferences, the system feels almost intuitive. But it takes only a slightly
unusual request — a mood the dataset doesn't have, an energy value out of range,
a genre with only one song in the whole catalog — to reveal that there's no real
understanding underneath, just arithmetic on labels and numbers.

If I extended this project, I'd want to fix the two structural issues we found:
giving genre partial credit for related categories instead of a flat exact-match
cliff, and actually scoring the tempo/valence/danceability data that's currently
loaded but ignored. I'd also want to add a "low confidence" signal for cases like
the Ghost Profile, where the system currently returns five confident-looking
results even though none of them are a real match.

---

# Applied AI System: Reflection and Ethics

*This section reflects specifically on the new agentic critique feature added to the original recommender for the Applied AI System project.*

## What are the limitations or biases in your system?

The agent inherits every bias already documented above in the original recommender's Model Card (genre-inflation, thin genre coverage, no input validation, etc.) — since it critiques the recommender's actual output, any structural flaw in the underlying scores shows up in what it's asked to evaluate. Beyond that, the agent has its own limitations:

- **It's a critic, not a fixer.** The agent can flag that Gym Hero's score is "inflated by the genre match," but it never adjusts the actual recommendation or reorders results — a user still sees the same ranked list, just with an added opinion layered on top. This is a deliberate design choice (see Design Decisions in README), but it means the agent can identify a problem it has no ability to resolve.
- **Confidence labels are self-reported, not calibrated.** "High," "Medium," and "Low" are the model's own subjective assessment, not a statistically validated confidence score. A "High" confidence critique is not the same as a guarantee of correctness — it's the model's best judgment based on the data it was given.
- **Scoped testing, not exhaustive testing.** Only 3 of the original project's 7 test profiles were run through the agent (to limit API cost during development — see `AGENT_PROFILE_LIMIT`). The 4 adversarial edge-case profiles (conflicting preferences, out-of-range values, no-match scenarios) that were stress-tested against the *original* recommender were never run through the *agent* specifically, so we don't yet know how the agent's critique behaves on those harder edge cases.

## Could your AI be misused, and how would you prevent that?

The most realistic misuse risk isn't malicious — it's **over-trust**. Because the agent produces confident-sounding, well-written prose with a "confidence" label attached, a user could reasonably mistake a "High" confidence critique for a verified fact rather than one AI's best-effort read of the data. If this system were extended toward real listeners, presenting the critique without also showing the underlying score breakdown (which it currently always does, side-by-side) would risk letting the LLM's fluent language substitute for actual evidence.

A second, smaller risk: since the agent's prompt includes the full recommendation data (song attributes, scores, reasons), a modified version of this system that accepted user-supplied songs or profiles without validation could be used to probe what the model will say about arbitrary or adversarial inputs, similar to prompt-injection-style testing. This system currently only operates on a fixed, trusted internal dataset (`songs.csv`), which limits this risk in its current form — but it's worth naming as a consideration if the project were extended to accept external data sources.

**Mitigation already in place:** the critique is always shown *alongside* the original score/reasons breakdown, never replacing it — so a user (or a grader reviewing this project) can independently verify whether the agent's claim matches the underlying numbers, rather than taking the AI's word alone.

## What surprised you while testing your AI's reliability?

The biggest surprise was how *consistent* the agent's reasoning was across repeated runs and across different profiles targeting the same song. Gym Hero was independently flagged as "Medium" confidence in two separate test profiles ("High-Energy Pop" and "Deep Intense Rock"), and in both cases the critique text pointed to the exact same underlying cause: a genre match inflating the score while the mood didn't align. This wasn't something the agent was told in advance — it re-derived the same structural finding from scratch each time, purely from being shown the raw score/reason data. That consistency gave real evidence that the critique reflects genuine pattern-recognition over the data rather than random or superficial text generation.

A second surprise was how informative the *failure* mode testing turned out to be. When the account genuinely ran out of API credits mid-project, the resulting error (`BadRequestError... credit balance is too low`) was caught cleanly by the existing error handling and became, itself, a piece of real reliability evidence for this write-up — a case where an unplanned real-world failure ended up strengthening the project's guardrail documentation rather than derailing it.

## AI collaboration: one helpful suggestion, one flawed one

**Helpful:** When asked to design multiple ranking strategies for the original recommender without duplicating scoring logic (a stretch feature from the earlier project), the AI coding assistant proposed treating each "strategy" as a swappable weights configuration dictionary rather than a separate scoring function — recognizing that all the planned strategies (Genre-First, Mood-First, Energy-Focused) differed only in *how much* each factor was worth, not in *what* was being checked. This was a genuinely good design insight: it avoided code duplication, kept the original scoring behavior byte-for-byte unchanged as the default, and made adding new strategies trivial going forward.

**Flawed:** Earlier in the original project, when analyzing why one song (Gym Hero) outranked another despite a worse overall fit, an AI assistant asserted that "genre dominates the ranking regardless of how far off energy is." Running the actual numbers across a dedicated test case ("Wrong Energy Right Genre") showed this claim didn't fully hold up — a strong mood-plus-energy match could still outrank a genre-only match in some cases. The claim was directionally useful (genre *does* have outsized influence) but overstated as an absolute rule. This was a clear lesson in verifying an AI's specific claims against real, generated output rather than accepting a plausible-sounding generalization at face value — a practice this project's own architecture diagram now explicitly encodes as a "Human review" checkpoint in the pipeline.