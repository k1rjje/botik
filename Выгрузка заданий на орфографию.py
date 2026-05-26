import requests
from bs4 import BeautifulSoup
import re
import json

def scrape_problems_and_answers(page_url, start_problem_num):
    response = requests.get(page_url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    problems_data_on_page = []

    problem_containers = soup.find_all('div', class_='prob_view')

    if not problem_containers:
        print(f"No problem containers found on {page_url}. Please check the class name.")
        return [], 0

    current_problem_num = start_problem_num
    for problem_container in problem_containers:
        problem_text = "N/A"
        answer_text = "N/A"

        # получаем все содержимое
        full_content = problem_container.get_text(separator=' ', strip=True)
        # убираем лишнее
        full_content = full_content.replace('\xad', '').replace('\u202f', ' ').strip()

        # конец текста задания (на 'Ответ:' или 'Пояснение')
        answer_keyword_index = full_content.find("Ответ:")
        explanation_start_match = re.search(r'Пояснение[\s.:]', full_content)
        explanation_index = explanation_start_match.start() if explanation_start_match else -1

        end_of_problem_text_index = len(full_content)

        if answer_keyword_index != -1 and explanation_index != -1:
            end_of_problem_text_index = min(answer_keyword_index, explanation_index)
        elif answer_keyword_index != -1:
            end_of_problem_text_index = answer_keyword_index
        elif explanation_index != -1:
            end_of_problem_text_index = explanation_index

        # начало с 'Укажите варианты ответов'
        start_problem_text_marker = "Укажите варианты ответов"
        problem_start_index = full_content.find(start_problem_text_marker)

        if problem_start_index != -1:
            problem_text = full_content[problem_start_index:end_of_problem_text_index].strip()
        else:
            # если маркера нет
            problem_text = full_content[:end_of_problem_text_index].strip()

        if not problem_text: # если нет текста задания
            problem_text = "N/A"

        # ответ начиная с 'Ответ:' в формате 'Ответ: [digits]'
        answer_match = re.search(r'Ответ:\s*(\d+)[.|]?', full_content, re.IGNORECASE)
        if answer_match:
            answer_value = answer_match.group(1).strip()
            answer_text = f"Ответ: {answer_value}"
        else:
            answer_text = "Ответ не найден."

        # Post-process problem_text to add newlines for numbered options
        if problem_text != "N/A":
            # чиним пробелы
            problem_text = re.sub(r'\s*(\d+\)\s*)', r'###OPTION_START###\1', problem_text)
            # отступы (абзацы)
            problem_text = problem_text.replace('###OPTION_START###1)', '\n\n1)', 1)
            problem_text = problem_text.replace('###OPTION_START###', '\n')
            problem_text = re.sub(r'\n{3,}', '\n\n', problem_text)
            # опять пробелы
            problem_text = problem_text.strip()

        problem_text = problem_text.replace('\xad', '').replace('\u202f', ' ').replace('...', '..').strip()
        answer_text = answer_text.replace('\xad', '').replace('\u202f', ' ').strip()

        # добавляем только если есть задание и ответ
        if problem_text != "N/A" and answer_text != "Ответ не найден.":
            problems_data_on_page.append({
                'problem_number': current_problem_num,
                'problem_text': problem_text,
                'answer': answer_text
            })
            current_problem_num += 1
        else:
            print(f"DEBUG: Skipping problem {current_problem_num} due to extraction issues. Page: {page_url}. Problem Text: '{problem_text}' (Length: {len(problem_text)}). Answer Text: '{answer_text}' (Length: {len(answer_text) if answer_text else 0}).")
            current_problem_num += 1

    return problems_data_on_page, current_problem_num

ege_tasks_1_data = [] # для хранения обработанных данных
global_next_problem_num = 1

categories_to_scrape = [
    {"category_id": 380, "max_pages": 3},
    {"category_id": 358, "max_pages": 10},
    {"category_id": 259, "max_pages": 18},
    {"category_id": 381, "max_pages": 5},
    {"category_id": 344, "max_pages": 6},
    {"category_id": 348, "max_pages": 20},
    {"category_id": 382, "max_pages": 5},
    {"category_id": 343, "max_pages": 5},
    {"category_id": 351, "max_pages": 21},
    {"category_id": 383, "max_pages": 4},
    {"category_id": 346, "max_pages": 6},
    {"category_id": 350, "max_pages": 21},
]

base_url_template = "https://rus-ege.sdamgia.ru/test?category_id={category_id}&filter=all"

for category_info in categories_to_scrape:
    category_id = category_info["category_id"]
    max_pages = category_info["max_pages"]
    base_category_url = base_url_template.format(category_id=category_id)

    print(f"\nScraping from category_id={category_id}")
    for page_num in range(1, max_pages):
        page_url = f"{base_category_url}&page={page_num}" if page_num > 1 else base_category_url
        page_problems, global_next_problem_num = scrape_problems_and_answers(page_url, global_next_problem_num)
        ege_tasks_1_data.extend(page_problems)

# сохраняем
if ege_tasks_1_data:
    with open("ege_tasks_1.json", "w", encoding="utf-8") as f:
        json.dump(ege_tasks_1_data, f, ensure_ascii=False, indent=4)
    print(f"Successfully scraped {len(ege_tasks_1_data)} problems and saved to ege_tasks_1.json")
else:
    print("Ничего не нашлось.")
