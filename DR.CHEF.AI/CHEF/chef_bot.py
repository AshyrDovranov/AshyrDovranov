import os
import telebot
import google.generativeai as genai
from telebot import types

# Setup
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Kullanıcı dili
user_language = {}

# Küfür listesi
BAD_WORDS = ['fuck', 'shit', 'damn', 'bitch', 'asshole']

# Mesajlar
MESSAGES = {
    'en': {
        'welcome': '👨‍🍳 Welcome to Chef.AI!\n\nChoose your language:',
        'ask_ingredients': '🥘 What ingredients do you have?\n\n(e.g., "chicken, tomato, rice")',
        'thinking': '🔍 Searching recipes...',
        'bad_word': '⚠️ Please use appropriate language!',
        'error': '❌ Something went wrong!',
    },
    'ru': {
        'welcome': '👨‍🍳 Добро пожаловать в Chef.AI!\n\nВыберите язык:',
        'ask_ingredients': '🥘 Какие у вас продукты?\n\n(например: "курица, помидор, рис")',
        'thinking': '🔍 Ищу рецепты...',
        'bad_word': '⚠️ Используйте корректную речь!',
        'error': '❌ Ошибка!',
    }
}

def contains_bad_word(text):
    return any(word in text.lower() for word in BAD_WORDS)

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    btn_en = types.InlineKeyboardButton('🇬🇧 English', callback_data='lang_en')
    btn_ru = types.InlineKeyboardButton('🇷🇺 Русский', callback_data='lang_ru')
    markup.row(btn_en, btn_ru)
    bot.send_message(message.chat.id, MESSAGES['en']['welcome'], reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def language_choice(call):
    lang = call.data.split('_')[1]
    user_language[call.message.chat.id] = lang
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, MESSAGES[lang]['ask_ingredients'])

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id
    lang = user_language.get(user_id, 'en')
    
    if contains_bad_word(message.text):
        bot.send_message(user_id, MESSAGES[lang]['bad_word'])
        return
    
    bot.send_message(user_id, MESSAGES[lang]['thinking'])
    
    try:
        prompt = f"""You are Chef.AI. User has: {message.text}

Give 1 recipe in {'English' if lang == 'en' else 'Russian'}.

Format:
🍛 **Recipe Name**
⏱ Time: X min
👥 Servings: X

**Ingredients:**
- Item 1
- Item 2

**Steps:**
1. Step 1
2. Step 2

Short and clear!"""
        
        response = model.generate_content(prompt)
        bot.send_message(user_id, response.text, parse_mode='Markdown')
        bot.send_message(user_id, MESSAGES[lang]['ask_ingredients'])
        
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(user_id, MESSAGES[lang]['error'])

print("🤖 Chef.AI is running...")
bot.infinity_polling()



