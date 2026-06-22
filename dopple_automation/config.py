"""
Where we keep URLs, selectors, and timing.

For each UI bit we list a few locator guesses — the script tries them in order
until one works. Put the most reliable selector first.
"""

URLS = {
    "create": "https://www.dopple.ai/create",
    "messages": "https://www.dopple.ai/messages",
    "mydopples": "https://www.dopple.ai/mydopples",
}

CHAT_API_TARGETS = [
    "chat",
    "message",
    "completion",
]

# Step 1 of the wizard: name, tagline, bio, two images, two dropdowns, Continue.
CREATE_SELECTORS = {
    "name": ["@name=name", "@placeholder:Your Dopple Name"],
    "tagline": ["@name=tagLine", "@placeholder:Your Dopple Tagline"],
    "bio": ["@name=bio", "@placeholder:Write a short biography"],
    # Hidden file inputs: index 0 = profile, 1 = banner.
    "file_inputs": ["tag:input@type=file"],
    "category_dropdown": ["text:Select category"],
    "visibility_dropdown": ["text:Select visibility"],
    "continue": ["text:Continue"],
    "submit": ["text:Publish", "text:Create Dopple", "text:Finish", "text:Save"],
}

CATEGORY_PREFERENCE = ["Original", "Anime", "Helpers", "Games"]
VISIBILITY_PREFERENCE = ["Private", "Only Me", "Unlisted", "Public"]

# Step 2: personality text, greeting, content rating, terms, Continue.
STEP2_SELECTORS = {
    # Plain @name=description hits the <meta> tag first — need the textarea.
    "description": ["tag:textarea@name=description", "@placeholder:Joe Shmoe"],
    "greeting": ["@name=greeting"],
    "rating_dropdown": ["text:Select rating"],
    "terms_checkbox": ["tag:input@type=checkbox"],
    "continue": ["text:Continue"],
}
RATING_PREFERENCE = ["Everyone", "All Ages", "Everyone (10+)", "Teen", "Mature", "18+"]

CHAT_SELECTORS = {
    # Bottom-of-chat textarea. Don't use @placeholder:Message alone — that
    # matches the sidebar "Search Message" box and messages go to the wrong place.
    "input": [
        "tag:textarea@placeholder=Message ...",
        "tag:textarea@placeholder:Message ...",
        "tag:textarea@placeholder=Message",
        "tag:textarea@placeholder:Send a message",
        "css:textarea.input.bg-inherit",
    ],
    "send": [
        "@aria-label:Send",
        "text:Send",
        "css:button[type='submit']",
    ],
    "message_bubbles": [
        "css:[data-role='assistant']",
        "css:[data-author='assistant']",
        ".message",
        ".chat-message",
    ],
}

TIMING = {
    "page_load": 8.0,
    "reply_timeout": 60.0,
    "dom_stable_window": 2.0,   # reply done when text stops changing for this long
    "between_messages": 2.5,    # small pause so we don't hammer the API
}
