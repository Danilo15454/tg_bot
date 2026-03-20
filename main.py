import calendar
import copy
import telebot
from datetime import datetime, timedelta
from telebot import types

from telebot.apihelper import ApiTelegramException
from educationCore.moodleReader import MoodleHandler
from educationCore.schedule import scheduleCore
from educationCore.lessons import format_link, lessonHandler, getWeek, weekDay
from educationCore.sirenReader import sirenReminder
from educationCore.devInterface import *
from educationCore.reminder import ReminderSystem
from educationCore.scheduleChange import lessonReschedulerHandler
from educationCore.fakeMessage import *
import os, sys
import re
import json
from dotenv import load_dotenv
from enum import Enum
import random
import logging
from difflib import SequenceMatcher

LOCK_FILE = "bot.lock"
if os.path.exists(LOCK_FILE):
    sys.exit()
else:
    open(LOCK_FILE, "w").close()

load_dotenv()
data = {}
FLEXIBLE_SUB = {}
RUNNING = False
SUPRESS_TIMEOUT = True
#
# DATA HANDLING
#
def pop():
    global data
    with open('config.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
pop()

def push(DATA=None,TYPE:str="NONE"):
    if TYPE != "NONE":
        data[TYPE] = DATA

    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def getUserAcc(chat_id):
    return data["users"].get(str(chat_id), {"account": 0})["account"]

def is_group(chat_id): 
    return int(chat_id) < 0

def is_admin(user_id):
    pop()
    return user_id in data["admins"]

def is_dev(user_id):
    pop()
    return user_id in data["devs"]
#
#
# MAIN BOT LOGIC
#
#
bot = telebot.TeleBot(os.getenv("TOKEN"))
BOT_ID = bot.get_me().id
SCHEDULE = scheduleCore(data["bot_data"]["sheet"]).maplike()
DATABASE = lessonHandler(data["bot_data"]["schedule"]["subjects"],data["bot_data"]["schedule"]["weeks"],SCHEDULE)
MOODLE = MoodleHandler(os.getenv("MOODLE"))
REMINDER = ReminderSystem(DATABASE, MOODLE, data,60,globals())
RESCHEDULER = lessonReschedulerHandler(data["scheduled"],push)
SIREN = sirenReminder(data["bot_data"]["citySiren"],os.getenv("ALERTS"))
INTERACE = TGBotInterface()
DATABASE.setChanger(RESCHEDULER)
DATABASE.load()
#SIREN.getData()

def BulkSendMessage(chat_id, text, reply_markup=None, parse_mode="HTML"):
    try:
        bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        print(f"⚠️ Could not send to {chat_id}: {e}")

class BASIC_MESSAGE(str, Enum):
    NO_ACCESS = "❌ <b>У тебе немає прав на цю команду</b>"
    NOT_SUBBED = "❌ <b>Ви не підписані на нагадування. Щоб підписатися, оберіть відповідну опцію в меню 'Інше'</b>"
    ALR_SUBBED = "✅ <b>Ви вже підписані на нагадування</b>"

FLEX_SUB_INTERACTION_REGEX = r"@\((.*?)\)"
DATE_BY_STR_FORMAT_INDEX = "!"

def get_regexed(txt):
    return re.search(FLEX_SUB_INTERACTION_REGEX, txt)

def dateBySTR(txt:str) -> datetime:
    if txt[0] != DATE_BY_STR_FORMAT_INDEX:
        return

    d = datetime.now()
    r = txt[2:] if len(txt) > 1 else ""
    match txt[1]:
        case "n":
            pass
        case "w":
            d -= timedelta(days=datetime.now().weekday())
        case "l":
            DAY = int(r)
            d = datetime(d.year,d.month,DAY)
            return d
    
    for s in r:
        match s:
            case "+":
                d += timedelta(days=1)
            case "-":
                d -= timedelta(days=1)

    return d

class FLEX_SUB_INTERACTION(int, Enum):
    NONE = -1,
    DAY_CHOICE = 0,
    EDIT_CHEDULE = 1,
    CHECK_DAY = 2,
    EDIT_LESSON = 3,
    ADD_LESSON = 4,
    GET_HOMEWORK_LINK = 5,
    DEV_HELP = 6,
    FIND_LESSON = 7
    
def flexSub(type_index, admin_only: bool = True, dev_only: bool = False):
    def decorator(func):
        def wrapper(message, *args, **kwargs):
            if admin_only:
                return admin_command(message, lambda msg: func(msg, *args, **kwargs))
            elif dev_only:
                if is_dev(message.chat.id):
                    return func(message, *args, **kwargs)
            else:
                return func(message, *args, **kwargs)

        FLEXIBLE_SUB[type_index] = wrapper
        return wrapper
    return decorator
# 
#
# FLEX SUB HANDLERS
#
#
@bot.message_handler(func = lambda message: bool(re.search(FLEX_SUB_INTERACTION_REGEX, message.text)))
def flexibleReader(message):
    match = get_regexed(message.text)
    if match:
        content = match.group(1).strip()
        parts = content.split(":", 1)
        type_index = parts[0].strip()
        values = parts[1].strip() if len(parts) > 1 else ""
        handler = FLEXIBLE_SUB.get(int(type_index))
        if handler:
            tbl = values.split(",") if values else []
            for i,s in enumerate(tbl):
                n = dateBySTR(s)
                tbl[i] = str(n.day) if n is not None else s
            handler(message, tbl)
        elif message.reply_to_message:
            bot.reply_to(message, f"Unknown type OR missing function for type {type_index}", parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: True)
def all_callback_handler(call):
    match = re.search(FLEX_SUB_INTERACTION_REGEX, call.data)
    if match:
        fake_message = FMfromCall(call)
        flexibleReader(fake_message)
        bot.answer_callback_query(call.id)
#
# SUB FUNCTIONS
#
@flexSub(FLEX_SUB_INTERACTION.DAY_CHOICE,False)
def dayChooseMSG(message, DATA, format_override:list=None, rows:int = 4):
    if len(DATA) == 0:
        return
    if format_override is not None:
        if len(format_override) != 2:
            return
    bot.send_message(message.chat.id, "Це може заняти декілька секунд.")
    now = datetime.now()
    year, month = now.year, now.month
    days_in_month = calendar.monthrange(year, month)[1]

    start_week = now - timedelta(days=now.weekday())
    end_week = start_week + timedelta(days=6)

    def format_day(y,m,day):
        date = datetime(y, m, day)
        changed = RESCHEDULER.isChanged(day)
        if date.date() == now.date():
            symbol = "🟥"
        elif start_week.date() <= date.date() <= end_week.date():
            symbol = "🟨" if date.weekday() < 5 else "🟩"
        else:
            symbol = ""
        mark = "★" if changed else ""
        busy = "?" if MOODLE.key_error else ( "❗" if MOODLE.has_lessons(date) else "" )
        return f"{symbol}{mark}{busy} {day}"
    
    text = (
        "Оберіть день:\n"
        "🟥 - Сьогодні, 🟨 - Ця неділя, 🟩 - Вихідні\n"
        "★ - Змінено, ❗ - Є якісь завдання"
    )

    format_override = format_override or [format_day,text]

    markup = types.InlineKeyboardMarkup(row_width=rows)
    buttons = [
        types.InlineKeyboardButton(
            text=format_override[0](year,month,day),
            callback_data=f"@({DATA[0]}:!l{day})"
        )
        for day in range(1, days_in_month + 1)
    ]

    markup.add(*buttons)
    bot.send_message(message.chat.id, format_override[1], reply_markup=markup)

@flexSub(FLEX_SUB_INTERACTION.EDIT_CHEDULE)
def change_lesson_flex(message, DATA):
    if len(DATA) == 0:
        return
    day_id = int(DATA[0])
    if day_id:
        date = datetime.now().replace(day=day_id)
        raw_day = DATABASE.getSchedule(getWeek(date),date,False)
        week_day = weekDay(date)
        upd_day = DATABASE.getSchedule(getWeek(date),date,True)
        raw_changes = RESCHEDULER.getChanges(day_id)
        text = (
            f"День {day_id} ({week_day}):\n"
            "❌ - Видалено, 🔄 - Змінено, ☆ - Без змін, 🟩 - Додано\n"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)

        raw_day_copy = copy.deepcopy(raw_day)
        for time, lesson in upd_day.items():
            if time not in raw_day_copy:
                raw_day_copy[time] = lesson

        raw_day_copy = dict(sorted(raw_day_copy.items(), key=lambda item: [int(x) for x in item[0].split(":")]))

        for time, lesson in raw_day_copy.items():
            changes = raw_changes.get(time)
            mark = ("❌" if changes == "-1" else "🔄") if changes else "☆"
            if time not in raw_day:
                mark = "🟩"
            lesson_name = lesson.get("name", "?") if changes is None else upd_day.get(time, {}).get("name","?") if changes != "-1" else "Видалено"
            markup.add(
                types.InlineKeyboardButton(
                    text=f"{time} : {lesson_name} {mark}",
                    callback_data=f"@(3:{day_id},{time})"
                )
            )
        markup.add(types.InlineKeyboardButton(
            text="Додати урок ⏰",
            callback_data=f"@(4:{day_id})"
        ))
        bot.send_message(message.chat.id, text, reply_markup=markup)

@flexSub(FLEX_SUB_INTERACTION.NONE,False)
def _flex_none(message, DATA):
    pass

@flexSub(FLEX_SUB_INTERACTION.FIND_LESSON,False)
def find_lessons(message, DATA):
    if len(DATA) != 1:
        return
    LESSON_ID = int(DATA[0]) + 1
    lesson_name = DATABASE.lessons_names.get(LESSON_ID)

    def format(y,m,d):
        date = datetime(y, m, d)
        has_lesson,ln = DATABASE.has_lesson(getWeek(date),date,LESSON_ID) 
        has = "🟩" if has_lesson else "🟥"
        return f"{has} {d}"

    txt = (
        f"Дні коли є {lesson_name}\n"
        "🟩 - Є урок, 🟥 - Немає урока"
    )

    dayChooseMSG(message,["-1"],[format,txt],6)

@flexSub(FLEX_SUB_INTERACTION.GET_HOMEWORK_LINK,False)
def get_homework_link_flex(message, DATA):
    if len(DATA) == 1:
        day = int(DATA[0])
        now = datetime.now()
        date = datetime(now.year, now.month, day)

        if MOODLE.has_lessons(date):
            txt = MOODLE.day_lessons(date)
            markup = types.InlineKeyboardMarkup(row_width=1)
            if (txt == MOODLE.KEY_ERROR or txt == MOODLE.LOGIN_ERROR) and is_dev(message.chat.id):
                markup.add(types.InlineKeyboardButton(text="view dev stuff",callback_data=f"@(6)"))
            bot.send_message(message.chat.id, txt, parse_mode="HTML",reply_markup=markup)

@flexSub(FLEX_SUB_INTERACTION.DEV_HELP,False,True)
def dev_help(message, Data):
    txt = (
        "* - Required\n"
        ".env\n"
        "TOKEN* = XXXX (BOT token)\n"
        "MOODLE = 'xxx:xxx' (MOODLE Login)"
    )
    bot.send_message(message.chat.id, txt, parse_mode="HTML")

@flexSub(FLEX_SUB_INTERACTION.ADD_LESSON)
def add_lesson_flex(message, DATA):

    def request_next(msg):
        DATA.append(msg.text)
        add_lesson_flex(msg, DATA)

    match len(DATA):
        case 0:
            return
        case 1:
            bot.send_message(message.chat.id, "⏰ Введіть час пари (HH:MM):")
            bot.register_next_step_handler(message, request_next)
            return
        case 2:
            bot.send_message(message.chat.id, DATABASE.getLessonIds(False), parse_mode="HTML")
            bot.register_next_step_handler(message, request_next)
            return
        case 3:
            edit_lesson_flex(message, DATA)

@flexSub(FLEX_SUB_INTERACTION.EDIT_LESSON)
def edit_lesson_flex(message, DATA):
    if len(DATA) == 0:
        return
    day = int(DATA[0])
    time = DATA[1]
    if day and time:
        if len(DATA) == 3:
            
            if int(DATA[2]) < 0:
                RESCHEDULER.clearLesson(day, time)
                bot.send_message(message.chat.id, f"Урок востановлено.",parse_mode="HTML")
            else:
                
                if int(DATA[2]) == 0:
                    RESCHEDULER.schedule(day, time, "-1")
                    bot.send_message(message.chat.id, f"Урок о <b>{time}</b> на <b>{day}</b> видалено",parse_mode="HTML")
                else:
                    date = datetime.now().replace(day=day)
                    raw_day = DATABASE.getSchedule(getWeek(date),date,False)
                    RESCHEDULER.schedule(day, time, DATA[2], time in raw_day)

            change_lesson_flex(message, [day])
        else:
            def request(message):
                edit_lesson_flex(message, [day, time, message.text])
            text = DATABASE.getLessonIds()
            bot.send_message(message.chat.id, text,parse_mode="HTML")
            bot.register_next_step_handler(message, request)

@flexSub(FLEX_SUB_INTERACTION.CHECK_DAY,False)
def check_day_flex(message, DATA):
    if len(DATA) == 0:
        return
    day = int(DATA[0])
    if day:
        this = datetime.now()
        date = datetime(day=day,month=this.month,year=this.year)
        bot.send_message(message.chat.id, DATABASE.schedule_target_day(day,getUserAcc(message.chat.id)),parse_mode="HTML",reply_markup=offerHomeworkView(date))


def admin_command(message,func):
    if (is_admin(message.chat.id)):
        func(message)
    else:
        bot.send_message(message.chat.id, BASIC_MESSAGE.NO_ACCESS,parse_mode="HTML")
#
#
# OTHER
#
# /start
@bot.message_handler(commands=['start'])
def start(message):
    text = (
    "👋 Вітаю! Це бот розкладу занять 📚\n\n"
    "Тут ви можете:\n"
    "• 📅 дізнатися розклад на сьогодні\n"
    "• ⏭️ переглянути розклад на завтра\n"
    "• 🗓️ отримати розклад на будь-який день тижня\n"
    "• 🔔 підписатися на нагадування\n"
    "• ⏰ отримувати нагадування перед початком занять\n\n"
    "Користуйтеся командами або кнопками меню 👇"
    )
    bot.send_message(message.chat.id, text, reply_markup=start_keyboard(message), parse_mode="HTML" )

@bot.message_handler(func=lambda message: message.text == "Розклад пар")
def lessons_keyboard(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton(
            text=DATABASE.lessons_names.get(lid) or "",
            callback_data=f"@(7:{lid - 1})"
        )
        for lid in DATABASE.lessons_ids.keys()
    ]
    markup.add(*buttons)
    bot.send_message(message.chat.id, "Виберіть предмет для перегляду", reply_markup=markup, parse_mode="HTML" )

# Розклад на сьогодні
@bot.message_handler(func=lambda message: message.text == "Розклад на сьогодні")
def scheduleToday(message):
    date = datetime.now()
    bot.send_message(message.chat.id, DATABASE.schedule_today(getUserAcc(message.chat.id)),
    parse_mode="HTML",reply_markup=offerHomeworkView(date))

# Розклад на завтра
@bot.message_handler(func=lambda message: message.text == "Розклад на завтра")
def scheduleToday(message):
    date = datetime.now() + timedelta(days=1)
    bot.send_message(message.chat.id, DATABASE.schedule_tomorrow(getUserAcc(message.chat.id)),
    parse_mode="HTML",reply_markup=offerHomeworkView(date))

def offerHomeworkView(date):
    start_of_day = datetime(date.year, date.month, date.day)
    markup = types.InlineKeyboardMarkup(row_width=1)
    if MOODLE.has_lessons(start_of_day):
        markup.add(types.InlineKeyboardButton(text="Домашне Завдання",callback_data=f"@(5:!l{start_of_day.day})"))
        return markup

# Розклад на день
@bot.message_handler(func=lambda message: message.text == "Розклад")
def scheduleDay(message):
    keyboard = None
    if not is_group(message.chat.id):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    date = datetime.now()
    ws = (date - timedelta(days=date.weekday())).day
    keyboard.add(f"ПН @(2:{ws})", f"ВТ @(2:{ws+1})", f"СР @(2:{ws+2})", f"ЧТ @(2:{ws+3})", f"ПТ @(2:{ws+4})", "Календар @(0:2)", "Розклад пар", "Назад")
    bot.send_message(message.chat.id, "Виберіть день", reply_markup=keyboard)

# Інше
@bot.message_handler(func=lambda message: message.text == "Інше")
def scheduleToday(message):
    keyboard = None
    if not is_group(message.chat.id):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Підписатися на напоминання", "Відписатися від напоминань", "обрати Google акаунт", "Автори", "Назад")
    bot.send_message(message.chat.id, "Виберіть що хочете", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == "Автори")
def scheduleDay(message):
    txt = (
        "@Nebula_Protogen та @danilka_kryt"
    )
    bot.send_message(message.chat.id, txt,
    parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "Підписатися на напоминання")
def scheduleDay(message):
    chat_id = message.chat.id
    if str(chat_id) in data["users"]:
        bot.send_message(chat_id, BASIC_MESSAGE.ALR_SUBBED, reply_markup=start_keyboard(message), parse_mode="HTML" )
    else:
        bot.send_message(chat_id, "Ви підписалися на напоминання", reply_markup=start_keyboard(message), parse_mode="HTML" )
        data["users"][str(chat_id)] = {
            "name":f"{message.from_user.username}","account":0
        }
        push()

@bot.message_handler(func=lambda message: message.text == "Відписатися від напоминань")
def scheduleDay(message):
    chat_id = str(message.chat.id)
    if chat_id in data["users"]:
        bot.send_message(message.chat.id, "Ви відписалися на напоминання", reply_markup=start_keyboard(message), parse_mode="HTML" )
        data["users"].pop(chat_id, None)
        push()
    else:
        bot.send_message(message.chat.id, BASIC_MESSAGE.NOT_SUBBED, reply_markup=start_keyboard(message), parse_mode="HTML" )

@bot.message_handler(func=lambda message: message.text == "обрати Google акаунт")
def scheduleDay(message):
    if str(message.chat.id) in data["users"]:
        bot.send_message(message.chat.id, "Напишіть цифру акаунту", reply_markup=start_keyboard(message), parse_mode="HTML" ) 
        bot.register_next_step_handler(message, process_google_acc)
    else:
        bot.send_message(message.chat.id, BASIC_MESSAGE.NOT_SUBBED, reply_markup=start_keyboard(message), parse_mode="HTML" ) 

@bot.message_handler(func=lambda message: message.text == "cat")
def scheduleDay(message):
    txt = (
    "───▐▀▄──────▄▀▌───▄▄▄▄▄▄▄\n"
    "───▌▒▒▀▄▄▄▄▀▒▒▐▄▀▀▒██▒██▒▀▀▄\n"
    "──▐▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▀▄\n"
    "──▌▒▒▒▒▒▒▒▒▒▒▒▒▒▄▒▒▒▒▒▒▒▒▒▒▒▒▒▀▄\n"
    "▀█▒▒█▌▒▒█▒▒▐█▒▒▀▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▌\n"
    "▀▌▒▒▒▒▒▀▒▀▒▒▒▒▒▀▀▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▐ ▄▄\n"
    "▐▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▄█▒█\n"
    "▐▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒█▀\n"
    "──▐▄▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▄▌\n"
    "────▀▄▄▀▀▀▀▄▄▀▀▀▀▀▀▄▄▀▀▀▀▀▀▄▄▀"
    )
    bot.send_message(message.chat.id, txt,
    parse_mode="HTML")


@bot.message_handler(func=lambda message: message.text == "pusheen")
def catImage(message):
    folder_path = os.path.join(os.getcwd(), "media/pusheen")
    images = [f for f in os.listdir(folder_path)
              if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]

    if not images:
        bot.send_message(message.chat.id, "No images found.")
        return

    random_image = random.choice(images)
    image_path = os.path.join(folder_path, random_image)

    with open(image_path, "rb") as photo:
        bot.send_photo(message.chat.id, photo)

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

@bot.message_handler(func=lambda message: similar(
    str.lower(message.text), "а кому щяс легко") >= 0.75
)
def funkyMessage(message):
    with open("media/legko.png", "rb") as photo:
        bot.send_photo(message.chat.id, photo)

def process_google_acc(message):
    try:
        number = int(message.text)
        if number < 0 or number > 255:
            raise ValueError
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ Невірне число."
        )
        return

    bot.send_message(message.chat.id,f"✅ Ви обрали акаунт №{number}")
    data["users"][str(message.chat.id)]["account"] = number
    push()

def admin_keyboard(message):
    keyboard = None
    if not is_group(message.chat.id):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Оголошення", "Змінити графік @(0:1)", "Назад")
    return keyboard

def start_keyboard(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    id = message.chat.id
    if not is_group(id):
        keyboard.add("Розклад на сьогодні", "Розклад на завтра", "Розклад")
    if is_admin(id):
        keyboard.add("Адмін Панель")
        keyboard.add("Інше")
    return keyboard

@bot.message_handler(commands=["announce"])
def announce(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, BASIC_MESSAGE.NO_ACCESS, parse_mode="HTML")
        return

    text = message.text.replace("/announce", "", 1).strip()
    if not text:
        bot.reply_to(message, "❗ <b>Напишіть текст оголошення після команди</b>", parse_mode="HTML")
        return

    with open("config.json", "r", encoding="utf-8") as f:
        users = json.load(f).get("users", [])

    sent = 0
    failed = 0

    for chat_id in users:
        try:
            bot.send_message(
                chat_id,
                f"📢 <b>Оголошення:</b>\n\n{text}",
                parse_mode="HTML"
            )
            sent += 1
        except ApiTelegramException as e:
            failed += 1
            print(f"❌ Не надіслано {chat_id}: {e}")

    bot.reply_to(
        message,
        f"✅ <b>Відправлено:</b> {sent}\n"
        f"⚠️ <b>Не доставлено:</b> {failed}",
        parse_mode="HTML"
    )

# назад
@bot.message_handler(func=lambda message: message.text == "Назад")
def goback(message):
    bot.send_message(message.chat.id, "Виберіть що хочете", reply_markup=start_keyboard(message), parse_mode="HTML" )



@bot.message_handler(func=lambda message: message.text == "Адмін Панель")
def goback(message):
    admin_command(message, lambda msg:
            bot.send_message(message.chat.id, "Виберіть операцію:", reply_markup=admin_keyboard(message), parse_mode="HTML" )
        )

@bot.message_handler(content_types=["new_chat_members"])
def new_chat_member_handler(message):
    for new_user in message.new_chat_members:
        if new_user.id == BOT_ID:
            chat_id = str(message.chat.id)
            if chat_id not in data["groups"]:
                data["groups"].append(chat_id)
                bot.send_message(message.chat.id, "Бот автоматично підписан на группу та буде відправляти нагадування!", parse_mode="HTML" )
                push()

@bot.message_handler(content_types=["left_chat_member"])
def left_chat_handler(message):
    left_user = message.left_chat_member
    if left_user.id == BOT_ID:
        chat_id = str(message.chat.id)
        if chat_id in data["groups"]:
            data["groups"].remove(chat_id)
            push()

def _finallyKILL():
    print("🧹 Завершення роботи...")
    REMINDER.stop()
    MOODLE.close()
    push()
    os.remove(LOCK_FILE)

try:
    if(SUPRESS_TIMEOUT):
        logging.getLogger("telebot").setLevel(logging.CRITICAL)
    print("🤖 Бот запущений")
    REMINDER.start()
    #INTERACE.start(_finallyKILL)
    bot.infinity_polling(skip_pending=True)
except KeyboardInterrupt:
    print("🛑 Бот зупинено вручну")
finally:
    _finallyKILL()