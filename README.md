# Brain Games Telegram Bot (Aiogram 3.x + SQLite3)

Ushbu bot intellektual salohiyat, tezkor hisoblash, diqqat va xotirani rivojlantiruvchi o'yinlar to'plamidir.

## 🎮 Mavjud O'yinlar
1. **🧮 Tezkor Arifmetika:** Tasodifiy misollar (qo'shish, ayirish, ko'paytirish) va 4 ta variant.
2. **🔤 Anagramma (So'z topish):** Harflari chalkashgan so'zlar va maslahat (hint) tizimi.
3. **❓ Mantiqiy Savollar va Topishmoqlar:** O'ylantiruvchi topishmoqlar va test savollari.
4. **🎨 Stroop Diqqat Testi:** Matn va belgi rangining mosligini tezkor aniqlash.
5. **🔢 Xotira Mashqi:** Sonlar ketma-ketligini 4 soniya eslab qolib, to'g'ri variantni tanlash.
6. **🎯 Sirli Son (1 dan 100 gacha):** Bot o'ylagan sonni ishoralar yordamida topish.

## 🏆 Tizim Imkoniyatlari
- **SQLite3 Bazasi:** Foydalanuvchilar, to'plangan XP ballar, o'yinlar soni va aniqlik darajasi avtomatik saqlanadi.
- **TOP 10 Reyting:** Eng yuqori ball to'plagan o'yinchilar jadvali.
- **Foydalanuvchi Profili:** O'yinchining to'liq statistikasi.

## 🚀 Ishga Tushirish Qo'llanmasi

1. **Kutubxonani o'rnatish:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Bot Tokenni sozlash:**
   - Telegram'da [@BotFather](https://t.me/botfather) ga kirib `/newbot` buyrug'i orqali yangi bot yarating.
   - Olingan tokenni `brain_games_bot.py` faylidagi `BOT_TOKEN` o'zgaruvchisiga yozing:
     ```python
     BOT_TOKEN = "SIZNING_BOT_TOKENINGIZ"
     ```

3. **Botni ishga tushirish:**
   ```bash
   python brain_games_bot.py
   ```
