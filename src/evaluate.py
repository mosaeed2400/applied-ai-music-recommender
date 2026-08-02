#!/usr/bin/env python3
"""
Deterministic evaluation harness for the rule-based recommender.

This formalizes the manual stress tests recorded in model_card.md's
"Appendix: Raw Stress Test Output" into automated pass/fail assertions. It
exercises ONLY recommend_songs() — the deterministic scoring logic — so it makes
no Claude API calls and costs nothing to run. The LLM critique/decision layer in
agent.py is intentionally out of scope here.

Run:
    python -m src.evaluate

Exit code is 0 if every test passes, 1 if any fails, so it can gate a CI job.
"""

import sys
from typing import Dict, List, Tuple

from .recommender import load_songs, recommend_songs

SONGS_CSV = "data/songs.csv"

# Each test case declares a `check` that selects how the actual top-5 output is
# asserted. Expected values are taken verbatim from model_card.md's Appendix, so
# this harness locks in behavior we've already manually verified.
#
#   check = "top_title"       -> the #1 ranked song's title must equal expected_top_title
#   check = "contains"        -> every title in expected_songs must appear in the top-5
#   check = "has_negative"    -> at least one top-5 song must have a negative score
#                                (out-of-range energy drives energy contribution negative)
TEST_CASES: List[Dict] = [
    # --- Standard profiles (expect a specific #1) --------------------------
    {
        "name": "High-Energy Pop matches genre/mood/energy -> Sunrise City #1",
        "user_prefs": {"genre": "pop", "mood": "happy", "energy": 0.9},
        "check": "top_title",
        "expected_top_title": "Sunrise City",
    },
    {
        "name": "Chill Lofi matches genre/mood/energy -> Library Rain #1",
        "user_prefs": {"genre": "lofi", "mood": "chill", "energy": 0.3},
        "check": "top_title",
        "expected_top_title": "Library Rain",
    },
    {
        "name": "Deep Intense Rock matches genre/mood/energy -> Storm Runner #1",
        "user_prefs": {"genre": "rock", "mood": "intense", "energy": 0.9},
        "check": "top_title",
        "expected_top_title": "Storm Runner",
    },
    # --- Adversarial: genre-right song still loses on poor energy fit -------
    {
        "name": "Wrong Energy Right Genre -> genre match (Gym Hero) beats the "
                "only classical song",
        "user_prefs": {"genre": "classical", "mood": "intense", "energy": 1.0},
        "check": "top_title",
        "expected_top_title": "Gym Hero",
    },
    # --- Adversarial: conflicting mood still lands on the genre+energy song -
    {
        # mood=sad has no match in the pop set, so Gym Hero wins on genre + a
        # near-perfect energy fit (0.93 vs 0.95) despite the mood conflict.
        "name": "Sad But Hyper (conflict) -> Gym Hero #1 on genre + energy",
        "user_prefs": {"genre": "pop", "mood": "sad", "energy": 0.95},
        "check": "top_title",
        "expected_top_title": "Gym Hero",
    },
    # --- Adversarial edge cases (non-top-title assertions) -----------------
    {
        # No song matches polka or euphoric, so the top result is carried by
        # energy proximity alone; Golden Horizon is the documented #1.
        "name": "Ghost Profile (no genre/mood matches) -> Golden Horizon surfaces "
                "on energy alone",
        "user_prefs": {"genre": "polka", "mood": "euphoric", "energy": 0.5},
        "check": "contains",
        "expected_songs": ["Golden Horizon"],
    },
    {
        # energy=2.0 is out of the valid [0,1] range and is never clamped, so the
        # energy term goes negative and pushes several songs' scores below zero.
        "name": "Overclocked (energy=2.0, out of range) -> out-of-range energy "
                "produces negative scores",
        "user_prefs": {"genre": "rock", "mood": "intense", "energy": 2.0},
        "check": "has_negative",
    },
]


def _check_case(
    case: Dict, results: List[Tuple[Dict, float, str]]
) -> Tuple[bool, str]:
    """Apply a test case's check to the recommend_songs output; return (passed, detail)."""
    check = case["check"]
    titles = [song["title"] for song, _, _ in results]

    if check == "top_title":
        top_song, top_score, _ = results[0]
        expected = case["expected_top_title"]
        passed = top_song["title"] == expected
        detail = f"top = {top_song['title']!r} ({top_score:.2f}), expected {expected!r}"
        return passed, detail

    if check == "contains":
        expected_songs = case["expected_songs"]
        missing = [t for t in expected_songs if t not in titles]
        passed = not missing
        detail = (
            f"top-5 = {titles}; all of {expected_songs} present"
            if passed
            else f"missing {missing} from top-5 {titles}"
        )
        return passed, detail

    if check == "has_negative":
        negatives = [(s["title"], score) for s, score, _ in results if score < 0]
        passed = bool(negatives)
        detail = (
            f"negative-scoring songs present: {negatives}"
            if passed
            else f"expected at least one negative score, got {[(s['title'], round(sc, 2)) for s, sc, _ in results]}"
        )
        return passed, detail

    return False, f"unknown check type {check!r}"


def main() -> int:
    songs = load_songs(SONGS_CSV)
    print(f"Loaded {len(songs)} songs from {SONGS_CSV}")
    print(f"Running {len(TEST_CASES)} deterministic recommender tests (no API calls)\n")

    passed_count = 0
    for case in TEST_CASES:
        results = recommend_songs(case["user_prefs"], songs, k=5)
        passed, detail = _check_case(case, results)
        status = "PASS" if passed else "FAIL"
        if passed:
            passed_count += 1
        print(f"[{status}] {case['name']}")
        print(f"        {detail}")

    total = len(TEST_CASES)
    print(f"\n{passed_count}/{total} tests passed")
    return 0 if passed_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
