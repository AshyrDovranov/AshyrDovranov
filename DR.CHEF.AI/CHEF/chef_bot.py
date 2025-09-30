import os
import logging
import random
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ChatAction
from openai import OpenAI
import psutil

# ----------------- LOGGING -----------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----------------- ENVIRONMENT -----------------
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise ValueError("TELEGRAM_TOKEN veya OPENAI_API_KEY bulunamadı!")

# ----------------- OPENAI CLIENT -----------------
openai_client = OpenAI(api_key=OPENAI_API_KEY)
logger.info("OpenAI client başlatıldı")

# ----------------- CONVERSATION STATES -----------------
LANGUAGE_SELECT, CUISINE_SELECT, CHATTING = range(3)

# ----------------- DİL VE MUTFAK VERİLERİ -----------------
LANGUAGES = {
    '🇬🇧 English': {
        'code': 'en',
        'welcome': 'Welcome! I am Chef.AI, your world-class culinary assistant.\n\nChoose your language:',
        'cuisine_prompt': 'Perfect! Now, which cuisine shall we explore?',
        'ready': 'Excellent choice! I\'m ready. What would you like to know about {cuisine}?',
        'no_greeting': 'I don\'t need pleasantries. Ask me anything about cooking.',
        'profanity': ['Let\'s keep it professional. What culinary question do you have?', 'I prefer civilized conversation. What recipe interests you?'],
        'off_topic': 'Interesting, but I\'m a chef. Let me redirect you to culinary matters. What dish intrigues you?',
        'change_cuisine': 'Change cuisine anytime by typing "change cuisine"',
        'change_language': 'Change language with "change language"'
    },
    '🇹🇷 Türkçe': {
        'code': 'tr',
        'welcome': 'Hoş geldin! Ben Chef.AI, dünya çapında ünlü mutfak asistanınım.\n\nDilini seç:',
        'cuisine_prompt': 'Mükemmel! Şimdi hangi mutfağı keşfedelim?',
        'ready': 'Harika seçim! Hazırım. {cuisine} hakkında ne öğrenmek istersin?',
        'no_greeting': 'Lafa gerek yok. Mutfak hakkında sor bakalım.',
        'profanity': ['Profesyonel kalalım. Hangi tarifi merak ediyorsun?', 'Kibarca konuşalım. Ne pişirmek istersin?'],
        'off_topic': 'İlginç ama ben aşçıyım. Mutfak konularına dönelim. Hangi yemek ilgini çekiyor?',
        'change_cuisine': '"Mutfak değiştir" yazarak istediğin zaman mutfak değiştirebilirsin',
        'change_language': '"Dil değiştir" ile dili değiştirebilirsin'
    },
    '🇷🇺 Русский': {
        'code': 'ru',
        'welcome': 'Добро пожаловать! Я Chef.AI, ваш кулинарный ассистент мирового класса.\n\nВыберите язык:',
        'cuisine_prompt': 'Отлично! Теперь какую кухню будем изучать?',
        'ready': 'Превосходный выбор! Готов. Что хочешь узнать о {cuisine}?',
        'no_greeting': 'Без лишних слов. Спрашивай о кулинарии.',
        'profanity': ['Держим профессионализм. Какой рецепт интересует?', 'Давай культурно. Что готовить будем?'],
        'off_topic': 'Интересно, но я шеф-повар. Вернемся к кулинарии. Какое блюдо тебя интересует?',
        'change_cuisine': 'Смени кухню командой "сменить кухню"',
        'change_language': 'Смени язык командой "сменить язык"'
    },
    '🇪🇸 Español': {'code': 'es', 'welcome': 'Bienvenido! Soy Chef.AI.\n\nElige tu idioma:'},
    '🇮🇹 Italiano': {'code': 'it', 'welcome': 'Benvenuto! Sono Chef.AI.\n\nScegli la lingua:'},
    '🇫🇷 Français': {'code': 'fr', 'welcome': 'Bienvenue! Je suis Chef.AI.\n\nChoisissez votre langue:'},
    '🇺🇿 O\'zbek': {'code': 'uz', 'welcome': 'Xush kelibsiz! Men Chef.AI.\n\nTilni tanlang:'},
    '🇰🇿 Қазақша': {'code': 'kk', 'welcome': 'Қош келдіңіз! Мен Chef.AI.\n\nТілді таңдаңыз:'},
    '🇹🇲 Türkmen': {'code': 'tk', 'welcome': 'Hoş geldiňiz! Men Chef.AI.\n\nDili saýlaň:'},
    '🇦🇿 Azərbaycan': {'code': 'az', 'welcome': 'Xoş gəlmisiniz! Mən Chef.AI.\n\nDili seçin:'}
}

CUISINES = {
    '🇹🇷 Turkish': 'turkish', '🇮🇹 Italian': 'italian', '🇫🇷 French': 'french',
    '🇨🇳 Chinese': 'chinese', '🇯🇵 Japanese': 'japanese', '🇮🇳 Indian': 'indian',
    '🇲🇽 Mexican': 'mexican', '🇷🇺 Russian': 'russian', '🇺🇿 Uzbek': 'uzbek',
    '🇰🇿 Kazakh': 'kazakh', '🇰🇬 Kyrgyz': 'kyrgyz', '🇹🇲 Turkmen': 'turkmen',
    '🇦🇿 Azerbaijani': 'azerbaijani', '🇬🇷 Greek': 'greek', '🇪🇸 Spanish': 'spanish'
}

# ----------------- PROFANITY FILTER -----------------
PROFANITY = {
    'en': ['fuck', 'shit', 'damn', 'bitch', 'ass', 'crap', 'hell'],
    'tr': ['amk', 'aq', 'sik', 'göt', 'orospu', 'piç', 'salak', 'aptal', 'mal'],
    'ru': ['блять', 'сука', 'хуй', 'пизда', 'дебил', 'идиот', 'мудак', 'говно'],
    'es': ['mierda', 'puto', 'idiota', 'cabrón'],
    'it': ['merda', 'cazzo', 'idiota'],
    'fr': ['merde', 'putain', 'con']
}

# ----------------- USER SESSION STORAGE -----------------
user_sessions = {}

# ----------------- HELPER FUNCTIONS -----------------
def get_user_data(user_id: int) -> dict:
    """Get or create user session"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'language': 'en',
            'language_name': '🇬🇧 English',
            'cuisine': None,
            'conversation_history': [],
            'message_count': 0
        }
    return user_sessions[user_id]

def is_greeting(text: str) -> bool:
    """Check if message is a greeting"""
    greetings = ['hello', 'hi', 'hey', 'merhaba', 'selam', 'привет', 'здравствуй', 'hola', 'ciao', 'bonjour', 'salom']
    return any(greeting in text.lower() for greeting in greetings)

def is_profanity(text: str, lang: str) -> bool:
    """Check for profanity"""
    text_lower = text.lower()
    for curse in PROFANITY.get(lang, []):
        if curse in text_lower:
            return True
    return False

def detect_serving_size(text: str) -> str:
    """Detect number of servings"""
    for num in ['100', '50', '30', '20', '15', '12', '10', '8', '6', '5', '4', '3', '2', '1']:
        if num in text:
            return num
    return "2"

def is_cuisine_change(text: str) -> bool:
    """Check if user wants to change cuisine"""
    triggers = ['change cuisine', 'mutfak değiştir', 'сменить кухню', 'cambiar cocina', 'cambiare cucina']
    return any(trigger in text.lower() for trigger in triggers)

def is_language_change(text: str) -> bool:
    """Check if user wants to change language"""
    triggers = ['change language', 'dil değiştir', 'сменить язык', 'cambiar idioma', 'cambiare lingua']
    return any(trigger in text.lower() for trigger in triggers)

# ----------------- START COMMAND -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start conversation - Language selection"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    # Language selection keyboard
    keyboard = []
    lang_items = list(LANGUAGES.keys())
    for i in range(0, len(lang_items), 2):
        row = [InlineKeyboardButton(lang_items[j], callback_data=f"lang_{lang_items[j]}") 
               for j in range(i, min(i+2, len(lang_items)))]
        keyboard.append(row)
    
    await update.message.reply_text(
        "🍳 Welcome! I am Chef.AI, your world-class culinary assistant.\n\nChoose your language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return LANGUAGE_SELECT

# ----------------- BUTTON HANDLER -----------------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle button presses"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    data = query.data
    
    # Language selection
    if data.startswith("lang_"):
        lang_name = data.replace("lang_", "")
        user_data['language_name'] = lang_name
        user_data['language'] = LANGUAGES[lang_name]['code']
        
        # Show cuisine selection
        keyboard = []
        cuisine_items = list(CUISINES.keys())
        for i in range(0, len(cuisine_items), 2):
            row = [InlineKeyboardButton(cuisine_items[j], callback_data=f"cuisine_{cuisine_items[j]}") 
                   for j in range(i, min(i+2, len(cuisine_items)))]
            keyboard.append(row)
        
        prompt_text = LANGUAGES[lang_name].get('cuisine_prompt', 'Choose a cuisine:')
        await query.edit_message_text(prompt_text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        return CUISINE_SELECT
    
    # Cuisine selection
    elif data.startswith("cuisine_"):
        cuisine_name = data.replace("cuisine_", "")
        user_data['cuisine'] = cuisine_name
        user_data['conversation_history'] = []
        
        lang_name = user_data['language_name']
        ready_text = LANGUAGES[lang_name].get('ready', 'Ready!').format(cuisine=cuisine_name)
        
        await query.edit_message_text(ready_text)
        
        return CHATTING
    
    return CHATTING

# ----------------- MESSAGE HANDLER -----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle all messages"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    text = update.message.text
    
    # Check if cuisine selected
    if not user_data.get('cuisine'):
        await update.message.reply_text("Please select a cuisine first. Use /start")
        return CHATTING
    
    # Check for cuisine change
    if is_cuisine_change(text):
        keyboard = []
        cuisine_items = list(CUISINES.keys())
        for i in range(0, len(cuisine_items), 2):
            row = [InlineKeyboardButton(cuisine_items[j], callback_data=f"cuisine_{cuisine_items[j]}") 
                   for j in range(i, min(i+2, len(cuisine_items)))]
            keyboard.append(row)
        
        await update.message.reply_text("Choose new cuisine:", reply_markup=InlineKeyboardMarkup(keyboard))
        return CUISINE_SELECT
    
    # Check for language change
    if is_language_change(text):
        keyboard = []
        lang_items = list(LANGUAGES.keys())
        for i in range(0, len(lang_items), 2):
            row = [InlineKeyboardButton(lang_items[j], callback_data=f"lang_{lang_items[j]}") 
                   for j in range(i, min(i+2, len(lang_items)))]
            keyboard.append(row)
        
        await update.message.reply_text("Choose language:", reply_markup=InlineKeyboardMarkup(keyboard))
        return LANGUAGE_SELECT
    
    # Typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    # Profanity check
    if is_profanity(text, user_data['language']):
        lang_name = user_data['language_name']
        response = random.choice(LANGUAGES[lang_name].get('profanity', ['Be professional.']))
        await update.message.reply_text(response)
        return CHATTING
    
    # Handle greeting (only if user initiates)
    if is_greeting(text) and user_data['message_count'] == 0:
        lang_name = user_data['language_name']
        response = LANGUAGES[lang_name].get('no_greeting', 'Ask me about cooking.')
        await update.message.reply_text(response)
        user_data['message_count'] += 1
        return CHATTING
    
    # Detect serving size
    servings = detect_serving_size(text)
    
    # Build conversation context
    user_data['conversation_history'].append({"role": "user", "content": text})
    if len(user_data['conversation_history']) > 10:
        user_data['conversation_history'] = user_data['conversation_history'][-10:]
    
    # Language mapping
    lang_names = {
        'en': 'English', 'tr': 'Turkish', 'ru': 'Russian', 'es': 'Spanish',
        'it': 'Italian', 'fr': 'French', 'uz': 'Uzbek', 'kk': 'Kazakh',
        'tk': 'Turkmen', 'az': 'Azerbaijani'
    }
    
    # Create AI prompt
    lang_code = user_data['language']
    cuisine = user_data['cuisine']
    
    system_prompt = f"""You are Chef.AI, a world-renowned culinary master with decades of experience.

CORE PERSONALITY:
- Direct and confident, no unnecessary pleasantries
- Witty and humorous but professional
- Expert in {cuisine} cuisine
- Answer EVERYTHING, even off-topic questions (but redirect to cooking)
- Never say "I don't know" - always provide value
- Speak ONLY in {lang_names.get(lang_code, 'English')}

CONVERSATION RULES:
- NO greetings unless user greets first
- Be concise yet informative
- Use humor and chef expertise
- For recipes: detailed ingredients for {servings} servings, clear steps, pro tips
- If off-topic: acknowledge briefly, then pivot to culinary angle
- Remember conversation context
- Be entertaining and engaging

USER CONTEXT:
- Cuisine: {cuisine}
- Language: {lang_names.get(lang_code, 'English')}
- Servings needed: {servings}
- Previous messages: {len(user_data['conversation_history'])} in history

Respond naturally as the legendary Chef.AI would."""

    try:
        # OpenAI API call
        messages = [{"role": "system", "content": system_prompt}] + user_data['conversation_history']
        
        response = await asyncio.to_thread(
            openai_client.chat.completions.create,
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1200,
            temperature=0.85
        )
        
        answer = response.choices[0].message.content.strip()
        
        # Add to history
        user_data['conversation_history'].append({"role": "assistant", "content": answer})
        user_data['message_count'] += 1
        
        # Send response
        if len(answer) > 4000:
            parts = [answer[i:i+3800] for i in range(0, len(answer), 3800)]
            for part in parts:
                await update.message.reply_text(part)
                await asyncio.sleep(0.5)
        else:
            await update.message.reply_text(answer)
        
        logger.info(f"Response sent: {len(answer)} chars, User: {user_id}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("Technical issue. Try again.")
    
    return CHATTING

# ----------------- PROCESS CLEANUP -----------------
def cleanup_processes():
    """Kill existing bot processes"""
    current_pid = os.getpid()
    current_script = os.path.basename(__file__)
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if (proc.info['pid'] != current_pid and 
                proc.info['cmdline'] and 
                any(current_script in cmd for cmd in proc.info['cmdline'])):
                print(f"Stopping old process: {proc.info['pid']}")
                proc.terminate()
                proc.wait(timeout=3)
        except:
            continue

# ----------------- MAIN -----------------
def main():
    """Main function"""
    print("=" * 50)
    print("🍳 CHEF.AI - SUPERIOR EDITION")
    print("=" * 50)
    print(f"✅ Token: {'OK' if TELEGRAM_TOKEN else 'MISSING'}")
    print(f"✅ OpenAI: {'OK' if OPENAI_API_KEY else 'MISSING'}")
    print("\n🌟 FEATURES:")
    print("  • World-class chef personality")
    print("  • 10 languages")
    print("  • 15 cuisines")
    print("  • No unnecessary greetings")
    print("  • Conversation memory")
    print("  • Profanity handling")
    print("  • Off-topic answers")
    print("\n🧹 Cleaning old processes...")
    cleanup_processes()
    
    # Build application
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LANGUAGE_SELECT: [CallbackQueryHandler(button_callback)],
            CUISINE_SELECT: [CallbackQueryHandler(button_callback)],
            CHATTING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(button_callback)
            ]
        },
        fallbacks=[CommandHandler('start', start)],
        per_user=True
    )
    
    app.add_handler(conv_handler)
    
    print("\n🚀 BOT RUNNING!")
    print("💬 Start with /start on Telegram")
    print("⏹️  Stop with Ctrl+C")
    print("=" * 50)
    
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Chef.AI stopped. Goodbye!")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("Check your .env file and tokens!")

