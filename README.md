# ✈️ Travel Advisor Bot

Telegram-бот с опросником для подбора путешествий, интегрированный с Perplexity AI.

## Возможности

- 7-шаговый опросник (возраст, пол, увлечения, состав группы, бюджет, даты, длительность)
- 3 персонализированных рекомендации с ценами
- Уточняющие вопросы в режиме диалога
- Детальная программа поездки: авиабилеты, отели, трансфер, план по дням, итоговый бюджет
- Интеграция с Perplexity Sonar Pro для актуальных данных

## Локальный запуск

```bash
pip install -r requirements.txt

# Создайте .env файл:
cp .env.example .env
# Заполните TELEGRAM_BOT_TOKEN и PERPLEXITY_API_KEY

python bot.py
```

## Деплой на Railway

### Вариант 1: через GitHub (рекомендуется)

1. Создайте репозиторий на GitHub и залейте код
2. Зайдите на [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
3. Выберите ваш репозиторий
4. В разделе **Variables** добавьте переменные окружения:
   - `TELEGRAM_BOT_TOKEN` = ваш токен
   - `PERPLEXITY_API_KEY` = ваш ключ
5. Railway автоматически обнаружит `railway.json` и задеплоит бота

### Вариант 2: через Railway CLI

```bash
npm install -g @railway/cli
railway login
railway init
railway up

# Добавьте переменные:
railway variables set TELEGRAM_BOT_TOKEN=ваш_токен
railway variables set PERPLEXITY_API_KEY=ваш_ключ
```

## Переменные окружения

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather |
| `PERPLEXITY_API_KEY` | API ключ от perplexity.ai/settings/api |

## Команды бота

| Команда | Действие |
|---|---|
| `/start` | Начать новый опрос |
| `/cancel` | Отменить текущий диалог |
| `программа` | Составить детальный план поездки |
