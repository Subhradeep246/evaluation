# Q2: Automation Approach and Proof of Concept

## Platform Selected: Character.AI

**URL:** https://character.ai  
**Reason for selection:**
- Highest review count among web-accessible companion apps (591K+ reviews)
- No subscription required for long conversations (free tier is unlimited)
- Directly studied in all 6 research papers provided — most relevant to the project
- Full web interface available (not mobile-only)
- Most widely used AI companion platform globally

---

## Approach: Reverse-Engineered API

**Method:** API reverse engineering using [PyCharacterAI](https://github.com/Xtr4F/PyCharacterAI), an unofficial Python wrapper that replicates the internal HTTP/WebSocket calls the Character.AI website makes.

**How it works:**
1. The user authenticates once via browser and extracts their session token from the `Authorization` header in DevTools
2. The script uses this token to call Character.AI's internal API endpoints directly — no browser needed
3. A chat session is created with a chosen character, messages are sent programmatically, and responses are captured

---

## Implementation

**File:** `poc_characterai.py`

**Dependencies:**
```
pip install PyCharacterAI
```

**Setup:**
1. Log in to character.ai in your browser
2. Open DevTools (F12) → Network tab
3. Make any request (visit profile, start a chat)
4. Find a request to `plus.character.ai`, copy the `Authorization` header value (after `Token `)
5. Set it: `set CAI_TOKEN=your_token_here` (Windows) or `export CAI_TOKEN=your_token_here` (Mac/Linux)

**Run:**
```bash
python poc_characterai.py
```

**Output:** Prints each exchange to console and saves full conversation to `conversation_log.json`

---

## Justification: Why This Approach is Effective and Scalable

| Criterion | API Approach | Playwright/Selenium |
|---|---|---|
| Speed | ~10x faster (no browser rendering) | Slow (full browser) |
| Reliability | High (no DOM changes break it) | Fragile (UI updates break selectors) |
| Headless server use | ✅ Yes | ⚠️ Requires display/virtual framebuffer |
| Parallel execution | ✅ Easy (async, multiple clients) | ❌ Heavy (one browser per instance) |
| Rate limit handling | ✅ Precise control | ❌ Hard to time accurately |
| Scalability | ✅ Thousands of messages/day | ❌ Limited by browser resources |

The API approach is the same method used by researchers in the papers provided (e.g., the safety benchmarking paper evaluated 16 platforms by sending 5,000 questions each — only feasible via API).

---

## Assumptions and Limitations

1. **Token required:** The user must manually extract their auth token from the browser once. This is a one-time setup step.
2. **Unofficial API:** PyCharacterAI reverse-engineers Character.AI's internal endpoints. These may change without notice, requiring library updates.
3. **Rate limits:** Character.AI enforces rate limits. The script includes a 2-second delay between messages to stay within acceptable usage.
4. **Age verification (April 2026):** Character.AI now requires face-based age verification for new accounts. Existing authenticated sessions are unaffected.
5. **Terms of Service:** Automated access may violate Character.AI's ToS. For research purposes, this is standard practice (as done in the referenced papers).

---

## Extending to Multiple Platforms

The same API reverse-engineering approach works across platforms:

| Platform | Method | Notes |
|---|---|---|
| Character.AI | PyCharacterAI (Python) | ✅ Ready |
| Janitor AI | HTTP API (reverse-engineered) | Uses OpenAI-compatible endpoints |
| PolyBuzz | HTTP API | Requires token extraction |
| Talkie | HTTP API | Requires token extraction |
| CHAI | Mobile API (mitmproxy) | Mobile-only, needs proxy interception |
| Replika | HTTP API | Well-documented community reverse engineering |

**General pattern for any platform:**
1. Use mitmproxy or browser DevTools to capture API calls
2. Identify the authentication endpoint and chat message endpoint
3. Replicate the calls in Python using `httpx` or `requests`
4. Wrap in async loop for batch message sending

A unified multi-platform runner could:
- Accept a platform name + character ID + message list as config
- Route to the appropriate platform-specific client
- Output standardized JSON with `{platform, character_id, messages: [{role, text, timestamp}]}`

---

## Sample Output (`conversation_log.json`)

```json
{
  "platform": "character.ai",
  "character_id": "...",
  "chat_id": "...",
  "authenticated_user": "username",
  "started_at": "2026-04-16T10:00:00",
  "approach": "Reverse-engineered API via PyCharacterAI",
  "messages": [
    {"turn": 0, "role": "character", "text": "Hello! How can I help you today?"},
    {"turn": 1, "role": "user", "text": "Hi! Can you introduce yourself?"},
    {"turn": 2, "role": "character", "text": "Sure! I'm an AI assistant..."},
    ...
  ],
  "ended_at": "2026-04-16T10:01:30",
  "total_exchanges": 12
}
```
