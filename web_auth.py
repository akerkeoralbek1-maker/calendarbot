import os
from flask import Flask, request
from dotenv import load_dotenv

from google_auth_oauthlib.flow import Flow

load_dotenv()

app = Flask(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")


@app.route("/")
def home():
    return "Calendar bot auth server is running."


@app.route("/auth")
def auth():
    user_id = request.args.get("user_id")

    if not user_id:
        return "Missing user_id", 400

    flow = Flow.from_client_secrets_file(
        "credentials.json",
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

    flow = Flow.from_client_secrets_file(
        "credentials.json",
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials

    os.makedirs("tokens", exist_ok=True)

    with open(f"tokens/{user_id}.json", "w") as token_file:
        token_file.write(credentials.to_json())

    return "✅ Google Calendar привязан. Теперь вернитесь в Telegram-бот."
