# 🇲🇩 МолдовБот — Руководство по установке и хостингу

## 📦 Структура файлов

```
moldova_bot/
├── bot.py            ← Основной код бота
├── requirements.txt  ← Зависимости Python
├── .env.example      ← Шаблон переменных окружения
├── Procfile          ← Для деплоя на Railway/Render
└── README.md         ← Это руководство
```

---

## 🤖 Шаг 1: Создай бота в Telegram

1. Открой Telegram и напиши **@BotFather**
2. Отправь команду `/newbot`
3. Введи имя бота (например: `МолдовБот`)
4. Введи username бота (например: `moldova_my_bot` — должен заканчиваться на `bot`)
5. **BotFather пришлёт тебе токен** — сохрани его! Выглядит примерно так:
   ```
   1234567890:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

### Настрой команды бота (необязательно, но красиво)
Напиши BotFather `/setcommands` и отправь:
```
start - Запустить бота
help - Список команд
fact - Факт о Молдове
quiz - Викторина о Молдове
weather - Погода в Кишинёве
mdl - Курс молдавского лея
anekdot - Молдавский анекдот
roll - Бросить кубик 🎲
flip - Орёл или решка 🪙
8ball - Магический шар 🔮
choice - Выбрать случайный вариант
time - Время в Кишинёве
id - ID чата
```

### Разреши боту читать сообщения в группах
Напиши BotFather `/setprivacy` → выбери своего бота → **Disable**
(Это позволит боту видеть все сообщения в группе, а не только команды)

---

## 💻 Шаг 2: Локальный запуск (тест на своём компьютере)

### Установка
```bash
# Клонируй или скопируй папку с файлами
cd moldova_bot

# Создай виртуальное окружение
python -m venv venv

# Активируй (Windows)
venv\Scripts\activate

# Активируй (Mac/Linux)
source venv/bin/activate

# Установи зависимости
pip install -r requirements.txt
```

### Запуск
```bash
# Вариант 1: через переменную окружения (рекомендуется)
set BOT_TOKEN=1234567890:AAFxxx...   # Windows CMD
$env:BOT_TOKEN="1234567890:AAFxxx..." # Windows PowerShell
export BOT_TOKEN=1234567890:AAFxxx... # Mac/Linux

python bot.py

# Вариант 2: создай файл .env
# Скопируй .env.example → .env и вставь токен
# Затем в bot.py добавь в начале:
# from dotenv import load_dotenv
# load_dotenv()
```

### Добавление бота в группу
1. Открой группу в Telegram
2. Нажми на название группы → **Добавить участников**
3. Найди своего бота по username
4. Добавь его и **дай права администратора**
   (минимум: чтение сообщений и отправка сообщений)

---

## ☁️ Шаг 3: Бесплатный хостинг

### 🚂 Вариант 1: Railway.app (РЕКОМЕНДУЮ — проще всего)

**Бесплатно: $5 кредитов в месяц** — хватит для небольшого бота.

1. Зарегистрируйся на [railway.app](https://railway.app) (через GitHub)
2. Нажми **New Project** → **Deploy from GitHub repo**
3. Загрузи файлы бота в GitHub репозиторий (публичный или приватный)
4. Railway автоматически обнаружит `Procfile`
5. Перейди в **Variables** и добавь:
   ```
   BOT_TOKEN = 1234567890:AAFxxx...
   ```
6. Деплой запустится автоматически! ✅

```bash
# Если нет GitHub, установи Railway CLI:
npm install -g @railway/cli
railway login
railway init
railway up
```

---

### 🎨 Вариант 2: Render.com

**Бесплатно: Background Worker** (бот не нуждается в HTTP-сервере).

1. Зарегистрируйся на [render.com](https://render.com)
2. **New** → **Background Worker**
3. Подключи GitHub репозиторий с файлами бота
4. Настройки:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
5. В разделе **Environment Variables** добавь:
   ```
   BOT_TOKEN = 1234567890:AAFxxx...
   ```
6. Нажми **Create Background Worker** ✅

⚠️ На бесплатном тарифе Render сервис засыпает через 15 минут без активности.
Для бота это **не проблема** — бот использует long polling, он сам держит соединение.

---

### 🐍 Вариант 3: PythonAnywhere.com

**Бесплатно:** Один "always-on" процесс на бесплатном тарифе.

1. Зарегистрируйся на [pythonanywhere.com](https://pythonanywhere.com)
2. Перейди в **Files** и загрузи `bot.py` и `requirements.txt`
3. Открой **Bash консоль**:
   ```bash
   pip install --user python-telegram-bot aiohttp
   ```
4. Перейди в **Tasks** → **Always-on tasks**
   (На бесплатном тарифе это ограничено — нужно периодически перезапускать)
   
   **Лучше:** Используй **Scheduled tasks** каждые 24 часа:
   ```bash
   cd /home/твой_логин && python bot.py
   ```

---

### 🐋 Вариант 4: Oracle Cloud Free Tier (самый мощный бесплатно)

Oracle даёт **навсегда бесплатно** 2 виртуальные машины ARM.

1. Зарегистрируйся на [cloud.oracle.com](https://cloud.oracle.com)
2. Создай VM Instance (Ubuntu 22.04, ARM)
3. Подключись по SSH и установи бот:
   ```bash
   sudo apt update && sudo apt install python3-pip -y
   pip3 install python-telegram-bot aiohttp
   
   # Создай файл бота
   nano bot.py  # вставь код
   
   # Запусти в фоне через systemd или screen
   screen -S moldovabot
   export BOT_TOKEN="твой_токен"
   python3 bot.py
   # Ctrl+A, D — выйти из screen, бот продолжит работать
   ```

---

## 🔄 Автоматический перезапуск (для своего сервера)

Создай файл `/etc/systemd/system/moldovabot.service`:
```ini
[Unit]
Description=Moldova Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/moldova_bot
Environment=BOT_TOKEN=1234567890:AAFxxx...
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable moldovabot
sudo systemctl start moldovabot
sudo systemctl status moldovabot
```

---

## 🎮 Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие |
| `/help` | Список всех команд |
| `/fact` | Случайный факт о Молдове |
| `/quiz` | Викторина (Telegram Quiz Poll) |
| `/weather` | Погода в Кишинёве (реальная) |
| `/mdl` | Курс лея к USD, EUR, RUB, RON, UAH |
| `/anekdot` | Молдавский анекдот |
| `/roll` | Кубик 1-6 🎲 |
| `/flip` | Орёл или решка 🪙 |
| `/8ball вопрос` | Магический шар 🔮 |
| `/choice а\|б\|в` | Случайный выбор из вариантов |
| `/time` | Время в Кишинёве |
| `/id` | ID чата и пользователя |

### Автоматические реакции (без команды)
Бот автоматически реагирует в группе, когда кто-то пишет:
- `вино` / `wine` → цитата про молдавское вино 🍷
- `мамалыга` → рассказ о национальном блюде 🍽️
- `кишинёв` / `chisinau` → факт о столице 🏛️
- `молдова` / `молдавия` → случайный факт 🇲🇩

---

## ❓ Частые проблемы

**Бот не отвечает в группе?**
→ Убедись, что Privacy Mode выключен у BotFather (`/setprivacy` → Disable)
→ Убедись, что бот — администратор группы

**Ошибка `Conflict: terminated by other getUpdates request`?**
→ Запущено два экземпляра бота одновременно. Останови один из них.

**Ошибка `Unauthorized`?**
→ Неверный токен. Проверь BOT_TOKEN.

**Погода/курс не загружаются?**
→ Временная проблема с внешними API. Попробуй позже.
