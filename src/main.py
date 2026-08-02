"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

from .recommender import (
    load_songs,
    recommend_songs,
    recommend_songs_diverse,
    STRATEGIES,
)
from .agent import (
    critique_recommendations,
    decide_on_recommendations,
    log_agent_run,
    log_reasoning_trace,
)

try:
    from tabulate import tabulate
except ImportError:  # tabulate not installed yet
    tabulate = None

# Pick a ranking mode here. Options: "Balanced", "Genre-First", "Mood-First",
# "Energy-Focused" (see STRATEGIES in recommender.py).
STRATEGY = "Balanced"

# When True, penalize repeated artists/genres in the top-k (recommend_songs_diverse).
DIVERSITY_MODE = False

# When True, ask the LLM agent (src/agent.py) to critique the recommendations
# and assign a confidence label. Each critiqued profile makes one real API call.
AGENT_MODE = True

# The agent makes a real (paid) API call per profile, so by default we only
# critique the first AGENT_PROFILE_LIMIT profiles to avoid burning credits across
# all 7 profiles every run. Set AGENT_PROFILE_LIMIT to a large number (or
# len(profiles)) to critique every profile.
AGENT_PROFILE_LIMIT = 1


def main() -> None:
    songs = load_songs("data/songs.csv")
    print(f"Loaded songs: {len(songs)}")
    print(f"Ranking strategy: {STRATEGY}  (options: {', '.join(STRATEGIES)})")
    print(f"Diversity mode: {DIVERSITY_MODE}")

    high_energy_pop = {"genre": "pop", "mood": "happy", "energy": 0.9}
    chill_lofi = {"genre": "lofi", "mood": "chill", "energy": 0.3}
    deep_intense_rock = {"genre": "rock", "mood": "intense", "energy": 0.9}

    sad_but_hyper = {"genre": "pop", "mood": "sad", "energy": 0.95}
    ghost_profile = {"genre": "polka", "mood": "euphoric", "energy": 0.5}
    overclocked = {"genre": "rock", "mood": "intense", "energy": 2.0}
    wrong_energy_right_genre = {"genre": "classical", "mood": "intense", "energy": 1.0}

    profiles = [
        ("High-Energy Pop", high_energy_pop),
        ("Chill Lofi", chill_lofi),
        ("Deep Intense Rock", deep_intense_rock),
        ("Sad But Hyper (conflict)", sad_but_hyper),
        ("Ghost Profile (no matches)", ghost_profile),
        ("Overclocked (energy=2.0)", overclocked),
        ("Wrong Energy Right Genre", wrong_energy_right_genre),
    ]

    if tabulate is None:
        print(
            "\nNote: the 'tabulate' package is not installed — falling back to plain text.\n"
            "Install it with:  pip install tabulate\n"
        )

    # Collected during the loop and logged once per profile after all profiles
    # have been processed (see log_agent_run calls below).
    agent_runs = []

    for index, (name, user_prefs) in enumerate(profiles):
        print(f"\n=== {name} ===\n")
        if DIVERSITY_MODE:
            recommendations = recommend_songs_diverse(user_prefs, songs, k=5, strategy=STRATEGY)
        else:
            recommendations = recommend_songs(user_prefs, songs, k=5, strategy=STRATEGY)

        rows = [
            (rank, song["title"], f"{score:.2f}", explanation)
            for rank, (song, score, explanation) in enumerate(recommendations, start=1)
        ]
        headers = ["Rank", "Title", "Score", "Reasons"]

        if tabulate is not None:
            print(tabulate(rows, headers=headers, tablefmt="github"))
        else:
            # Plain-text fallback when tabulate isn't available.
            for rank, title, score, explanation in rows:
                print(f"{rank}. {title} - Score: {score}")
                print(f"   Because: {explanation}")
        print()

        # Only critique the first AGENT_PROFILE_LIMIT profiles by default, so a
        # full run doesn't make 7 paid API calls (see the constant above).
        if AGENT_MODE and index < AGENT_PROFILE_LIMIT:
            # Step 1: critique each recommendation and assign a confidence label.
            critiques = critique_recommendations(user_prefs, recommendations)
            # Step 2: a separate, chained call that decides an action per song,
            # reasoning from the step-1 critiques.
            decisions = decide_on_recommendations(user_prefs, recommendations, critiques)

            print("--- Agent critique + decision ---")
            for critique, decision in zip(critiques, decisions):
                print(f"[{critique['confidence']}] {critique['title']}")
                print(f"   critique: {critique['critique_text']}")
                action = decision["action"]
                if action == "suggest_alternative" and decision["suggested_alternative"]:
                    action = f"suggest_alternative -> {decision['suggested_alternative']}"
                print(f"   decision: {action}")
                print(f"   reasoning: {decision['reasoning']}")
            print()

            agent_runs.append((user_prefs, critiques, decisions))

    # Persist per critiqued profile after the run: the confidence log, plus the
    # full multi-step reasoning trace (critique + decision, raw).
    for user_prefs, critiques, decisions in agent_runs:
        log_agent_run(user_prefs, critiques)
        log_reasoning_trace(user_prefs, critiques, decisions)


if __name__ == "__main__":
    main()
