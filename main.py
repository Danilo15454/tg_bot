import telebot
from telebot import types
from schedule import scheduleCore

TOKEN = "7854842729:AAGAyOEeo7T94TrbNN7LHr2xxowQiqD0DBY"
SCHEDULE = scheduleCore("https://docs.google.com/spreadsheets/d/1Kd1MBIkr9AlfbhB3tZynjG4VfK8sGSX0Pla60DF0A_I/export?format=csv&gid=1091222058").maplike()
bot = telebot.TeleBot(TOKEN)

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    # Создаём кнопку
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    scheduleAllbtn = types.KeyboardButton("Розклад на неділю")
    keyboard.add(scheduleAllbtn)
    
    bot.send_message(message.chat.id, "👋 Вітаю! Це бот розкладу занять", reply_markup=keyboard)

# Обработчик нажатия кнопки
@bot.message_handler(func=lambda message: message.text == "Розклад на неділю")
def scheduleDay(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("ПН", "ВТ", "СР", "ЧТ", "ПТ")
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
    

# Запуск бота
bot.polling()
