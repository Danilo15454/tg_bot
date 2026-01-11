import telebot
from telebot import types
from schedule import scheduleCore
from lessons import lessonHandler
import os
import json
from dotenv import load_dotenv
load_dotenv()

with open('config.json', 'r', encoding='utf-8') as f:
    # Загружаем данные из файла в переменную (обычно это словарь или список)
    data = json.load(f)

print(data["admins"])

SCHEDULE = scheduleCore(data["bot_data"]["sheet"]).maplike()
DATABASE = lessonHandler(data["bot_data"]["schedule"]["subjects"],data["bot_data"]["schedule"]["weeks"],SCHEDULE)
bot = telebot.TeleBot(os.getenv("TOKEN"))

def start_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Розклад на сьогодні", "Розклад на завтра", "Розклад на день", "Інше")
    return keyboard

# /start
@bot.message_handler(commands=['start'])
def start(message):

    bot.send_message(message.chat.id, "👋 Вітаю! Це бот розкладу занять", reply_markup=start_keyboard())

# Розклад на сьогодні
@bot.message_handler(func=lambda message: message.text == "Розклад на сьогодні")
def scheduleToday(message):
    bot.send_message(message.chat.id, "Розклад на сьогодні:")

# Розклад на завтра
@bot.message_handler(func=lambda message: message.text == "Розклад на завтра")
def scheduleToday(message):
    bot.send_message(message.chat.id, "Розклад на завтра:")

# Розклад на день
@bot.message_handler(func=lambda message: message.text == "Розклад на день")
def scheduleDay(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("ПН", "ВТ", "СР", "ЧТ", "ПТ", "Назад")
    bot.send_message(message.chat.id, "Виберіть день", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == "ПН")
def scheduleDay(message):
    bot.send_message(message.chat.id, "ПН:")

@bot.message_handler(func=lambda message: message.text == "ВТ")
def scheduleDay(message):
    bot.send_message(message.chat.id, "ВТ:")

@bot.message_handler(func=lambda message: message.text == "СР")
def scheduleDay(message):
    bot.send_message(message.chat.id, "СР:")
    
@bot.message_handler(func=lambda message: message.text == "ЧТ")
def scheduleDay(message):
    bot.send_message(message.chat.id, "ЧТ:")

@bot.message_handler(func=lambda message: message.text == "ПТ")
def scheduleDay(message):
    bot.send_message(message.chat.id, "ПТ:")


# Інше
@bot.message_handler(func=lambda message: message.text == "Інше")
def scheduleToday(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Підписатися на напоминання", "Відписатися від напоминань", "обрати Google акаунт", "Назад")
    bot.send_message(message.chat.id, "Виберіть що хочете", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == "Підписатися на напоминання")
def scheduleDay(message):
    bot.send_message(message.chat.id, "Ви підписалися на напоминання", reply_markup=start_keyboard())

@bot.message_handler(func=lambda message: message.text == "Відписатися від напоминань")
def scheduleDay(message):
    bot.send_message(message.chat.id, "Ви відписалися від напоминань", reply_markup=start_keyboard())

@bot.message_handler(func=lambda message: message.text == "обрати Google акаунт")
def scheduleDay(message):
    bot.send_message(message.chat.id, "Напишіть цифру акаунту(test)", reply_markup=start_keyboard()) 
    # Зделать вибор акаунта 


# назад
@bot.message_handler(func=lambda message: message.text == "Назад")
def goback(message):
    bot.send_message(message.chat.id, "Виберіть що хочете", reply_markup=start_keyboard())


# Запуск бота
bot.polling()
