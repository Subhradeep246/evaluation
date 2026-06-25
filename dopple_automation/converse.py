"""
Chat with a Dopple character: open the thread, send a message, read the reply.

Dopple streams replies over SSE (POST /api/messages/send). We have to wait for
all the chunks — grabbing only the first one gives you cut-off text like
"Here's one for".
"""

from __future__ import annotations

import json
import time

from config import CHAT_SELECTORS, TIMING

CHAT_API_TARGET = "api/messages/send"
SEND_BTN_XPATH = (
    'xpath://textarea[contains(@placeholder,"Message ...")]/following-sibling::button'
)

# How long the reply text must sit unchanged before we call it done.
SSE_IDLE_GAP = 2.0
# Don't trust a short idle-only exit (stubs like "Here's one for").
SSE_MIN_CHARS_FOR_IDLE = 35
# Cap wait when Dopple never sends [DONE] in the stream.
SSE_MAX_WAIT = 25.0
# Poll for the next network chunk this often (avoids a 60s block per message).
SSE_POLL = 0.8


def _is_search_field(el) -> bool:
    ph = (el.attr("placeholder") or "").lower()
    return "search" in ph


def _find_composer(page, timeout=2.5):
    """The real message box — not the sidebar search field."""
    for sel in CHAT_SELECTORS["input"]:
        try:
            el = page.ele(sel, timeout=timeout)
            if el and not _is_search_field(el):
                return el
        except Exception:
            continue
    try:
        for el in page.eles("tag:textarea", timeout=0.8):
            ph = (el.attr("placeholder") or "").lower()
            if ph and "search" not in ph and "message" in ph:
                return el
    except Exception:
        pass
    return None


def open_created_chat(page):
    """After creation, click Chat Now on the success screen."""
    btn = None
    for _ in range(6):
        try:
            btn = page.ele("text:Chat Now", timeout=2)
            if btn:
                break
        except Exception:
            pass
        time.sleep(1)
    if not btn:
        print("  [warn] 'Chat Now' not found")
        return None
    btn.click()
    print("  [ok]   clicked Chat Now")
    time.sleep(TIMING["page_load"])
    return page.url


def _find_send_button(page, composer):
    try:
        b = page.ele(SEND_BTN_XPATH, timeout=1.0)
        if b:
            return b
    except Exception:
        pass
    try:
        return composer.next("tag:button")
    except Exception:
        return None


def _fast_type(composer, text: str) -> None:
    composer.click()
    try:
        composer.clear()
    except Exception:
        pass
    try:
        composer.input(text)
        if (composer.property("value") or "").strip() == text.strip():
            return
    except Exception:
        pass
    composer.run_js(
        "const s=Object.getOwnPropertyDescriptor("
        "window.HTMLTextAreaElement.prototype,'value').set;"
        "s.call(this, arguments[0]);"
        "this.dispatchEvent(new Event('input',{bubbles:true}));",
        text,
    )


def _sse_chunk_done(body) -> bool:
    if body is None:
        return False
    raw = body if isinstance(body, str) else json.dumps(body)
    if "[DONE]" in raw:
        return True
    if '"finish_reason"' in raw and '"stop"' in raw:
        return True
    return False


def _parse_sse_bodies(bodies) -> tuple[str, str | None]:
    if not bodies:
        return "", None
    if not isinstance(bodies, list):
        bodies = [bodies]

    text, chat_id = "", None
    for body in bodies:
        if body is None:
            continue
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        for line in str(body).splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                obj = json.loads(payload)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            chunk = obj.get("text") or obj.get("content") or ""
            if chunk:
                text += chunk
            if obj.get("chat_id"):
                chat_id = obj["chat_id"]
    return text.strip(), chat_id


def _should_stop_sse(reply: str, saw_done: bool, idle_s: float) -> bool:
    """Exit listening when the stream is clearly finished."""
    if saw_done and idle_s >= 0.3:
        return True
    if not reply:
        return False
    if idle_s >= SSE_IDLE_GAP and len(reply) >= SSE_MIN_CHARS_FOR_IDLE:
        return True
    # Tiny stub ("Here's one for") — wait longer, then fall through to DOM.
    if idle_s >= 5.0 and len(reply) < SSE_MIN_CHARS_FOR_IDLE:
        return True
    return False


def _collect_sse_reply(page, timeout: float) -> tuple[str, str | None]:
    """Poll the SSE stream; stop on [DONE] or when reply text stops growing."""
    bodies: list = []
    chat_id = None
    saw_done = False
    last_len = 0
    last_growth = time.time()
    deadline = time.time() + min(timeout, SSE_MAX_WAIT)

    while time.time() < deadline:
        got_any = False
        try:
            for packet in page.listen.steps(timeout=SSE_POLL):
                got_any = True
                body = getattr(packet.response, "body", None)
                if body is None:
                    continue
                bodies.append(body)
                if _sse_chunk_done(body):
                    saw_done = True
                reply, cid = _parse_sse_bodies(bodies)
                if cid:
                    chat_id = cid
                if len(reply) > last_len:
                    last_len = len(reply)
                    last_growth = time.time()
                idle = time.time() - last_growth
                if _should_stop_sse(reply, saw_done, idle):
                    return reply, chat_id
        except Exception:
            pass

        if not got_any:
            reply, cid = _parse_sse_bodies(bodies)
            if cid:
                chat_id = cid
            idle = time.time() - last_growth
            if _should_stop_sse(reply, saw_done, idle):
                return reply, chat_id

    reply, cid = _parse_sse_bodies(bodies)
    return reply, chat_id or cid


def _looks_incomplete(text: str) -> bool:
    if not text or len(text) < 30:
        return True
    if text.rstrip()[-1] not in ".!?\"')]}…":
        return True
    return False


def _dom_chat_lines(page) -> list[str]:
    try:
        lines = page.run_js("""
            const composer = document.querySelector('textarea[placeholder*="Message"]');
            if (!composer) return [];
            let root = composer.closest('main') || composer.parentElement;
            for (let i = 0; i < 10 && root; i++) {
                if (root.scrollHeight > 250) break;
                root = root.parentElement;
            }
            if (!root) root = document.body;
            const seen = new Set();
            const out = [];
            root.querySelectorAll('div, p').forEach(el => {
                const t = (el.innerText || '').trim().replace(/\\s+/g, ' ');
                if (t.length < 12 || seen.has(t)) return;
                seen.add(t);
                out.push(t);
            });
            return out;
        """)
        return [l for l in (lines or []) if isinstance(l, str)]
    except Exception:
        return []


def _wait_dom_new_reply(page, baseline: list[str], timeout: float) -> str:
    best = ""
    last, stable_since = None, None
    deadline = time.time() + timeout
    window = TIMING["dom_stable_window"]
    baseline_set = set(baseline)

    while time.time() < deadline:
        lines = _dom_chat_lines(page)
        new_lines = [l for l in lines if l not in baseline_set]
        current = max(new_lines, key=len, default="")

        if len(current) > len(best):
            best = current

        if len(current) >= 15:
            if current == last:
                if stable_since and (time.time() - stable_since) >= window:
                    return current
            else:
                last = current
                stable_since = time.time()

        time.sleep(0.25)
    return best


def send_and_capture(page, message):
    composer = _find_composer(page, timeout=2.5)
    if not composer:
        raise RuntimeError("Chat composer not found (not the Search Message box)")

    baseline = _dom_chat_lines(page)
    page.listen.start(CHAT_API_TARGET)
    t0 = time.time()

    _fast_type(composer, message)
    time.sleep(0.15)
    btn = _find_send_button(page, composer)
    if not btn:
        page.listen.stop()
        raise RuntimeError("Send button not found")
    btn.click()

    reply, chat_id = "", None
    try:
        reply, chat_id = _collect_sse_reply(page, TIMING["reply_timeout"])
    finally:
        try:
            page.listen.stop()
        except Exception:
            pass

    if _looks_incomplete(reply):
        dom = _wait_dom_new_reply(page, baseline, timeout=TIMING["dom_fallback_timeout"])
        if len(dom) > len(reply):
            reply = dom

    return {
        "text": reply,
        "chat_id": chat_id,
        "response_time_ms": int((time.time() - t0) * 1000),
        "response_length_chars": len(reply),
    }


if __name__ == "__main__":
    from browser import build_browser

    page = build_browser()
    open_created_chat(page)
    c = _find_composer(page, timeout=5)
    print("composer present:", bool(c))
    if c:
        print("composer placeholder:", c.attr("placeholder"))
    res = send_and_capture(page, "Hi! In one sentence, who are you?")
    print("chat_id:", res["chat_id"])
    print("reply:", res["text"])
