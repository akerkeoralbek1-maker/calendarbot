import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


load_dotenv()

TIMEZONE = os.getenv("TIMEZONE", "Asia/Almaty")
SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarClient:
    def __init__(self, user_id=None):
        self.tz = ZoneInfo(TIMEZONE)
        self.user_id = user_id
        self.service = self.get_service()

    def get_service(self):
        creds = None

        token_path = (
            f"tokens/{self.user_id}.json"
            if self.user_id
            else "token.json"
        )

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(
                token_path,
                SCOPES
            )

        if not creds or not creds.valid:

            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())

            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json",
                    SCOPES
                )

                creds = flow.run_local_server(port=0)

            os.makedirs("tokens", exist_ok=True)

            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return build(
            "calendar",
            "v3",
            credentials=creds
        )

    def get_events_between(self, start_dt, end_dt):
        result = (
            self.service.events()
            .list(
                calendarId="primary",
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        return result.get("items", [])

    def get_today_events(self):
        now = datetime.now(self.tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return self.get_events_between(start, end)

    def get_tomorrow_events(self):
        now = datetime.now(self.tz)
        start = (now + timedelta(days=1)).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )
        end = start + timedelta(days=1)
        return self.get_events_between(start, end)

    def get_week_events(self):
        now = datetime.now(self.tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        return self.get_events_between(start, end)

    def create_event(self, title, start_dt, end_dt):
        event = {
            "summary": title,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": TIMEZONE,
            },
        }

        created_event = (
            self.service.events()
            .insert(
                calendarId="primary",
                body=event
            )
            .execute()
        )

        return created_event

    def format_events(self, events):
        if not events:
            return "Событий нет 🎉"

        lines = []

        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date", ""))

            try:
                if "T" in start:
                    dt = datetime.fromisoformat(start).astimezone(self.tz)
                    time_text = dt.strftime("%d.%m %H:%M")
                else:
                    time_text = start
            except Exception:
                time_text = start

            title = event.get("summary", "(без названия)")
            lines.append(f"• {time_text} — {title}")

        return "\n".join(lines)


class CalendarAgent:
    def __init__(self, user_id=None):
        self.tz = ZoneInfo(TIMEZONE)
        self.user_id = user_id
        self.calendar = CalendarClient(user_id)

    async def handle_message(self, message):
        original_text = message.strip()
        text = original_text.lower()

        if text in ["/help", "help", "помощь", "что ты умеешь"]:
            return self.help_text()

        if self.is_create_request(text):
            return self.create_event_from_text(original_text)

        if "сегодня" in text or "бүгін" in text:
            events = self.calendar.get_today_events()
            return "📅 События на сегодня:\n\n" + self.calendar.format_events(events)

        if "завтра" in text or "ертең" in text:
            events = self.calendar.get_tomorrow_events()
            return "📆 События на завтра:\n\n" + self.calendar.format_events(events)

        if "недел" in text or "апта" in text:
            events = self.calendar.get_week_events()
            return "🗓 События на ближайшие 7 дней:\n\n" + self.calendar.format_events(events)

        return self.help_text()

    def help_text(self):
        return (
            "Я умею работать с Google Calendar 👇\n\n"
            "• Что у меня сегодня?\n"
            "• Что завтра?\n"
            "• Что на этой неделе?\n"
            "• Создай встречу завтра в 15:00 — Созвон\n"
            "• Добавь событие сегодня в 18:30 — Тренировка"
        )

    def is_create_request(self, text):
        words = [
            "создай",
            "добавь",
            "запиши",
            "поставь",
            "назначь",
            "create",
            "add",
            "қос",
        ]

        return any(word in text for word in words)

    def create_event_from_text(self, original_text):
        try:
            lower = original_text.lower()

            date_value = self.extract_date(lower)
            time_value = self.extract_time(lower)
            title = self.extract_title(original_text)

            if not date_value:
                return (
                    "Не поняла дату.\n\n"
                    "Напиши так:\n"
                    "Создай встречу завтра в 15:00 — Созвон"
                )

            if not time_value:
                return (
                    "Не поняла время.\n\n"
                    "Напиши так:\n"
                    "Создай встречу завтра в 15:00 — Созвон"
                )

            if not title:
                title = "Событие"

            start_dt = datetime.combine(date_value, time_value).replace(tzinfo=self.tz)
            end_dt = start_dt + timedelta(minutes=60)

            self.calendar.create_event(
                title=title,
                start_dt=start_dt,
                end_dt=end_dt
            )

            return (
                "✅ Событие создано в Google Calendar:\n\n"
                f"📌 {title}\n"
                f"📅 {start_dt.strftime('%d.%m.%Y')}\n"
                f"🕒 {start_dt.strftime('%H:%M')}"
            )

        except Exception as e:
            return (
                "Не смогла создать событие.\n\n"
                f"Ошибка: {str(e)}\n\n"
                "Попробуй так:\n"
                "Создай встречу завтра в 15:00 — Созвон"
            )

    def extract_date(self, text):
        now = datetime.now(self.tz)

        if "сегодня" in text or "бүгін" in text:
            return now.date()

        if "завтра" in text or "ертең" in text:
            return (now + timedelta(days=1)).date()

        match = re.search(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?", text)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3)) if match.group(3) else now.year
            return datetime(year, month, day).date()

        return None

    def extract_time(self, text):
        match = re.search(r"(\d{1,2})[:.](\d{2})", text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            return datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0).time()

        match = re.search(r"в\s+(\d{1,2})", text)
        if match:
            hour = int(match.group(1))
            return datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0).time()

        return None

    def extract_title(self, text):
        if "—" in text:
            return text.split("—", 1)[1].strip()

        if "-" in text:
            return text.split("-", 1)[1].strip()

        cleaned = re.sub(
            r"(создай|добавь|запиши|поставь|назначь|событие|встречу|сегодня|завтра|в\s+\d{1,2}[:.]?\d{0,2})",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        return cleaned if cleaned else "Событие"
