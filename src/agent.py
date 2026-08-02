"""
LLM critique agent for the Music Recommender Simulation.

The rule-based recommender in recommender.py produces a ranked top-k with a
transparent, additive score. That score can be *inflated by one factor* — a
genre match adds a flat +2.0 even when mood and energy are a poor fit. This
module asks Claude to act as a second opinion: it critiques each recommendation,
flags scores that don't hold up, and attaches a confidence label.

Usage:
    from src.recommender import load_songs, recommend_songs
    from src.agent import critique_recommendations, log_agent_run

    songs = load_songs("data/songs.csv")
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.9}
    recs = recommend_songs(prefs, songs, k=5)
    critiques = critique_recommendations(prefs, recs)
    log_agent_run(prefs, critiques)
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from dotenv import load_dotenv
import anthropic

# Load ANTHROPIC_API_KEY (and anything else) from .env into the environment.
# anthropic.Anthropic() then picks the key up automatically.
load_dotenv()

# The user explicitly requested Sonnet 4.5; it's an active model on the API.
MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 1000
VALID_CONFIDENCE = {"High", "Medium", "Low"}
VALID_ACTIONS = {"keep", "flag_for_review", "suggest_alternative"}


def _build_prompt(user_prefs: Dict, recommendations: List[Tuple[Dict, float, str]]) -> str:
    """
    Render the user's stated preferences and all recommendations (with scores and
    the rule-based reasons) into a single prompt asking Claude to critique each one.
    """
    prefs_lines = [f"- {key}: {value}" for key, value in user_prefs.items()]
    prefs_block = "\n".join(prefs_lines)

    rec_blocks = []
    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        rec_blocks.append(
            f"{rank}. \"{song['title']}\" by {song.get('artist', 'unknown')}\n"
            f"   - score: {score:.2f}\n"
            f"   - genre: {song.get('genre')}, mood: {song.get('mood')}, "
            f"energy: {song.get('energy')}, acousticness: {song.get('acousticness')}\n"
            f"   - why the recommender scored it this way: {explanation}"
        )
    rec_block = "\n\n".join(rec_blocks)

    return (
        "You are reviewing the output of a simple rule-based music recommender. "
        "The recommender scores each song by adding fixed points for a genre match, "
        "a mood match, closeness to a target energy, and (optionally) popularity. "
        "Because the points are additive, a single strong factor (e.g. genre) can "
        "inflate the score even when the other attributes are a poor fit for the "
        "listener.\n\n"
        "The listener's stated preferences are:\n"
        f"{prefs_block}\n\n"
        "Here are the recommendations to critique:\n\n"
        f"{rec_block}\n\n"
        "For EACH recommendation, decide whether it is a genuinely strong match or "
        "whether something doesn't add up (for example, the score is carried almost "
        "entirely by the genre match while the mood or energy is a poor fit). Then "
        "assign a confidence label of exactly \"High\", \"Medium\", or \"Low\" "
        "reflecting how well the song matches the listener's actual preferences.\n\n"
        "Respond with ONLY a JSON object of the form:\n"
        '{\n'
        '  "critiques": [\n'
        '    {"title": "<song title>", "confidence": "High|Medium|Low", '
        '"critique_text": "<one to three sentences>"}\n'
        '  ]\n'
        '}\n'
        "Include one entry per recommendation, in the same order. Do not include any "
        "text outside the JSON object."
    )


def _extract_json(text: str) -> Dict:
    """
    Parse the model's response into a dict, tolerating markdown code fences that
    some responses wrap the JSON in.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Strip a leading ```json / ``` fence and the trailing ``` fence.
        lines = cleaned.splitlines()
        lines = lines[1:] if lines and lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


def _fallback(recommendations: List[Tuple[Dict, float, str]], reason: str) -> List[Dict]:
    """
    Build a per-song fallback response used when the agent is unavailable, so the
    caller always receives one dict per recommendation with the expected keys.
    """
    return [
        {
            "title": song.get("title", "unknown"),
            "confidence": "Unavailable",
            "critique_text": f"Agent unavailable: {reason}",
        }
        for song, _, _ in recommendations
    ]


def critique_recommendations(
    user_prefs: Dict, recommendations: List[Tuple[Dict, float, str]]
) -> List[Dict]:
    """
    Ask Claude to critique each recommendation and assign a confidence label.

    Args:
        user_prefs: the listener's preference dict (genre, mood, energy, ...).
        recommendations: the (song_dict, score, explanation) tuples from
            recommend_songs().

    Returns:
        A list of dicts, one per song, each with:
          - title: the song title
          - confidence: "High" | "Medium" | "Low" (or "Unavailable" on failure)
          - critique_text: Claude's critique of the recommendation

    On any API/parse failure this returns a fallback response instead of raising,
    so a caller iterating a batch of profiles never crashes on one bad call.
    """
    if not recommendations:
        return []

    prompt = _build_prompt(user_prefs, recommendations)

    try:
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next((block.text for block in response.content if block.type == "text"), "")
        data = _extract_json(text)
        critiques = data["critiques"]
    except anthropic.APIError as exc:
        # Auth, rate limit, network, overloaded, bad request — surface gracefully.
        return _fallback(recommendations, f"{type(exc).__name__}: {exc}")
    except (KeyError, ValueError, TypeError) as exc:
        # Response wasn't the JSON shape we asked for.
        return _fallback(recommendations, f"could not parse response ({exc})")
    except Exception as exc:  # noqa: BLE001 - never let the agent crash the caller
        return _fallback(recommendations, f"unexpected error ({exc})")

    # Normalize into exactly one clean dict per recommendation, matched by order.
    results: List[Dict] = []
    for (song, _, _), raw in zip(recommendations, critiques):
        confidence = str(raw.get("confidence", "")).strip().capitalize()
        if confidence not in VALID_CONFIDENCE:
            confidence = "Medium"
        results.append(
            {
                "title": song.get("title", raw.get("title", "unknown")),
                "confidence": confidence,
                "critique_text": str(raw.get("critique_text", "")).strip(),
            }
        )

    # If the model returned fewer entries than songs, pad so the caller still gets
    # one dict per recommendation.
    for song, _, _ in recommendations[len(results):]:
        results.append(
            {
                "title": song.get("title", "unknown"),
                "confidence": "Unavailable",
                "critique_text": "Agent unavailable: no critique returned for this song.",
            }
        )

    return results


def _build_decision_prompt(
    user_prefs: Dict,
    recommendations: List[Tuple[Dict, float, str]],
    critiques: List[Dict],
) -> str:
    """
    Render the second-step prompt: the listener's preferences, each recommendation,
    and the critique already produced for it, then ask for a per-song action.
    """
    prefs_block = "\n".join(f"- {key}: {value}" for key, value in user_prefs.items())

    titles = [song["title"] for song, _, _ in recommendations]
    titles_block = ", ".join(f'"{t}"' for t in titles)

    # Align each recommendation with its critique by order (both come from the same
    # top-k list, in the same order).
    blocks = []
    for rank, ((song, score, explanation), critique) in enumerate(
        zip(recommendations, critiques), start=1
    ):
        blocks.append(
            f"{rank}. \"{song['title']}\" by {song.get('artist', 'unknown')}\n"
            f"   - score: {score:.2f}\n"
            f"   - genre: {song.get('genre')}, mood: {song.get('mood')}, "
            f"energy: {song.get('energy')}\n"
            f"   - recommender reasons: {explanation}\n"
            f"   - critique confidence: {critique.get('confidence')}\n"
            f"   - critique: {critique.get('critique_text')}"
        )
    rec_block = "\n\n".join(blocks)

    return (
        "You are the second step in a two-step review of a music recommender. In the "
        "first step, each recommendation was critiqued and given a confidence label "
        "(High/Medium/Low). Your job now is to DECIDE what to do with each "
        "recommendation, based on that critique.\n\n"
        "The listener's stated preferences are:\n"
        f"{prefs_block}\n\n"
        "The recommendations, each with its first-step critique:\n\n"
        f"{rec_block}\n\n"
        "For EACH recommendation, choose exactly one action:\n"
        '  - "keep": the recommendation is solid; leave it in the list.\n'
        '  - "flag_for_review": the recommendation is questionable and a human '
        "should double-check it.\n"
        '  - "suggest_alternative": another song in the list above would likely be a '
        "better fit; name it.\n\n"
        "When you choose \"suggest_alternative\", the suggested song MUST be one of "
        f"these exact titles: {titles_block}. Otherwise set the alternative to null.\n\n"
        "Respond with ONLY a JSON object of the form:\n"
        '{\n'
        '  "decisions": [\n'
        '    {"title": "<song title>", "action": "keep|flag_for_review|suggest_alternative", '
        '"suggested_alternative": "<title or null>", "reasoning": "<one to two sentences>"}\n'
        '  ]\n'
        '}\n'
        "Include one entry per recommendation, in the same order. Do not include any "
        "text outside the JSON object."
    )


def _decision_fallback(
    recommendations: List[Tuple[Dict, float, str]], reason: str
) -> List[Dict]:
    """
    Per-song fallback used when the decision step is unavailable, so the caller
    always receives one dict per recommendation with the expected keys.
    """
    return [
        {
            "title": song.get("title", "unknown"),
            "action": "unavailable",
            "suggested_alternative": None,
            "reasoning": f"Agent unavailable: {reason}",
        }
        for song, _, _ in recommendations
    ]


def decide_on_recommendations(
    user_prefs: Dict,
    recommendations: List[Tuple[Dict, float, str]],
    critiques: List[Dict],
) -> List[Dict]:
    """
    Second reasoning step: make a *separate* Claude call that decides an action for
    each recommendation, using the first-step critiques as input.

    This is deliberately a second API call chained after critique_recommendations,
    not merged into one prompt — critique first, then decide based on the critique.

    Args:
        user_prefs: the listener's preference dict.
        recommendations: the (song_dict, score, explanation) tuples from
            recommend_songs().
        critiques: the output of critique_recommendations() for these same
            recommendations, in the same order.

    Returns:
        A list of dicts, one per song, each with:
          - title: the song title
          - action: "keep" | "flag_for_review" | "suggest_alternative"
            (or "unavailable" on failure)
          - suggested_alternative: a title from the list (only for
            "suggest_alternative"), otherwise None
          - reasoning: Claude's justification for the action

    On any API/parse failure this returns a fallback response instead of raising.
    """
    if not recommendations:
        return []

    prompt = _build_decision_prompt(user_prefs, recommendations, critiques)

    try:
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next((block.text for block in response.content if block.type == "text"), "")
        data = _extract_json(text)
        decisions = data["decisions"]
    except anthropic.APIError as exc:
        return _decision_fallback(recommendations, f"{type(exc).__name__}: {exc}")
    except (KeyError, ValueError, TypeError) as exc:
        return _decision_fallback(recommendations, f"could not parse response ({exc})")
    except Exception as exc:  # noqa: BLE001 - never let the agent crash the caller
        return _decision_fallback(recommendations, f"unexpected error ({exc})")

    valid_titles = {song["title"] for song, _, _ in recommendations}

    results: List[Dict] = []
    for (song, _, _), raw in zip(recommendations, decisions):
        action = str(raw.get("action", "")).strip().lower()
        if action not in VALID_ACTIONS:
            action = "flag_for_review"  # unrecognized action → safest is human review

        alternative = raw.get("suggested_alternative")
        # Only honor an alternative for the matching action, and only if it names a
        # real song from the list (and isn't just the song itself).
        if action == "suggest_alternative":
            if alternative not in valid_titles or alternative == song.get("title"):
                action = "flag_for_review"
                alternative = None
        else:
            alternative = None

        results.append(
            {
                "title": song.get("title", raw.get("title", "unknown")),
                "action": action,
                "suggested_alternative": alternative,
                "reasoning": str(raw.get("reasoning", "")).strip(),
            }
        )

    # Pad if the model returned fewer entries than songs.
    for song, _, _ in recommendations[len(results):]:
        results.append(
            {
                "title": song.get("title", "unknown"),
                "action": "unavailable",
                "suggested_alternative": None,
                "reasoning": "Agent unavailable: no decision returned for this song.",
            }
        )

    return results


def log_agent_run(
    user_prefs: Dict, critiques: List[Dict], log_path: str = "logs/agent_log.jsonl"
) -> None:
    """
    Append one JSON line recording the timestamp, the user profile, and the
    critiques returned by the agent. Creates the logs/ directory if needed.
    """
    directory = os.path.dirname(log_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_profile": user_prefs,
        "critiques": critiques,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def log_reasoning_trace(
    user_prefs: Dict,
    critiques: List[Dict],
    decisions: List[Dict],
    log_path: str = "logs/reasoning_trace.jsonl",
) -> None:
    """
    Append one JSON line capturing the full multi-step reasoning trace: both the
    step-1 critique output and the step-2 decision output, raw, alongside the
    profile and timestamp. This is the committed record of the critique -> decide
    chain referenced from ai_interactions.md. Creates logs/ if needed.
    """
    directory = os.path.dirname(log_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_profile": user_prefs,
        "step_1_critiques": critiques,
        "step_2_decisions": decisions,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
