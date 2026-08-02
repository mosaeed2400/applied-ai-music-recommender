# 🎵 Applied AI Music Recommender

## Original Project

This project extends **Music Recommender Simulation**, a content-based song recommender built in an earlier module. That original project scored songs against a user's stated taste profile (genre, mood, energy) using a weighted point system, returning ranked recommendations with plain-language explanations for each score. Testing that original system surfaced a real bias: genre matches (worth a flat +2.0 points) could outrank songs that were actually a stronger overall fit, since genre acted as a binary bonus rather than a graded signal. Full details on the original system's design, scoring recipe, and four optional extensions are preserved below under "Original Project Details."

## What's New: An Agentic Critique Layer

This version adds a genuine AI agent on top of the existing recommender. After the recommender produces its usual ranked list, a new agent (`src/agent.py`) sends the user's preferences and all recommendations to Claude, which independently critiques each recommendation — flagging whether a high score is a genuinely strong match or is being inflated by a single factor — and assigns a High/Medium/Low confidence label. This is a real **Agentic Workflow**: the agent plans what to evaluate, acts by calling the LLM, checks the recommender's own work, and logs the results.

Notably, when tested, the agent independently rediscovered the exact genre-inflation bias already documented in this project's `model_card.md` — without being told about it in advance. That's a meaningful signal that the critique is grounded in real reasoning about the data, not just restating the recommender's own explanation strings.

## Architecture Overview

See [`diagrams/architecture.mmd`](diagrams/architecture.mmd) for the full Mermaid source.

The flow: a user profile enters the CLI (`main.py`) → `load_songs` reads the catalog → `recommend_songs` scores and ranks every song → the top results are handed to `agent.py`'s `critique_recommendations`, which builds a prompt describing the user's preferences and all recommendations, sends it to Claude, and parses back a confidence label and critique per song → results print to the terminal and are logged as structured JSON via `log_agent_run`. A human review checkpoint and the existing `pytest` suite both independently verify the system's behavior — the diagram shows exactly where each of these fits into the pipeline.

## Setup Instructions

1. Clone this repo and enter the folder:
```bash
   git clone https://github.com/mosaeed2400/applied-ai-music-recommender.git
   cd applied-ai-music-recommender
```

2. Create and activate a virtual environment:
```bash
   python3 -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows
```

3. Install dependencies (includes `tabulate`, `anthropic`, `python-dotenv`):
```bash
   pip install -r requirements.txt
```

4. **Set up your Anthropic API key** (required for the agent feature):
   - Get a key from [console.anthropic.com](https://console.anthropic.com) → API keys
   - Create a `.env` file in the project root containing:
```
     ANTHROPIC_API_KEY=sk-ant-your-key-here
```
   - This file is git-ignored and never committed

5. Run the app:
```bash
   python3 -m src.main
```

By default, `AGENT_MODE = True` and `AGENT_PROFILE_LIMIT = 1` in `main.py`, meaning only the first user profile is sent to the agent (to limit API usage during testing). To critique every profile, increase `AGENT_PROFILE_LIMIT` or set it to `len(profiles)`. To try the original project's optional extensions, edit the `STRATEGY` and `DIVERSITY_MODE` constants near the top of `src/main.py`.

## Sample Interactions

### Example 1: Standard recommendation + agent critique

Input profile: `{"genre": "pop", "mood": "happy", "energy": 0.9}`

```
=== High-Energy Pop ===

|   Rank | Title          |   Score | Reasons                                                              |
|--------|----------------|---------|----------------------------------------------------------------------|
|      1 | Sunrise City   |    4.38 | genre match (+2.0), mood match (+1.0), energy close to target (+1.4) |
|      2 | Gym Hero       |    3.46 | genre match (+2.0), energy close to target (+1.5)                    |
|      3 | Rooftop Lights |    2.29 | mood match (+1.0), energy close to target (+1.3)                     |

--- Agent critique ---
[High] Sunrise City
   This is a genuinely strong match across all dimensions. It matches the genre
   (pop) and mood (happy) perfectly, and the energy level of 0.82 is reasonably
   close to the target of 0.9, making this a well-rounded recommendation.
[Medium] Gym Hero
   While this song matches the genre and has nearly perfect energy (0.93 vs 0.9
   target), the mood is 'intense' rather than 'happy', which is a significant
   mismatch. The score is inflated by the genre match, but the mood discrepancy
   means this may not satisfy the listener's emotional preferences.
```

### Example 2: Agent correctly flags a weak recommendation

Same profile, continued:

```
[Low] Storm Runner
   This song only matches the energy preference and misses on both genre (rock
   vs pop) and mood (intense vs happy). With a score carried entirely by energy
   proximity, this is a poor fit for someone specifically seeking happy pop music.
```

### Example 3: Graceful failure handling (guardrail demonstration)

Tested with a deliberately invalid API key and, separately, with an account at $0 credit balance:

```
[Unavailable] Sunrise City
   Agent unavailable: BadRequestError: Error code: 400 - {'type': 'error',
   'error': {'type': 'invalid_request_error', 'message': 'Your credit balance
   is too low to access the Anthropic API...'}}
```

In both failure cases, the program did not crash — it printed a clear
`[Unavailable]` label per song and continued processing the remaining profiles
normally.

## Design Decisions and Trade-offs

- **Agent scoped to one profile by default** — critiquing all 7 test profiles on every run would multiply API cost and latency unnecessarily during development; `AGENT_PROFILE_LIMIT` makes this an explicit, documented choice rather than a hidden constraint.
- **JSON prompting instead of structured outputs** — the model used isn't guaranteed to support strict structured-output formatting, so the agent prompts for JSON and parses it defensively (tolerating markdown code fences), trading a small amount of parsing robustness work for model flexibility.
- **Graceful degradation over hard failure** — since this feature depends on an external, billed API, the system was explicitly designed to keep working (with a visible "Unavailable" state) rather than crash if the API call fails for any reason. This was verified with two real failure modes, not just simulated.
- **Original scoring logic left untouched** — the agent is a read-only critique layer; it doesn't alter the recommender's actual scores or rankings, preserving the original project's tested and documented behavior.

## Testing Summary

- The original project's `pytest` suite (2 tests covering the `Recommender` class) still passes unmodified — the new agent doesn't touch that code path.
- The agent's error-handling path was tested twice with real conditions: an invalid API key (401 authentication error) and a genuine $0 credit balance (400 billing error) — both correctly triggered the graceful fallback rather than crashing.
- The agent was also verified with a real, successful API call, producing critiques that independently corroborated a bias already documented in `model_card.md` (see "What's New" above) — a meaningful cross-check that the critique reflects genuine reasoning about the data.
- Full reliability findings, biases, and reflection are documented in [`model_card.md`](model_card.md).

## Reflection

A detailed reflection on this project's responsible-AI considerations — limitations, potential misuse, testing surprises, and specific examples of helpful and flawed AI collaboration — is documented in [`model_card.md`](model_card.md), as required.

---
---

# Original Project Details

*The sections below document the original Music Recommender Simulation project this Applied AI System builds on.*

## Project Summary

This project is a simplified simulation of how music platforms like Spotify or YouTube predict what you'll want to hear next. My version is a content-based recommender: it doesn't know anything about other users, only about the songs themselves. It represents each song as a set of numeric and categorical attributes (genre, mood, energy, valence, acousticness), compares those attributes against a user's stated taste profile, and calculates a weighted score for every song in the catalog. The highest-scoring songs are returned as recommendations, along with a plain-language breakdown of why each one was picked.

## How The System Works

Real-world recommendation systems generally rely on two approaches. **Collaborative filtering** predicts what a user will like based on patterns across many other users (e.g., "people who liked what you liked also liked this"). **Content-based filtering** predicts recommendations purely from a song's own attributes — genre, tempo, mood, energy — compared against what a specific user tends to enjoy. Big platforms like Spotify blend both approaches, but since this project only has a static catalog and one user profile (no cross-user data), it implements a pure content-based recommender.

**Features used by `Song`:**
- `genre` — categorical (e.g., pop, lofi, rock)
- `mood` — categorical (e.g., happy, chill, intense)
- `energy` — numeric, 0.0–1.0 scale
- `valence` — numeric, 0.0–1.0 scale (a "positivity" measure independent of energy)
- `acousticness` — numeric, 0.0–1.0 scale

I initially considered dropping `acousticness` since it was almost perfectly inversely correlated with `energy` in this dataset (energy + acousticness ≈ 1.0 for every song). I planned to use `valence` as a bonus signal instead, since it catches distinctions `mood` alone misses — for example, two songs both tagged "intense" can have very different valence scores (one aggressive/dark, one upbeat/motivating).

However, during implementation I discovered `tests/test_recommender.py` requires a specific `UserProfile` shape with a `likes_acoustic: bool` field rather than `target_valence`. Rather than break the required tests, I adapted my recipe: the graded `Recommender` class uses `likes_acoustic` as a simple boolean preference (do you want acoustic songs or not) instead of a numeric valence target. This is a good example of a real constraint — a recommender's scoring logic has to work within whatever data contract the rest of the system (or its tests) expects, even if a different design was originally planned.

**Two parallel implementations exist in this project:**
1. **OOP path** (`Song`, `UserProfile`, `Recommender` class) — required by the test suite
2. **Functional path** (`load_songs`, `score_song`, `recommend_songs`) — used by the CLI in `main.py`, working on plain dictionaries

**Information stored in `UserProfile` (OOP path):**
- `favorite_genre`
- `favorite_mood`
- `target_energy`
- `likes_acoustic` (boolean)

**How the `Recommender` class computes a score:**
- **+2.0** if `genre` exactly matches `favorite_genre`
- **+1.0** if `mood` exactly matches `favorite_mood`
- **Up to +1.5** based on energy similarity: `(1 - abs(song.energy - target_energy)) * 1.5`
- **+1.0** if `likes_acoustic` is `True` and the song's `acousticness > 0.6`
- **+0.5** if `likes_acoustic` is `False` and the song's `acousticness < 0.4`

**How the functional `score_song`/`recommend_songs` compute a score (used by the CLI):**
- **+2.0** if `genre` matches
- **+1.0** if `mood` matches
- **Up to +1.5** based on energy similarity, same closeness formula as above

Both paths return a numeric score plus a list of plain-language reasons (e.g., `"genre match (+2.0)"`, `"energy close to target (+1.4)"`) so a user can see *why* a song was recommended, not just that it was.

**How recommendations are chosen:**
Each implementation runs its scoring function across every song in the catalog — this is necessary because a single song's score is meaningless in isolation; it only matters relative to every other song's score. Once every song has been scored, the list is sorted from highest to lowest (using `.sort()`, since the scored list is temporary and local to the function — no need to preserve the original order or allocate a second list), and the top `k` results are returned as the final recommendations.

**Example User Profile (functional/CLI path):**
```python
user_prefs = {"genre": "pop", "mood": "happy", "energy": 0.8}
```

**Example User Profile (OOP/tested path):**
```python
user = UserProfile(
    favorite_genre="pop",
    favorite_mood="happy",
    target_energy=0.8,
    likes_acoustic=False,
)
```

**Finalized Algorithm Recipe:**

| Feature | Rule | Max points |
|---|---|---|
| `genre` | exact match | +2.0 |
| `mood` | exact match | +1.0 |
| `energy` | `(1 - abs(song.energy - target_energy)) * 1.5` | up to +1.5 |
| `acousticness` (OOP path only) | bonus/penalty based on `likes_acoustic` | +1.0 or +0.5 |

Max possible score (OOP path): 5.5 points
Max possible score (functional/CLI path): 4.5 points

**Expected bias:** Because genre and mood are exact-match categorical checks worth significant flat points, this system may over-prioritize genre matches even when a song's actual energy profile is a poor fit — for example, any "pop" song scores +2.0 regardless of how different its energy actually is from the user's target. This bias was confirmed during Phase 4 testing — see `model_card.md` for the full analysis.

## Optional Extensions (from the original project)

Beyond the core original project, four optional extensions were implemented:

1. **Advanced Song Features** — added `popularity`, `release_decade`, `explicit`, `vocal_type`, and `detailed_mood_tags` to the dataset, with an optional popularity-similarity scoring bonus.
2. **Multiple Scoring Modes** — a Strategy pattern (`STRATEGY` constant in `main.py`) lets you switch between Balanced, Genre-First, Mood-First, and Energy-Focused ranking, all sharing one scoring function via configurable weights.
3. **Diversity and Fairness Logic** — a `DIVERSITY_MODE` toggle in `main.py` penalizes repeated artists/genres in the top-k results, directly addressing the genre-imbalance bias documented in `model_card.md`.
4. **Visual Summary Table** — CLI output renders as a formatted table (via `tabulate`) when the package is installed, with a graceful plain-text fallback if it isn't.

Full prompts, agent-generated changes, and manual verification notes for all four are documented in [`ai_interactions.md`](ai_interactions.md).

## Original Sample Recommendation Output

*Note: this output reflects the original core project's default behavior (before both the Visual Summary Table extension and the new Agentic Critique Layer were added).*

```
Loaded songs: 18

Top recommendations:

Sunrise City - Score: 4.47
Because: genre match (+2.0), mood match (+1.0), energy close to target (+1.5)

Gym Hero - Score: 3.30
Because: genre match (+2.0), energy close to target (+1.3)

Rooftop Lights - Score: 2.44
Because: mood match (+1.0), energy close to target (+1.4)

Night Drive Loop - Score: 1.42
Because: energy close to target (+1.4)

Neon Uprising - Score: 1.35
Because: energy close to target (+1.4)
```

## Original Experiments

I tested the system with 3 standard profiles ("High-Energy Pop," "Chill Lofi," "Deep Intense Rock") plus 4 adversarial edge-case profiles designed to probe for weaknesses (a nonexistent mood, a genre/mood combo matching nothing in the catalog, an out-of-range energy value, and a genre-vs-fit conflict test). Full terminal output for all 7 profiles is documented in `model_card.md`'s Appendix.

**Weight Shift experiment:** I halved the genre weight (2.0 → 1.0) and doubled the energy weight (1.5 → 3.0) to test sensitivity. Across all 7 profiles, this compressed score margins everywhere and actually changed the top-5 ranking order in 2 of them. The clearest effect: Gym Hero (a strong mood/energy match but wrong genre) closed its score gap to Storm Runner from 2.02 points down to 1.06 — confirming that genre's flat +2.0 bonus was suppressing otherwise-strong matches. The tradeoff: Autumn Sonata, the catalog's only classical song, dropped out of the top 5 entirely once its genre bonus was halved, since its energy fit was poor. **Conclusion:** the reweighting made results different, not simply more accurate — it's a real tradeoff between genre fidelity and overall vibe similarity. Full before/after data is in `model_card.md`.

**On genre coverage:** since 13 of the catalog's 15 genres appear in only one song, fans of underrepresented genres (rock, jazz, classical, country, etc.) can never get more than one true genre match in their top 5, regardless of any weight change — this is a data limitation, not a tuning problem.

## Original Limitations and Risks

- **The catalog is very small (18 songs) and genre coverage is thin** — 13 of 15 genres appear in only one song, so the system can't distinguish "likes this genre" from "likes this one song," and niche-genre fans structurally cannot receive a fully genre-coherent top 5.
- **Genre acts as a flat, binary bonus with no partial credit and no concept of similarity** — "pop" vs. "rock" scores identically to "pop" vs. "polka," even though some genres are much closer neighbors than others. This can let a poor overall fit beat a near-perfect mood/energy match, purely on a categorical label (confirmed directly: see the Gym Hero vs. Storm Runner case in `model_card.md`).
- **There is no input validation.** An out-of-range energy value (e.g., 2.0) produces literal negative scores and a broken-looking explanation string (e.g., `"energy close to target (+-0.1)"`) instead of being rejected or clamped.
- **Genre/mood values not present in the dataset fail silently** rather than raising an error or warning — the system confidently returns results even when a stated preference matched nothing at all.
- **Some preference combinations are impossible to satisfy no matter how the weights are tuned** — e.g., every acoustic song in the catalog is also low-energy, so a "loud and acoustic" listener is asking for something the data cannot provide.
- **`tempo_bpm`, `valence`, and `danceability` are loaded from the CSV but never actually used in scoring**, in either the OOP or functional path — a listener who cares about danceability has no way to express that preference, even though the data already exists.
- It has no understanding of lyrics, language, or subjective quality — only numeric and categorical attributes.
- With no other users' behavior to draw from, the system can't discover songs outside a user's stated preferences — it has no serendipity, unlike collaborative filtering.
- The project has two parallel scoring implementations (OOP and functional) that use slightly different recipes (the functional/CLI path doesn't use acousticness at all), which could confuse a future maintainer if not kept in sync.

The full bias analysis, including a dataset-level check for systemic issues, is documented in `model_card.md`, Section 6.

## Running Tests

Run the original project's tests with:

```bash
pytest
```

You can add more tests in `tests/test_recommender.py`.