"""
OrionAI – Telegram Bot (Ultimate Edition)
Version: 4.2.0
Features: AI chat, memory, rate limits, admin broadcast, jokes, quotes, time, stats, Flask health check.
All credentials hardcoded.
"""

import asyncio
import json
import logging
import time
import random
import threading
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional

# ---------- External imports ----------
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI

# ---------- Flask for health check (Render/Heroku) ----------
try:
    from flask import Flask, jsonify
    flask_available = True
except ImportError:
    flask_available = False

# ============================================================
# 1. HARDCODED CREDENTIALS
# ============================================================
TELEGRAM_TOKEN = "8852905226:AAE9RC1LXVKKmclEdBTdUBru--atQo4c1IM"
OPENAI_API_KEY = "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"
ADMIN_ID = 7949945669   # integer

# ============================================================
# 2. CONFIGURATION
# ============================================================
MODEL = "gpt-4o-mini"
MAX_HISTORY = 15
RATE_LIMIT = 5   # messages per minute per user

# ============================================================
# 3. LOGGING
# ============================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("OrionAI")

# ============================================================
# 4. OPENAI CLIENT
# ============================================================
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ============================================================
# 5. PERSISTENT STORAGE (JSON)
# ============================================================
DATA_FILE = "orion_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"histories": {}, "user_settings": {}, "stats": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

data_cache = load_data()
user_histories: Dict[int, List[dict]] = {
    int(uid): hist for uid, hist in data_cache.get("histories", {}).items()
}
user_settings: Dict[int, dict] = {
    int(uid): settings for uid, settings in data_cache.get("user_settings", {}).items()
}
user_stats: Dict[int, dict] = {
    int(uid): stats for uid, stats in data_cache.get("stats", {}).items()
}

def persist_user(user_id: int):
    data_cache["histories"][str(user_id)] = user_histories.get(user_id, [])
    data_cache["user_settings"][str(user_id)] = user_settings.get(user_id, {})
    data_cache["stats"][str(user_id)] = user_stats.get(user_id, {})
    save_data(data_cache)

# ============================================================
# 6. RATE LIMITING
# ============================================================
rate_limit_store = defaultdict(list)

def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    timestamps = rate_limit_store[user_id]
    timestamps = [t for t in timestamps if now - t < 60]
    rate_limit_store[user_id] = timestamps
    if len(timestamps) >= RATE_LIMIT:
        return True
    timestamps.append(now)
    return False

# ============================================================
# 7. CONVERSATION MEMORY
# ============================================================
def get_user_history(user_id: int) -> List[dict]:
    if user_id not in user_histories:
        default_prompt = user_settings.get(user_id, {}).get(
            "system_prompt",
            "You are OrionAI, a brilliant, witty, and deeply thoughtful AI assistant created by Orion. Respond with clarity, creativity, and occasional cosmic metaphors."
        )
        user_histories[user_id] = [
            {"role": "system", "content": default_prompt}
        ]
        persist_user(user_id)
    return user_histories[user_id]

def trim_history(history: List[dict], max_messages: int = MAX_HISTORY) -> List[dict]:
    if len(history) > max_messages + 1:
        return [history[0]] + history[-(max_messages):]
    return history

def summarize_history(history: List[dict]) -> str:
    pairs = []
    for i in range(1, len(history), 2):
        if i+1 < len(history):
            user_msg = history[i].get("content", "")[:50]
            asst_msg = history[i+1].get("content", "")[:50]
            pairs.append(f"U: {user_msg}... | A: {asst_msg}...")
    return " | ".join(pairs[-3:])

# ============================================================
# 8. AI RESPONSE ENGINE
# ============================================================
async def get_ai_response(user_id: int, user_message: str) -> str:
    history = get_user_history(user_id)
    history.append({"role": "user", "content": user_message})
    
    if len(history) > MAX_HISTORY + 5:
        summary = summarize_history(history)
        new_history = [history[0]]
        new_history.append({"role": "assistant", "content": f"Previous conversation summary: {summary}"})
        new_history.extend(history[-5:])
        history = new_history
    
    history = trim_history(history)
    user_histories[user_id] = history
    persist_user(user_id)
    
    try:
        response = openai_client.chat.completions.create(
            model=MODEL,
            messages=history,
            temperature=0.78,
            max_tokens=1200,
            top_p=0.92,
            frequency_penalty=0.3,
            presence_penalty=0.2,
        )
        assistant_reply = response.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": assistant_reply})
        user_histories[user_id] = trim_history(history)
        persist_user(user_id)
        return assistant_reply
    except Exception as e:
        logger.error(f"OpenAI error for {user_id}: {e}")
        return "🌌 OrionAI's neural core just hiccupped. Try again in a few seconds."

# ============================================================
# 9. BUILT-IN JOKES & QUOTES
# ============================================================
JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "What did the AI say to the human? 'You had me at Hello World.'",
    "How many programmers does it take to change a light bulb? None – that's a hardware problem.",
    "Why was the computer cold? It left its Windows open.",
    "What did the router say to the doctor? 'I have a bad gateway.'",
    "Why do Python programmers wear glasses? Because they can't C#.",
    "What's a computer's favorite snack? Chips and data.",
    "Why did the developer go broke? Because he used up all his cache.",
    "What do you call a fake noodle? An impasta.",
    "Why did the AI cross the road? To optimize the chicken's path.",
    "How does a computer get drunk? It takes screenshots.",
    "What do you get when you cross a computer and a life? A reboot.",
    "Why did the programmer quit his job? He didn't get arrays.",
    "What's a robot's favorite genre? Techno.",
    "Why don't robots wear sunglasses? They already have perfect vision.",
]

QUOTES = [
    "The only way to do great work is to love what you do. – Steve Jobs",
    "In the middle of difficulty lies opportunity. – Einstein",
    "Be yourself; everyone else is already taken. – Oscar Wilde",
    "Knowledge is power. – Francis Bacon",
    "Simplicity is the ultimate sophistication. – Leonardo da Vinci",
    "The future belongs to those who believe in the beauty of their dreams. – Eleanor Roosevelt",
]

# ============================================================
# 10. COMMANDS
# ============================================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    uid = user.id
    user_histories.pop(uid, None)
    user_settings.pop(uid, None)
    persist_user(uid)
    
    welcome = f"""
✨ **ORIONAI** ✨
*Version 4.2 – The Ultimate Edition*

Greetings, **{user.first_name}**. I am OrionAI, your digital oracle.

🪐 **Capabilities:**
• AI chat with memory
• Jokes, quotes, time, stats
• Admin broadcast
• Custom system prompt

📖 **Commands:**
/start — Reset session
/help — Show help
/clear — Forget chat
/about — Tech details
/settings — Your config
/prompt <text> — Change personality
/joke — Random joke
/quote — Inspiring quote
/time — Current IST time
/stats — Your usage stats

💫 Just type anything — I'm listening.
"""
    keyboard = [[InlineKeyboardButton("🌌 GitHub", url="https://github.com/orionai")]]
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🧠 See /start for all commands. I remember last 15 messages.")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    user_histories.pop(uid, None)
    user_settings.pop(uid, None)
    persist_user(uid)
    await update.message.reply_text("🧹 Memory wiped.")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"🌟 OrionAI v4.2\nEngine: OpenAI {MODEL}\nPersistent JSON storage.\nCreated by Orion.")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    settings = user_settings.get(uid, {})
    prompt = settings.get("system_prompt", "Default")
    history_len = len(user_histories.get(uid, []))
    await update.message.reply_text(f"⚙️ Prompt: {prompt[:60]}...\nMemory size: {history_len}\nRate limit: {RATE_LIMIT}/min")

async def prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /prompt <new system prompt>")
        return
    new_prompt = " ".join(args)
    if uid not in user_settings:
        user_settings[uid] = {}
    user_settings[uid]["system_prompt"] = new_prompt
    user_histories[uid] = [{"role": "system", "content": new_prompt}]
    persist_user(uid)
    await update.message.reply_text(f"✅ Prompt updated: {new_prompt}")

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(random.choice(JOKES))

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(random.choice(QUOTES))

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now().astimezone()
    ist = now.astimezone(timezone(timedelta(hours=5, minutes=30)))  # IST
    await update.message.reply_text(f"🕐 IST: {ist.strftime('%I:%M %p, %d %b %Y')}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if uid not in user_stats:
        user_stats[uid] = {"messages": 0, "started": str(datetime.now())}
    stats = user_stats[uid]
    await update.message.reply_text(f"📊 You sent {stats.get('messages',0)} messages since {stats.get('started','N/A')}.")

# Admin broadcast
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Unauthorized.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    msg = " ".join(args)
    await update.message.reply_text(f"📢 Broadcast sent (demo): {msg}")

# ============================================================
# 11. MESSAGE HANDLER
# ============================================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    text = update.message.text
    if not text:
        return
    
    # Update stats
    if uid not in user_stats:
        user_stats[uid] = {"messages": 0, "started": str(datetime.now())}
    user_stats[uid]["messages"] = user_stats[uid].get("messages", 0) + 1
    persist_user(uid)
    
    if is_rate_limited(uid):
        await update.message.reply_text("⏳ Slow down. Wait 60s.")
        return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    reply = await get_ai_response(uid, text)
    if len(reply) > 4096:
        for chunk in [reply[i:i+4096] for i in range(0, len(reply), 4096)]:
            await update.message.reply_text(chunk)
    else:
        await update.message.reply_text(reply)

# ============================================================
# 12. FLASK HEALTH CHECK (for Render/Heroku)
# ============================================================
if flask_available:
    flask_app = Flask(__name__)
    @flask_app.route('/health')
    def health():
        return jsonify({"status": "OrionAI is alive", "time": str(datetime.now())})
    @flask_app.route('/')
    def home():
        return "OrionAI bot is running."

    def run_flask():
        flask_app.run(host='0.0.0.0', port=8080)
else:
    def run_flask():
        pass

# ============================================================
# 13. ERROR HANDLER
# ============================================================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("⚠️ Stellar anomaly. Try again.")

# ============================================================
# 14. MAIN
# ============================================================
def main():
    # Start Flask in a background thread (if available)
    if flask_available:
        thread = threading.Thread(target=run_flask, daemon=True)
        thread.start()
        logger.info("Flask health server started on port 8080.")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("prompt", prompt_command))
    app.add_handler(CommandHandler("joke", joke_command))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info("🚀 OrionAI 4.2 launched. All systems nominal.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    import os
    from datetime import timedelta, timezone
    main()
