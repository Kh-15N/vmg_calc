import sqlite3
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import json
import io
from playwright.sync_api import sync_playwright

DB_PATH = "props_data_base.db"
rho = 1.225

# ==============================================================================
# НАСТРОЙКА ПРОКСИ
# ==============================================================================
# Впишите сюда адрес вашего прокси, например: "http://192.168.1.100:8080"
# Если прокси не нужен, оставьте пустым: ""
PROXY_SERVER = ""


# ==============================================================================

def parse_float(val):
    """Безопасное преобразование строки в float."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def init_db(db_path):
    """Инициализация базы данных и создание таблиц."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS props (
            "id"	INTEGER,
            "name"	TEXT,
            "D"	REAL,
            "H"	REAL,
            "source"	INTEGER,
            PRIMARY KEY("id" AUTOINCREMENT)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS props_stats (
            "id"	INTEGER,
            "name"	TEXT NOT NULL,
            "RPM"	REAL,
            "CT"	REAL,
            "CP"	REAL,
            "T"	REAL,
            "eta"	REAL,
            "P"	REAL
        )
    ''')
    conn.commit()
    return conn


def get_propellers_list():
    """Получает список пропеллеров из встроенного JSON на странице каталога."""
    url = "https://database.tytorobotics.com/propellers"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    proxies = {"http": PROXY_SERVER, "https": PROXY_SERVER} if PROXY_SERVER else None

    try:
        response = requests.get(url, headers=headers, proxies=proxies, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"[!] Ошибка сети при получении списка пропеллеров: {e}")
        return []

    html = response.text
    propellers = []

    # Сайт рендерит таблицу через JS, поэтому ищем встроенный JSON-массив
    match = re.search(r'\[\s*\{\s*"name"\s*:\s*"[^"]*propeller[^"]*"', html, re.IGNORECASE)
    if not match:
        match = re.search(r'\[\s*\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"brand"', html)

    if match:
        start_idx = match.start()
        bracket_count = 0
        in_array = False
        array_start = -1
        array_end = -1

        for i in range(start_idx, len(html)):
            if html[i] == '[':
                if not in_array:
                    in_array = True
                    array_start = i
                bracket_count += 1
            elif html[i] == ']':
                bracket_count -= 1
                if in_array and bracket_count == 0:
                    array_end = i + 1
                    break

        if array_start != -1 and array_end != -1:
            json_str = html[array_start:array_end]
            try:
                data = json.loads(json_str)
                for item in data:
                    measures = item.get('measures', {})
                    d_val = measures.get('diameter', {}).get('value') if 'diameter' in measures else None
                    h_val = measures.get('pitch', {}).get('value') if 'pitch' in measures else None

                    propellers.append({
                        'name': item.get('title') or item.get('name'),
                        'd': parse_float(d_val),
                        'h': parse_float(h_val),
                        'link': item.get('link')
                    })
            except json.JSONDecodeError as e:
                print(f"[!] Ошибка декодирования JSON: {e}")

    return propellers


def get_test_stats_for_propeller(page, prop_link):
    """Находит первый тест для пропеллера и возвращает макс. тягу, мощность и обороты."""
    if not prop_link:
        return None

    url = f"https://database.tytorobotics.com{prop_link}" if prop_link.startswith('/') else prop_link

    try:
        # 1. Заходим на страницу пропеллера через Playwright
        page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # 2. Ищем ссылку на первый доступный тест
        test_link = None
        try:
            # Ждем полной загрузки страницы (включая отрисовку JS-таблиц и ссылок)
            page.wait_for_load_state('networkidle', timeout=20000)

            # Получаем все ссылки (атрибуты href) со страницы через JS
            all_links = page.eval_on_selector_all('a', 'elements => elements.map(el => el.getAttribute("href"))')

            # Фильтруем ссылки в Python (это надежнее, чем сложные CSS-селекторы)
            for link in all_links:
                if not link:
                    continue
                # Ищем ссылки, содержащие /tests/, но исключаем /tests/upload и просто /tests
                if '/tests/' in link and 'upload' not in link and not link.rstrip('/').endswith('/tests'):
                    test_link = link
                    break

        except Exception as e:
            print(f"  [!] Ошибка при поиске ссылок на тесты для {prop['name']}: {e}")
            return None

        if not test_link:
            # print(f"  [!] Ссылки на тесты не найдены для {prop['name']}")
            return None

        test_url = f"https://database.tytorobotics.com{test_link}" if test_link.startswith('/') else test_link

        # 3. Переходим на страницу теста
        page.goto(test_url, wait_until="domcontentloaded", timeout=30000)

        # Ждем появления таблицы с данными
        try:
            page.wait_for_selector('table', timeout=15000)
        except Exception:
            # Если таблица не появилась, возможно, данные подгружаются иначе
            pass

        # Получаем HTML отрендеренной страницы (со всеми JS-данными)
        html_content = page.content()

        # 4. Парсим таблицы на странице теста с помощью pandas
        import io
        tables = pd.read_html(io.StringIO(html_content))
        target_table = None

        for df in tables:
            if 'Rotation speed (rpm)' in df.columns and 'Thrust (kgf)' in df.columns:
                target_table = df
                break

        if target_table is not None:
            target_table['Thrust (kgf)'] = pd.to_numeric(target_table['Thrust (kgf)'], errors='coerce')
            target_table['Rotation speed (rpm)'] = pd.to_numeric(target_table['Rotation speed (rpm)'], errors='coerce')
            target_table['Mechanical power (W)'] = pd.to_numeric(target_table['Mechanical power (W)'], errors='coerce')

            clean_df = target_table.dropna(subset=['Thrust (kgf)', 'Rotation speed (rpm)', 'Mechanical power (W)'])

            if not clean_df.empty:
                max_thrust_idx = clean_df['Thrust (kgf)'].idxmax()
                row = clean_df.loc[max_thrust_idx]

                return {
                    'T': float(row['Thrust (kgf)']),
                    'RPM': float(row['Rotation speed (rpm)']),
                    'P': float(row['Mechanical power (W)'])
                }
    except Exception as e:
        print(f"  [!] Общая ошибка при парсинге {url}: {e}")

    return None


def main():
    print("Инициализация базы данных...")
    conn = init_db(DB_PATH)
    cursor = conn.cursor()

    print("Получение списка пропеллеров...")
    propellers = get_propellers_list()
    print(f"Найдено {len(propellers)} пропеллеров в каталоге.")

    if not propellers:
        print("Список пропеллеров пуст.")
        conn.close()
        return

    limit = 3
    print(f"Начало обработки (ограничено {limit} шт. для примера)...\n")

    # Инициализируем Playwright один раз для всех пропеллеров
    with sync_playwright() as p:
        proxy_settings = {"server": PROXY_SERVER} if PROXY_SERVER else None
        # headless=True для работы без открытия окна браузера
        browser = p.chromium.launch(headless=True, proxy=proxy_settings)
        page = browser.new_page()

        for prop in propellers[:limit]:
            print(f"Обработка: {prop['name']}")

            # 1. Записываем базовые данные в props
            cursor.execute('''
                INSERT OR IGNORE INTO props (name, D, H, source)
                VALUES (?, ?, ?, 5)
                RETURNING id
            ''', (prop['name'], prop['d'], prop['h']))

            result = cursor.fetchone()
            if result:
                prop_id = result[0]
            else:
                cursor.execute('SELECT id FROM props WHERE name = ?', (prop['name'],))
                res = cursor.fetchone()
                prop_id = res[0] if res else None

            # 2. Получаем статистику из тестов через Playwright
            stats = get_test_stats_for_propeller(page, prop['link'])

            if stats and prop_id:
                T = float(stats['T'])
                P = float(stats['P'])
                RPM = float(stats['RPM'])

                d = float(prop['d']) * 2.54 * 0.01
                n = RPM / 60

                if n > 0 and d > 0:
                    CT = T / (rho * n ** 2 * d ** 4)
                    CP = P / (rho * n ** 3 * d ** 5)
                    eta = 1 / (n ** 0.5 * d ** 2) * T ** 1.5 / P
                else:
                    CT = CP = eta = 0

                cursor.execute('''
                    INSERT INTO props_stats (id, name, RPM, CT, CP, T, P, eta)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (prop_id, prop['name'], RPM, CT, CP, T, P, eta))
                print(f"  -> Успешно: T={T}, P={P}, RPM={RPM}")
            else:
                print(f"  -> Не удалось найти данные тестов")

            time.sleep(1.5)

        browser.close()

    conn.commit()
    conn.close()
    print("\nГотово! Данные успешно сохранены в базу.")


if __name__ == "__main__":
    main()