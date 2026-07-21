import os
import time
import threading
import logging
from datetime import datetime, timedelta
from flask import Flask, send_from_directory
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

# ---------- Setup ----------
app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5000")

logging.basicConfig(level=logging.INFO)

# ---------- Auto-cleanup: delete files older than 24 hours ----------
def cleanup_old_files():
    now = time.time()
    cutoff = now - (24 * 60 * 60)
    deleted_count = 0
    for filename in os.listdir(UPLOAD_FOLDER):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(filepath):
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                deleted_count += 1
    if deleted_count > 0:
        logging.info(f"Cleanup done: {deleted_count} files removed.")

def cleanup_scheduler():
    while True:
        cleanup_old_files()
        time.sleep(3600)

threading.Thread(target=cleanup_scheduler, daemon=True).start()

# ---------- Flask routes ----------
@app.route('/')
def wake():
    return "Bot is awake – files auto-deleted after 24h."

@app.route('/files/<filename>')
def serve_file(filename):
    if '..' in filename or '/' in filename:
        return "Invalid filename", 400
    return send_from_directory(UPLOAD_FOLDER, filename)

# ---------- Telegram bot ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    doc = update.message.document
    ext = os.path.splitext(doc.file_name)[1] or ".bin"
    unique_name = f"{int(time.time() * 1000)}{ext}"
    local_path = os.path.join(UPLOAD_FOLDER, unique_name)

    await file.download_to_drive(local_path)
    file_size_kb = doc.file_size / 1024
    public_url = f"{BASE_URL}/files/{unique_name}"

    keyboard = [
        [
            InlineKeyboardButton("📋 Copy Link", url=public_url),
            InlineKeyboardButton("🌐 Visit Website", url=BASE_URL)
        ]
    ]
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

def run_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.run_polling()

# ---------- Start both ----------
if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
