"""
Q2 Proof of Concept: Automated Message Sending to Character.AI
==============================================================

Platform:     Character.AI (https://character.ai)
Approach:     Reverse-engineered API via PyCharacterAI (unofficial wrapper)
              Uses the same WebSocket/HTTP endpoints the website uses internally.

Why this approach:
  - No browser overhead — pure API calls, ~10x faster than Playwright
  - Fully scriptable and scalable to thousands of messages
  - Works headlessly on any server/CI environment
  - Easily extended to batch multiple characters or platforms

Requirements:
  pip install PyCharacterAI

Setup:
  1. Log in to character.ai in your browser
  2. Open DevTools (F12) -> Network tab
  3. Make any request (e.g. visit your profile)
  4. Find a request to plus.character.ai, copy the Authorization header value
     (the part after "Token ")
  5. Set it as CAI_TOKEN below or as environment variable CAI_TOKEN

Usage:
  python poc_characterai.py

Output:
  - Prints each message and response to console
  - Saves full conversation to conversation_log.json
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load token and config from .env file
load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────────
CAI_TOKEN = os.getenv("CAI_TOKEN", "")
CHARACTER_NAME = os.getenv("CAI_CHARACTER_NAME", "HyperGlot")

# Input messages to send (at least 10 as required)
INPUT_MESSAGES = [
    "Hi! Can you introduce yourself?",
    "What topics do you enjoy talking about?",
    "Tell me something interesting about artificial intelligence.",
    "What do you think about the future of AI companions?",
    "Can you write a short poem about technology?",
    "What are some benefits of talking to an AI?",
    "How do you handle difficult or sensitive topics?",
    "What's the most creative thing you've helped someone with?",
    "Do you remember our previous messages in this conversation?",
    "What would you say to someone who is feeling lonely?",
    "How do you think AI will change human relationships?",
    "Thank you for chatting with me today!",
]

# Delay between messages in seconds (be respectful to the platform)
MESSAGE_DELAY = 2.0

# Output file
OUTPUT_FILE = "conversation_log.json"


# ── Main automation logic ──────────────────────────────────────────────────────
async def run_conversation():
    if not CAI_TOKEN:
        print("ERROR: CAI_TOKEN not found.")
        print("Add it to your .env file:")
        print("  CAI_TOKEN=your_token_here")
        sys.exit(1)

    try:
        from PyCharacterAI import get_client
        from PyCharacterAI.exceptions import SessionClosedError
    except ImportError:
        print("ERROR: PyCharacterAI not installed. Run: pip install PyCharacterAI")
        sys.exit(1)

    print("=" * 60)
    print("Character.AI Automation PoC")
    print("=" * 60)
    print(f"Searching for: {CHARACTER_NAME}")
    print(f"Messages     : {len(INPUT_MESSAGES)}")
    print(f"Output file  : {OUTPUT_FILE}")
    print("=" * 60)
    print()

    # Authenticate
    print("Authenticating...")
    client = await get_client(token=CAI_TOKEN)
    me = await client.account.fetch_me()
    print(f"Authenticated as: @{me.username}")
    print()

    # Search for the character
    print(f"Searching for character '{CHARACTER_NAME}'...")
    search_results = await client.character.search_characters(CHARACTER_NAME)
    
    if not search_results:
        print(f"ERROR: No characters found matching '{CHARACTER_NAME}'")
        print("Try a different character name or visit character.ai to find one.")
        await client.close_session()
        sys.exit(1)
    
    character = search_results[0]
    CHARACTER_ID = character.character_id
    print(f"Found: {character.name} (ID: {CHARACTER_ID})")
    print(f"       {character.greeting[:100] if character.greeting else 'No greeting'}...")
    print()

    # Create a new chat session with the character
    print(f"Starting chat...")
    chat, greeting = await client.chat.create_chat(CHARACTER_ID)
    greeting_text = greeting.get_primary_candidate().text
    print(f"[{greeting.author_name}]: {greeting_text}")
    print()

    # Build conversation log
    log = {
        "platform": "character.ai",
        "character_name": character.name,
        "character_id": CHARACTER_ID,
        "chat_id": chat.chat_id,
        "authenticated_user": me.username,
        "started_at": datetime.now().isoformat(),
        "approach": "Reverse-engineered API via PyCharacterAI",
        "messages": [
            {
                "turn": 0,
                "role": "character",
                "text": greeting_text,
                "timestamp": datetime.now().isoformat(),
            }
        ],
    }

    # Send each message and capture response
    try:
        for i, message in enumerate(INPUT_MESSAGES, 1):
            print(f"[You ({i}/{len(INPUT_MESSAGES)})]: {message}")

            t_start = datetime.now()
            answer = await client.chat.send_message(
                CHARACTER_ID, chat.chat_id, message
            )
            t_end = datetime.now()
            response_text = answer.get_primary_candidate().text
            response_time_ms = int((t_end - t_start).total_seconds() * 1000)

            print(f"[{answer.author_name}]: {response_text}")
            print()

            log["messages"].append({
                "turn": i * 2 - 1,
                "role": "user",
                "text": message,
                "timestamp": t_start.isoformat(),
            })
            log["messages"].append({
                "turn": i * 2,
                "role": "character",
                "author_name": answer.author_name,
                "response_time_ms": response_time_ms,
                "response_length_chars": len(response_text),
                "text": response_text,
                "timestamp": datetime.now().isoformat(),
            })

            # Respectful delay between messages
            if i < len(INPUT_MESSAGES):
                await asyncio.sleep(MESSAGE_DELAY)

    except SessionClosedError:
        print("Session closed by server.")
    finally:
        log["ended_at"] = datetime.now().isoformat()
        log["total_exchanges"] = len(INPUT_MESSAGES)
        await client.close_session()

    # Save log
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print(f"Done! {len(INPUT_MESSAGES)} messages sent and captured.")
    print(f"Full conversation saved to: {OUTPUT_FILE}")
    print("=" * 60)

    return log


if __name__ == "__main__":
    asyncio.run(run_conversation())
