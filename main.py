import calendar
import copy
import telebot
from datetime import datetime, timedelta
from telebot import types
from telebot.apihelper import ApiTelegramException
from schedule import scheduleCore
from lessons import format_link, lessonHandler, getWeek, weekDay
from reminder import ReminderSystem
from scheduleChange import lessonReschedulerHandler
import os
import re
import json
from dotenv import load_dotenv
from enum import Enum
load_dotenv()
data = {}
FLEXIBLE_SUB = {}
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

def is_admin(user_id):
    pop()
    return user_id in data["admins"]
#
#
# MAIN BOT LOGIC
#
#
bot = telebot.TeleBot(os.getenv("TOKEN"))
BOT_ID = bot.get_me().id
SCHEDULE = scheduleCore(data["bot_data"]["sheet"]).maplike()
DATABASE = lessonHandler(data["bot_data"]["schedule"]["subjects"],data["bot_data"]["schedule"]["weeks"],SCHEDULE)
REMINDER = ReminderSystem(bot, DATABASE, data["users"],60,lambda x, y: format_link(x, getUserAcc(y)))
RESCHEDULER = lessonReschedulerHandler(data["scheduled"],push)
DATABASE.setChanger(RESCHEDULER)
#REMINDER.setChanger(RESCHEDULER)
DATABASE.load()
REMINDER.start()

class BASIC_MESSAGE(str, Enum):
    NO_ACCESS = "❌ <b>У тебе немає прав на цю команду</b>"
    NOT_SUBBED = "❌ <b>Ви не підписані на нагадування. Щоб підписатися, оберіть відповідну опцію в меню 'Інше'</b>"
    ALR_SUBBED = "✅ <b>Ви вже підписані на нагадування</b>"

FLEX_SUB_INTERACTION_REGEX = r"@\((.*?)\)"

class FLEX_SUB_INTERACTION(int, Enum):
    DAY_CHOICE = 0,
    EDIT_CHEDULE = 1,
    CHECK_DAY = 2,
    EDIT_LESSON = 3,
    ADD_LESSON = 4
    
def flexSub(type_index, admin_only: bool = True):
    def decorator(func):
        def wrapper(message, *args, **kwargs):
            if admin_only:
                return admin_command(message, lambda msg: func(msg, *args, **kwargs))
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
    match = re.search(FLEX_SUB_INTERACTION_REGEX, message.text)
    if match:
        content = match.group(1).strip()
        parts = content.split(":", 1)
        type_index = parts[0].strip()
        values = parts[1].strip() if len(parts) > 1 else ""
        handler = FLEXIBLE_SUB.get(int(type_index))
        if handler:
            handler(message, values.split(",") if values else [])
        else:
            bot.reply_to(message, f"Unknown type OR missing function for type {type_index}", parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: True)
def all_callback_handler(call):
    match = re.search(FLEX_SUB_INTERACTION_REGEX, call.data)
    if match:
        class FakeMessage:
            def __init__(self, call):
                self.chat = call.message.chat
                self.from_user = call.from_user
                self.text = call.data
                self.message_id = call.message.message_id
                self.reply_to_message = call.message

        fake_message = FakeMessage(call)
        flexibleReader(fake_message)
        bot.answer_callback_query(call.id)
#
# SUB FUNCTIONS
#
@flexSub(FLEX_SUB_INTERACTION.DAY_CHOICE,False)
def dayChooseMSG(message, DATA):
    if len(DATA) == 0:
        return
    now = datetime.now()
    year, month = now.year, now.month
    days_in_month = calendar.monthrange(year, month)[1]

    text = (
        "Оберіть день:\n"
        "🟥 - Сьогодні, 🟨 - Ця неділя, 🟩 - Вихідні, ⬛ - Інші дні\n"
        "☆ - Без змін ★ - Змінено"
    )
    start_week = now - timedelta(days=now.weekday())
    end_week = start_week + timedelta(days=6)

    def format_day(day):
        date = datetime(year, month, day)
        changed = RESCHEDULER.isChanged(day)
        if date.date() == now.date():
            symbol = "🟥"
        elif start_week.date() <= date.date() <= end_week.date():
            symbol = "🟨" if date.weekday() < 5 else "🟩"
        else:
            symbol = "⬛"
        mark = "★" if changed else "☆"
        return f"{symbol}{mark} {day}"

    markup = types.InlineKeyboardMarkup(row_width=5)
    buttons = [
        types.InlineKeyboardButton(
            text=format_day(day),
            callback_data=f"@({DATA[0]}:{day})"
        )
        for day in range(1, days_in_month + 1)
    ]

    markup.add(*buttons)
    bot.send_message(message.chat.id, text, reply_markup=markup)

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
        bot.send_message(message.chat.id, DATABASE.schedule_target_day(day,getUserAcc(message.chat.id)),parse_mode="HTML")


def admin_command(message,func):
    if (is_admin(message.chat.id)):
        func(message)
    else:
        bot.send_message(message.chat.id, BASIC_MESSAGE.NO_ACCESS,parse_mode="HTML")


#@bot.message_handler(func=lambda message: message.text == "Змінити графік @(6:0)")
#def scheduleDay(message):
#    admin_command(message, lambda msg:
#        bot.send_message(message.chat.id, f"", reply_markup=admin_keyboard(), parse_mode="HTML" ))
    # def schedule_operation(msg):
    #     keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    #     keyboard.add("Додати урок @(6:3)", "Змінити урок @(6:4)", "Видалити урок @(6:5)", "Адмін Панель")
    #     bot.send_message(message.chat.id, "Оберіть операцію", reply_markup=keyboard, parse_mode="HTML")
    
    #admin_command(message, schedule_operation)
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
    bot.send_message(message.chat.id, text, reply_markup=start_keyboard(is_admin(message.chat.id)), parse_mode="HTML" )

# Розклад на сьогодні
@bot.message_handler(func=lambda message: message.text == "Розклад на сьогодні")
def scheduleToday(message):
    bot.send_message(message.chat.id, DATABASE.schedule_today(getUserAcc(message.chat.id)),
    parse_mode="HTML")

# Розклад на завтра
@bot.message_handler(func=lambda message: message.text == "Розклад на завтра")
def scheduleToday(message):
    bot.send_message(message.chat.id, DATABASE.schedule_tomorrow(getUserAcc(message.chat.id)),
    parse_mode="HTML")

# Розклад на день
@bot.message_handler(func=lambda message: message.text == "Розклад на день")
def scheduleDay(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("ПН", "ВТ", "СР", "ЧТ", "ПТ", "Календар @(0:2)", "Назад")
    bot.send_message(message.chat.id, "Виберіть день", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == "ПН")
def scheduleDay(message):
    bot.send_message(message.chat.id, DATABASE.take_schedule_day("ПН",getUserAcc(message.chat.id)),
    parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "ВТ")
def scheduleDay(message):
    bot.send_message(message.chat.id, DATABASE.take_schedule_day("ВТ",getUserAcc(message.chat.id)),
    parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "СР")
def scheduleDay(message):
    bot.send_message(message.chat.id, DATABASE.take_schedule_day("СР",getUserAcc(message.chat.id)),
    parse_mode="HTML")
    
@bot.message_handler(func=lambda message: message.text == "ЧТ")
def scheduleDay(message):
    bot.send_message(message.chat.id, DATABASE.take_schedule_day("ЧТ",getUserAcc(message.chat.id)),
    parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "ПТ")
def scheduleDay(message):
    bot.send_message(message.chat.id, DATABASE.take_schedule_day("ПТ",getUserAcc(message.chat.id)),
    parse_mode="HTML")


# Інше
@bot.message_handler(func=lambda message: message.text == "Інше")
def scheduleToday(message):
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
        bot.send_message(chat_id, BASIC_MESSAGE.ALR_SUBBED, reply_markup=start_keyboard(is_admin(chat_id)), parse_mode="HTML" )
    else:
        bot.send_message(chat_id, "Ви підписалися на напоминання", reply_markup=start_keyboard(), parse_mode="HTML" )
        data["users"][str(chat_id)] = {
            "name":f"{message.from_user.username}","account":0
        }
        push()

@bot.message_handler(func=lambda message: message.text == "Відписатися від напоминань")
def scheduleDay(message):
    chat_id = str(message.chat.id)
    if chat_id in data["users"]:
        bot.send_message(message.chat.id, "Ви відписалися на напоминання", reply_markup=start_keyboard(is_admin(message.chat.id)), parse_mode="HTML" )
        data["users"].pop(chat_id, None)
        push()
    else:
        bot.send_message(message.chat.id, BASIC_MESSAGE.NOT_SUBBED, reply_markup=start_keyboard(is_admin(message.chat.id)), parse_mode="HTML" )

@bot.message_handler(func=lambda message: message.text == "обрати Google акаунт")
def scheduleDay(message):
    if str(message.chat.id) in data["users"]:
        bot.send_message(message.chat.id, "Напишіть цифру акаунту", reply_markup=start_keyboard(is_admin(message.chat.id)), parse_mode="HTML" ) 
        bot.register_next_step_handler(message, process_google_acc)
    else:
        bot.send_message(message.chat.id, BASIC_MESSAGE.NOT_SUBBED, reply_markup=start_keyboard(is_admin(message.chat.id)), parse_mode="HTML" ) 

    # Зделати вибор акаунта 

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

def admin_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Оголошення", "Змінити графік @(0:1)", "Назад")
    return keyboard

def start_keyboard(isAdmin:bool):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Розклад на сьогодні", "Розклад на завтра", "Розклад на день")
    if (isAdmin):
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
    bot.send_message(message.chat.id, "Виберіть що хочете", reply_markup=start_keyboard(is_admin(message.chat.id)), parse_mode="HTML" )



@bot.message_handler(func=lambda message: message.text == "Адмін Панель")
def goback(message):
    admin_command(message, lambda msg:
            bot.send_message(message.chat.id, "Виберіть операцію:", reply_markup=admin_keyboard(), parse_mode="HTML" )
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

# Запуск бота
try:
    print("🤖 Бот запущений")
    bot.infinity_polling(skip_pending=True)
except KeyboardInterrupt:
    print("⛔ Бота зупинено вручну")
finally:
    print("🧹 Завершення роботи...")
    REMINDER.stop()
    push()
