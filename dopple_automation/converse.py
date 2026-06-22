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
SSE_IDLE_GAP = 1.5  # no new chunks for this long → assume the stream is done


def _is_search_field(el) -> bool:
    ph = (el.attr("placeholder") or "").lower()
    return "search" in ph


def _find_composer(page, timeout=4.0):
    """The real message box — not the sidebar search field."""
    for sel in CHAT_SELECTORS["input"]:
        try:
            el = page.ele(sel, timeout=timeout)
            if el and not _is_search_field(el):
                return el
        except Exception:
            continue
    try:
        for el in page.eles("tag:textarea", timeout=1):
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
        b = page.ele(SEND_BTN_XPATH, timeout=1.5)
        if b:
            return b
    except Exception:
        pass
    try:
        return composer.next("tag:button")
    except Exception:
        return None


def _fast_type(composer, text: str) -> None:
    """Paste the message in one go — typing char-by-char is painfully slow."""
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
    # React sometimes ignores plain .input(); nudge it through the native setter.
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
    """Stitch token chunks into one reply string."""
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


def _collect_sse_reply(page, timeout: float) -> tuple[str, str | None]:
    """Listen until Dopple finishes streaming or goes quiet."""
    bodies: list = []
    chat_id = None
    last_new = time.time()
    t0 = time.time()

    try:
        for packet in page.listen.steps(timeout=timeout):
            body = getattr(packet.response, "body", None)
            if body is not None:
                bodies.append(body)
                last_new = time.time()

            reply, cid = _parse_sse_bodies(bodies)
            if cid:
                chat_id = cid
            if _sse_chunk_done(body):
                return reply, chat_id
            if bodies and (time.time() - last_new) >= SSE_IDLE_GAP:
                return reply, chat_id
            if time.time() - t0 >= timeout:
                break
    except Exception:
        pass

    reply, cid = _parse_sse_bodies(bodies)
    return reply, chat_id or cid


def _dom_latest_reply(page) -> str:
    """Backup: read whatever's showing in the last chat bubble."""
    for sel in CHAT_SELECTORS["message_bubbles"]:
        try:
            bubbles = page.eles(sel, timeout=0.5)
            if bubbles:
                return (bubbles[-1].text or "").strip()
        except Exception:
            continue
    return ""


def _wait_dom_reply(page, min_len: int, timeout: float) -> str:
    """Wait until the bubble text stops growing (streaming finished)."""
    best, last, stable_since = "", None, None
    deadline = time.time() + timeout
    window = TIMING["dom_stable_window"]

    while time.time() < deadline:
        current = _dom_latest_reply(page)
        if len(current) >= min_len:
            if current == last:
                if stable_since and (time.time() - stable_since) >= window:
                    return current
            else:
                last = current
                stable_since = time.time()
            if len(current) > len(best):
                best = current
        time.sleep(0.35)
    return best


def send_and_capture(page, message):
    composer = _find_composer(page, timeout=4)
    if not composer:
        raise RuntimeError("Chat composer not found (not the Search Message box)")

    page.listen.start(CHAT_API_TARGET)
    t0 = time.time()

    _fast_type(composer, message)
    time.sleep(0.2)
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

    # If SSE gave us a stub, trust the rendered bubble instead.
    dom = _wait_dom_reply(page, min_len=len(reply), timeout=8.0)
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
