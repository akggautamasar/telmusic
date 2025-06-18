import os
import yt_dlp
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

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Store search results per user
SEARCH_RESULTS = {}

# Prepare downloads directory
os.makedirs("downloads", exist_ok=True)
for f in os.listdir("downloads"):
    try:
        os.remove(os.path.join("downloads", f))
    except:
        pass

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎵 Welcome! Send me a song or video name, and I'll fetch it for you.")

# When user sends song name
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    videos = yt_search(query)

    if not videos:
        await update.message.reply_text("❌ No results found.")
        return

    user_id = update.effective_user.id
    SEARCH_RESULTS[user_id] = {'query': query, 'videos': videos, 'page': 0}
    await show_video_list(update, context, user_id)

# Perform YouTube search
def yt_search(query):
    ydl_opts = {'quiet': True, 'extract_flat': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            result = ydl.extract_info(f"ytsearch20:{query}", download=False)
            return result['entries']
        except Exception as e:
            print(f"Search error: {e}")
            return []

# Show list of results with pagination
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

# When user clicks a video or paginates
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
                print(f"✅ Deleted: {file_path}")
            except Exception as e:
                print(f"❌ Error sending or deleting file: {e}")
                await context.bot.send_message(chat_id=query.message.chat_id, text="❌ Failed to send or delete the audio.")
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text="❌ Failed to download audio.")

# Download and convert to MP3
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

# Run bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 Bot running...")
    app.run_polling()
