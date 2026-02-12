import threading
import time
from lessons import weekDay
from datetime import datetime, timedelta
from fakeMessage import *
#from main import format_link,getUserAcc,BulkSendMessage

REMINDER_WINDOW = 5
LESSON_WINDOW = 5

class ReminderSystem:
    def __init__(self, database, mreader, data, check_interval=60,main_ref=None):
        """
        bot        – telebot.TeleBot instance
        database   – DATABASE from lessonHandler
        users      – list of chat_ids from config.json
        """
        self.database = database
        self.users = data['users']
        self.groups = data['groups']
        self.check_interval = check_interval
        self.running = False
        self.sent_cache = set()
        self.custom_reminders = data['bot_data']['reminders']
        self.mreader = mreader
        self._GLOBALS_ = main_ref

    def _SEND_REAL(self,chat_id,text):
        self._GLOBALS_["BulkSendMessage"](chat_id, text,None,"HTML")

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
        if self._GLOBALS_["get_regexed"](text):
            MSG = FMfromRaw(chat_id,text)
            self._GLOBALS_["flexibleReader"](MSG)
        else:
            self._SEND_REAL(chat_id, text)

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

            remind_time = reminder_time - timedelta(minutes=10)
            if weekDay(remind_time) in reminder['exclude']:
                continue

            cache_key = f"REMINDER_{reminder_time}"

            if remind_time <= now < remind_time + timedelta(minutes=REMINDER_WINDOW):
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
            cache_key = f"{lesson['id']}_{lesson_time.strftime('%Y-%m-%d %H:%M')}"

            if remind_time <= now < lesson_time + timedelta(minutes=LESSON_WINDOW):
                if cache_key not in self.sent_cache:
                    self._send(lesson, lesson_time)
                    self._sendGroup(lesson, lesson_time)
                    self.sent_cache.add(cache_key)

    def _sendRAW(self,chat_id,lesson, lesson_time):
        formatted = self._GLOBALS_["format_link"](lesson['id'],self._GLOBALS_["getUserAcc"](chat_id))
        text = (
        "⏰ <b>Через 10 хвилин починається урок: </b>\n\n"
        f"📚{lesson['name']}\n"
        f"🕒{lesson_time.strftime('%H:%M')}\n"
        "🔗 Підключення:\n"
        f"{formatted}"
        )
        self._SEND_REAL(chat_id, text)

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
