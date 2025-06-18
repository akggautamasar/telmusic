import os
import yt_dlp
import threading
from flask import Flask
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SEARCH_RESULTS = {}

# Flask setup
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "✅ Bot is running on Koyeb!"

# Telegram handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send a song name to download its audio.")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    videos = yt_search(query)
    if not videos:
        await update.message.reply_text("❌ No results found.")
        return

    user_id = update.effective_user.id
    SEARCH_RESULTS[user_id] = {'query': query, 'videos': videos, 'page': 0}
    await show_results(update, context, user_id)

def yt_search(query):
    ydl_opts = {'quiet': True, 'extract_flat': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch10:{query}", download=False)
            return result['entries']
    except Exception as e:
        print(f"Search error: {e}")
        return []

async def show_results(update, context, user_id):
    videos = SEARCH_RESULTS[user_id]['videos']
    page = SEARCH_RESULTS[user_id]['page']
    start = page * 5
    end = start + 5

    buttons = []
    for i, video in enumerate(videos[start:end], start=start):
        title = video.get('title', 'No Title')[:50]
        buttons.append([InlineKeyboardButton(title, callback_data=f"select_{i}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="prev"))
    if end < len(videos):
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data="next"))
    if nav_buttons:
        buttons.append(nav_buttons)

    await update.message.reply_text(
        f"Results for '{SEARCH_RESULTS[user_id]['query']}' (Page {page+1})",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if user_id not in SEARCH_RESULTS:
        await query.edit_message_text("Session expired. Send query again.")
        return

    if query.data == "next":
        SEARCH_RESULTS[user_id]['page'] += 1
        await show_results(query, context, user_id)
    elif query.data == "prev":
        SEARCH_RESULTS[user_id]['page'] -= 1
        await show_results(query, context, user_id)
    elif query.data.startswith("select_"):
        index = int(query.data.split("_")[1])
        video = SEARCH_RESULTS[user_id]['videos'][index]
        url = f"https://www.youtube.com/watch?v={video['id']}"

        await query.edit_message_text(f"⬇️ Downloading audio: {video['title']}")
        file_path = await download_audio(url)
        if file_path:
            try:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=open(file_path, 'rb'))
                os.remove(file_path)
            except Exception as e:
                print(f"Send error: {e}")
                await context.bot.send_message(chat_id=query.message.chat_id, text="❌ Failed to send file.")
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text="❌ Download failed.")

async def download_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            return filename if os.path.exists(filename) else None
    except Exception as e:
        print(f"Download error: {e}")
        return None

# ✅ MAIN without asyncio.run
def run_flask():
    flask_app.run(host="0.0.0.0", port=8000)

def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 Telegram bot started...")
    app.run_polling()  # No await or asyncio.run here

# Entry point
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()
