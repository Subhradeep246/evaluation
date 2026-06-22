"""
Builds a random (or fixed) character and walks through Dopple's creation wizard.

Set DOPPLE_RANDOMIZE=0 in .env for the same character every time.
DOPPLE_RANDOM_SEED=42 gives you reproducible randomness.
"""

from __future__ import annotations

import os
import random

from config import CATEGORY_PREFERENCE, VISIBILITY_PREFERENCE, RATING_PREFERENCE

NUM_CONVERSATION_TURNS = 5  # task asks for exactly five back-and-forth turns

FIRST = (
    "Aria", "Kai", "Nova", "Sage", "Ember", "River", "Lyra", "Orion",
    "Mira", "Felix", "Zara", "Juno", "Cleo", "Rex", "Ivy", "Theo",
)
LAST = (
    "Nightingale", "Ashford", "Vale", "Sterling", "Cross", "Wren",
    "Holloway", "Drake", "Quinn", "Mercer", "Blake", "Rowan", "Fox",
)
ROLES = (
    "starship navigator", "arcane librarian", "desert cartographer",
    "underwater archaeologist", "clockwork inventor", "forest ranger",
    "street magician", "tea-house philosopher", "comet chaser",
    "ghost-story collector", "mountain guide", "pirate poet",
)
TRAITS = (
    "witty and warm", "calm and curious", "bold and playful",
    "gentle but sharp", "dry-humored and loyal", "restless and kind",
)
INTERESTS = (
    "riddles", "astronomy", "old maps", "sea shanties", "chess puzzles",
    "forgotten myths", "botany", "meteor showers", "antique keys",
)
GREETING_TEMPLATES = (
    "Hello there — {name} at your service. What shall we explore today?",
    "Hey! I'm {name}. Pull up a chair and tell me what's on your mind.",
    "Greetings, traveler. {name} here — ready when you are.",
    "Welcome! I'm {name}. Ask me anything, or let's just wander somewhere interesting.",
)

# Four different 5-message scripts — we pick one per run.
CONVERSATION_FLOWS = (
    (
        "Hi {name}! Could you introduce yourself in a sentence or two?",
        "What's the most interesting place or idea you've encountered lately?",
        "Give me a short riddle to solve.",
        "Nice try — what's the real answer, and why?",
        "This was fun. Any parting words before we sign off?",
    ),
    (
        "Hey {name}! What makes you different from every other character here?",
        "Tell me a short story from your past — real or invented.",
        "What do you think about when you're alone?",
        "If you could change one thing about yourself, what would it be?",
        "Thanks for opening up. Goodbye for now!",
    ),
    (
        "Hello {name}! Surprise me with something creative.",
        "Can you write a haiku about your world?",
        "Describe your favorite sound or smell in vivid detail.",
        "Invent a tiny legend in three sentences.",
        "That was lovely. Until next time!",
    ),
    (
        "Hi {name}! What's your personal philosophy in one line?",
        "If we could visit anywhere together, where would you take me?",
        "What's a question you wish more people asked you?",
        "How do you handle disagreement or conflict?",
        "I appreciate this chat. Any final thought?",
    ),
)


def _validate_flows() -> None:
    for i, flow in enumerate(CONVERSATION_FLOWS):
        if len(flow) != NUM_CONVERSATION_TURNS:
            raise ValueError(
                f"CONVERSATION_FLOWS[{i}] has {len(flow)} messages; "
                f"expected {NUM_CONVERSATION_TURNS}"
            )


_validate_flows()


def init_random() -> None:
    """Call once at the start of a run if you want a fixed random seed."""
    seed = os.getenv("DOPPLE_RANDOM_SEED", "").strip()
    if seed:
        random.seed(int(seed))


def _randomize_enabled() -> bool:
    return os.getenv("DOPPLE_RANDOMIZE", "1").strip().lower() in ("1", "true", "yes")


def _pick(pool):
    return random.choice(pool)


def _truncate(text: str, limit: int) -> str:
    return text[:limit] if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def generate_character_details() -> dict:
    if not _randomize_enabled():
        name = os.getenv("DOPPLE_CHARACTER_NAME", "Aria Nightingale")[:25]
        tagline = os.getenv("DOPPLE_CHARACTER_TAGLINE", "Witty starship navigator")[:30]
        bio = (
            "Aria is a witty, warm starship navigator who loves riddles, astronomy "
            "and old sea-shanties. She answers with playful, adventurous charm."
        )[:300]
        greeting = os.getenv(
            "DOPPLE_CHARACTER_GREETING",
            "Welcome aboard, traveler. Where are we charting a course to today?",
        )
        description = (
            f"{name} is the witty, warm navigator of the starship Lumen. They adore "
            "riddles, deep-space astronomy and old sea-shanties, and meet every "
            "question with playful, adventurous charm."
        )[:500]
        return {
            "name": name,
            "tagline": tagline,
            "bio": bio,
            "greeting": greeting,
            "description": description,
            "category": CATEGORY_PREFERENCE[0],
            "visibility": VISIBILITY_PREFERENCE[0],
            "rating": RATING_PREFERENCE[0],
            "profile_color": (37, 99, 235),
            "banner_color": (15, 23, 42),
        }

    role = _pick(ROLES)
    trait = _pick(TRAITS)
    interest_a, interest_b = random.sample(INTERESTS, 2)
    first, last = _pick(FIRST), _pick(LAST)
    name = _truncate(f"{first} {last}", 25)
    tagline = _truncate(f"A {trait} {role}", 30)
    bio = _truncate(
        f"{first} is a {trait} {role} who loves {interest_a} and {interest_b}. "
        f"They answer with charm, curiosity, and a touch of adventure.",
        300,
    )
    greeting = _truncate(_pick(GREETING_TEMPLATES).format(name=first), 200)
    description = _truncate(
        f"{name} is a {trait} {role} drawn to {interest_a} and {interest_b}. "
        f"They speak like a companion you'd meet mid-journey — reflective, playful, "
        f"and always ready with a story or a question.",
        500,
    )

    return {
        "name": name,
        "tagline": tagline,
        "bio": bio,
        "greeting": greeting,
        "description": description,
        "category": _pick(CATEGORY_PREFERENCE),
        "visibility": _pick(VISIBILITY_PREFERENCE),
        "rating": _pick(RATING_PREFERENCE),
        "profile_color": (random.randint(40, 200), random.randint(40, 200), random.randint(40, 200)),
        "banner_color": (random.randint(10, 80), random.randint(10, 80), random.randint(30, 120)),
    }


def generate_conversation_messages(character_name: str) -> list[str]:
    first = character_name.split()[0] if character_name else "there"
    if not _randomize_enabled():
        messages = [
            f"Hi {first}! Could you introduce yourself in a sentence or two?",
            "What's the most thrilling place you've ever navigated the ship to?",
            "Give me a short riddle to solve.",
            "Hmm, let me guess... is it 'a map'? What's the real answer?",
            "This was fun. Any parting wisdom before we sign off?",
        ]
    else:
        flow = _pick(CONVERSATION_FLOWS)
        messages = [t.format(name=first) for t in flow]

    if len(messages) != NUM_CONVERSATION_TURNS:
        raise RuntimeError(
            f"Expected {NUM_CONVERSATION_TURNS} messages, got {len(messages)}"
        )
    return messages
