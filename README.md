# Bees House 🐝

Telegram бот для обліку виробництва рамок та інших продуктів бджільництва.

## Структура проєкту

```
bees-house/
├── bot/
│   └── bot.py          # Основний код бота (Python + aiogram 3)
├── miniapp/
│   └── index.html      # Telegram Mini App (повний веб-інтерфейс)
├── data/
│   └── db.json         # База даних (JSON)
├── requirements.txt    # Python залежності
├── render.yaml         # Конфіг для Render.com
└── start.sh            # Скрипт запуску
```

## Налаштування

### 1. Змінні середовища

| Змінна | Опис |
|--------|------|
| `BOT_TOKEN` | Токен від BotFather |
| `WEBAPP_URL` | URL GitHub Pages (міні-апп) |

### 2. GitHub Pages (Mini App)

1. Створи репозиторій `bees-house` на GitHub
2. Завантаж вміст папки `miniapp/` в корінь репо
3. Settings → Pages → Source: `main` branch, `/ (root)`
4. URL буде: `https://YOUR_USERNAME.github.io/bees-house`

### 3. Render.com (Бот)

1. Зареєструйся на render.com
2. New → Background Worker
3. Підключи GitHub репозиторій
4. Environment Variables:
   - `BOT_TOKEN` = твій токен
   - `WEBAPP_URL` = URL з GitHub Pages
5. Deploy!

### 4. Локальний запуск

```bash
pip install -r requirements.txt
export BOT_TOKEN="ваш_токен"
export WEBAPP_URL="https://your-username.github.io/bees-house"
cd bot && python bot.py
```

## Команди бота

| Команда/Кнопка | Дія |
|----------------|-----|
| `/start` | Головне меню |
| 🏠 Головна | Загальна статистика |
| 👷 Виконавці | Список з боргами |
| 🔨 Рамки | Додати збиті рамки |
| 💰 Виплата | Виплатити виконавцю |
| 📊 Звіт | Звіт по виконавцях |
| 📱 Відкрити додаток | Повний Mini App |

## Оновлення через Git

```bash
git add .
git commit -m "оновлення"
git push
```
Render автоматично перезапустить бота.
