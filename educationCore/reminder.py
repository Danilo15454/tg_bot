import threading
import time
from .lessons import weekDay
from datetime import datetime, timedelta
from .fakeMessage import *
from enum import Enum
import re

REMINDER_WINDOW = 5
LESSON_WINDOW = 5

class SIREN_STATUS(str, Enum):
    SIREN = "Є тривога"
    NO_SIREN = "Немає тривоги"
    SIREN_START = "!Повітряна тривоги!"
    SIREN_STOP = "!Відбій тривоги!"
    SIREN_LESSON = "УВАГА! Зараз іде повітряна тривога\n"

def vlen(text):
    text = re.sub(r"<[^>]+>", "", text)
    return len(text)

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
        self.thereWasAirSiren = False
        self.airSirenMarkDirty = False
        self.sent_cache = set()
        self.custom_reminders = data['bot_data']['reminders']
        self.mreader = mreader
        self._GLOBALS_ = main_ref

    def _SEND_REAL(self,chat_id,text):
        self._GLOBALS_["BulkSendMessage"](chat_id, text,None,"HTML")

    def _isSiren(self) -> bool:
        return self._GLOBALS_["SIREN"].cityTake()

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
                self._check_siren_end()
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

    def _check_siren_end(self):
        now = datetime.now()

        if hasattr(self, "_last_siren_check"):
            if now - self._last_siren_check < timedelta(seconds=25):
                return
        self._last_siren_check = now
        siren = self._isSiren()

        if not self.airSirenMarkDirty:
            self.thereWasAirSiren = siren
            self.airSirenMarkDirty = True
            print(f"Current air siren status: {'true' if siren else 'false'}")
            return

        if not self.thereWasAirSiren and siren:
            self._airSirenMsgAll(SIREN_STATUS.SIREN_START, True)
            self.thereWasAirSiren = True
            return

        if self.thereWasAirSiren and not siren:
            self._airSirenMsgAll(SIREN_STATUS.SIREN_STOP, False)
            self.thereWasAirSiren = False

    def getSirenStatus(self,chat_id):
        siren = self._isSiren()
        self._airSirenMsg(chat_id,SIREN_STATUS.SIREN if siren else SIREN_STATUS.NO_SIREN,siren)

    def _decorSiren(self, length, isSiren):
        symbol = "═"
        siren_symbol = "🟥" if isSiren else "🟩"
        return (symbol + siren_symbol + (symbol * max(0, length - 8)) + siren_symbol + symbol)

    def _airSirenMsgAll(self,TXT,siren):
            for chat_id_str in self.users:
                try:
                    self._airSirenMsg(int(chat_id_str),TXT,siren)
                except Exception as e:
                    print(f"Send failed ({chat_id_str}):", e)
            for group_id in self.groups:
                try:
                    self._airSirenMsg(int(group_id),TXT,siren)
                except Exception as e:
                    print(f"Send failed ({group_id}):", e)

    def _airSirenMsg(self,chat_id,TXT,siren):
        text = (
            self._decorSiren(vlen(TXT), siren)
            + "\n"
            + TXT
            + "\n"
            + self._decorSiren(vlen(TXT), siren)
        )
        self._SEND_REAL(chat_id,text)

    def _sendRAW(self, chat_id, lesson, lesson_time):
        formatted = self._GLOBALS_["format_link"](lesson["id"],self._GLOBALS_["getUserAcc"](chat_id))
        icon_text = "⏰ <b>Через 10 хвилин починається урок: </b>\n\n"
        siren = self._isSiren()
        
        text = (
            self._decorSiren(vlen(icon_text), siren)
            + "\n"
            + icon_text
            + f"📚 {lesson['name']}\n"
            + f"🕒 {lesson_time.strftime('%H:%M')}\n"
            + "🔗 Підключення:\n"
            + formatted
            + "\n"
            + (SIREN_STATUS.SIREN_LESSON if siren else "")
            + self._decorSiren(vlen(icon_text), siren)
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
