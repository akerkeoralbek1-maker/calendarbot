import os
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

try:
    import google.generativeai as genai
except Exception:
    genai = None


load_dotenv()

TIMEZONE = os.getenv("TIMEZONE", "Asia/Almaty")
SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarClient:
    def __init__(self):
        self.tz = ZoneInfo(TIMEZONE)
        self.service = self._get_service()

    def _get_service(self):
        creds = None

        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)

            with open("token.json", "w") as token:
                token.write(creds.to_json())

        return build("calendar", "v3", credentials=creds)

    def get_events_between(self, start_dt, end_dt):
        events_result = (
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
        return events_result.get("items", [])

    def get_today_events(self):
        now = datetime.now(self.tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return self.get_events_between(start, end)

    def get_tomorrow_events(self):
        now = datetime.now(self.tz)
        start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
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

        return (
            self.service.events()
            .insert(calendarId="primary", body=event)
            .execute()
        )

    def format_events(self, events):
        if not events:
            return "Событий нет 🎉"

        lines = []

        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date", ""))

            try:
                if "T" in start:
                    dt = datetime.fromisoformat(start).astimezone(self.tz)
                    time_str = dt.strftime("%d.%m %H:%M")
                else:
                    time_str = start
            except Exception:
                time_str = start

            title = event.get("summary", "(без названия)")
            lines.append(f"• {time_str} — {title}")

        return "\n".join(lines)


class CalendarAgent:
    def __init__(self):
        self.tz = ZoneInfo(TIMEZONE)
        self.calendar = CalendarClient()

        self.model = None
        gemini_key = os.getenv("GEMINI_API_KEY")

        if genai and gemini_key:
            try:
                genai.configure(api_key=gemini_key)
                self.model = genai.GenerativeModel("gemini-2.0-flash-lite")
            except Exception:
                self.model = None

    async def handle_message(self, message):
        text = message.strip()
        lower = text.lower()

        # 1. Команды без AI
        simple_response = self.handle_without_ai(lower, text)
        if simple_response:
            return simple_response

        # 2. Если простая логика не поняла, пробуем AI
        ai_response = await self.handle_with_ai(text)
        if ai_response:
            return ai_response

        # 3. Финальный fallback
        return (
            "Я могу работать с календарём даже без AI 👇\n\n"
            "Напиши, например:\n"
            "• Что у меня сегодня?\n"
            "• Что завтра?\n"
            "• Что на этой неделе?\n"
            "• Создай встречу завтра в 15:00 — Созвон\n"
            "• Добавь событие сегодня в 18:30 — Тренировка"
        )

    def handle_without_ai(self, lower, original_text):
        # Сегодня
        if any(word in lower for word in ["сегодня", "бүгін"]) and not self.is_create_request(lower):
            events = self.calendar.get_today_events()
            return "📅 События на сегодня:\n\n" + self.calendar.format_events(events)

        # Завтра
        if any(word in lower for word in ["завтра", "ертең"]) and not self.is_create_request(lower):
            events = self.calendar.get_tomorrow_events()
            return "📅 События на завтра:\n\n" + self.calendar.format_events(events)

        # Неделя
        if any(word in lower for word in ["недел", "апта", "week"]) and not self.is_create_request(lower):
            events = self.calendar.get_week_events()
            return "📅 События на ближайшие 7 дней:\n\n" + self.calendar.format_events(events)

        # Создание события
        if self.is_create_request(lower):
            return self.create_event_from_text(lower, original_text)

        # Help
        if lower in ["/help", "help", "помощь", "что ты умеешь"]:
            return (
                "Я умею работать с Google Calendar 👇\n\n"
                "• показать события на сегодня\n"
                "• показать события на завтра\n"
                "• показать события на неделю\n"
                "• создать простую встречу\n\n"
                "Пример:\n"
                "Создай встречу завтра в 15:00 — Созвон"
            )

        return None

    def is_create_request(self, lower):
        create_words = [
            "создай",
            "добавь",
            "запиши",
            "поставь",
            "назначь",
            "create",
            "add",
            "кос",
            "қос",
        ]
        return any(word in lower for word in create_words)

    def create_event_from_text(self, lower, original_text):
        try:
            date = self.extract_date(lower)
            time = self.extract_time(lower)
            title = self.extract_title(original_text)

            if not date:
                return "Не поняла дату. Напиши, например: «завтра» или «сегодня»."

            if not time:
                return "Не поняла время. Напиши, например: «в 15:00»."

            if not title:
                title = "Событие"

            start_dt = datetime.combine(date, time).replace(tzinfo=self.tz)
            end_dt = start_dt + timedelta(minutes=60)

            self.calendar.create_event(title, start_dt, end_dt)

            return (
                "✅ Создала событие:\n\n"
                f"📌 {title}\n"
                f"📅 {start_dt.strftime('%d.%m.%Y')}\n"
                f"🕒 {start_dt.strftime('%H:%M')}"
            )

        except Exception as e:
            return (
                "Не смогла создать событие.\n\n"
                "Попробуй написать так:\n"
                "Создай встречу завтра в 15:00 — Созвон"
            )

    def extract_date(self, lower):
        now = datetime.now(self.tz)

        if "сегодня" in lower or "бүгін" in lower:
            return now.date()

        if "завтра" in lower or "ертең" in lower:
            return (now + timedelta(days=1)).date()

        # формат 20.05.2026 или 20.05
        match = re.search(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?", lower)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3)) if match.group(3) else now.year
            return datetime(year, month, day).date()

        return None

    def extract_time(self, lower):
        match = re.search(r"(\d{1,2})[:.](\d{2})", lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            return datetime.now().replace(hour=hour, minute=minute).time()

        match = re.search(r"в\s+(\d{1,2})", lower)
        if match:
            hour = int(match.group(1))
            return datetime.now().replace(hour=hour, minute=0).time()

        return None

    def extract_title(self, text):
        # Лучше всего: "Создай встречу завтра в 15:00 — Созвон"
        if "—" in text:
            return text.split("—", 1)[1].strip()

        if "-" in text:
            return text.split("-", 1)[1].strip()

        # Если нет тире, убираем служебные слова
        cleaned = re.sub(
            r"(создай|добавь|запиши|поставь|назначь|событие|встречу|сегодня|завтра|в\s+\d{1,2}[:.]?\d{0,2})",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        return cleaned if cleaned else None

    async def handle_with_ai(self, text):
        if not self.model:
            return None

        prompt = f"""
Ты ассистент Google Calendar. Ответь коротко.
Если пользователь просит календарь, объясни, что лучше использовать команды:
- Что у меня сегодня?
- Что завтра?
- Что на этой неделе?
- Создай встречу завтра в 15:00 — Название

Сообщение пользователя:
{text}
"""

        try:
            response = self.model.generate_content(prompt)
            return response.text

        except Exception as e:
            error_text = str(e)

            if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
                return (
                    "⚠️ AI временно недоступен из-за лимита Gemini.\n\n"
                    "Но календарь работает без AI 👇\n"
                    "Напиши:\n"
                    "• Что у меня сегодня?\n"
                    "• Что завтра?\n"
                    "• Что на этой неделе?\n"
                    "• Создай встречу завтра в 15:00 — Созвон"
                )

            return None
