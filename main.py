import telebot
from telebot import types

TOKEN = ""
bot = telebot.TeleBot(TOKEN)

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    # Создаём кнопку
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_hi = types.KeyboardButton("Сказать привет")
    keyboard.add(button_hi)
    
    bot.send_message(message.chat.id, "Привет! Нажми кнопку ниже:", reply_markup=keyboard)

# Обработчик нажатия кнопки
@bot.message_handler(func=lambda message: message.text == "Сказать привет")
def say_hi(message):
    bot.send_message(message.chat.id, "👋 Привет!")

# Запуск бота
bot.polling()
