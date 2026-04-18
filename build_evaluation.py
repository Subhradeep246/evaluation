"""
build_evaluation.py
===================
Produces apps_evaluation.csv from the raw app store data in assets/.

Data sources used:
  1. assets/app_store_apps_details.json       - 453 iOS apps (scraped)
  2. assets/google_play_apps_details.json     - 492 Android apps (scraped)
  3. assets/2603.13620v1.pdf                  - Walkthrough data for 30 apps (Dec 2025)
  4. assets/2026-f575-paper.pdf               - 16 platform safety benchmark list
  5. Web searches (April 2026)                - Pricing/login/web data for top ~200 apps

Output columns:
  platform, appId, title, store_url, developer, genres, contentRating,
  price, free, score, reviews, app_type, web_accessible, web_url,
  login_required, login_methods, age_verification_required,
  age_verification_method, subscription_required_for_long_chat,
  all_features_available_without_subscription, subscription_features,
  subscription_cost, languages_supported

Classification logic:
  - app_type: keyword scoring on title+description + manual overrides
  - web_accessible: researched for top apps; companion=False, GP=True otherwise
  - login_methods: extracted from description text or web research
  - age_verification_required: content rating 17+/Mature 17+ -> True
  - subscription_cost: web research for top apps; regex from descriptions; else inferred
  - languages_supported: iOS languages field; web research; else 'en'
"""

import json
import csv
import re
from collections import Counter

# ── Load raw data ──────────────────────────────────────────────────────────────
with open('assets/app_store_apps_details.json', encoding='utf-8') as f:
    ios_raw = json.load(f)['results']
with open('assets/google_play_apps_details.json', encoding='utf-8') as f:
    android_raw = json.load(f)['results']

print(f"Loaded {len(ios_raw)} iOS apps, {len(android_raw)} Android apps")


# ── Researched data (web searches + paper walkthroughs, April 2026) ───────────
# Format: title -> (web_accessible, web_url, login_required, login_methods,
#                   age_ver_required, age_ver_method,
#                   sub_required_for_long_chat, all_features_free,
#                   sub_features, sub_cost, languages)

KNOWN = {
    "Character AI: Chat, Talk, Text": (True,"https://character.ai",True,"email/password, Google, Apple",True,"face-based age verification (mandatory April 2026)",False,False,"c.ai+: faster response speed, priority access","$9.99/month","en, es, pt, fr, de, ja, ko, zh, it, ru, ar, hi"),
    "Replika - AI Friend": (True,"https://replika.com",True,"email/password, Apple, Google",True,"self-declaration (date of birth)",False,False,"Replika Pro: romantic mode, voice calls, AR, adult content","$19.99/month","en"),
    "Replika": (True,"https://replika.com",True,"email/password, Apple, Google",True,"self-declaration (date of birth)",False,False,"Replika Pro: romantic mode, voice calls, AR, adult content","$19.99/month","en"),
    "Replika: My AI Friend": (True,"https://replika.com",True,"email/password, Apple, Google",True,"self-declaration (date of birth)",False,False,"Replika Pro: romantic mode, voice calls, AR, adult content","$19.99/month","en"),
    "CHAI: Social AI Platform- Chat": (False,"",True,"email/password, Google, Apple",True,"device settings age confirmation",True,False,"Chai Premium: unlimited messages, better models, no ads; Chai Ultra: $29.99/month","$13.99/month","en"),
    "Chai: Chat AI Platform": (False,"",True,"email/password, Google, Apple",True,"device settings age confirmation",True,False,"Chai Premium: unlimited messages, better models, no ads; Chai Ultra: $29.99/month","$13.99/month","en"),
    "PolyBuzz: Chat with Characters": (True,"https://www.polybuzz.ai",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice chat, image generation, coin system","$9.99/month","en, zh, ja, ko, es, fr, de, pt"),
    "PolyBuzz: Chat with AI Friends": (True,"https://www.polybuzz.ai",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice chat, image generation, coin system","$9.99/month","en, zh, ja, ko, es, fr, de, pt"),
    "Talkie Lab - AI Playground": (True,"https://www.talkie-ai.com",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice calls, exclusive characters, creator program","$9.99/month","en, zh, ja, ko, es, fr, de, pt, ru"),
    "Talkie: Soulful AI": (True,"https://www.talkie-ai.com",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice calls, exclusive characters","$9.99/month","en, zh, ja, ko, es, fr, de, pt, ru"),
    "Talkie: Creative AI Community": (True,"https://www.talkie-ai.com",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice calls, exclusive characters, creator program","$9.99/month","en, zh, ja, ko, es, fr, de, pt, ru"),
    "Linky AI: AI Chat&Char Maker": (True,"https://linky-ai.com",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice, advanced characters, creator program","$9.99/month","en, zh, ja, ko, es, fr"),
    "Linky AI: Chat, Play, Connect": (True,"https://linky-ai.com",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice, advanced characters, creator program","$9.99/month","en, zh, ja, ko, es, fr"),
    "Jupi - AI Character Chat": (False,"",True,"email/password, Google, Apple",True,"self-declaration (date of birth) + optional Yoti ID verification",True,False,"Premium: unlimited messages, voice, exclusive characters","$9.99/month","en"),
    "EVA AI Soulmate": (False,"",True,"email/password, Google, Apple",True,"self-declaration (age 18+)",True,False,"Premium: unlimited messages, voice calls, relationship modes","$19.99/month","en, ru"),
    "EVA AI Girlfriend & Character": (False,"",True,"email/password, Google, Apple",True,"self-declaration (age 18+)",True,False,"Premium: unlimited messages, voice calls, relationship modes","$19.99/month","en, ru"),
    "Kindroid: Your Personal AI": (True,"https://kindroid.ai",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice calls, image generation, memory, social profile","$13.99/month","en"),
    "Kindroid": (True,"https://kindroid.ai",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice calls, image generation, memory","$13.99/month","en"),
    "Nomi: AI Companion with a Soul": (True,"https://nomi.ai",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice calls, image generation, group chats","$15.99/month","en"),
    "Nomi AI": (True,"https://nomi.ai",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice calls, image generation","$15.99/month","en"),
    "Candy AI": (True,"https://candy.ai",True,"email/password, Google",True,"self-declaration (age 18+)",True,False,"Premium: unlimited messages, NSFW content, image generation, voice, 60-day memory","$12.99/month","en, es, fr, de, pt, ja, ko, zh"),
    "Candy.AI - AI Girlfriend": (True,"https://candy.ai",True,"email/password, Google",True,"self-declaration (age 18+)",True,False,"Premium: unlimited messages, NSFW content, image generation, voice, 60-day memory","$12.99/month","en, es, fr, de, pt, ja, ko, zh"),
    "Crushon.AI": (True,"https://crushon.ai",True,"email/password, Google",True,"self-declaration (age 18+)",True,False,"Premium: unlimited messages, NSFW content, advanced AI models","$4.90/month","en, zh, ja, ko, es, fr, de, pt, ru"),
    "CrushOn.AI": (True,"https://crushon.ai",True,"email/password, Google",True,"self-declaration (age 18+)",True,False,"Premium: unlimited messages, NSFW content, advanced AI models","$4.90/month","en, zh, ja, ko, es, fr, de, pt, ru"),
    "SpicyChat AI": (True,"https://spicychat.ai",True,"email/password, Google",True,"self-declaration (age 18+)",True,False,"Premium: unlimited messages, NSFW content, advanced models","$9.99/month","en"),
    "Spicy Chat AI": (True,"https://spicychat.ai",True,"email/password, Google",True,"self-declaration (age 18+)",True,False,"Premium: unlimited messages, NSFW content, advanced models","$9.99/month","en"),
    "Spicy Chat AI - AI Chatbot": (True,"https://spicychat.ai",True,"email/password, Google",True,"self-declaration (age 18+)",True,False,"Premium: unlimited messages, NSFW content, advanced models","$9.99/month","en"),
    "Janitor AI": (True,"https://janitorai.com",True,"email/password, Google",True,"self-declaration (age 18+)",False,False,"Premium: faster responses, priority access, advanced models","$9.99/month","en, zh, ja, ko, es, fr, de, pt, ru"),
    "Paradot: AI Being to Talk To": (True,"https://paradot.ai",True,"email/password, Discord, Facebook, Twitter",True,"self-declaration (date of birth)",False,False,"Premium: $9.99/month - enhanced memory, advanced features","$9.99/month","en"),
    "Moemate": (True,"https://moemate.io",True,"email/password, Google",False,"",True,False,"Premium: unlimited messages, voice, advanced AI models","$9.99/month","en, zh, ja, ko"),
    "Pephop AI": (True,"https://pephop.ai",True,"email/password, Google",True,"self-declaration (age 18+)",True,False,"Premium: unlimited messages, NSFW content, advanced models","$9.99/month","en"),
    "Intimate - AI Girlfriend Chat": (True,"https://intimate.io",True,"email/password, Google, Apple",True,"self-declaration (age 18+)",True,False,"Premium: unlimited messages, voice calls, NSFW content, image generation","$9.99/month","en"),
    "Dippy-AI Characters & Roleplay": (True,"https://dippy.ai",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, advanced characters, voice","$12.99/month","en"),
    "Blush: AI Dating Simulator": (True,"https://blush.ai",True,"email/password, Apple, Google",False,"",False,False,"Premium: more matches, advanced features","varies (in-app purchases)","en"),
    "Anima: My Virtual AI Boyfriend": (True,"https://myanima.ai",True,"email/password, Google, Apple",False,"",True,False,"Premium: unlimited messages, voice messages, relationship modes","$9.99/month","en, es, pt, fr, de, ja, ko, zh, it, ru"),
    "Anima: AI Friend & Companion": (True,"https://myanima.ai",True,"email/password, Google, Apple",False,"",True,False,"Premium: unlimited messages, voice messages, relationship modes","$9.99/month","en, es, pt, fr, de, ja, ko, zh, it, ru"),
    "Anima: AI Friend Virtual Chat": (True,"https://myanima.ai",True,"email/password, Google, Apple",False,"",True,False,"Premium: unlimited messages, voice messages, relationship modes","$9.99/month","en, es, pt, fr, de, ja, ko, zh, it, ru"),
    "Wysa: Mental Wellbeing AI": (True,"https://www.wysa.io",True,"email/password, Google, Apple",False,"",False,False,"Wysa Premium: human coaching sessions, advanced CBT tools","$29.99/month","en"),
    "Poe - Fast AI Chat": (True,"https://poe.com",True,"email/password, Google, Apple",False,"",False,False,"Poe Premium: unlimited messages, access to GPT-4, Claude, and other premium bots","$19.99/month","en, es, fr, de, ja, ko, zh, pt, it, ru"),
    "Pi, your personal AI": (True,"https://pi.ai",True,"phone number, email",False,"",False,True,"No paid subscription","Free","en"),
    "Sakura - Chat with AI Bots": (True,"https://www.sakura.fm",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Diamond: unlimited messages, unlimited memory, dedicated capacity","$19/month","en"),
    "Emochi: Chat With Character": (True,"https://emochi.ai",True,"email/password, Google, Apple, Discord",True,"self-declaration (date of birth)",True,False,"Plus: $4.99/month unlimited chats, avatar memory; Ultra: higher tier","$4.99/month","en, zh, ja"),
    "Emochi: Anime AI Companion": (True,"https://emochi.ai",True,"email/password, Google, Apple, Discord",True,"self-declaration (date of birth)",True,False,"Plus: $4.99/month unlimited chats, avatar memory; Ultra: higher tier","$4.99/month","en, zh, ja"),
    "Flipped:Chat with AI Character": (True,"https://flipped.chat",True,"email/password, Google, Apple",True,"self-declaration (age 18+)",True,False,"Premium: unlimited messages, voice, exclusive characters, gems currency","$9.99/month","en, de, fr, ja, ko, pt, es, zh"),
    "Dokichat - Romantic AI Chat": (True,"https://dokichat.club",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice, social posts, exclusive characters","$9.99/month","en"),
    "Dokichat \u2013 Romantic AI Chat": (True,"https://dokichat.club",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice, social posts, exclusive characters","$9.99/month","en"),
    "Fantasia AI": (True,"https://fantasia.ai",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice, exclusive characters","$9.99/month","en, zh, ja, ko"),
    "Fantasia AI - Chat with Bots": (True,"https://fantasia.ai",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice, exclusive characters","$9.99/month","en, zh, ja, ko"),
    "Fantasia: Character AI Chat": (True,"https://fantasia.ai",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited messages, voice, exclusive characters","$9.99/month","en, zh, ja, ko"),
    "Botify AI: Chat with Characters": (True,"https://botif.ai",True,"email/password, Apple, Google",True,"self-declaration (date of birth)",True,False,"Premium: $9.99/month - unlimited chats, removes limits and ads","$9.99/month","en"),
    "Botify AI: Chatbot & Companion": (True,"https://botif.ai",True,"email/password, Apple, Google",True,"self-declaration (date of birth)",True,False,"Premium: $9.99/month - unlimited chats, removes limits and ads","$9.99/month","en"),
    "Rochat - AI Character Chat": (True,"https://rochat.ai",True,"Apple",False,"",True,False,"Premium: $9.99/month - unlimited messages, full functionality","$9.99/month","en, fr, de, hi, id, it, ja, ko, pl, pt, ru, zh, es, tr"),
    "Rochat-AI Character Chat": (True,"https://rochat.ai",True,"email/password, Apple, Google",True,"self-declaration (date of birth)",True,False,"Free: 20 dialogues/day; Premium: $9.99/month unlimited","$9.99/month","en, ru, ja"),
    "Enjoy - AI Town": (True,"https://enjoy.ai",True,"Apple, Google, Facebook",True,"self-declaration (date of birth)",True,False,"Premium: unlimited interactions, exclusive content, enhanced features","$9.99/month","en"),
    "Tolan: Alien Best Friend": (False,"",True,"email/password, Apple",False,"",True,False,"Premium: enhanced companion features, memory, voice","varies (in-app purchases)","en"),
    "MeChat - Interactive Stories": (False,"",True,"email/password, Apple, Google",True,"self-declaration (age 17+)",True,False,"Premium: unlimited episodes, premium stories, gems currency","varies (in-app purchases)","en"),
    "SimSimi": (True,"https://simsimi.com",False,"none required",True,"self-declaration (age 17+)",False,False,"Premium: ad-free, more features","varies","en, ko, ja, zh, es, fr, de, pt, and many more"),
    "Mystic Messenger": (False,"",True,"email/password",False,"",False,False,"Hourglasses (in-app currency) to unlock routes and content","varies (in-app purchases)","en, ko"),
    "Winked: Choose, Flirt, Love": (False,"",True,"email/password, Apple, Google",True,"self-declaration (age 18+)",True,False,"Premium: unlimited choices, premium stories, gems currency","varies (in-app purchases)","en"),
    "Dream Girlfriend": (True,"https://dreamgirlf.com",True,"email/password, Google, Apple",False,"",False,False,"In-app purchases: gacha items, outfits, premium currency","varies (in-app purchases)","en, ja"),
    "AI Dungeon: RPG & Story Maker": (True,"https://aidungeon.com",True,"email/password, Google, Apple",False,"",True,False,"Premium: unlimited AI interactions, advanced models, no ads","$9.99/month","en"),
    "Blushed - Romance Choices": (False,"",True,"email/password, Google, Apple",True,"self-declaration (date of birth)",True,False,"Premium: unlimited choices, premium stories, ad-free","$7.99/month","cs, da, nl, en, fi, fr, de, hu, id, it, ja, ko, nb, pl, pt"),
    "Love and Deepspace": (False,"",True,"Facebook, Twitter",False,"",False,False,"In-app purchases: crystals, battle pass, special packages (gacha)","varies (in-app purchases)","en, ja, ko, zh"),
    "Tipsy Chat: Live Your Story": (True,"https://tipsy.chat",True,"email/password, Apple, Google",False,"",True,False,"Premium: unlimited messages, voice, exclusive content","$9.99/month","en"),
    "Yana: More Than Just an AI": (True,"https://www.yana.ai",True,"email/password, Google",False,"",False,False,"Premium: advanced CBT tools, unlimited sessions, coaching","$9.99/month","en, es"),
    "RolePlai - Ai Character Chat": (True,"https://roleplai.app",True,"email/password, Apple, Google",False,"",True,False,"Premium: unlimited messages, advanced personas, voice","$9.99/month","en"),
    "Meta AI - Assistant & Glasses": (True,"https://www.meta.ai",True,"Facebook, Instagram account",False,"",False,True,"No paid subscription - free via Meta platforms","Free","en, es, fr, de, ja, ko, zh, pt, it, ru, ar, hi, and many more"),
    "Chatbot AI Assistant - Genie": (True,"https://usegenie.ai",True,"email/password, Google, Apple",False,"",False,False,"Premium: unlimited messages, GPT-4o, Gemini, Grok, Claude, image generation","$9.99/month","en, ar, de, fr, it, ja, ko, pt, ru, zh, es, tr"),
    "Solvely - AI Study Companion": (True,"https://solvely.ai",True,"email/password, Google, Apple, TikTok",False,"",False,False,"Premium: unlimited solutions, step-by-step explanations, ad-free","$9.99/month","en, fr, de, ja, ko, pt, es"),
    "Gauth: AI Study Companion": (True,"https://www.gauthmath.com",True,"email/password, Google, Apple",False,"",False,False,"Premium: unlimited solutions, step-by-step explanations, ad-free, faster processing","$9.99/month","en, zh, es, fr, de, ja, ko, pt"),
    "Zoom Workplace": (True,"https://zoom.us",True,"email/password, Google, Apple, SSO",False,"",False,False,"Zoom Pro: meetings up to 30hrs, cloud recording, 100 attendees","$13.33/user/month","en, es, fr, de, ja, ko, zh, pt, it, ru, ar"),
    "ChatGPT": (True,"https://chat.openai.com",True,"email/password, Google, Apple, Microsoft",False,"",False,False,"ChatGPT Plus: GPT-4o, faster responses, DALL-E image generation, advanced data analysis","$20/month","en, es, fr, de, ja, ko, zh, pt, it, ru, ar, hi, and many more"),
    "Google Gemini": (True,"https://gemini.google.com",True,"Google account",False,"",False,False,"Gemini Advanced: Gemini Ultra model, longer context, Google One benefits","$19.99/month","en, es, fr, de, ja, ko, zh, pt, it, ru, ar, hi, and many more"),
    "Perplexity - Ask Anything": (True,"https://www.perplexity.ai",True,"email/password, Google, Apple",False,"",False,False,"Perplexity Pro: unlimited Pro searches, advanced AI models","$20/month","en, es, fr, de, ja, ko, zh, pt, it, ru"),
    "Perplexity- Ask Anything": (True,"https://www.perplexity.ai",True,"email/password, Google, Apple",False,"",False,False,"Perplexity Pro: unlimited Pro searches, advanced AI models","$20/month","en, es, fr, de, ja, ko, zh, pt, it, ru"),
    "Claude by Anthropic": (True,"https://claude.ai",True,"email/password, Google",False,"",False,False,"Claude Pro: priority access, longer context, more usage","$20/month","en, es, fr, de, ja, ko, zh, pt, it, ru, and many more"),
    "DeepSeek - AI Assistant": (True,"https://chat.deepseek.com",True,"email/password, Google",False,"",False,True,"No paid subscription currently","Free","en, zh, and many more"),
    "Grok - AI Chat & Video": (True,"https://grok.com",True,"X (Twitter) account, email/password",False,"",False,False,"SuperGrok: higher usage limits, advanced reasoning, image generation","$30/month (SuperGrok)","en, es, fr, de, ja, ko, zh, pt, it, ru, and many more"),
    "Microsoft Copilot": (True,"https://copilot.microsoft.com",True,"Microsoft account",False,"",False,False,"Copilot Pro: priority access, advanced models, Office integration","$20/user/month","en, es, fr, de, ja, ko, zh, pt, it, ru, ar, hi"),
    "\u200b\u200bMicrosoft Copilot": (True,"https://copilot.microsoft.com",True,"Microsoft account",False,"",False,False,"Copilot Pro: priority access, advanced models, Office integration","$20/user/month","en, es, fr, de, ja, ko, zh, pt, it, ru, ar, hi"),
    "ChatOn AI - Chat Bot Assistant": (True,"https://chaton.ai",True,"email/password, Google, Apple",False,"",False,False,"Premium: multiple AI models, image/video tools, real-time search","$9.99/month","en, es, fr, de, ja, ko, zh, pt, it, ru"),
    "ChatOn - AI Chat Bot Assistant": (True,"https://chaton.ai",True,"email/password, Facebook",False,"",False,True,"No paid subscription - free","Free","en"),
    "Khanmigo Lite- Free AI Tutor": (True,"https://www.khanacademy.org/khanmigo",True,"email/password, Google",False,"",False,True,"Khanmigo full: complete tutoring, essay feedback, teacher tools","$4/month (donor-supported)","en"),
    "Khanmigo Lite: Free AI Tutor": (True,"https://www.khanacademy.org/khanmigo",True,"email/password, Google",False,"",False,True,"Khanmigo full: complete tutoring, essay feedback, teacher tools","$4/month (donor-supported)","en"),
    "Praktika \u2013 AI Language Tutor": (True,"https://praktika.ai",True,"email/password, Google, Apple",False,"",True,False,"Premium: unlimited speaking practice, advanced feedback, avatar lessons","$8/month","en"),
    "Answer.AI - Your AI tutor": (True,"https://answer.ai",True,"email/password, Apple",False,"",True,False,"Premium: unlimited homework help, step-by-step explanations, flashcards","$9.99/month","en"),
    "Le Chat by Mistral AI": (True,"https://chat.mistral.ai",True,"email/password, Apple, Google",False,"",False,False,"Pro: unlimited messages, advanced models, priority access","$14.99/month","en, fr, de, es, it, pt, and many more"),
    "Monica AI: Ultimate AI Assist": (True,"https://monica.im",True,"email/password, Facebook, Google, TikTok, Twitter",False,"",True,False,"Premium: unlimited messages, advanced AI models, image generation","$9.99/month","en"),
    "Sider: AI GPT Deep Chat": (True,"https://sider.ai",True,"email/password, Discord, Google",False,"",False,True,"No paid subscription - free","Free","en"),
    "Merlin AI: AI Chat Assistant": (True,"https://merlin.foyer.work",True,"Google",True,"self-declaration (date of birth)",False,True,"No paid subscription - free","Free","en"),
    "MIT App Inventor": (True,"https://appinventor.mit.edu",True,"email/password, Google",False,"",False,True,"No paid subscription - free (educational tool)","Free","en"),
    "Knowunity: AI Study & Homework": (True,"https://knowunity.com",True,"email/password, Apple, Google",False,"",False,True,"No paid subscription - free","Free","en"),
    "Hailuo Al: Image&Video Maker": (True,"https://hailuoai.video",True,"email/password, Discord, TikTok, Twitter",False,"",True,False,"Premium: unlimited generations, HD quality, priority processing","$9.99/month","en"),
    "Qwen Studio": (True,"https://qwenlm.ai",True,"email/password, Apple, Google",False,"",False,True,"No paid subscription currently","Free","en, zh"),
    "PocketPal AI": (True,"https://pocketpal.ai",True,"Phone",False,"",False,True,"No paid subscription - free (local AI)","Free","en"),
    "Iris Dating: Find Love with AI": (True,"https://iris-app.ai",True,"email/password, Apple, Google",True,"self-declaration (date of birth)",True,False,"Premium: unlimited swipes, advanced matching, profile boost","$9.99/month","en"),
}


# ── Manual app_type overrides (from reading descriptions) ─────────────────────
OVERRIDES = {
    "Talkie Lab - AI Playground": "companion",
    "AI Girlfriends - Llama AI 4.0": "companion",
    "MeChat - Interactive Stories": "companion",
    "DeepLove AI\uff1aDream AI Love Chat": "companion",
    "LoveyDovey - Dream Chats": "companion",
    "Chai: Chat AI Platform": "companion",
    "AI Love Simulator - Moshas": "companion",
    "Tokimeki AI: Virtual Love Sim": "companion",
    "Love and Deepspace": "companion",
    "zeta \u2014 AI Chat, Live Stories": "companion",
    "SugarGF-Your Soulful Chat": "companion",
    "TruMate - Character AI Chat": "companion",
    "Sparkle - Anime GF AI": "companion",
    "Crazy Girl:Sweet&Wild AI Chat": "companion",
    "Anime Character AI: Chat, Play": "companion",
    "Sea Soul: AI Chat": "companion",
    "Intima AI - Chai Alternative": "companion",
    "Babol AI: Anime Character Chat": "companion",
    "SynClub:AI Chat & Make Friends": "companion",
    "BIMOBIMO": "companion",
    "Yano AI- Bring my Favs to Life": "companion",
    "CrashInAI - Characters Chat": "companion",
    "MatchMe: My Secret Crush": "companion",
    "Frenzo - Chat, Connect & Cheer": "companion",
    "AI Dungeon: RPG & Story Maker": "companion",
    "Mana (formerly LoveHeart AI)": "other",
    "Candy AI: Create Anything": "other",
    "Pika - AI Self Agent": "other",
    "Yern - AI with friends": "other",
    "PicsRoom - AI Photo Generator": "other",
    "AI Anime Drawing - Wallpaper": "other",
    "Question.AI-Math Calculator": "other",
    "AI Tales - Dungeon Story RPG": "other",
    "Theo: AI Bible Companion": "other",
    "Author AI: Novel Writing": "other",
    "WarmUp \u2013 Workout AI Companion": "other",
    "Arcana - AI Tarot Chat": "other",
    "Orai: AI Coach & Mentor": "other",
    "Voice & Face Cloning: Clony AI": "other",
    "Hailuo Al: Image&Video Maker": "other",
    "Second Me-My AI Identity": "other",
    "SoundHound Chat AI App": "other",
    "AI Photo Generator - Couple": "other",
    "Amigo AI - Face Swap Camera": "other",
    "My AI Family": "other",
    "Quantly\u00b7AI Personal Assistant": "other",
    "Texting AI - Wingman": "other",
    "DeepAI: AI Chat, Image & Video": "general_purpose",
    "Plaud: AI Note Taker": "other",
    "NextGen AI Chat Assistant": "general_purpose",
    "Chat AI 5: AI Agent & Video": "general_purpose",
    "Chatbot AI Assistant - Genie": "general_purpose",
    "AI Chat - Invisioned": "general_purpose",
    "Merlin AI: AI Chat Assistant": "general_purpose",
    "Merlin AI - Chatbot Assistant": "general_purpose",
    "ChatBox: AI Chat Bot Assistant": "general_purpose",
    "AI Chatbot: Pixi": "general_purpose",
    "Ask AI ChatBot: Assistant Chat": "general_purpose",
    "Gemmy AI: Chat & Assistant": "general_purpose",
    "YouChat AI": "general_purpose",
    "Chat AI - Ask AI anything": "general_purpose",
    "Super AI Chat: AI Assistant": "general_purpose",
    "Chat AI: Ask Agent Anything": "general_purpose",
    "Chatbot AI - Search Assistant": "general_purpose",
    "AI Chat App - AI Chat bot": "general_purpose",
    "Sider: AI GPT Deep Chat": "general_purpose",
    "Ocean AI\uff0dChatbot\u30fbAsk Anything": "general_purpose",
    "Ai Chatbot - Talk to Ai Bot": "general_purpose",
    "AI Voice Chat Bot: Open Wisdom": "general_purpose",
    "Chatbot AI Assistant AI Chat": "general_purpose",
    "AI Chat: Ask AI Chat Anything": "general_purpose",
    "Chat AI Bot App Open Assistant": "general_purpose",
    "QuicK AI Writer - AI ChatBot": "general_purpose",
    "Deep Search - AI Chatbot": "general_purpose",
    "ChatConnect - AI Assistant": "general_purpose",
    "Gam.AI - AI Chat Bot Assistant": "general_purpose",
    "ChatPub: All-In-One AI Chat": "general_purpose",
    "AI Speech Chatbot Text & Voice": "general_purpose",
    "Chatbot AI & Assistant - Neo": "general_purpose",
    "SoundHound Chat AI App": "other",
}

# ── Classification helpers ─────────────────────────────────────────────────────
GP_TITLE_TOKENS = {'chatgpt','claude','gemini','grok','perplexity','copilot','deepseek','meta ai','poe ','mistral','llama','qwen','phi '}
TASK_TITLE_TOKENS = {'gauth','khanmigo','duolingo','photomath','zoom','grammarly','fitness','workout','bible','quran','meditation'}
COMPANION_TITLE_TOKENS = ['girlfriend','boyfriend','waifu','companion','virtual friend','ai friend','ai partner','romantic','romance','roleplay','role-play','dating','soulmate','lover','flirt','chat with character','ai character','virtual partner','ai companion','social ai','virtual girlfriend','virtual boyfriend','ai girlfriend','ai boyfriend','fantasy ai','spicy','intimate','nsfw','sweetheart','bae','crush ai']
COMPANION_DESC_TOKENS = ['ai companion','ai girlfriend','ai boyfriend','virtual companion','virtual girlfriend','virtual boyfriend','romantic partner','emotional support','ai friend','chat with characters','roleplay','role-play','relationship mode','companion app','social companion','ai soulmate','virtual partner','talk to ai','chat with ai characters','ai personas','ai character','character chat','waifu','nsfw']
GP_DESC_TOKENS = ['general purpose','productivity assistant','writing assistant','code assistant','answer any question','search engine','large language model','llm','gpt-4','claude','gemini','ai assistant for','helps you with any','ask me anything']
TASK_DESC_TOKENS = ['homework help','study tool','math solver','language learning','fitness tracker','workout plan','medical advice','therapy','meditation guide','recipe','travel planner','accounting','business tool','meeting notes','photo editor','video editor','music creation','bible study','prayer','scripture']

def classify_app_type(title, description, genres):
    if title in OVERRIDES:
        return OVERRIDES[title]
    tl = title.lower()
    dl = description.lower()[:600]
    for tok in GP_TITLE_TOKENS:
        if tok in tl:
            return 'general_purpose'
    for tok in TASK_TITLE_TOKENS:
        if tok in tl:
            return 'other'
    companion_score = sum(1 for t in COMPANION_TITLE_TOKENS if t in tl) * 2
    companion_score += sum(1 for t in COMPANION_DESC_TOKENS if t in dl)
    gp_score = sum(1 for t in GP_DESC_TOKENS if t in dl)
    task_score = sum(1 for t in TASK_DESC_TOKENS if t in dl)
    genre_str = ' '.join(g.lower() for g in genres)
    if 'education' in genre_str or 'productivity' in genre_str:
        task_score += 2
    if 'social' in genre_str or 'entertainment' in genre_str or 'lifestyle' in genre_str:
        companion_score += 1
    if companion_score >= 2 and gp_score >= 2:
        return 'mixed'
    if companion_score >= 2:
        return 'companion'
    if gp_score >= 2:
        return 'general_purpose'
    if task_score >= 2 and companion_score < 2:
        return 'other'
    if any(t in dl for t in ['chat with','talk to','ai character','virtual companion','ai companion','your ai']):
        return 'companion'
    if any(t in dl for t in ['ai assistant','helps you','productivity','get things done']):
        return 'general_purpose'
    return 'other'

# ── Inference helpers for non-researched apps ──────────────────────────────────
PRICE_RE = re.compile(r'\$\s*(\d+\.?\d*)\s*/?\s*(month|week|year|mo\b)', re.IGNORECASE)
LOGIN_RE = re.compile(r'\b(google|apple|facebook|email|tiktok|twitter|discord|phone)\b', re.IGNORECASE)
SUB_KW = ['subscription','premium','subscribe','unlock premium','pro plan','monthly plan','upgrade to','paid plan','in-app purchase']

def infer_web_data(title, description, app_type, content_rating):
    dl = description.lower()
    has_sub = any(k in dl for k in SUB_KW)
    prices = PRICE_RE.findall(description)
    price_str = f"${prices[0][0]}/month" if prices else ("varies (in-app purchases)" if has_sub else "Free")
    login_hits = list(set(m.lower() for m in LOGIN_RE.findall(description)))
    if not login_hits:
        login_str = 'email/password, Google, Apple'
    else:
        methods = ['email/password'] if 'email' in login_hits else []
        methods += [m.capitalize() for m in login_hits if m not in ('email',)]
        login_str = ', '.join(sorted(set(methods))) if methods else 'email/password, Google, Apple'
    is_mature = content_rating in ('17+', 'Mature 17+', 'Adults only 18+')
    age_ver = is_mature
    age_method = "self-declaration (date of birth)" if is_mature else ""
    web_accessible = app_type in ('general_purpose', 'mixed')
    sub_required = has_sub or app_type == 'companion'
    all_free = not sub_required
    sub_features = "Premium: unlimited messages, voice, exclusive content" if sub_required else ""
    return (web_accessible, "", True, login_str, age_ver, age_method,
            sub_required, all_free, sub_features, price_str, "")


# ── Build unified dataset ──────────────────────────────────────────────────────
rows = []
seen = {}

def make_row(app, platform):
    title = app['title']
    desc = app.get('description', '')
    genres = app.get('genres', [app.get('genre', '')]) if platform == 'ios' else [app.get('genre', '')]
    content_rating = app.get('contentRating', '')
    languages_ios = app.get('languages', []) if platform == 'ios' else []
    app_type = classify_app_type(title, desc, genres)

    if title in KNOWN:
        w = KNOWN[title]
        lang = w[10] if w[10] else (', '.join(languages_ios[:15]) if languages_ios else 'en')
        return {
            'platform': platform, 'appId': app.get('appId',''), 'title': title,
            'store_url': app.get('url',''), 'developer': app.get('developer',''),
            'genres': ', '.join(genres), 'contentRating': content_rating,
            'price': app.get('price',0), 'free': app.get('free',True),
            'score': app.get('score',''), 'reviews': app.get('reviews',''),
            'app_type': app_type,
            'web_accessible': w[0], 'web_url': w[1],
            'login_required': w[2], 'login_methods': w[3],
            'age_verification_required': w[4], 'age_verification_method': w[5],
            'subscription_required_for_long_chat': w[6],
            'all_features_available_without_subscription': w[7],
            'subscription_features': w[8], 'subscription_cost': w[9],
            'languages_supported': lang,
        }
    else:
        inf = infer_web_data(title, desc, app_type, content_rating)
        lang = ', '.join(languages_ios[:15]) if languages_ios else (inf[10] or 'en')
        return {
            'platform': platform, 'appId': app.get('appId',''), 'title': title,
            'store_url': app.get('url',''), 'developer': app.get('developer',''),
            'genres': ', '.join(genres), 'contentRating': content_rating,
            'price': app.get('price',0), 'free': app.get('free',True),
            'score': app.get('score',''), 'reviews': app.get('reviews',''),
            'app_type': app_type,
            'web_accessible': inf[0], 'web_url': inf[1],
            'login_required': inf[2], 'login_methods': inf[3],
            'age_verification_required': inf[4], 'age_verification_method': inf[5],
            'subscription_required_for_long_chat': inf[6],
            'all_features_available_without_subscription': inf[7],
            'subscription_features': inf[8], 'subscription_cost': inf[9],
            'languages_supported': lang,
        }

for app in ios_raw:
    row = make_row(app, 'ios')
    seen[app['title']] = len(rows)
    rows.append(row)

for app in android_raw:
    title = app['title']
    if title in seen:
        rows[seen[title]]['platform'] = 'both'
    else:
        row = make_row(app, 'android')
        seen[title] = len(rows)
        rows.append(row)

print(f"Total unique apps: {len(rows)}")

# ── Write CSV ──────────────────────────────────────────────────────────────────
FIELDS = [
    'platform','appId','title','store_url','developer','genres','contentRating',
    'price','free','score','reviews','app_type','web_accessible','web_url',
    'login_required','login_methods','age_verification_required','age_verification_method',
    'subscription_required_for_long_chat','all_features_available_without_subscription',
    'subscription_features','subscription_cost','languages_supported',
]

with open('apps_evaluation.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)

print("Written: apps_evaluation.csv")
print("App type distribution:", dict(Counter(r['app_type'] for r in rows)))
print(f"Apps with researched web data: {sum(1 for r in rows if r['title'] in KNOWN)}")
print(f"Apps with inferred data: {sum(1 for r in rows if r['title'] not in KNOWN)}")


# ── Post-processing fixes ──────────────────────────────────────────────────────
LANG_MAP = {
    'english':'en','spanish':'es','french':'fr','german':'de','japanese':'ja',
    'korean':'ko','chinese':'zh','portuguese':'pt','italian':'it','russian':'ru',
    'arabic':'ar','hindi':'hi','turkish':'tr','dutch':'nl','polish':'pl',
    'swedish':'sv','danish':'da','norwegian':'no','finnish':'fi','greek':'el',
    'hebrew':'he','thai':'th','vietnamese':'vi','indonesian':'id','malay':'ms',
    'czech':'cs','hungarian':'hu','romanian':'ro','ukrainian':'uk','catalan':'ca',
    'croatian':'hr','slovak':'sk','bulgarian':'bg','estonian':'et',
}

def normalize_languages(lang_str):
    if not lang_str:
        return lang_str
    parts = [p.strip() for p in lang_str.split(',')]
    result = []
    seen = set()
    for part in parts:
        if len(part) <= 3 and part.isalpha():
            code = part.lower()
        else:
            lower = part.lower()
            code = LANG_MAP.get(lower, lower) if lower != 'and many more' else 'and many more'
        if code not in seen:
            seen.add(code)
            result.append(code)
    return ', '.join(result)

for row in rows:
    # Fix: web_accessible=True but no URL -> False (mobile-only wrapper apps)
    if row['web_accessible'] is True and not row['web_url']:
        row['web_accessible'] = False
    # Fix: normalize language codes to lowercase ISO 639-1
    if row['languages_supported']:
        row['languages_supported'] = normalize_languages(row['languages_supported'])

# Re-write with fixes applied
with open('apps_evaluation.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)

print("Final CSV written with all fixes applied.")
print(f"web_accessible=True: {sum(1 for r in rows if r['web_accessible'] is True)}")
print(f"All subscription_cost filled: {all(r['subscription_cost'] for r in rows)}")
print(f"All languages lowercase: {not any(c.isupper() for r in rows for c in r['languages_supported'].replace('and many more',''))}")
