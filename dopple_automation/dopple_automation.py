"""
Dopple automation — the full task in one script.

1. You log in manually (once; saved in browser_profile/)
2. Script creates a character
3. Script chats for 5 turns
4. Transcript lands in dopple_conversation.json

    pip install -r requirements.txt
    python make_assets.py
    python dopple_automation.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime

from browser import build_browser, ensure_logged_in, HERE
from character_specs import (
    NUM_CONVERSATION_TURNS,
    generate_conversation_messages,
    init_random,
)
from config import URLS, TIMING
from create_character import create_character
from converse import open_created_chat, send_and_capture


def main():
    output_file = HERE / os.getenv("DOPPLE_OUTPUT_FILE", "dopple_conversation.json")

    log = {
        "platform": "dopple.ai",
        "approach": (
            "Browser automation via DrissionPage. Manual one-time login; automated "
            "multi-step character creation and chat. Replies captured from the chat "
            "SSE stream (POST /api/messages/send)."
        ),
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "messages": [],
        "error": None,
    }

    page = build_browser()
    try:
        init_random()

        ensure_logged_in(page, URLS["create"])

        character = create_character(page)
        log["character"] = character
        input_messages = generate_conversation_messages(character["name"])

        print("\n=== Opening conversation ===")
        chat_url = open_created_chat(page)
        log["chat_url"] = chat_url

        if character.get("greeting"):
            log["messages"].append({
                "turn": 0, "role": "character", "text": character["greeting"],
                "note": "greeting", "timestamp": datetime.now().isoformat(timespec="seconds"),
            })

        print(f"\n=== {NUM_CONVERSATION_TURNS}-turn conversation ===")
        for i, message in enumerate(input_messages[:NUM_CONVERSATION_TURNS], start=1):
            print(f"\n[You {i}/{NUM_CONVERSATION_TURNS}]: {message}")
            res = send_and_capture(page, message)
            print(f"[{character.get('name', 'Character')}]: {res['text'][:500]}")
            if res.get("chat_id"):
                log["chat_id"] = res["chat_id"]

            ts = datetime.now().isoformat(timespec="seconds")
            log["messages"].append({"turn": i * 2 - 1, "role": "user",
                                    "text": message, "timestamp": ts})
            log["messages"].append({
                "turn": i * 2, "role": "character", "text": res["text"],
                "response_time_ms": res["response_time_ms"],
                "response_length_chars": res["response_length_chars"],
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            })

            if i < NUM_CONVERSATION_TURNS:
                time.sleep(TIMING["between_messages"])

        log["total_turns"] = NUM_CONVERSATION_TURNS
        log["user_messages"] = input_messages[:NUM_CONVERSATION_TURNS]

    except Exception as exc:
        log["error"] = f"{type(exc).__name__}: {exc}"
        print(f"\n[error] {log['error']}", file=sys.stderr)
    finally:
        log["ended_at"] = datetime.now().isoformat(timespec="seconds")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2, ensure_ascii=False)
        print("\n" + "=" * 70)
        print(f"Transcript written to: {output_file}")
        print("=" * 70)


if __name__ == "__main__":
    main()
