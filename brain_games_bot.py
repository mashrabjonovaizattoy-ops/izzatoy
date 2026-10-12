"""
Brain Games Telegram Bot (Aiogram 3.x + SQLite3)
Miya mashqlari va intellektual o'yinlar barchasi bittada!

O'yinlar:
1. 🧮 Tezkor Arifmetika (Mental Math)
2. 🔤 Anagramma / So'z topish (Word Scramble)
3. ❓ Mantiqiy Savollar va Topishmoqlar (Logic Riddles)
4. 🎨 Stroop Diqqat Sinovi (Stroop Color-Word Test)
5. 🔢 Xotira Mashqi (Memory Number Sequence)
6. 🎯 Sirli Son (Number Guessing 1-100)

Muallif: Fazilat uchun tayyorlandi
"""

import asyncio
import logging
import os
import random
import sqlite3
from typing import Dict, Any, List

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

# ==========================================
# SOZLAMALAR (CONFIG)
# ==========================================
# Railway yoki boshqa muhit o'zgaruvchisidan BOT_TOKEN olinadi
BOT_TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKENINGIZNI_SHU_YERGA_YOZING")
DB_NAME = "brain_games.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# MA'LUMOTLAR BAZASI (SQLITE)
# ==========================================
def init_db():
    """Ma'lumotlar bazasi jadvallarini yaratish"""
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            score INTEGER DEFAULT 0,
            games_played INTEGER DEFAULT 0,
            correct_answers INTEGER DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS game_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_type TEXT,
            score_earned INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()

def db_get_or_create_user(user_id: int, username: str, full_name: str) -> Dict[str, Any]:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, username, full_name, score, games_played, correct_answers FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            cur.execute("""
            INSERT INTO users (user_id, username, full_name, score, games_played, correct_answers)
            VALUES (?, ?, ?, 0, 0, 0)
            """, (user_id, username or "", full_name or ""))
            conn.commit()
            return {
                "user_id": user_id,
                "username": username or "",
                "full_name": full_name or "",
                "score": 0,
                "games_played": 0,
                "correct_answers": 0
            }
        return {
            "user_id": row[0],
            "username": row[1],
            "full_name": row[2],
            "score": row[3],
            "games_played": row[4],
            "correct_answers": row[5]
        }

def db_add_score(user_id: int, points: int, is_correct: bool, game_type: str):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
        UPDATE users
        SET score = score + ?,
            games_played = games_played + 1,
            correct_answers = correct_answers + ?
        WHERE user_id = ?
        """, (points, 1 if is_correct else 0, user_id))
        cur.execute("""
        INSERT INTO game_history (user_id, game_type, score_earned)
        VALUES (?, ?, ?)
        """, (user_id, game_type, points))
        conn.commit()

def db_get_top_users(limit: int = 10) -> List[Dict[str, Any]]:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
        SELECT full_name, username, score, games_played
        FROM users
        ORDER BY score DESC
        LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        return [
            {"full_name": r[0], "username": r[1], "score": r[2], "games_played": r[3]}
            for r in rows
        ]

# ==========================================
# FSM HOLATLARI
# ==========================================
class BotStates(StatesGroup):
    waiting_anagram = State()
    waiting_guess_number = State()

# ==========================================
# O'YINLAR MA'LUMOTLAR BAZASI VA GENERATORLAR
# ==========================================

# 1. Anagramma so'zlar to'plami
ANAGRAM_WORDS = [
    {"word": "IDROK", "hint": "Aql, tushunish, zehn qobiliyati"},
    {"word": "MANTIQ", "hint": "To'g'ri va izchil fikrlash ilmi"},
    {"word": "TAFAKKUR", "hint": "Chuqur o'y, aql yuritish jarayoni"},
    {"word": "XOTIRA", "hint": "O'tmishdagi axborotni eslab qolish kuchi"},
    {"word": "ZUKKO", "hint": "Tez fahmlaydigan, o'tkir aql egasi"},
    {"word": "BILIM", "hint": "O'qib, o'rganib to'plangan tushunchalar"},
    {"word": "FAROSAT", "hint": "Ichki sezgi orqali vaziyatni tez anglash"},
    {"word": "DIQQAT", "hint": "Ongni bir nuqtaga jamlash holati"},
    {"word": "KITOBLAR", "hint": "Bilim manbai bo'lgan sahifali boylik"},
    {"word": "FALSAFA", "hint": "Borliq va tafakkurning umumiy qonuniyatlari"},
    {"word": "MUVAFFAQIYAT", "hint": "Ko'zlangan yuksak maqsadga erishish"},
    {"word": "XAYOL", "hint": "Ongda yaratiladigan tasavvur"}
]

# 2. Mantiqiy savollar to'plami
RIDDLES = [
    {
        "q": "❓ Qorong'i xonada gugurt, sham va kerosin chiroq bor. Xonani yoritish uchun avval nimani yoqish kerak?",
        "options": ["Gugurtni", "Shamni", "Kerosin chiroqni", "Elektrni"],
        "answer": "Gugurtni"
    },
    {
        "q": "❓ U sizga tegishli, ammo boshqalar uni sizdan ko'ra ko'proq ishlatishadi. U nima?",
        "options": ["Ismingiz", "Telefoningiz", "Pul", "Soyangiz"],
        "answer": "Ismingiz"
    },
    {
        "q": "❓ Bir yilda nechta oyda 28 kun bor?",
        "options": ["Barcha 12 ta oyda", "Faqat fevralda", "Hech birida", "6 ta oyda"],
        "answer": "Barcha 12 ta oyda"
    },
    {
        "q": "❓ Ikki ota va ikki o'g'il o'rmonga borib, jami 3 ta quyon ovlashdi. Har biriga bittadan quyon yetdi. Bu qanday bo'lishi mumkin?",
        "options": ["Bobo, ota va nabira edi", "Ular 4 kishi edi", "Bir quyon ikkiga bo'lindi", "Xato savol"],
        "answer": "Bobo, ota va nabira edi"
    },
    {
        "q": "❓ Sindirish uchun unga qo'l tegizish yoki urish shart emas. Birgina so'z kifoya. U nima?",
        "options": ["Sukunat yoki Va'da", "Oyna", "Qalb", "Daraxt"],
        "answer": "Sukunat yoki Va'da"
    },
    {
        "q": "❓ To'kilsa yig'ib bo'lmaydi, o'tib ketsa qaytarib bo'lmaydi. U nima?",
        "options": ["Vaqt", "Suv", "Qum", "Boylik"],
        "answer": "Vaqt"
    },
    {
        "q": "❓ Qayerda kecha bugundan oldin keladi?",
        "options": ["Lug'atda (Alifboda)", "Boshqa sayyorada", "Tushda", "Tarixda"],
        "answer": "Lug'atda (Alifboda)"
    },
    {
        "q": "❓ O'zi bitta, ko'zi mingta, yuradi-yu oyog'i yo'q. U nima?",
        "options": ["Baliq to'ri", "Ilon", "Suv", "Yulduzlar"],
        "answer": "Baliq to'ri"
    }
]

# 3. Stroop testi ranglari
STROOP_COLORS = [
    {"name": "QIZIL", "emoji": "🔴"},
    {"name": "KO'K", "emoji": "🔵"},
    {"name": "YASHIL", "emoji": "🟢"},
    {"name": "SARIQ", "emoji": "🟡"}
]

# ==========================================
# KEYBOARDS (KLAVIATURALAR)
# ==========================================
def main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧠 O'yinlar Menyusi"), KeyboardButton(text="👤 Profilim")],
            [KeyboardButton(text="🏆 Reyting (TOP 10)"), KeyboardButton(text="ℹ️ Qoidalar")]
        ],
        resize_keyboard=True
    )

def games_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🧮 Tezkor Arifmetika", callback_data="play_math"),
                InlineKeyboardButton(text="🔤 Anagramma (So'z)", callback_data="play_anagram")
            ],
            [
                InlineKeyboardButton(text="❓ Mantiqiy Savol", callback_data="play_riddle"),
                InlineKeyboardButton(text="🎨 Stroop (Diqqat)", callback_data="play_stroop")
            ],
            [
                InlineKeyboardButton(text="🔢 Xotira Mashqi", callback_data="play_memory"),
                InlineKeyboardButton(text="🎯 Sirli Son (1-100)", callback_data="play_guess")
            ]
        ]
    )

# ==========================================
# HANDLERS (DISPATCHER VA ROUTER)
# ==========================================
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = await asyncio.to_thread(
        db_get_or_create_user,
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.full_name or ""
    )
    text = (
        f"👋 **Assalomu alaykum, {message.from_user.first_name}!**\n\n"
        "🧠 **Brain Games** — intellektual o'yinlar va miya mashqlari botiga xush kelibsiz!\n\n"
        "Bu yerda siz o'z tafakkuringizni, tezkor hisoblash, diqqat va xotirangizni sinab ko'rishingiz "
        "hamda boshqa o'yinchilar bilan reytingda bellashishingiz mumkin.\n\n"
        "Quyidagi tugmalardan birini tanlang:"
    )
    await message.answer(text, reply_markup=main_reply_keyboard(), parse_mode="Markdown")

@router.message(F.text == "🧠 O'yinlar Menyusi")
@router.message(Command("games"))
async def show_games_menu(message: Message, state: FSMContext):
    await state.clear()
    text = (
        "🎮 **Miya mashqlari to'plami:**\n\n"
        "Qaysi o'yinda o'zingizni sinab ko'rmoqchisiz? Tanlang:"
    )
    await message.answer(text, reply_markup=games_inline_keyboard(), parse_mode="Markdown")

@router.message(F.text == "👤 Profilim")
@router.message(Command("profile"))
async def show_profile(message: Message):
    user = await asyncio.to_thread(
        db_get_or_create_user,
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.full_name or ""
    )
    accuracy = 0
    if user["games_played"] > 0:
        accuracy = round((user["correct_answers"] / user["games_played"]) * 100, 1)

    text = (
        f"👤 **O'yinchi Profili:**\n\n"
        f"🏷 **Ism:** {user['full_name']}\n"
        f"⭐ **Umumiy Ball (XP):** `{user['score']}` ball\n"
        f"🎮 **O'ynalgan o'yinlar:** `{user['games_played']}` ta\n"
        f"✅ **To'g'ri javoblar:** `{user['correct_answers']}` ta\n"
        f"🎯 **Aniqlik darajasi:** `{accuracy}%`\n"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "🏆 Reyting (TOP 10)")
@router.message(Command("top"))
async def show_leaderboard(message: Message):
    top_users = await asyncio.to_thread(db_get_top_users, 10)
    if not top_users:
        await message.answer("🏆 Hozircha reyting bo'sh.")
        return

    text = "🏆 **ENG AQLI VA TEZKOR O'YINCHILAR (TOP 10):**\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, u in enumerate(top_users):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = u["full_name"] or u["username"] or "Foydalanuvchi"
        text += f"{medal} **{name}** — `{u['score']}` ball ({u['games_played']} ta o'yin)\n"

    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "ℹ️ Qoidalar")
@router.message(Command("help"))
async def show_rules(message: Message):
    text = (
        "ℹ️ **O'yinlar Qoidalari va Ballar:**\n\n"
        "1. 🧮 **Tezkor Arifmetika:** Tasodifiy matematik misol beriladi. To'g'ri topsangiz +10 ball.\n"
        "2. 🔤 **Anagramma:** Harflari chalkashgan so'zni toping. To'g'ri topsangiz +15 ball.\n"
        "3. ❓ **Mantiqiy Savol:** Qiziqarli topishmoq yoki savolga to'g'ri javob toping. +15 ball.\n"
        "4. 🎨 **Stroop Testi:** Rang va yozuv mosligini tez aniqlang. +10 ball.\n"
        "5. 🔢 **Xotira Mashqi:** Berilgan sonni eslab qoling. +20 ball.\n"
        "6. 🎯 **Sirli Son:** 1 dan 100 gacha sonni kamroq urinishda toping. +25 ball.\n\n"
        "Miyangizni har kuni mashq qildiring va eng yuqori pog'onaga ko'tariling! 🚀"
    )
    await message.answer(text, parse_mode="Markdown")

# ==========================================
# 1-O'YIN: TEZKOR ARIFMETIKA
# ==========================================
@router.callback_query(F.data == "play_math")
async def game_math_start(call: CallbackQuery):
    op = random.choice(["+", "-", "*"])
    if op == "+":
        a, b = random.randint(10, 80), random.randint(10, 80)
        ans = a + b
    elif op == "-":
        a = random.randint(30, 99)
        b = random.randint(10, a)
        ans = a - b
    else:
        a = random.randint(3, 12)
        b = random.randint(3, 12)
        ans = a * b

    # Variantlar generatsiyasi
    options = {ans}
    while len(options) < 4:
        delta = random.choice([-5, -3, -2, -1, 1, 2, 3, 5, 10])
        wrong = ans + delta
        if wrong >= 0 and wrong != ans:
            options.add(wrong)
    opt_list = list(options)
    random.shuffle(opt_list)

    buttons = []
    row = []
    for opt in opt_list:
        is_corr = "1" if opt == ans else "0"
        row.append(InlineKeyboardButton(text=str(opt), callback_data=f"math_ans:{is_corr}:{ans}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Boshqa o'yinlar", callback_data="back_games")])

    text = f"🧮 **Tezkor Arifmetika:**\n\nMisolni hisoblang:\n#️⃣ **{a} {op} {b} = ?**"
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
    await call.answer()

@router.callback_query(F.data.startswith("math_ans:"))
async def game_math_check(call: CallbackQuery):
    _, is_corr, ans = call.data.split(":")
    user_id = call.from_user.id

    if is_corr == "1":
        await asyncio.to_thread(db_add_score, user_id, 10, True, "Arifmetika")
        msg = f"🎉 **Ajoyib! To'g'ri javob:** `{ans}`\nSizga **+10 ball** berildi!"
    else:
        await asyncio.to_thread(db_add_score, user_id, 0, False, "Arifmetika")
        msg = f"❌ **Afsus, xato!** To'g'ri javob `{ans}` edi."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yana misol yechish", callback_data="play_math")],
        [InlineKeyboardButton(text="🧠 Boshqa o'yinlar", callback_data="back_games")]
    ])
    await call.message.edit_text(msg, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

# ==========================================
# 2-O'YIN: ANAGRAMMA (SO'Z TOPISH)
# ==========================================
@router.callback_query(F.data == "play_anagram")
async def game_anagram_start(call: CallbackQuery, state: FSMContext):
    item = random.choice(ANAGRAM_WORDS)
    word = item["word"]
    hint = item["hint"]

    # Harflarni chalkashtirish
    letters = list(word)
    shuffled = letters.copy()
    for _ in range(10):
        random.shuffle(shuffled)
        if "".join(shuffled) != word:
            break
    scrambled = " ".join(shuffled)

    await state.set_state(BotStates.waiting_anagram)
    await state.update_data(target_word=word, hint=hint)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 Maslahat (Hint)", callback_data="anagram_hint")],
        [InlineKeyboardButton(text="❌ O'yinni to'xtatish", callback_data="back_games")]
    ])

    text = (
        "🔤 **Anagramma (So'z topish):**\n\n"
        f"Chalkashtirilgan harflar:\n👉 **`{scrambled}`**\n\n"
        "Shu harflardan tuzilgan to'g'ri so'zni xabar sifatida yozib yuboring:"
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

@router.callback_query(F.data == "anagram_hint")
async def game_anagram_hint(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    hint = data.get("hint", "Maslahat mavjud emas")
    await call.answer(f"💡 Maslahat: {hint}", show_alert=True)

@router.message(BotStates.waiting_anagram)
async def game_anagram_check(message: Message, state: FSMContext):
    data = await state.get_data()
    target_word = data.get("target_word", "").upper()
    user_input = message.text.strip().upper()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yana so'z topish", callback_data="play_anagram")],
        [InlineKeyboardButton(text="🧠 Boshqa o'yinlar", callback_data="back_games")]
    ])

    if user_input == target_word:
        await asyncio.to_thread(db_add_score, message.from_user.id, 15, True, "Anagramma")
        await state.clear()
        await message.answer(
            f"🎉 **Qoyilmaqom! To'g'ri topdingiz:** `{target_word}`\nSizga **+15 ball** berildi!",
            reply_markup=kb,
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            f"❌ Noto'g'ri bo'ldi. Yana bir urinib ko'ring yoki maslahat oling!\n"
            f"(Yoki to'xtatish uchun menyudan boshqa bo'limni tanlang)",
            parse_mode="Markdown"
        )

# ==========================================
# 3-O'YIN: MANTIQIY SAVOLLAR VA TOPISHMOQLAR
# ==========================================
@router.callback_query(F.data == "play_riddle")
async def game_riddle_start(call: CallbackQuery):
    riddle = random.choice(RIDDLES)
    opts = list(riddle["options"])
    random.shuffle(opts)

    buttons = []
    for opt in opts:
        is_corr = "1" if opt == riddle["answer"] else "0"
        # Callback ma'lumot hajmi kichik bo'lishi uchun
        buttons.append([InlineKeyboardButton(
            text=opt,
            callback_data=f"rid_ans:{is_corr}:{opts.index(opt)}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Boshqa o'yinlar", callback_data="back_games")])

    text = f"❓ **Mantiqiy Savol:**\n\n{riddle['q']}\n\nJavobingizni tanlang:"
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    await call.answer()

@router.callback_query(F.data.startswith("rid_ans:"))
async def game_riddle_check(call: CallbackQuery):
    _, is_corr, _ = call.data.split(":")
    user_id = call.from_user.id

    if is_corr == "1":
        await asyncio.to_thread(db_add_score, user_id, 15, True, "Mantiq")
        msg = "🎯 **TO'G'RI JAVOB!** Siz juda zehnlisiz!\nSizga **+15 ball** berildi!"
    else:
        await asyncio.to_thread(db_add_score, user_id, 0, False, "Mantiq")
        msg = "❌ **Afsuski, javob noto'g'ri.** Keyingi savolda omadingizni sinab ko'ring!"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Keyingi savol", callback_data="play_riddle")],
        [InlineKeyboardButton(text="🧠 Boshqa o'yinlar", callback_data="back_games")]
    ])
    await call.message.edit_text(msg, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

# ==========================================
# 4-O'YIN: STROOP TESTI (DIQQAT VA RANG)
# ==========================================
@router.callback_query(F.data == "play_stroop")
async def game_stroop_start(call: CallbackQuery):
    # Ranglar tanlash
    emoji_item = random.choice(STROOP_COLORS)
    text_item = random.choice(STROOP_COLORS)

    is_matching = (emoji_item["name"] == text_item["name"])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Mos keladi", callback_data=f"str_ans:{'1' if is_matching else '0'}"),
            InlineKeyboardButton(text="❌ Mos kelmaydi", callback_data=f"str_ans:{'0' if is_matching else '1'}")
        ],
        [InlineKeyboardButton(text="🔙 Boshqa o'yinlar", callback_data="back_games")]
    ])

    text = (
        "🎨 **Stroop Testi (Diqqat sinovi):**\n\n"
        f"Doira rangi: {emoji_item['emoji']}\n"
        f"Yozilgan matn: **{text_item['name']}**\n\n"
        "⚡ **Savol:** Doiraning rangi va yozilgan so'z bir-biriga mos keladimi?"
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

@router.callback_query(F.data.startswith("str_ans:"))
async def game_stroop_check(call: CallbackQuery):
    _, user_choice = call.data.split(":")
    user_id = call.from_user.id

    if user_choice == "1":
        await asyncio.to_thread(db_add_score, user_id, 10, True, "Stroop")
        msg = "⚡ **Qoyil! Diqqatingiz a'lo darajada!**\nSizga **+10 ball** berildi!"
    else:
        await asyncio.to_thread(db_add_score, user_id, 0, False, "Stroop")
        msg = "❌ **Chalg'idingiz!** Diqqat bilan qayta urinib ko'ring!"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yana sinash", callback_data="play_stroop")],
        [InlineKeyboardButton(text="🧠 Boshqa o'yinlar", callback_data="back_games")]
    ])
    await call.message.edit_text(msg, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

# ==========================================
# 5-O'YIN: XOTIRA MASHQI (SONLARNI ESLAB QOLISH)
# ==========================================
@router.callback_query(F.data == "play_memory")
async def game_memory_start(call: CallbackQuery):
    # 5 xonali tasodifiy son
    secret_seq = "".join([str(random.randint(1, 9)) for _ in range(5)])

    text = (
        "🔢 **Xotira Mashqi:**\n\n"
        "Quyidagi sonni eslab qoling (4 soniyadan so'ng yashiriladi!):\n\n"
        f"🧠 👉 **`{secret_seq}`** 👈\n\n"
        "⏳ Tayyor turing..."
    )
    await call.message.edit_text(text, parse_mode="Markdown")
    await call.answer()

    # 4 soniya kutish
    await asyncio.sleep(4)

    # Variantlar
    options = {secret_seq}
    while len(options) < 4:
        wrong = "".join([str(random.randint(1, 9)) for _ in range(5)])
        if wrong != secret_seq:
            options.add(wrong)
    opt_list = list(options)
    random.shuffle(opt_list)

    buttons = []
    for opt in opt_list:
        is_corr = "1" if opt == secret_seq else "0"
        buttons.append([InlineKeyboardButton(text=opt, callback_data=f"mem_ans:{is_corr}:{secret_seq}")])
    buttons.append([InlineKeyboardButton(text="🔙 Boshqa o'yinlar", callback_data="back_games")])

    hide_text = "❓ **Xotirangizni sinaymiz!**\nQaysi son ko'rsatilgan edi?"
    await call.message.edit_text(hide_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("mem_ans:"))
async def game_memory_check(call: CallbackQuery):
    _, is_corr, secret_seq = call.data.split(":")
    user_id = call.from_user.id

    if is_corr == "1":
        await asyncio.to_thread(db_add_score, user_id, 20, True, "Xotira")
        msg = f"🏆 **Ajoyib fotografik xotira!**\nTo'g'ri son: `{secret_seq}`\nSizga **+20 ball** berildi!"
    else:
        await asyncio.to_thread(db_add_score, user_id, 0, False, "Xotira")
        msg = f"❌ **Xato!** Ko'rsatilgan son `{secret_seq}` edi."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yana sinab ko'rish", callback_data="play_memory")],
        [InlineKeyboardButton(text="🧠 Boshqa o'yinlar", callback_data="back_games")]
    ])
    await call.message.edit_text(msg, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

# ==========================================
# 6-O'YIN: SIRLI SON (1-100 ORALIG'IDA)
# ==========================================
@router.callback_query(F.data == "play_guess")
async def game_guess_start(call: CallbackQuery, state: FSMContext):
    target_num = random.randint(1, 100)
    await state.set_state(BotStates.waiting_guess_number)
    await state.update_data(target_num=target_num, attempts=0)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ O'yinni to'xtatish", callback_data="back_games")]
    ])

    text = (
        "🎯 **Sirli Son (1 dan 100 gacha):**\n\n"
        "Men 1 dan 100 gacha bo'lgan bitta sirli son o'yladim.\n"
        "O'ylagan soningizni yozing, men 'Kattaroq' yoki 'Kichikroq' deb yo'l ko'rsataman!\n\n"
        "Dastlabki taxminingizni yuboring:"
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

@router.message(BotStates.waiting_guess_number)
async def game_guess_process(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat butun son yozing (1 dan 100 gacha)!")
        return

    guess = int(message.text)
    data = await state.get_data()
    target_num = data.get("target_num", 50)
    attempts = data.get("attempts", 0) + 1
    await state.update_data(attempts=attempts)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yangi o'yin", callback_data="play_guess")],
        [InlineKeyboardButton(text="🧠 Boshqa o'yinlar", callback_data="back_games")]
    ])

    if guess == target_num:
        await asyncio.to_thread(db_add_score, message.from_user.id, 25, True, "Sirli Son")
        await state.clear()
        await message.answer(
            f"🎉 **TABRIKLAYMIZ!** Siz sirli sonni topdingiz!\n\n"
            f"🎯 Sirli son: `{target_num}`\n"
            f"🔢 Urinishlar soni: `{attempts}` ta\n"
            f"⭐ Sizga **+25 ball** berildi!",
            reply_markup=kb,
            parse_mode="Markdown"
        )
    elif guess < target_num:
        await message.answer(f"⬆️ Men o'ylagan son **{guess} dan KATTAROQ**! Yana taxmin qiling:")
    else:
        await message.answer(f"⬇️ Men o'ylagan son **{guess} dan KICHIKROQ**! Yana taxmin qiling:")

# ==========================================
# MENYUGA QAYTISH
# ==========================================
@router.callback_query(F.data == "back_games")
async def back_to_games(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "🎮 **Miya mashqlari to'plami:**\n\nQuyidagi o'yinlardan birini tanlang:"
    await call.message.edit_text(text, reply_markup=games_inline_keyboard(), parse_mode="Markdown")
    await call.answer()

# ==========================================
# ASOSIY ISHGA TUSHIRISH (MAIN)
# ==========================================
async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Bot muvaffaqiyatli ishga tushdi...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
