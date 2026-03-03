import requests
import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from collections import defaultdict
import time

# ========== BU ALANA KENDİ TOKENLARINIZI GİRİN ==========
BOT_TOKEN = "8342289021:AAHBdWR_pJLUgXq1deu7RrjVYZQadwOZo2o"  # Telegram Bot Token'ınız
API_KEY = "sk-ci5GVGFS7qWSLjbOAERdygVm0c6OkeaEKgq4BncAkWELYse8"  # Sizin API Key'iniz
API_BASE_URL = "https://api.chatanywhere.tech/v1"

# ========== PREMIUM KULLANICILAR ==========
PREMIUM_USERS = [
    123456789,  # Buraya KENDİ TELEGRAM ID'NİZİ YAZIN
    # Diğer premium kullanıcıların ID'lerini buraya ekleyebilirsiniz
]

# ========== PREMIUM ÖZELLİKLER ==========
# Premium kullanıcılar için limit YOK (API key'in izin verdiği kadar)
# Normal kullanıcılar için günlük limit
DAILY_LIMIT_NORMAL = 30  # Normal kullanıcılar için günlük mesaj limiti
# ======================================================

# Loglama ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# TÜM MODELLER
MODELS = {
    # ========== GPT MODELLERİ ==========
    'gpt5mini': {
        'name': 'gpt-5-mini',
        'display': '⚡ GPT-5 Mini',
        'description': 'Hızlı ve ekonomik GPT-5',
        'category': 'GPT'
    },
    'gpt5nano': {
        'name': 'gpt-5-nano',
        'display': '🔹 GPT-5 Nano',
        'description': 'En hızlı GPT-5 - Özetleme',
        'category': 'GPT'
    },
    'gpt41mini': {
        'name': 'gpt-4.1-mini',
        'display': '💫 GPT-4.1 Mini',
        'description': 'Hızlı GPT-4.1',
        'category': 'GPT'
    },
    'gpt41nano': {
        'name': 'gpt-4.1-nano',
        'display': '✨ GPT-4.1 Nano',
        'description': 'En hızlı GPT-4.1',
        'category': 'GPT'
    },
    'gpt4omini': {
        'name': 'gpt-4o-mini',
        'display': '🌈 GPT-4o Mini',
        'description': 'GPT-4o Mini',
        'category': 'GPT'
    },
    'gpt35': {
        'name': 'gpt-3.5-turbo',
        'display': '💬 GPT-3.5 Turbo',
        'description': 'Temel sohbet modeli',
        'category': 'GPT'
    },
    
    # ========== DEEPSEEK MODELLERİ ==========
    'deepseekv3': {
        'name': 'deepseek-v3',
        'display': '🔍 Deepseek V3',
        'description': 'Deepseek V3',
        'category': 'Deepseek'
    },
    'deepseekr1': {
        'name': 'deepseek-r1',
        'display': '🧪 Deepseek R1',
        'description': 'Reasoning modeli',
        'category': 'Deepseek'
    },
    'deepseekreasoner': {
        'name': 'deepseek-reasoner',
        'display': '🤔 Deepseek Reasoner',
        'description': 'Gelişmiş reasoning',
        'category': 'Deepseek'
    },
    'deepseekchat': {
        'name': 'deepseek-chat',
        'display': '💭 Deepseek Chat',
        'description': 'Sohbet modeli',
        'category': 'Deepseek'
    }
}

# Kullanıcı mesaj sayaçları
user_message_counts = defaultdict(list)  # {user_id: [timestamp1, timestamp2, ...]}
user_processing = set()  # İşlemdeki kullanıcılar

def is_premium(user_id):
    """Kullanıcının premium olup olmadığını kontrol eder"""
    return user_id in PREMIUM_USERS

def get_user_limit(user_id):
    """Kullanıcının günlük limitini döndürür"""
    if is_premium(user_id):
        return float('inf')  # PREMIUM: sınırsız
    else:
        return DAILY_LIMIT_NORMAL  # Normal: 30 mesaj

def check_message_limit(user_id):
    """Kullanıcının günlük mesaj limitini kontrol eder"""
    if is_premium(user_id):
        # PREMIUM kullanıcı için limit yok
        return True, 0, float('inf')
    
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    
    today_messages = [ts for ts in user_message_counts[user_id] 
                     if ts >= today_start]
    
    user_message_counts[user_id] = today_messages
    
    limit = get_user_limit(user_id)
    if len(today_messages) >= limit:
        return False, len(today_messages), limit
    
    return True, len(today_messages), limit

async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE, model_name: str, is_premium_user: bool):
    """Mesaj gelme yüzdesini gösteren animasyon"""
    premium_icon = "👑 " if is_premium_user else ""
    message = await update.message.reply_text(f"{premium_icon}📤 **{model_name}** yanıtlıyor... `[0%]`", parse_mode='Markdown')
    
    # Yüzde animasyonu
    for percent in range(0, 101, 10):
        if percent == 0:
            continue
        
        bar_length = 10
        filled_length = int(bar_length * percent / 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        progress_text = f"{premium_icon}📤 **{model_name}** yanıtlıyor... `[{percent}%]` {bar}"
        
        try:
            await message.edit_text(progress_text, parse_mode='Markdown')
        except:
            pass
        
        # Premium kullanıcılar için daha hızlı animasyon
        if is_premium_user:
            await asyncio.sleep(0.05)
        else:
            if percent < 30:
                await asyncio.sleep(0.1)
            elif percent < 60:
                await asyncio.sleep(0.2)
            elif percent < 90:
                await asyncio.sleep(0.3)
            else:
                await asyncio.sleep(0.1)
    
    return message

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot başlatıldığında çalışır"""
    user_id = update.effective_user.id
    premium_status = "👑 **PREMIUM**" if is_premium(user_id) else "📊 **STANDART**"
    user_limit = get_user_limit(user_id)
    limit_text = "Sınırsız" if is_premium(user_id) else f"{user_limit} mesaj/gün"
    
    total_models = len(MODELS)
    welcome_text = (
        "🤖 **Çoklu AI Model Botu**\n\n"
        f"**Hesap Durumunuz:** {premium_status}\n"
        f"**Mesaj Limitiniz:** {limit_text}\n\n"
        f"📊 **Toplam Model Sayısı:** {total_models}\n\n"
        "**📌 Kullanım:**\n"
        "• /modeller - Tüm modelleri listele\n"
        "• /profil - Hesap bilgileriniz\n"
        "• /gpt5mini Merhaba - GPT-5 Mini'ye sor\n"
        "• /deepseekr1 Soru - Deepseek R1'e sor\n\n"
    )
    
    if is_premium(user_id):
        welcome_text += "👑 **PREMIUM üye olduğunuz için sınırsız kullanımınız var!**"
    else:
        welcome_text += f"📊 **Günlük {DAILY_LIMIT_NORMAL} mesaj hakkınız var.**\n"
        welcome_text += "💎 Premium olmak için iletişime geçin."
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def profil_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kullanıcı profil bilgilerini gösterir"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    premium_status = "👑 PREMIUM ÜYE" if is_premium(user_id) else "📊 STANDART ÜYE"
    user_limit = get_user_limit(user_id)
    
    within_limit, count, limit = check_message_limit(user_id)
    
    if is_premium(user_id):
        remaining_text = "Sınırsız"
        used_text = f"{count} (sınırsız)"
    else:
        remaining = limit - count
        remaining_text = str(remaining)
        used_text = f"{count}/{limit}"
    
    info_text = (
        f"👤 **Kullanıcı Profili**\n\n"
        f"İsim: {user.full_name}\n"
        f"ID: `{user_id}`\n"
        f"Username: @{user.username if user.username else 'Yok'}\n\n"
        f"**{premium_status}**\n\n"
        f"📊 **Mesaj Durumu:**\n"
        f"• Bugün kullanılan: {used_text}\n"
        f"• Kalan hakkınız: {remaining_text}\n"
    )
    
    if is_premium(user_id):
        info_text += "\n👑 **Premium avantajlar:**\n"
        info_text += "• Sınırsız mesaj hakkı\n"
        info_text += "• Tüm modellere tam erişim\n"
        info_text += "• Öncelikli işlem\n"
        info_text += "• Daha hızlı yanıt"
    
    await update.message.reply_text(info_text, parse_mode='Markdown')

async def modeller_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tüm modelleri listeler"""
    user_id = update.effective_user.id
    premium_icon = "👑 " if is_premium(user_id) else ""
    
    text = f"{premium_icon}📋 **MODELLER**\n\n"
    
    categories = {}
    for key, model in MODELS.items():
        if model['category'] not in categories:
            categories[model['category']] = []
        categories[model['category']].append((key, model))
    
    for category, models in categories.items():
        text += f"**{category}**\n"
        for key, model in models:
            text += f"• `/{key}` - {model['display']}\n"
            text += f"  _{model['description']}_\n"
        text += "\n"
    
    text += f"\n📊 Toplam: {len(MODELS)} model"
    await update.message.reply_text(text[:4096], parse_mode='Markdown')

async def model_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Her model için ayrı komut işleyici"""
    user_id = update.effective_user.id
    premium_user = is_premium(user_id)
    premium_icon = "👑 " if premium_user else ""
    
    # Aynı anda birden fazla isteği engelle
    if user_id in user_processing:
        await update.message.reply_text(f"{premium_icon}⏳ Önceki mesajınız işleniyor, lütfen bekleyin...")
        return
    
    command = update.message.text.split()[0][1:]
    model_key = command
    
    if model_key not in MODELS:
        await update.message.reply_text("❌ Geçersiz model komutu!")
        return
    
    message_parts = update.message.text.split(maxsplit=1)
    if len(message_parts) < 2:
        await update.message.reply_text(
            f"⚠️ Kullanım: `/{model_key} [sorunuz]`\n"
            f"Örnek: `/{model_key} Türkiye'nin başkenti neresi?`",
            parse_mode='Markdown'
        )
        return
    
    user_message = message_parts[1]
    model = MODELS[model_key]
    
    # Limit kontrolü (premium için limit yok)
    within_limit, count, limit = check_message_limit(user_id)
    if not within_limit and not premium_user:
        await update.message.reply_text(
            f"❌ Günlük mesaj limitiniz doldu! ({count}/{limit})\n"
            f"Yarın tekrar deneyin veya premium olun."
        )
        return
    
    # İşleme başladı
    user_processing.add(user_id)
    
    try:
        # YÜZDE GÖSTERGESİNİ BAŞLAT
        progress_message = await show_progress(update, context, model['display'], premium_user)
        
        # API isteği
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {API_KEY}'
        }
        
        json_data = {
            'model': model['name'],
            'messages': [
                {'role': 'user', 'content': user_message}
            ],
            'temperature': 0.7,
            'max_tokens': 2000
        }
        
        logger.info(f"API isteği gönderiliyor - Kullanıcı: {user_id} (Premium: {premium_user}) - Model: {model['name']}")
        
        response = requests.post(
            f'{API_BASE_URL}/chat/completions',
            headers=headers,
            json=json_data,
            timeout=60
        )
        
        # %100'e tamamla
        bar_length = 10
        bar = '█' * bar_length
        await progress_message.edit_text(
            f"{premium_icon}📤 **{model['display']}** yanıtlıyor... `[100%]` {bar}\n\n"
            f"✅ **Cevap geliyor...**",
            parse_mode='Markdown'
        )
        await asyncio.sleep(0.5)
        
        if response.status_code == 200:
            result = response.json()
            bot_response = result['choices'][0]['message']['content']
            
            # Sadece normal kullanıcılar için sayaç tut
            if not premium_user:
                user_message_counts[user_id].append(datetime.now())
                remaining = limit - (count + 1)
                limit_text = f"📊 Kalan hakkınız: {remaining}/{limit}"
            else:
                # Premium kullanıcılar için sayaç tutma ama göster
                user_message_counts[user_id].append(datetime.now())  # Sadece istatistik için
                limit_text = "👑 **Premium:** Sınırsız"
            
            # Progress mesajını sil ve cevabı gönder
            await progress_message.delete()
            
            response_text = (
                f"{premium_icon}**{model['display']}** yanıtlıyor:\n\n"
                f"{bot_response}\n\n"
                f"{limit_text}"
            )
            await update.message.reply_text(response_text[:4096], parse_mode='Markdown')
            
        else:
            error_msg = f"❌ API Hatası: {response.status_code}"
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_msg += f"\n{error_data['error'].get('message', '')}"
            except:
                pass
            
            logger.error(f"API Hatası: {response.status_code} - {response.text}")
            await progress_message.edit_text(error_msg)
            
    except requests.exceptions.Timeout:
        await progress_message.edit_text(f"{premium_icon}⏰ Zaman aşımı! Lütfen tekrar deneyin.")
    except requests.exceptions.ConnectionError:
        await progress_message.edit_text(f"{premium_icon}🔌 Bağlantı hatası! İnternetinizi kontrol edin.")
    except Exception as e:
        await progress_message.edit_text(f"{premium_icon}❌ Hata: {str(e)}")
        logger.error(f"Hata: {str(e)}")
    finally:
        # İşlem bitti
        user_processing.discard(user_id)

async def handle_direct_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direkt mesajları işler"""
    await update.message.reply_text(
        "⚠️ Lütfen bir model komutu kullanın!\n\n"
        "Örnek: `/gpt5mini Sorunuz`\n"
        "Modelleri görmek için: /modeller\n"
        "Profiliniz için: /profil",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yardım komutu"""
    user_id = update.effective_user.id
    premium_icon = "👑 " if is_premium(user_id) else ""
    
    help_text = (
        f"{premium_icon}📚 **Yardım Menüsü**\n\n"
        "**📌 TEMEL KOMUTLAR:**\n"
        "/start - Botu başlat\n"
        "/modeller - Tüm modelleri listele\n"
        "/profil - Hesap bilgileriniz\n"
        "/help - Bu menü\n\n"
        
        "**✅ MODELLER:**\n"
        "• `/gpt5mini Soru` - GPT-5 Mini\n"
        "• `/gpt5nano Soru` - GPT-5 Nano\n"
        "• `/gpt41mini Soru` - GPT-4.1 Mini\n"
        "• `/gpt41nano Soru` - GPT-4.1 Nano\n"
        "• `/gpt4omini Soru` - GPT-4o Mini\n"
        "• `/gpt35 Soru` - GPT-3.5 Turbo\n"
        "• `/deepseekv3 Soru` - Deepseek V3\n"
        "• `/deepseekr1 Soru` - Deepseek R1\n\n"
    )
    
    if is_premium(user_id):
        help_text += "👑 **PREMIUM ÜYESİNİZ - SINIRSIZ KULLANIM**\n"
    else:
        help_text += f"📊 **Standart Üye:** Günlük {DAILY_LIMIT_NORMAL} mesaj\n"
        help_text += "💎 Premium olmak için iletişime geçin.\n"
    
    help_text += "\n✨ **Canlı yüzde göstergesi aktif!**"
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    """Botu başlat"""
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("❌ HATA: Lütfen BOT_TOKEN değişkenine Telegram Bot Token'ınızı yazın!")
        return
    
    print(f"🤖 Bot başlatılıyor...")
    print(f"📊 Toplam model sayısı: {len(MODELS)}")
    print(f"👑 Premium kullanıcılar: {len(PREMIUM_USERS)}")
    print(f"📋 Normal kullanıcı limiti: {DAILY_LIMIT_NORMAL} mesaj/gün")
    print(f"🔑 API Key: {API_KEY[:15]}...")
    print(f"✨ Premium özellik: SINIRSIZ kullanım!")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Komutlar
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("modeller", modeller_command))
    application.add_handler(CommandHandler("profil", profil_command))
    
    # Tüm model komutları
    for model_key in MODELS.keys():
        application.add_handler(CommandHandler(model_key, model_command_handler))
    
    # Direkt mesajlar için uyarı
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_direct_message))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()