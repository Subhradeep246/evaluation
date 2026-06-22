"""
Opens Chrome for the Dopple automation and keeps you logged in.

We use a separate profile folder (not your everyday Chrome) so the session
survives between runs. Log in once manually; after that the script should
just work.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")


def _resolve(path_str: str) -> Path:
    p = Path(path_str).expanduser()
    return p if p.is_absolute() else (HERE / p)


def build_browser():
    """Launch Chrome with our saved profile."""
    from DrissionPage import ChromiumPage, ChromiumOptions

    profile_dir = _resolve(os.getenv("DOPPLE_PROFILE_DIR", "browser_profile"))
    profile_dir.mkdir(parents=True, exist_ok=True)

    local_port = int(os.getenv("DOPPLE_LOCAL_PORT", "9333"))
    browser_path = os.getenv("DOPPLE_BROWSER_PATH", "").strip()

    co = ChromiumOptions()
    co.set_local_port(local_port)
    co.set_user_data_path(str(profile_dir))
    if browser_path:
        co.set_browser_path(browser_path)

    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--start-maximized")

    return ChromiumPage(addr_or_opts=co)


def _looks_logged_in(page) -> bool:
    # Still logged out if we can see Log In / Sign Up on the page.
    for label in ("Log In", "Login", "Log in", "Sign Up", "Sign up", "Sign in"):
        try:
            if page.ele(f"text:{label}", timeout=0.4):
                return False
        except Exception:
            continue
    return True


def ensure_logged_in(page, login_url: str = "https://www.dopple.ai/create") -> None:
    """Go to /create and wait until you've signed in."""
    print(f"\nOpening {login_url} ...")
    page.get(login_url)
    print(
        "\n" + "=" * 70 + "\n"
        "MANUAL STEP: Log in or sign up in the opened browser window.\n"
        "  - The homepage is known to have rendering issues; stay on /create\n"
        "    and use the Log In / Sign Up controls there.\n"
        "  - Your session is saved to the dedicated profile, so you usually\n"
        "    only have to do this once.\n"
        + "=" * 70
    )

    force_poll = os.getenv("DOPPLE_NONINTERACTIVE", "").strip().lower() in (
        "1", "true", "yes",
    )
    interactive = (not force_poll) and bool(
        getattr(sys.stdin, "isatty", lambda: False)()
    )
    if interactive:
        try:
            input("\nPress ENTER here once you are fully logged in... ")
            print("Continuing with automation.\n")
            return
        except EOFError:
            # No stdin (e.g. running from an agent) — fall back to polling.
            pass

    wait_seconds = int(os.getenv("DOPPLE_LOGIN_WAIT_SECONDS", "180"))
    print(
        f"\n(Non-interactive run: waiting up to {wait_seconds}s for you to finish "
        f"logging in. I'll continue automatically once the Log In / Sign Up\n"
        f"controls disappear.)"
    )
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if _looks_logged_in(page):
            print("Detected a logged-in session. Continuing.\n")
            time.sleep(2)
            return
        remaining = int(deadline - time.time())
        print(f"  ...still waiting for login ({remaining}s left)")
        time.sleep(5)
    print("Wait window elapsed; continuing anyway (may fail if not logged in).\n")
