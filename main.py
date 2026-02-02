import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
from schedule import scheduleCore
from lessons import lessonHandler
from reminder import ReminderSystem
from lessons import format_link
import os
import json
from dotenv import load_dotenv
load_dotenv()

with open('config.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

def push():
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def getUserAcc(chat_id):
    return data["users"].get(str(chat_id), {"account": 0})["account"]

bot = telebot.TeleBot(os.getenv("TOKEN"))
SCHEDULE = scheduleCore(data["bot_data"]["sheet"]).maplike()
DATABASE = lessonHandler(data["bot_data"]["schedule"]["subjects"],data["bot_data"]["schedule"]["weeks"],SCHEDULE)
REMINDER = ReminderSystem(bot, DATABASE, data["users"],60,lambda x, y: format_link(x, getUserAcc(y)))
DATABASE.load()
REMINDER.start()

def start_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Розклад на сьогодні", "Розклад на завтра", "Розклад на день", "Інше")
    return keyboard

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
    bot.send_message(message.chat.id, text, reply_markup=start_keyboard(), parse_mode="HTML" )

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
    keyboard.add("ПН", "ВТ", "СР", "ЧТ", "ПТ", "Назад")
    bot.send_message(message.chat.id, "Виберіть день", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == "ПН")
def scheduleDay(message):
    bot.send_message(message.chat.id, DATABASE.take_schedule_day("ПН",getUserAcc(message.chat.id)),
    parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "ВТ")
def scheduleDay(message):
    bot.send_message(message.chat.id, DATABASE.take_schedule_day("ВТ",getUserAcc(message.chat.id)),
    parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "СР",
    parse_mode="HTML")
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
        bot.send_message(chat_id, "Ви вже піписані на напоминання", reply_markup=start_keyboard(), parse_mode="HTML" )
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
        bot.send_message(message.chat.id, "Ви відписалися на напоминання", reply_markup=start_keyboard(), parse_mode="HTML" )
        data["users"].pop(chat_id, None)
        push()
    else:
        bot.send_message(message.chat.id, "Ви ще не підисані на напоминання", reply_markup=start_keyboard(), parse_mode="HTML" )

@bot.message_handler(func=lambda message: message.text == "обрати Google акаунт")
def scheduleDay(message):
    if str(message.chat.id) in data["users"]:
        bot.send_message(message.chat.id, "Напишіть цифру акаунту", reply_markup=start_keyboard(), parse_mode="HTML" ) 
        bot.register_next_step_handler(message, process_google_acc)
    else:
        bot.send_message(message.chat.id, "Ви ще не підисані на напоминання", reply_markup=start_keyboard(), parse_mode="HTML" ) 
    
    # Зделать вибор акаунта 

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

def is_admin(user_id):
    with open("config.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return user_id in data["admins"]

@bot.message_handler(commands=["announce"])
def announce(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ <b>У тебе немає прав на цю команду</b>", parse_mode="HTML")
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
    bot.send_message(message.chat.id, "Виберіть що хочете", reply_markup=start_keyboard(), parse_mode="HTML" )


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
