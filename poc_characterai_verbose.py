"""
Verbose version of the PoC - shows detailed progress and timing
"""
import asyncio
import json
import os
import sys
from datetime import datetime
import time
from dotenv import load_dotenv

load_dotenv()

CAI_TOKEN = os.getenv("CAI_TOKEN", "")
CHARACTER_NAME = os.getenv("CAI_CHARACTER_NAME", "HyperGlot")

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

MESSAGE_DELAY = 2.0
OUTPUT_FILE = "conversation_log_verbose.json"

async def run_conversation():
    if not CAI_TOKEN:
        print("ERROR: CAI_TOKEN not found. Add it to your .env file.")
        sys.exit(1)

    try:
        from PyCharacterAI import get_client
        from PyCharacterAI.exceptions import SessionClosedError
    except ImportError:
        print("ERROR: pip install PyCharacterAI")
        sys.exit(1)

    print("=" * 80)
    print(" " * 20 + "Character.AI Automation PoC (VERBOSE)")
    print("=" * 80)
    print(f"  Character to find : {CHARACTER_NAME}")
    print(f"  Total messages    : {len(INPUT_MESSAGES)}")
    print(f"  Output file       : {OUTPUT_FILE}")
    print(f"  Delay per message : {MESSAGE_DELAY}s")
    print("=" * 80)
    print()

    start_time = time.time()

    # Authenticate
    print("[1/4] Authenticating...")
    client = await get_client(token=CAI_TOKEN)
    me = await client.account.fetch_me()
    print(f"      ✓ Authenticated as @{me.username}")
    print()

    # Search
    print(f"[2/4] Searching for '{CHARACTER_NAME}'...")
    search_results = await client.character.search_characters(CHARACTER_NAME)
    
    if not search_results:
        print(f"      ✗ No characters found")
        await client.close_session()
        sys.exit(1)
    
    character = search_results[0]
    CHARACTER_ID = character.character_id
    print(f"      ✓ Found: {character.name}")
    print(f"        ID: {CHARACTER_ID}")
    print(f"        Interactions: {character.num_interactions:,}")
    print()

    # Create chat
    print("[3/4] Creating chat session...")
    chat, greeting = await client.chat.create_chat(CHARACTER_ID)
    greeting_text = greeting.get_primary_candidate().text
    print(f"      ✓ Chat ID: {chat.chat_id}")
    print(f"      ✓ Greeting received ({len(greeting_text)} chars)")
    print()
    print(f"      [{character.name}]: {greeting_text}")
    print()

    log = {
        "platform": "character.ai",
        "character_name": character.name,
        "character_id": CHARACTER_ID,
        "chat_id": chat.chat_id,
        "authenticated_user": me.username,
        "started_at": datetime.now().isoformat(),
        "approach": "Reverse-engineered API via PyCharacterAI",
        "messages": [{"turn": 0, "role": "character", "text": greeting_text, "timestamp": datetime.now().isoformat()}],
    }

    # Send messages
    print("[4/4] Sending messages...")
    print("-" * 80)
    
    try:
        for i, message in enumerate(INPUT_MESSAGES, 1):
            msg_start = time.time()
            
            print(f"\n[{i}/{len(INPUT_MESSAGES)}] YOU: {message}")
            
            answer = await client.chat.send_message(CHARACTER_ID, chat.chat_id, message)
            response_text = answer.get_primary_candidate().text
            
            msg_elapsed = time.time() - msg_start
            
            print(f"     ⏱️  Response time: {msg_elapsed:.2f}s")
            print(f"     📝 Response length: {len(response_text)} chars")
            print(f"     [{character.name}]: {response_text}")

            log["messages"].append({"turn": i * 2 - 1, "role": "user", "text": message, "timestamp": datetime.now().isoformat()})
            log["messages"].append({"turn": i * 2, "role": "character", "author_name": character.name, "text": response_text, "timestamp": datetime.now().isoformat()})

            if i < len(INPUT_MESSAGES):
                print(f"     ⏸️  Waiting {MESSAGE_DELAY}s...")
                await asyncio.sleep(MESSAGE_DELAY)

    except SessionClosedError:
        print("\n⚠️  Session closed by server")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        log["ended_at"] = datetime.now().isoformat()
        log["total_exchanges"] = len(INPUT_MESSAGES)
        log["total_time_seconds"] = time.time() - start_time
        await client.close_session()

    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

    print()
    print("=" * 80)
    print(f"✅ COMPLETE")
    print(f"   Messages sent     : {len(INPUT_MESSAGES)}")
    print(f"   Responses captured: {len(INPUT_MESSAGES)}")
    print(f"   Total time        : {time.time() - start_time:.1f}s")
    print(f"   Saved to          : {OUTPUT_FILE}")
    print("=" * 80)

    return log

if __name__ == "__main__":
    asyncio.run(run_conversation())
