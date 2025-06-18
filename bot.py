import os
import threading
import yt_dlp
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

SEARCH_RESULTS = {}
app_flask = Flask(__name__)

# Flask dummy route
@app_flask.route("/")
def health():
    return "Bot is alive", 200

# Telegram Bot Functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎵 Welcome! Send me a song or video name, and I'll fetch it for you.")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    videos = yt_search(query)
    if not videos:
        await update.message.reply_text("❌ No results found.")
        return
    user_id = update.effective_user.id
    SEARCH_RESULTS[user_id] = {'query': query, 'videos': videos, 'page': 0}
    await show_video_list(update, context, user_id)

def yt_search(query):
    ydl_opts = {'quiet': True, 'extract_flat': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            result = ydl.extract_info(f"ytsearch20:{query}", download=False)
            return result['entries']
        except Exception as e:
            print(f"Search error: {e}")
            return []

async def show_video_list(update, context, user_id):
    page = SEARCH_RESULTS[user_id]['page']
    videos = SEARCH_RESULTS[user_id]['videos']
    items_per_page = 5
    start = page * items_per_page
    end = start + items_per_page

    if start >= len(videos):
        await update.message.reply_text("⚠️ No more results.")
        return

    buttons = []
    for i, video in enumerate(videos[start:end], start=start):
        title = video.get('title', 'No Title')
        buttons.append([InlineKeyboardButton(f"{title[:50]}", callback_data=f"select_{i}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="prev"))
    if end < len(videos):
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data="next"))

    if nav_buttons:
        buttons.append(nav_buttons)

    await update.message.reply_text(
        f"🎬 Results for '{SEARCH_RESULTS[user_id]['query']}' (Page {page+1})",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer()

    if user_id not in SEARCH_RESULTS:
        await query.edit_message_text("❗ Session expired. Please search again.")
        return

    if query.data == "next":
        SEARCH_RESULTS[user_id]['page'] += 1
        await show_video_list(query, context, user_id)
    elif query.data == "prev":
        SEARCH_RESULTS[user_id]['page'] -= 1
        await show_video_list(query, context, user_id)
    elif query.data.startswith("select_"):
        index = int(query.data.split("_")[1])
        video = SEARCH_RESULTS[user_id]['videos'][index]
        url = f"https://www.youtube.com/watch?v={video['id']}"
        await query.edit_message_text(f"🎧 Downloading audio for: {video['title'][:70]}")

        file_path = await download_audio(url)
        if file_path:
            try:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=open(file_path, 'rb'))
                os.remove(file_path)
            except Exception as e:
                await context.bot.send_message(chat_id=query.message.chat_id, text="❌ Failed to send audio.")
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text="❌ Failed to download audio.")

async def download_audio(url):
    try:
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
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            return filename if os.path.exists(filename) else None
    except Exception as e:
        print(f"Download error: {e}")
        return None

def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 Bot running in background...")
    app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host="0.0.0.0", port=port)
