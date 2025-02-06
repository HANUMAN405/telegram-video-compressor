import os
import requests
import subprocess
from telegram import Update
from dotenv import load_dotenv
from flask import Flask, send_from_directory
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext

# Load environment variables from .env file
load_dotenv()

# Fetch bot token and configure directories
BOT_TOKEN = os.getenv("BOT_TOKEN")
VIDEO_DIR = os.getenv("VIDEO_DIR", "./videos")
BASE_URL = os.getenv("BASE_URL", "http://localhost")

# Raise an error if BOT_TOKEN is not set
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables.")

# Create video directory if it doesn't exist
os.makedirs(VIDEO_DIR, exist_ok=True)

# Initialize Flask app
app = Flask(__name__)

@app.route('/videos/<path:filename>')
def serve_video(filename):
    return send_from_directory(VIDEO_DIR, filename)

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Send me a URL of a video, and I'll compress it for you!")

async def handle_url(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    user_id = update.message.chat_id

    # Validate URL
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("Invalid URL! Please send a valid URL.")
        return

    # Check if the URL is accessible
    try:
        response = requests.head(url, allow_redirects=True)
        if response.status_code != 200:
            await update.message.reply_text(f"URL is not accessible! Status code: {response.status_code}")
            return
        content_length = response.headers.get('content-length', 'unknown')
        await update.message.reply_text(f"URL is valid! File size: {content_length} bytes")
    except Exception as e:
        await update.message.reply_text(f"Error validating URL: {e}")
        return

    await update.message.reply_text("Downloading video... Please wait.")
    try:
        file_path = os.path.join(VIDEO_DIR, f"{user_id}_video.mp4")
        download_video(url, file_path)

        compressed_path = os.path.join(VIDEO_DIR, f"{user_id}_compressed.mp4")
        compress_video(file_path, compressed_path)

        await update.message.reply_text("Video compressed successfully!")

        # Check the size of the compressed video
        if os.path.getsize(compressed_path) > 50 * 1024 * 1024:
            download_url = f"{BASE_URL}/videos/{user_id}_compressed.mp4"
            await update.message.reply_text(
                f"The file is too large to send via Telegram. You can download it from: {download_url}"
            )
        else:
            await update.message.reply_document(document=open(compressed_path, "rb"))
    except Exception as e:
        await update.message.reply_text(f"Error processing video: {e}")

def download_video(url: str, file_path: str):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()  # Raise an error for bad responses
        with open(file_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

def compress_video(input_file: str, output_file: str):
    command = ["ffmpeg", "-y", "-i", input_file, "-vcodec", "libx264", "-crf", "32", output_file]
    subprocess.run(command, check=True)  # Ensure subprocess raises an error if FFmpeg fails

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add handlers for the bot
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    # Run Flask in a separate thread
    from threading import Thread
    flask_thread = Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 5000})
    flask_thread.start()

    # Start polling for updates
    application.run_polling()

if __name__ == "__main__":
    main()
