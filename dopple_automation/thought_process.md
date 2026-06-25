# Dopple AI Automation — Approach & Justification

## Objective

Use **DrissionPage** to (1) create a character on Dopple AI and (2) automate a
5-turn conversation, saving the full exchange to JSON. Login/sign-up is done
manually; everything after is automated.

---

## Approach: browser automation with manual-login persistence + hybrid capture


| Decision      | Choice                                        | Why                                                                                  |
| ------------- | --------------------------------------------- | ------------------------------------------------------------------------------------ |
| Library       | DrissionPage (CDP-driven Chromium)            | Required by the task; controls a real browser, good for auth/anti-bot                |
| Login         | Manual, once                                  | Required by the task; persisted via a dedicated user-data profile so re-runs skip it |
| Selectors     | Ordered candidate lists in `config.py`        | DOM is unknown until logged in; `recon.py` discovers the exact ones                  |
| Reply capture | **Hybrid** — network listener + DOM stability | Listener detects completion of streamed replies; DOM gives canonical text            |
| Output        | `dopple_conversation.json`                    | Schema consistent with the Character.AI Q2 deliverable                               |


### Why hybrid capture

LLM replies often **stream token-by-token**, so naively reading the DOM can grab
a half-finished message. DrissionPage v4's `page.listen` lets us watch the chat
API call to know when generation finishes; we then read the **final rendered
bubble** as the canonical reply text and keep the raw API body for transparency.

### Why a recon phase

We can't see Dopple's real DOM/API without a logged-in session. `recon.py` opens
the site, waits for manual login, and dumps form fields, buttons, message bubbles,
and **all network calls** fired while sending a message. Those findings are pasted
into `config.py`, keeping the main script clean rather than built on guesses.

---

## Comparison to the Character.AI PoC


|       | Character.AI (Q2)                        | Dopple AI (this)       |
| ----- | ---------------------------------------- | ---------------------- |
| Tool  | `PyCharacterAI` (reverse-engineered API) | DrissionPage (browser) |
| Auth  | Token from DevTools                      | Manual browser login   |
| Scope | Find existing char → chat                | **Create char** → chat |
| Turns | 12                                       | 5                      |


The two are deliberately kept as **separate components** because they use
different paradigms (API vs browser) and different platforms.

---

## Assumptions & limitations

1. **Headed browser** is needed for the one-time manual login.
2. **UI drift:** Dopple's markup may change; candidate selectors + `recon.py`
  make rediscovery fast.
3. **Chat API extraction:** the canonical reply text comes from the DOM; the raw
  API body is stored only when the endpoint is captured (it varies in shape).
4. **ToS / research framing:** automated access may be subject to platform terms;
  used here for an engineering/research evaluation, consistent with the provided
   papers' methodology.

---

## Deliverables

- `dopple_automation.py` — working automation script
- `recon.py`, `browser.py`, `config.py` — supporting modules
- `dopple_conversation.json` — produced after a run (the captured transcript)

