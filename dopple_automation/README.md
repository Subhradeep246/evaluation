# Dopple AI — Character Creation + Conversation Automation

A **self-contained** automation component that uses [**DrissionPage**](https://www.drissionpage.cn/) to:

1. Let you **log in / sign up manually** on `https://www.dopple.ai/create`.
2. **Create a character** automatically.
3. Hold a **5-turn conversation** and capture the replies.
4. Save the full transcript to **`dopple_conversation.json`**.

> The Dopple homepage has a known rendering issue, so the scripts always use the
> direct URLs (`/create`, `/messages`, `/mydopples`) and never navigate from `/`.

---

## Layout

```
dopple_automation/
├── dopple_automation.py    # Main entry: login → create → chat → JSON
├── create_character.py     # Multi-step character creation wizard
├── converse.py             # Open chat + send/capture messages (SSE)
├── browser.py              # Persistent Chrome profile + manual login wait
├── config.py               # URLs, selectors, timing
├── character_specs.py      # Random/fixed character + message generation
├── make_assets.py          # Generate required profile/banner placeholder images
├── assets/                 # profile.png, banner.png (run make_assets.py first)
├── requirements.txt
├── .env.example
├── writeup.md              # Approach & justification
└── dopple_conversation.json  # Output (after a successful run)
```

---

## Setup

```bash
cd evaluation/dopple_automation
pip install -r requirements.txt
copy .env.example .env          # then edit if desired
python make_assets.py           # one-time: create placeholder images
```

## Run

```bash
python dopple_automation.py
```

- First run: log in manually in the opened Chrome window (session saved to `browser_profile/`).
- Creates a **randomized** character each run (name, bio, category, colors, etc.).
- Sends 5 messages, captures 5 replies.

Set `DOPPLE_RANDOMIZE=0` in `.env` to use fixed values from `DOPPLE_CHARACTER_*` instead.
Optional `DOPPLE_RANDOM_SEED=42` for reproducible random runs.
- Writes everything to `dopple_conversation.json`.

---

## Notes

- **Headed browser:** manual login requires a visible window (at least once).
- **Never commit** `browser_profile/` or `.env` — they contain your session/secrets
  (already in `.gitignore`).
