import telebot
from telebot import types
from schedule import scheduleCore
from lessons import lessonHandler
from reminder import ReminderSystem
import os
import json
from dotenv import load_dotenv
load_dotenv()


with open('config.json', 'r', encoding='utf-8') as f:
    # Загружаем данные из файла в переменную (обычно это словарь или список)
    data = json.load(f)

print(data["admins"])

bot = telebot.TeleBot(os.getenv("TOKEN"))
SCHEDULE = scheduleCore(data["bot_data"]["sheet"]).maplike()
DATABASE = lessonHandler(data["bot_data"]["schedule"]["subjects"],data["bot_data"]["schedule"]["weeks"],SCHEDULE)
REMINDER = ReminderSystem(bot, DATABASE, data["users"])
DATABASE.load()
REMINDER.start()

print(DATABASE.take_day())

def start_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Розклад на сьогодні", "Розклад на завтра", "Розклад на день", "Інше")
    return keyboard

# /start
@bot.message_handler(commands=['start'])
def start(message):

    bot.send_message(message.chat.id, "👋 Вітаю! Це бот розкладу занять", reply_markup=start_keyboard(), parse_mode="HTML" )

@bot.message_handler(commands=['id'])
def send_ids(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    language_code = message.from_user.language_code
    print(f"\nchat_id: {chat_id}\nuser_id: {user_id}\nusername: {username}\nfirst_name: {first_name}\nlanguage_code: {language_code}")
    bot.reply_to(
        message,
        f"chat_id: {chat_id}\nuser_id: {user_id}\nusername: {username}\nfirst_name: {first_name}\nlanguage_code: {language_code}"
    )   

# Розклад на сьогодні
@bot.message_handler(func=lambda message: message.text == "Розклад на сьогодні")
def scheduleToday(message):
    bot.send_message(message.chat.id, DATABASE.schedule_today(),
    parse_mode="HTML")

# Розклад на завтра
@bot.message_handler(func=lambda message: message.text == "Розклад на завтра")
def scheduleToday(message):
    bot.send_message(message.chat.id, DATABASE.schedule_tomorrow(),
    parse_mode="HTML")

# Розклад на день
@bot.message_handler(func=lambda message: message.text == "Розклад на день")
def scheduleDay(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("ПН", "ВТ", "СР", "ЧТ", "ПТ", "Назад")
    bot.send_message(message.chat.id, "Виберіть день", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == "ПН")
def scheduleDay(message):
    bot.send_message(message.chat.id, DATABASE.take_schedule_day("ПН"),
    parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "ВТ")
def scheduleDay(message):
    bot.send_message(message.chat.id, DATABASE.take_schedule_day("ВТ"),
    parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "СР",
    parse_mode="HTML")
def scheduleDay(message):
    bot.send_message(message.chat.id, DATABASE.take_schedule_day("СР"),
    parse_mode="HTML")
    
@bot.message_handler(func=lambda message: message.text == "ЧТ")
def scheduleDay(message):
    bot.send_message(message.chat.id, DATABASE.take_schedule_day("ЧТ"),
    parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "ПТ")
def scheduleDay(message):
    bot.send_message(message.chat.id, DATABASE.take_schedule_day("ПТ"),
    parse_mode="HTML")


# Інше
@bot.message_handler(func=lambda message: message.text == "Інше")
def scheduleToday(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Підписатися на напоминання", "Відписатися від напоминань", "обрати Google акаунт", "Назад")
    bot.send_message(message.chat.id, "Виберіть що хочете", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == "Підписатися на напоминання")
def scheduleDay(message):
    bot.send_message(message.chat.id, "Ви підписалися на напоминання", reply_markup=start_keyboard(), parse_mode="HTML" )

@bot.message_handler(func=lambda message: message.text == "Відписатися від напоминань")
def scheduleDay(message):
    bot.send_message(message.chat.id, "Ви відписалися від напоминань", reply_markup=start_keyboard(), parse_mode="HTML" )

@bot.message_handler(func=lambda message: message.text == "обрати Google акаунт")
def scheduleDay(message):
    bot.send_message(message.chat.id, "Напишіть цифру акаунту(test)", reply_markup=start_keyboard(), parse_mode="HTML" ) 
    # Зделать вибор акаунта 


# назад
@bot.message_handler(func=lambda message: message.text == "Назад")
def goback(message):
    bot.send_message(message.chat.id, "Виберіть що хочете", reply_markup=start_keyboard(), parse_mode="HTML" )


# Запуск бота
try:
    bot.polling()
finally:
    REMINDER.stop()


# infinity_polling()