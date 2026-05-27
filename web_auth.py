import os

from flask import Flask, request
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow


load_dotenv()

app = Flask(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT_URI],
    }
}


@app.route("/")
def home():
    return "Calendar bot auth server is running."


@app.route("/auth")
def auth():
    user_id = request.args.get("user_id")

    if not user_id:
        return "Missing user_id", 400

    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=user_id,
    )

    return f'<a href="{authorization_url}">Привязать Google Calendar</a>'


@app.route("/oauth2callback")
def oauth2callback():
    user_id = request.args.get("state")

    if not user_id:
        return "Missing user_id", 400

    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    secure_url = request.url.replace("http://", "https://", 1)

    flow.fetch_token(
        authorization_response=secure_url
    )

    credentials = flow.credentials

    os.makedirs("tokens", exist_ok=True)

    with open(f"tokens/{user_id}.json", "w") as token_file:
        token_file.write(credentials.to_json())

    return "✅ Google Calendar привязан. Теперь вернитесь в Telegram-бот."
