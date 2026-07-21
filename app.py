import os
import time
import threading
from flask import Flask, send_from_directory, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5000")

# ---------- Auto-cleanup: keep disk under 900 MB ----------
MAX_DISK_USAGE_MB = 900

def cleanup_if_needed():
    total_size = 0
    files = []
    for f in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, f)
        size = os.path.getsize(path)
        total_size += size
        files.append((path, size, os.path.getctime(path)))
    
    total_mb = total_size / (1024 * 1024)
    if total_mb > MAX_DISK_USAGE_MB:
        # Sort by oldest first
        files.sort(key=lambda x: x[2])
        for path, size, _ in files:
            os.remove(path)
            total_size -= size
            if total_size / (1024 * 1024) < MAX_DISK_USAGE_MB * 0.8:
                break

# ---------- Flask routes ----------
@app.route('/')
def wake():
    return "Bot is awake!"

@app.route('/files/<filename>')
def serve_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ---------- Telegram bot ----------
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_if_needed()  # Clean before saving new file
    
    file = await update.message.document.get_file()
    doc = update.message.document
    ext = os.path.splitext(doc.file_name)[1] or ".bin"
    unique_name = f"{int(time.time() * 1000)}{ext}"
    local_path = os.path.join(UPLOAD_FOLDER, unique_name)
    
    await file.download_to_drive(local_path)
    
    public_url = f"{BASE_URL}/files/{unique_name}"
    
    # Inline keyboard: Copy Link + Visit Website
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
        f"Size: {doc.file_size / 1024:.2f} KB\n"
        f"Mime Type: {doc.mime_type}\n\n"
        f"Direct Link: {public_url}"
    )
    await update.message.reply_text(reply, reply_markup=reply_markup)

def run_bot():
    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app_bot.run_polling()

# ---------- Start both ----------
if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
