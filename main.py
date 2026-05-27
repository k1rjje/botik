# Убиваем все старые процессы перед запуском
import requests
import time
import os

TOKEN = "8800514965:AAFTf7rzwTKFR5BoLGYY0Mn7OweraNIWCM8"

print("Очистка старых сессий бота...")
for i in range(5):
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook?drop_pending_updates=True", timeout=3)
        time.sleep(1)
        print(f"Попытка {i + 1} выполнена")
    except Exception as e:
        print(f"Попытка {i + 1}: {e}")

print("Старые сессии очищены, запускаем бота...\n")
time.sleep(2)

os.system("!pip install python-telegram-bot")
os.system("!pip install nest_asyncio -q")

import json
import random
import nest_asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import re
from datetime import date, datetime

nest_asyncio.apply()


def escape_markdown(text):
    return text.replace('*', '').replace('_', '').replace('`', '')


PICTURES = ["pic1.png", "pic2.png", "pic3.png", "pic4.png", "pic5.png", "pic6.png", "pic7.png", "pic8.png", "pic9.png",
            "pic10.png", "pic11.png", "pic12.png", "pic13.png", "pic14.png"]
available_pictures = list(PICTURES)

# Загрузка заданий паронимов
with open("tasks.txt", "r", encoding="utf-8") as f:
    lines = [x.strip() for x in f if x.strip()]

tasks = []
for i, line in enumerate(lines):
    if line.startswith("Ответ:"):
        answer = line.replace("Ответ:", "").strip()
        if '|' in answer:
            answer = answer.split('|')[0].strip()
        task_lines = []
        j = i - 1
        while j >= 0 and not lines[j].startswith("Ответ:"):
            line_text = lines[j]
            if not any(x in line_text for x in ['Тип', '№', 'i']):
                if not line_text.replace('.', '').replace('-', '').isdigit():
                    task_lines.insert(0, line_text)
            j -= 1
        tasks.append({"text": "\n".join(task_lines), "answer": answer})

TASKS = [{"text": escape_markdown(t['text']), "answer": t['answer']} for t in tasks]
print(f"Загружено {len(TASKS)} заданий для Паронимов")

with open('ege_tasks_1.json', 'r', encoding='utf-8') as f:
    raw_ege_tasks_1_data = json.load(f)

bot_tasks_set_1 = []
for task_raw in raw_ege_tasks_1_data:
    q_text = task_raw['problem_text']
    raw_answer_from_json = task_raw['answer']
    ans_match = re.search(r'Ответ:\s*(\d+)', raw_answer_from_json, re.IGNORECASE)
    ans = ans_match.group(1).strip() if ans_match else ""
    if ans:
        bot_tasks_set_1.append({
            "id": task_raw['problem_number'],
            "text": escape_markdown(q_text),
            "answer": ans.lower()
        })

print(f"Загружено {len(bot_tasks_set_1)} заданий из ege_tasks_1.json")


# Загрузка заданий "Слитно/Раздельно"
def ifsep(s):
    if "/C/" in s or "/С/" in s:
        return "Слитно"
    else:
        return "Раздельно"


f = open('task13.txt', 'r', encoding='utf-8')
t13_tasks = []
k = f.readline().strip()
counter = 1
while k != "":
    t13_tasks.append({"id": counter, "text": k.replace("/C/", "").replace("/С/", ""), "answer": ifsep(k)})
    k = f.readline().strip()
    counter += 1
f.close()

# Общий список всех заданий
ALL_TASKS = bot_tasks_set_1 + TASKS + t13_tasks
print(f"Всего заданий для случайного режима: {len(ALL_TASKS)}")

user_ans = {}
user_streaks = {}
user_solved_tasks = {}


def get_correct_word_form(number, form1, form2, form3):
    if number % 100 == 11:
        return form3
    elif number % 10 == 1:
        return form1
    elif number % 100 in [12, 13, 14]:
        return form3
    elif number % 10 in [2, 3, 4]:
        return form2
    else:
        return form3


async def send_random_photo(chat_id, context):
    global available_pictures
    if not PICTURES:
        return
    if not available_pictures:
        available_pictures = list(PICTURES)
    pic = random.choice(available_pictures)
    available_pictures.remove(pic)
    try:
        with open(pic, "rb") as img:
            await context.bot.send_photo(chat_id=chat_id, photo=img)
    except FileNotFoundError:
        await send_random_photo(chat_id, context)
    except Exception as e:
        await send_random_photo(chat_id, context)


def mark_task_completed(uid, context):
    """Удаляет текущее задание из available_tasks и добавляет в решённые"""
    task = context.user_data.get('current_task_obj')
    if not task:
        return
    available = context.user_data.get('available_tasks')
    if available and task in available:
        available.remove(task)
        context.user_data['available_tasks'] = available
    task_id = task.get('id', task['text'])
    if uid not in user_solved_tasks:
        user_solved_tasks[uid] = set()
    user_solved_tasks[uid].add(task_id)
    if uid in user_ans:
        del user_ans[uid]
    if 'current_task_obj' in context.user_data:
        del context.user_data['current_task_obj']


async def send_random_task(update_or_query, context, set_name_display=None, is_retry=False):
    uid = update_or_query.effective_user.id
    chat_id = update_or_query.effective_chat.id

    if is_retry and 'current_task_obj' in context.user_data:
        task = context.user_data['current_task_obj']
        selected_task_type_key = context.user_data.get('selected_task_type_key')
    else:
        available_tasks = context.user_data.get('available_tasks')
        if not available_tasks:
            total_solved = len(user_solved_tasks.get(uid, set()))
            total_all = len(ALL_TASKS)
            if total_solved >= total_all:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Да!", callback_data='restart_all_tasks')],
                    [InlineKeyboardButton("Нет, я всё!", callback_data='tired')]
                ])
                await context.bot.send_message(chat_id=chat_id,
                                               text="Ничего себе! Все задания прорешаны! Начнём заново?",
                                               reply_markup=keyboard)
            else:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Да!", callback_data='restart_current_type')],
                    [InlineKeyboardButton("Нет, вернуться к выбору типа", callback_data='back_to_main_menu')]
                ])
                await context.bot.send_message(chat_id=chat_id,
                                               text="Ничего себе! Все задания этого типа прорешаны! Начнём заново?",
                                               reply_markup=keyboard)
            return

        task = random.choice(available_tasks)
        context.user_data['current_task_obj'] = task
        context.user_data['current_task_text'] = task['text']
        user_ans[uid] = task['answer']
        selected_task_type_key = context.user_data.get('selected_task_type_key')
        context.user_data['task_counter'] = context.user_data.get('task_counter', 0) + 1

    task_display_number = context.user_data.get('task_counter', 1)
    prefix = f"Выбран тип {set_name_display}.\n\n" if set_name_display else ""
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"{prefix}📝 *Задание {task_display_number}*\n\n{task['text']}",
        parse_mode='Markdown'
    )

    if selected_task_type_key == 'set_4':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Слитно", callback_data='answer_slitno')],
            [InlineKeyboardButton("Раздельно", callback_data='answer_razdelno')]
        ])
        await context.bot.send_message(chat_id=chat_id, text="Выбери ответ:", reply_markup=keyboard)
    else:
        await context.bot.send_message(chat_id=chat_id, text="✏️ *Напиши ответ:*", parse_mode='Markdown')


async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("Орфография", callback_data='choose_set_1')],
        [InlineKeyboardButton("Паронимы", callback_data='choose_set_2')],
        [InlineKeyboardButton("Слитно/Раздельно", callback_data='choose_set_4')],
        [InlineKeyboardButton("🎲 Случайное", callback_data='choose_random')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(
        "Привет! Это бот для подготовки к ЕГЭ по русскому языку. Выбери, чем займешься сегодня 👇",
        reply_markup=reply_markup
    )


async def show_task_types(update, context):
    keyboard = [
        [InlineKeyboardButton("Орфография", callback_data='choose_set_1')],
        [InlineKeyboardButton("Паронимы", callback_data='choose_set_2')],
        [InlineKeyboardButton("Слитно/Раздельно", callback_data='choose_set_4')],
        [InlineKeyboardButton("🎲 Случайное", callback_data='choose_random')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(
        "Выбери тип заданий, которые будем тренировать:",
        reply_markup=reply_markup
    )


async def skolko_command(update, context):
    ege = date(2026, 6, 24)
    now = datetime.now()
    n = (ege - now.date()).days
    day_word = get_correct_word_form(n, "день", "дня", "дней")
    await update.message.reply_text(f"До ЕГЭ осталось {n} {day_word}")


async def button_callback_handler(update, context):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    chat_id = query.message.chat.id

    if query.data == 'choose_set_1':
        filtered_tasks = [t for t in bot_tasks_set_1 if t.get('id', t['text']) not in user_solved_tasks.get(uid, set())]
        context.user_data['available_tasks'] = filtered_tasks
        context.user_data['selected_task_type_key'] = 'set_1'
        context.user_data['task_counter'] = 0
        await query.message.delete()
        await send_random_task(update, context, "Орфография")
    elif query.data == 'choose_set_2':
        filtered_tasks = [t for t in TASKS if t.get('id', t['text']) not in user_solved_tasks.get(uid, set())]
        context.user_data['available_tasks'] = filtered_tasks
        context.user_data['selected_task_type_key'] = 'set_2'
        context.user_data['task_counter'] = 0
        await query.message.delete()
        await send_random_task(update, context, "Паронимы")
    elif query.data == 'choose_set_4':
        filtered_tasks = [t for t in t13_tasks if t.get('id', t['text']) not in user_solved_tasks.get(uid, set())]
        context.user_data['available_tasks'] = filtered_tasks
        context.user_data['selected_task_type_key'] = 'set_4'
        context.user_data['task_counter'] = 0
        await query.message.delete()
        await send_random_task(update, context, "Слитно/Раздельно")
    elif query.data == 'choose_random':
        filtered_tasks = [t for t in ALL_TASKS if t.get('id', t['text']) not in user_solved_tasks.get(uid, set())]
        context.user_data['available_tasks'] = filtered_tasks
        context.user_data['selected_task_type_key'] = 'random'
        context.user_data['task_counter'] = 0
        await query.message.delete()
        await send_random_task(update, context, "Случайный режим")
    elif query.data == 'get_another_task':
        if uid in user_ans:
            del user_ans[uid]
        if 'current_task_obj' in context.user_data:
            task = context.user_data['current_task_obj']
            available = context.user_data.get('available_tasks')
            if available and task in available:
                available.remove(task)
                context.user_data['available_tasks'] = available
            del context.user_data['current_task_obj']
        await query.message.delete()
        await send_random_task(update, context)
    elif query.data == 'back_to_main_menu':
        if 'available_tasks' in context.user_data:
            del context.user_data['available_tasks']
        if 'selected_task_type_key' in context.user_data:
            del context.user_data['selected_task_type_key']
        if 'current_task_obj' in context.user_data:
            del context.user_data['current_task_obj']
        context.user_data['task_counter'] = 0
        if uid in user_ans:
            del user_ans[uid]
        await query.message.delete()
        await show_task_types(update, context)
    elif query.data == 'tired':
        await query.message.delete()
        await context.bot.send_message(chat_id=chat_id, text="Ну иди отдохни. Ты молодец! 🫶")
        if uid in user_ans:
            del user_ans[uid]
    elif query.data == 'restart_all_tasks':
        if uid in user_solved_tasks:
            del user_solved_tasks[uid]
        selected = context.user_data.get('selected_task_type_key')
        if selected == 'set_1':
            context.user_data['available_tasks'] = list(bot_tasks_set_1)
            display = "Орфография"
        elif selected == 'set_2':
            context.user_data['available_tasks'] = list(TASKS)
            display = "Паронимы"
        elif selected == 'set_4':
            context.user_data['available_tasks'] = list(t13_tasks)
            display = "Слитно/раздельно"
        elif selected == 'random':
            context.user_data['available_tasks'] = list(ALL_TASKS)
            display = "Случайный режим"
        else:
            return
        context.user_data['task_counter'] = 0
        if uid in user_ans:
            del user_ans[uid]
        await query.message.delete()
        await context.bot.send_message(chat_id=chat_id, text=f"Начинаем заново! Выбран тип {display}.")
        await send_random_task(update, context, display)
    elif query.data == 'restart_current_type':
        selected = context.user_data.get('selected_task_type_key')
        if selected == 'set_1':
            context.user_data['available_tasks'] = list(bot_tasks_set_1)
            display = "Орфография"
            type_ids = {t.get('id', t['text']) for t in bot_tasks_set_1}
            if uid in user_solved_tasks:
                user_solved_tasks[uid] -= type_ids
        elif selected == 'set_2':
            context.user_data['available_tasks'] = list(TASKS)
            display = "Паронимы"
            type_ids = {t.get('id', t['text']) for t in TASKS}
            if uid in user_solved_tasks:
                user_solved_tasks[uid] -= type_ids
        elif selected == 'set_4':
            context.user_data['available_tasks'] = list(t13_tasks)
            display = "Слитно/раздельно"
            type_ids = {t.get('id', t['text']) for t in t13_tasks}
            if uid in user_solved_tasks:
                user_solved_tasks[uid] -= type_ids
        elif selected == 'random':
            if uid in user_solved_tasks:
                del user_solved_tasks[uid]
            context.user_data['available_tasks'] = list(ALL_TASKS)
            display = "Случайный режим"
        else:
            return
        context.user_data['task_counter'] = 0
        if uid in user_ans:
            del user_ans[uid]
        await query.message.delete()
        await context.bot.send_message(chat_id=chat_id, text=f"Начинаем заново! Выбран тип {display}.")
        await send_random_task(update, context, display)
    elif query.data == 'incorrect_try_again':
        await query.message.delete()
        await send_random_task(update, context, is_retry=True)
    elif query.data == 'incorrect_show_answer':
        await query.message.delete()
        want = user_ans.get(uid)
        if want:
            await context.bot.send_message(chat_id=chat_id, text=f"Правильный ответ: *{want}*", parse_mode='Markdown')
            mark_task_completed(uid, context)
            user_streaks[uid] = 0
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Ещё!", callback_data='get_another_task')],
                [InlineKeyboardButton("К выбору типа", callback_data='back_to_main_menu')]
            ])
            await context.bot.send_message(chat_id=chat_id, text="Что дальше?", reply_markup=keyboard)
    elif query.data in ('answer_slitno', 'answer_razdelno'):
        correct_answer = user_ans.get(uid)
        if not correct_answer:
            await query.message.reply_text("Сначала выбери задание через /start")
            return
        user_answer = "Слитно" if query.data == 'answer_slitno' else "Раздельно"
        current_streak = user_streaks.get(uid, 0)
        if user_answer.lower() == correct_answer.lower():
            current_streak += 1
            user_streaks[uid] = current_streak
            await query.message.reply_text(f"✅ Правильно! Это {current_streak}-й правильный ответ подряд.")
            if current_streak % 5 == 0:
                await query.message.reply_text(f"🎉 Ты набрал {current_streak} правильных ответов подряд, поздравляю! 🎉")
            mark_task_completed(uid, context)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Ещё!", callback_data='get_another_task')],
                [InlineKeyboardButton("К выбору типа", callback_data='back_to_main_menu')]
            ])
            await query.message.reply_text("Что дальше?", reply_markup=keyboard)
        else:
            broken = current_streak
            user_streaks[uid] = 0
            await send_random_photo(chat_id, context)
            if broken > 0:
                await query.message.reply_text(f"❌ Неправильно. Прерван страйк из {broken} правильных ответов. Можешь попробовать ещё раз!")
            else:
                await query.message.reply_text("❌ Неправильно. Можешь попробовать ещё раз!")
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Попытаться ещё раз!", callback_data='incorrect_try_again')],
                [InlineKeyboardButton("Показать ответ", callback_data='incorrect_show_answer')]
            ])
            await query.message.reply_text("Выбери действие:", reply_markup=keyboard)
        await query.message.delete()


async def check(update, context):
    uid = update.effective_user.id
    text = update.message.text.lower().strip()
    if text in ["сколько?", "сколько"]:
        await skolko_command(update, context)
        return
    if uid not in user_ans:
        keyboard = [
            [InlineKeyboardButton("Орфография", callback_data='choose_set_1')],
            [InlineKeyboardButton("Паронимы", callback_data='choose_set_2')],
            [InlineKeyboardButton("Слитно/Раздельно", callback_data='choose_set_4')],
            [InlineKeyboardButton("🎲 Случайное", callback_data='choose_random')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Сначала выбери тип задания!", reply_markup=reply_markup)
        return
    if context.user_data.get('selected_task_type_key') == 'set_4':
        await update.message.reply_text("Пожалуйста, используй кнопки 'Слитно' или 'Раздельно' для ответа.")
        return
    raw_user_input = update.message.text.lower().replace('ё', 'е').strip()
    want = user_ans[uid].lower().replace('ё', 'е').strip()
    if want.isdigit():
        got = raw_user_input.replace(" ", "")
    else:
        got = " ".join(raw_user_input.split())
        want = " ".join(want.split())
    current_streak = user_streaks.get(uid, 0)
    if got == want:
        current_streak += 1
        user_streaks[uid] = current_streak
        await update.message.reply_text(f"✅ Правильно! Это {current_streak}-й правильный ответ подряд.")
        if current_streak % 5 == 0:
            await update.message.reply_text(f"🎉 Ты набрал {current_streak} правильных ответов подряд, поздравляю! 🎉")
        mark_task_completed(uid, context)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Ещё!", callback_data='get_another_task')],
            [InlineKeyboardButton("К выбору типа", callback_data='back_to_main_menu')]
        ])
        await update.message.reply_text("Что дальше?", reply_markup=keyboard)
    else:
        broken = current_streak
        user_streaks[uid] = 0
        await send_random_photo(update.effective_chat.id, context)
        if broken > 0:
            await update.message.reply_text(f"❌ Неправильно. Прерван страйк из {broken} правильных ответов. Можешь попробовать ещё раз!")
        else:
            await update.message.reply_text("❌ Неправильно. Можешь попробовать ещё раз!")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Попытаться ещё раз!", callback_data='incorrect_try_again')],
            [InlineKeyboardButton("Показать ответ", callback_data='incorrect_show_answer')]
        ])
        await update.message.reply_text("Выбери действие:", reply_markup=keyboard)


app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_callback_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check))

print("Бот запущен! Отправьте /start в Telegram")
app.run_polling(drop_pending_updates=True)
