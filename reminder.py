import threading
import time
from lessons import weekDay
from datetime import datetime, timedelta

class ReminderSystem:
    def __init__(self, bot, database, mreader, data, check_interval=60,format_link_lambda=None):
        """
        bot        – telebot.TeleBot instance
        database   – DATABASE from lessonHandler
        users      – list of chat_ids from config.json
        """
        self.bot = bot
        self.database = database
        self.users = data['users']
        self.groups = data['groups']
        self.check_interval = check_interval
        self.running = False
        self.format = format_link_lambda
        self.sent_cache = set()
        self.custom_reminders = data['bot_data']['reminders']
        self.mreader = mreader

    def start(self):
        if not self.users:
            print("ReminderSystem: users list is empty")
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            try:
                self._check_lessons()
                self._check_reminders()
            except Exception as e:
                print("ReminderSystem error:", e)
            time.sleep(self.check_interval)

    def _sendRAWReminder(self,chat_id,text):
        if text == "@(homework)":
            pass
        else:
            self.bot.send_message(chat_id, text, parse_mode="HTML")

    def _reminder_sent_all(self,msg):
        for group_id in self.groups:
            try:
                self._sendRAWReminder(int(group_id), msg)
            except Exception as e:
                print(f"Send failed ({group_id}):", e)
        for chat_id_str in self.users:
            try:
                self._sendRAWReminder(int(chat_id_str), msg)
            except Exception as e:
                print(f"Send failed ({chat_id_str}):", e)

    def _check_reminders(self):
        now = datetime.now()

        for time_str, reminder in self.custom_reminders.items():
            reminder_time = datetime.strptime(time_str, "%H:%M").replace(
                year=now.year,
                month=now.month,
                day=now.day
            )
            if weekDay(reminder_time) in reminder['exclude']:
                return

            remind_time = reminder_time - timedelta(minutes=10)
            cache_key = f"REMINDER_{reminder_time}"

            if remind_time <= now < remind_time + timedelta(minutes=1):
                if cache_key not in self.sent_cache:
                    self._reminder_sent_all(reminder['text'])
                    self.sent_cache.add(cache_key)

    def _check_lessons(self):
        now = datetime.now()

        day_schedule = self.database.take_day() or {}

        for time_str, lesson in day_schedule.items():
            lesson_time = datetime.strptime(time_str, "%H:%M").replace(
                year=now.year,
                month=now.month,
                day=now.day
            )

            remind_time = lesson_time - timedelta(minutes=10)
            cache_key = f"{lesson['id']}_{lesson_time}"

            if remind_time <= now < remind_time + timedelta(minutes=1):
                if cache_key not in self.sent_cache:
                    self._send(lesson, lesson_time)
                    self._sendGroup(lesson, lesson_time)
                    self.sent_cache.add(cache_key)

    def _sendRAW(self,chat_id,lesson, lesson_time):
        text = (
        "⏰ <b>Через 10 хвилин починається урок: </b>\n\n"
        f"📚{lesson['name']}\n"
        f"🕒{lesson_time.strftime('%H:%M')}\n"
        "🔗 Підключення:\n"
        f"{self.format(lesson['id'],chat_id)}"
        )

        self.bot.send_message(chat_id, text, parse_mode="HTML")

    def _sendGroup(self, lesson, lesson_time):
        for group_id in self.groups:
            try:
                self._sendRAW(int(group_id), lesson, lesson_time)
            except Exception as e:
                print(f"Send failed ({group_id}):", e)
        

    def _send(self, lesson, lesson_time):
        for chat_id_str in self.users:
            try:
                self._sendRAW(int(chat_id_str), lesson, lesson_time)
            except Exception as e:
                print(f"Send failed ({chat_id_str}):", e)
