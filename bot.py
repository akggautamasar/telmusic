import os
import yt_dlp
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from flask import Flask

# Load .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Telegram search results storage
SEARCH_RESULTS = {}

# Clean download folder
os.makedirs("downloads", exist_ok=True)
for f in os.listdir("downloads"):
    try:
        os.remove(os.path.join("downloads", f))
    except:
        pass

# Flask app
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "Bot is running!"

# Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎵 Send a song or video name to fetch it!")

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
        await query.edit_message_text(f"🎧 Downloading audio for:\n{video['title']}")

        file_path = await download_audio(url)
        if file_path:
            try:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=open(file_path, 'rb'))
                os.remove(file_path)
            except Exception as e:
                print(f"❌ Error sending/deleting: {e}")
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

# Async run function for both Flask and Bot
async def main():
    from telegram.ext import Application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Start Telegram bot polling
    print("🤖 Bot running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

# Entry point
if __name__ == "__main__":
    import threading

    # Run Flask in a separate thread
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8000)).start()

    # Run async bot
    asyncio.run(main())
