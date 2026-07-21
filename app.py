import os
import time
import logging
import json
import asyncio
import threading
from flask import Flask, request, send_from_directory
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup

# ---------- HARDCODED CONFIG ----------
BOT_TOKEN = "8844521685:AAHNqPD2iuzhZt73Gn0W9CXJKtRUvJ4NK0E"
BASE_URL = "https://mediahosting.onrender.com"
WEBHOOK_URL = f"{BASE_URL}/webhook"
# -------------------------------------

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

bot = Bot(token=BOT_TOKEN)
logging.basicConfig(level=logging.INFO)

# ---------- Auto-cleanup: delete files older than 24 hours ----------
def cleanup_old_files():
    now = time.time()
    cutoff = now - 24 * 60 * 60
    for filename in os.listdir(UPLOAD_FOLDER):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(filepath) and os.path.getmtime(filepath) < cutoff:
            os.remove(filepath)
            logging.info(f"Deleted old file: {filename}")

def cleanup_scheduler():
    while True:
        cleanup_old_files()
        time.sleep(3600)  # every hour

threading.Thread(target=cleanup_scheduler, daemon=True).start()

# ---------- Flask Routes ----------
@app.route('/')
def wake():
    cleanup_old_files()
    return "Bot is awake – webhook active."

@app.route('/files/<filename>')
def serve_file(filename):
    if '..' in filename or '/' in filename:
        return "Invalid filename", 400
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/webhook', methods=['POST'])
def webhook():
    if not request.is_json:
        return "Bad request", 400
    data = request.get_json()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(process_update(data))
    finally:
        loop.close()
    return "OK", 200

# ---------- Update Handlers ----------
async def process_update(data):
    update = Update.de_json(data, bot)
    if not update.message:
        return

    if update.message.text and update.message.text.startswith('/start'):
        await start(update)
    elif update.message.document:
        await handle_document(update)
    # you can add more handlers (URL upload, /speedtest) later

async def start(update):
    welcome_text = (
        "✨ Welcome to AR Uploader & Hosting ✨\n\n"
        "🚀 All-in-One Cloud Companion\n"
        "Easily transfer files from direct links to Telegram, or generate shareable direct links via AR Hosting instantly!\n\n"
        "🛠 Available Features:\n"
        "├ 🔗 URL Uploader: Send any link (up to 50MB) to upload directly to Telegram\n"
        "├ 🌐 AR Cloud Hosting: Send media (up to 20MB) to get a high-speed direct link\n"
        "├ ⚡️ Speed Diagnostics: Run /speedtest to check bot server speed\n"
        "└ 📄 Smart Detection: Auto-extracts metadata & extension"
    )
    await update.message.reply_text(welcome_text)

async def handle_document(update):
    doc = update.message.document
    file_obj = await bot.get_file(doc.file_id)
    ext = os.path.splitext(doc.file_name)[1] or ".bin"
    unique_name = f"{int(time.time() * 1000)}{ext}"
    local_path = os.path.join(UPLOAD_FOLDER, unique_name)

    await file_obj.download_to_drive(local_path)
    file_size_kb = doc.file_size / 1024
    public_url = f"{BASE_URL}/files/{unique_name}"

    keyboard = [[
        InlineKeyboardButton("📋 Copy Link", url=public_url),
        InlineKeyboardButton("🌐 Visit Website", url=BASE_URL)
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    reply = (
        f"✅ Cloud Host Success\n"
        f"Filename: {doc.file_name}\n"
        f"Size: {file_size_kb:.2f} KB\n"
        f"Mime Type: {doc.mime_type}\n\n"
        f"Direct Link: {public_url}\n\n"
        f"⏳ This file will be deleted automatically in 24 hours."
    )
    await update.message.reply_text(reply, reply_markup=reply_markup)

# ---------- Set webhook on startup ----------
def set_webhook():
    try:
        bot.set_webhook(WEBHOOK_URL)
        logging.info(f"Webhook set to {WEBHOOK_URL}")
    except Exception as e:
        logging.error(f"Webhook failed: {e}")

# ---------- Run ----------
if __name__ == "__main__":
    cleanup_old_files()
    set_webhook()          # set webhook once at startup
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))