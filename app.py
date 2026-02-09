import os
import sys
import threading
import tempfile
import uuid
from flask import Flask, request, abort, send_from_directory
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageMessage, ImageSendMessage
)
from dotenv import load_dotenv
from gemini_service import GeminiService
from image_service import ImageService

# Load env
load_dotenv()

app = Flask(__name__)

# Config
CHANNEL_ACCESS_TOKEN = os.getenv('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.getenv('CHANNEL_SECRET')

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    print("Error: LINE Channel Access Token or Secret is missing.")
    # In production, maybe exit, but for dev we might wait for .env update
    
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Services
gemini = GeminiService()
img_svc = ImageService()

# In-memory session store
# { user_id: { 'status': 'idle'|'collecting', 'location': str, 'date': str, 'images': [path, ...] } }
sessions = {}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@app.route("/static/images/<path:filename>")
def serve_image(filename):
    return send_from_directory("static/images", filename)

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    
    # Initialize session if not exists
    if user_id not in sessions:
        sessions[user_id] = {'status': 'idle', 'images': [], 'location': '', 'date': ''}
    
    session = sessions[user_id]

    if text.lower() == 'reset':
        sessions[user_id] = {'status': 'idle', 'images': [], 'location': '', 'date': ''}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="リセットしたよ！\nまた「場所」と「時期」を送ってね💖")
        )
        return

    # Status: Idle -> Start collecting info
    if session['status'] == 'idle':
        # Assume input format: "Location, Date" or just loose text
        # Simple parsing logic
        if "," in text or " " in text:
             # Very naive parsing, user can improve protocol later
            try:
                parts = text.replace("、", ",").split(",")
                if len(parts) < 2:
                    parts = text.split(" ")
                
                loc = parts[0].strip()
                date = parts[1].strip() if len(parts) > 1 else "最近"
                
                session['location'] = loc
                session['date'] = date
                session['status'] = 'collecting'
                
                reply = f"「{loc}」の「{date}」だね！把握💖\nじゃあ、写真をどんどん送って！\n送り終わったら「完了」って言ってね✨"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            except:
                line_bot_api.reply_message(
                     event.reply_token, 
                     TextSendMessage(text="場所と日時を教えて！\n例：「渋谷, 2024夏」みたいに送ってね😘")
                )
        else:
             line_bot_api.reply_message(
                 event.reply_token, 
                 TextSendMessage(text="場所と日時を教えて！\n例：「渋谷, 2024夏」みたいに送ってね😘")
            )

    elif session['status'] == 'collecting':
        if text == "完了" or text == "done":
            if len(session['images']) == 0:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="写真がまだないよ💦 送ってから「完了」してね！")
                )
                return

            # Start Processing in Thread
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"OK！{len(session['images'])}枚の写真から、最高のアルバムを作るね…🔥\n（枚数が多いと1〜2分かかるかも！ちょっと待ってて！）")
            )
            
            # Copy session data for thread
            session_data = {
                'location': session['location'],
                'date': session['date'],
                'images': session['images'][:] 
            }
            
            # Reset session immediately
            session['status'] = 'idle'
            session['images'] = []
            
            # Run background task
            thread = threading.Thread(target=generate_album_task, args=(user_id, session_data))
            thread.start()

        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="写真を送るか、「完了」って言ってね！")
            )

def generate_album_task(user_id, session_data):
    try:
        # 1. Select Best Photos (Use all for now)
        selected_paths = session_data['images']
        
        # 2. Get Captions
        captions = gemini.generate_captions(session_data['location'], session_data['date'])
        title = captions.get('title', 'Travel Memory')
        loc_romaji = captions.get('location_romaji', session_data['location'])
        
        # 3. Create Images
        pages = img_svc.create_album_pages(selected_paths, title=title, date=session_data['date'], location_romaji=loc_romaji)
        
        messages = []
        messages.append(TextSendMessage(text=f"{captions.get('comment', 'できたよー！')}\n場所: {loc_romaji}"))
        
        host_url = os.getenv("HOST_URL", "https://example.com")
        
        for i, page in enumerate(pages):
            unique_filename = f"{uuid.uuid4()}.jpg"
            output_path = os.path.join("static/images", unique_filename)
            page.save(output_path, quality=85) # slightly lower quality for speed
            
            image_url = f"{host_url}/static/images/{unique_filename}"
            messages.append(ImageSendMessage(original_content_url=image_url, preview_image_url=image_url))
        
        # Chunk messages
        def chunk_list(l, n):
            for i in range(0, len(l), n):
                yield l[i:i + n]

        for chunk in chunk_list(messages, 5):
            line_bot_api.push_message(user_id, chunk)
            
    except Exception as e:
        app.logger.error(f"Error processing album: {e}")
        try:
            line_bot_api.push_message(
                user_id,
                TextSendMessage(text="ごめん！アルバム作成中にエラーが出ちゃった💦 もう一回試してみて！")
            )
        except:
            pass

        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="写真を送るか、「完了」って言ってね！")
            )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    user_id = event.source.user_id
    if user_id not in sessions:
        sessions[user_id] = {'status': 'idle', 'images': [], 'location': '', 'date': ''}
    
    session = sessions[user_id]
    
    if session['status'] != 'collecting':
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="まずは「場所」と「日時」を教えてね！📸")
        )
        return

    # Save image
    message_content = line_bot_api.get_message_content(event.message.id)
    ext = "jpg" # Default
    # Could check content provider, but generally jpg/png
    
    tmp_filename = f"{uuid.uuid4()}.{ext}"
    tmp_path = os.path.join("tmp", tmp_filename)
    
    with open(tmp_path, 'wb') as fd:
        for chunk in message_content.iter_content():
            fd.write(chunk)
            
    session['images'].append(tmp_path)
    
    # Optional: Acknowledge every image? Or silent?
    # Sending reply for every image might be annoying if they simulate bulk upload.
    # LINE user sends 5 images -> 5 webhook events.
    # We can rely on user sending "done".
    # But usually good to give feedback occasionally? No, simpler is better.
    # Just silent logging.
    print(f"Received image for {user_id}. Count: {len(session['images'])}")


# Create dirs (Ensure these exist for Gunicorn too)
os.makedirs("tmp", exist_ok=True)
os.makedirs("static/images", exist_ok=True)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
