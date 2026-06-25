"""
Fills out Dopple's character creation wizard and publishes the Dopple.

Run on its own to test creation without the full chat flow:
    python -u create_character.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from browser import build_browser, HERE
from character_specs import generate_character_details
from config import (
    URLS,
    CREATE_SELECTORS,
    STEP2_SELECTORS,
)
from make_assets import generate_assets

ASSETS = HERE / "assets"


def _first(page, candidates, timeout=4.0):
    for sel in candidates:
        try:
            el = page.ele(sel, timeout=timeout)
            if el:
                return el
        except Exception:
            continue
    return None


def _dismiss_modal(page):
    # Dopple+ upsell and similar overlays block the form until dismissed.
    for label in ("Remind me later", "Maybe later", "Not now", "Close", "Skip"):
        try:
            el = page.ele(f"text:{label}", timeout=1)
            if el:
                el.click()
                time.sleep(1.5)
                return
        except Exception:
            continue


def _wait_no_crop(page, tries=12):
    """Make sure the image crop dialog isn't still open."""
    for _ in range(tries):
        try:
            btn = page.ele("text:Save Image", timeout=1)
        except Exception:
            btn = None
        if not btn:
            return True
        try:
            btn.click()
        except Exception:
            pass
        time.sleep(1.5)
    return False


def _react_set(el, text):
    """React-controlled fields sometimes drop plain typing — set value via JS."""
    proto = "HTMLTextAreaElement" if el.tag == "textarea" else "HTMLInputElement"
    script = (
        f"const s=Object.getOwnPropertyDescriptor(window.{proto}.prototype,'value').set;"
        "s.call(this, arguments[0]);"
        "this.dispatchEvent(new Event('input',{bubbles:true}));"
        "this.dispatchEvent(new Event('change',{bubbles:true}));"
    )
    el.run_js(script, text)


def _value_of(el):
    return (el.property("value") or el.attr("value") or el.text or "").strip()


def _fill_field(page, candidates, text, label):
    for _ in range(5):
        _wait_no_crop(page, tries=2)
        el = _first(page, candidates, timeout=4)
        if not el:
            time.sleep(0.6)
            continue
        try:
            el.click()
            el.clear()
            el.input(text)
        except Exception:
            pass
        time.sleep(0.4)
        if len(_value_of(el)) >= min(3, len(text)):
            print(f"  [ok]   {label} ({len(_value_of(el))} chars)")
            return True
        try:
            _react_set(el, text)
            time.sleep(0.4)
            if len(_value_of(el)) >= min(3, len(text)):
                print(f"  [ok]   {label} (react, {len(_value_of(el))} chars)")
                return True
        except Exception:
            pass
        time.sleep(0.4)
    print(f"  [warn] {label} not filled")
    return False


def _save_crop(page):
    for _ in range(20):
        try:
            sb = page.ele("text:Save Image", timeout=1)
        except Exception:
            sb = None
        if sb:
            try:
                sb.click()
            except Exception:
                pass
            time.sleep(2)
            try:
                if not page.ele("text:Save Image", timeout=1):
                    return True
            except Exception:
                return True
        time.sleep(0.5)
    return False


def _upload_image(page, index, path, label, retries=2):
    """Feed the hidden file input directly, then confirm the crop modal."""
    for attempt in range(retries + 1):
        try:
            files = page.eles("tag:input@type=file", timeout=4)
        except Exception:
            files = []
        if len(files) <= index:
            time.sleep(1)
            continue
        try:
            files[index].input(str(path))
            print(f"  [ok]   {label} selected" + (f" (retry {attempt})" if attempt else ""))
        except Exception as e:
            print(f"  [warn] {label} input failed: {e}")
            time.sleep(1)
            continue
        if _save_crop(page):
            print(f"  [ok]   {label} crop saved")
            time.sleep(1)
            return True
        print(f"  [warn] {label} crop did not save; retrying")
        time.sleep(1)
    print(f"  [warn] {label} could not be uploaded")
    return False


def _agree_terms(page):
    # It's a fake checkbox — just a button next to the legal paragraph.
    try:
        p = page.ele("text:By publishing this Dopple", timeout=3)
        if not p:
            print("  [warn] terms paragraph not found")
            return False
        container = p.parent()
        cb = container.ele("tag:button", timeout=2)
        if cb:
            cb.click()
            time.sleep(0.6)
            print("  [ok]   agreed to terms")
            return True
        container.click()
        time.sleep(0.6)
        print("  [ok]   agreed to terms (row)")
        return True
    except Exception as e:
        print(f"  [warn] terms agreement failed: {e}")
        return False


def _click_when_enabled(page, candidates, label, tries=8):
    """Continue stays greyed out until the step is valid — wait for that."""
    for _ in range(tries):
        btn = _first(page, candidates, timeout=2)
        if btn:
            disabled = btn.attr("disabled")
            if disabled in (None, False, "false"):
                try:
                    btn.click()
                    print(f"  [ok]   clicked {label}")
                    return True
                except Exception:
                    pass
        time.sleep(1)
    print(f"  [warn] {label} stayed disabled / not clickable")
    return False


def _select_dropdown(page, opener_candidates, preferences, label):
    btn = _first(page, opener_candidates, timeout=3)
    if not btn:
        print(f"  [skip] {label} dropdown not found")
        return False
    btn.click()
    time.sleep(1.0)
    for pref in preferences:
        try:
            opt = page.ele(f"text:{pref}", timeout=1)
            if opt:
                opt.click()
                time.sleep(0.8)
                print(f"  [ok]   {label} = {pref}")
                return True
        except Exception:
            continue
    print(f"  [warn] none of {preferences} found for {label}")
    return False



def _rating_placeholder_visible(page) -> bool:
    for text in ("Select rating", "Select content rating"):
        try:
            if page.ele(f"text:{text}", timeout=0.25):
                return True
        except Exception:
            continue
    return False


def _rating_labels_for(preferred: str) -> list[str]:
    """Map stored rating to the labels Dopple actually shows (10+ vs 18+)."""
    p = (preferred or "").strip()
    if "18" in p or p.lower() in ("mature", "adult"):
        return ["18+"]
    return ["Everyone (10+)"]


def _select_content_rating(page, preferred: str) -> bool:
    """Pick 10+ or 18+ once. Continue may stay grey until terms are checked too."""
    if not _rating_placeholder_visible(page):
        print("  [ok]   content rating already set")
        return True

    label = _rating_labels_for(preferred)[0]
    opener = _first(page, STEP2_SELECTORS["rating_dropdown"], timeout=1.5)
    if opener:
        try:
            opener.click()
            time.sleep(0.5)
        except Exception:
            pass

    try:
        opt = page.ele(f"text:{label}", timeout=1.5)
        if opt:
            opt.click()
            time.sleep(0.5)
    except Exception:
        pass

    if not _rating_placeholder_visible(page):
        print(f"  [ok]   content rating = {label}")
        return True

    # Tile-style UI (no dropdown placeholder) — one targeted click only.
    try:
        picked = page.run_js(
            """
            const want = arguments[0];
            const nodes = [...document.querySelectorAll(
                'button, [role="button"], [role="option"], [role="radio"], li, label'
            )];
            for (const el of nodes) {
                const t = (el.innerText || el.textContent || '').trim();
                if (t === want || t.includes(want)) {
                    el.click();
                    return want;
                }
            }
            return null;
            """,
            label,
        )
        if picked:
            time.sleep(0.5)
            print(f"  [ok]   content rating = {picked}")
            return True
    except Exception:
        pass

    print("  [warn] content rating not selected (10+ / 18+)")
    return False


def create_character(page, details=None):
    details = details or generate_character_details()
    print(f"\n=== Character: {details['name']} ===")
    print(f"  tagline   : {details['tagline']}")
    print(f"  category  : {details.get('category')}")
    print(f"  visibility: {details.get('visibility')}")

    generate_assets(details.get("profile_color"), details.get("banner_color"))

    print("\n=== Character creation: Step 1 ===")
    page.get(URLS["create"])
    time.sleep(6)
    _dismiss_modal(page)
    time.sleep(1.5)

    # Do images first — each one opens a crop modal that blocks everything else.
    _upload_image(page, 0, ASSETS / "profile.png", "profile image")
    _upload_image(page, 1, ASSETS / "banner.png", "banner image")
    _wait_no_crop(page)

    _fill_field(page, CREATE_SELECTORS["name"], details["name"], "name")
    _fill_field(page, CREATE_SELECTORS["tagline"], details["tagline"], "tagline")
    _fill_field(page, CREATE_SELECTORS["bio"], details["bio"], "bio")

    _select_dropdown(
        page, CREATE_SELECTORS["category_dropdown"],
        [details["category"], "Original", "Anime"], "category",
    )
    _select_dropdown(
        page, CREATE_SELECTORS["visibility_dropdown"],
        [details["visibility"], "Private", "Public"], "visibility",
    )

    _click_when_enabled(page, CREATE_SELECTORS["continue"], "Continue (step 1)")
    time.sleep(4)

    print("\n=== Character creation: Step 2 ===")
    # Give the wizard a moment to swap steps before we start typing.
    for _ in range(15):
        try:
            if page.ele("tag:textarea@name=description", timeout=1):
                break
        except Exception:
            pass
        time.sleep(1)
    time.sleep(1.5)

    greeting = details["greeting"]
    description = details["description"]
    _fill_field(page, STEP2_SELECTORS["description"], description, "description")
    _fill_field(page, STEP2_SELECTORS["greeting"], greeting, "greeting")
    _select_content_rating(page, details.get("rating", "Everyone (10+)"))

    _agree_terms(page)

    if not _click_when_enabled(page, STEP2_SELECTORS["continue"], "Continue (step 2)", tries=10):
        if _rating_placeholder_visible(page):
            _select_content_rating(page, "Everyone (10+)")
        _agree_terms(page)
        _click_when_enabled(page, STEP2_SELECTORS["continue"], "Continue (step 2, retry)", tries=8)
    time.sleep(5)

    print("\n=== Character created ===")
    return {
        "name": details["name"],
        "tagline": details["tagline"],
        "bio": details["bio"],
        "greeting": greeting,
        "description": description,
        "category": details.get("category"),
        "visibility": details.get("visibility"),
        "rating": details.get("rating"),
        "url_after_create": page.url,
    }


if __name__ == "__main__":
    from character_specs import init_random

    page = build_browser()
    init_random()
    result = create_character(page)
    print("\nResult:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\nBrowser left open for inspection.")
