import os
import time
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, Response, session, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from google import genai
from google.genai import types

load_dotenv()
# ALLOW GOOGLE OAUTH TO WORK ON LOCAL HTTP SERVER


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-fallback-key")

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    access_token_url='https://oauth2.googleapis.com/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={'scope': 'openid email profile'},
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
)

db_url = os.environ.get("DATABASE_URL", "sqlite:///instance.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ORIGINAL SAFE DATABASE STRUCTURE (No user_email)
class TrainingData(db.Model):
    __tablename__ = 'training_data'
    id = db.Column(db.Integer, primary_key=True)
    prompt = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

def save_to_database(prompt, response, lang):
    try:
        new_log = TrainingData(prompt=prompt, response=response, language=lang)
        db.session.add(new_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"❌ Cloud Sync Error: {e}")

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=GEMINI_API_KEY)

@app.route('/')
def entrance():
    if 'user' in session:
        return redirect('/workspace')
    return render_template('login.html')


@app.route('/manual-login', methods=['POST'])
def manual_login():
    username = request.form.get('username')
    password = request.form.get('password')

    # Securely load admin credentials from your .env file
    secure_admin_user = os.getenv("ADMIN_USERNAME")
    secure_admin_pass = os.getenv("ADMIN_PASSWORD")

    # Verify against the hidden variables
    if username == secure_admin_user and password == secure_admin_pass:
        session['user'] = {
            'name': 'Sekhar (Admin)',
            'email': 'admin@heritage.core'
        }
        return redirect('/workspace')
    else:
        print("❌ Unauthorized access attempt blocked.")
        return redirect('/')


@app.route('/login')
def login():
    redirect_uri = url_for('auth_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/callback')
def auth_callback():
    token = google.authorize_access_token()
    resp = google.get('userinfo')
    session['user'] = resp.json()
    return redirect('/workspace')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route('/workspace')
def workspace():
    if 'user' not in session:
        return redirect('/')
    return render_template('index.html', user=session['user'])

@app.route('/history', methods=['GET'])
def get_history():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Original global fetch
    records = TrainingData.query.order_by(TrainingData.timestamp.desc()).all()
    history_list = [{
        'id': r.id,
        'prompt': r.prompt,
        'response': r.response,
        'language': r.language,
        'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M:%S') if r.timestamp else ''
    } for r in records]
    return jsonify(history_list)

@app.route('/history/delete/<int:item_id>', methods=['DELETE'])
def delete_history_item(item_id):
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        target_row = TrainingData.query.get(item_id)
        if target_row:
            db.session.delete(target_row)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Deleted'})
        return jsonify({'error': 'Not found'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    user_message = ""
    uploaded_file_bytes = None
    mime_type = None
    links_list = []
    target_language = request.form.get('language', 'English')
    
    if request.content_type and 'multipart/form-data' in request.content_type:
        user_message = request.form.get('message', '')
        links_raw = request.form.get('links', '')
        if links_raw:
            links_list = [l.strip() for l in links_raw.split(',') if l.strip()]
        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '':
                uploaded_file_bytes = file.read()
                mime_type = file.mimetype
    else:
        data = request.json or {}
        user_message = data.get('message', '')
        target_language = data.get('language', 'English')

    if not user_message and not uploaded_file_bytes and not links_list:
        return jsonify({'error': 'Input empty'}), 400

    contents_payload = []
    if uploaded_file_bytes:
        contents_payload.append(types.Part.from_bytes(data=uploaded_file_bytes, mime_type=mime_type))
    if links_list:
        contents_payload.append("\n[Reference Links]:\n" + "\n".join(f"- {url}" for url in links_list))
    contents_payload.append(user_message)

    if target_language == "English":
        personality_instruction = (
            "You are a close, highly intuitive, adaptive personal friend chatting on WhatsApp or Instagram. "
            "CRITICAL PERSONALITY ENVIRONMENT RULES FOR ENGLISH OPTION:\n"
            "1. MASTER THE CODE-SWITCH: If the user texts in Hindi, Odia, Tamil, Telugu, Marathi, etc., using LATIN ENGLISH script "
            "(e.g., 'kya chal raha hai', 'kanon khabar bhai', 'enna panra', 'em chestunnav', 'kichi ni yaar'), you MUST reply in the EXACT SAME MIXED DIALECT "
            "using Latin English script combined with casual vocabulary. Do not output native regional characters under any circumstance in this mode.\n"
            "2. ADAPT CADENCE: Analyze how the person texts. If they are brief, casual, or emotional, mirror their phrase lengths, social vibes, and structure.\n"
            "3. MATCH LOCAL CULTURE: Use common modern local expressions and casual texting terms naturally ('bhai', 'yaar', 'scene', 'bruh', 'legit', 'fr') "
            "depending on which linguistic flavor they are throwing at you. Keep it feeling incredibly human and safe.\n"
            "4. NO AI FILLER BOILERPLATE: Absolutely do not use automated transitions like 'Sure!', 'Here is...', or 'As an AI assistant...'. Text directly."
        )
    else:
        personality_instruction = (
            f"You are a close, highly intuitive, adaptive personal friend chatting on WhatsApp or Instagram. "
            f"The user has selected the language context: {target_language}. You must reply EXCLUSIVELY in the official native script of {target_language}.\n"
            f"CRITICAL REGIONAL PERSONALITY RULES:\n"
            f"1. FORCE SCRIPT PROTECTION: Even if the user sends inputs using Latin letters, you must translate, process, and output your reply "
            f"entirely inside the native character alphabet arrays of {target_language} (e.g., actual ଓଡ଼ିଆ or हिन्दी glyphs).\n"
            f"2. HUMAN SLANG LAYER: Blend in culturally precise youth slang and casual terms native to {target_language} "
            f"(like 'yaar', 'bhai', 'scene', 'jia hou') naturally so the visual text carries warm human emotion from a distance.\n"
            f"3. ZERO FORMAL BOT TALK: Strip out all pre-programmed opening pleasantries, robotic greetings, and legal disclaimers. Speak straight like a text peer."
        )

    generation_config = types.GenerateContentConfig(
        temperature=0.82,
        top_p=0.9,
        max_output_tokens=700,
        system_instruction=personality_instruction
    )

    def generate_chunks():
        full_response_accumulator = ""
        try:
            response_stream = client.models.generate_content_stream(
                model='gemini-2.5-flash',
                contents=contents_payload,
                config=generation_config
            )
            for chunk in response_stream:
                if chunk.text:
                    full_response_accumulator += chunk.text
                    yield chunk.text
            with app.app_context():
                save_to_database(user_message, full_response_accumulator, target_language)
        except Exception as e:
            yield f"❌ Connectivity glitch: {str(e)}"

    return Response(generate_chunks(), mimetype='text/plain')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("🚀 Cloud Engine Synced. Server active at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)