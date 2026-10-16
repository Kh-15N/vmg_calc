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
PROXY_SERVER = ""


# ==============================================================================

def parse_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS props (
            "id" INTEGER,
            "name" TEXT,
            "D" REAL,
            "H" REAL,
            "source" INTEGER,
            PRIMARY KEY("id" AUTOINCREMENT)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS props_stats (
            "id" INTEGER,
            "name" TEXT NOT NULL,
            "RPM" REAL,
            "CT" REAL,
            "CP" REAL,
            "T" REAL,
            "eta" REAL,
            "P" REAL
        )
    ''')
    conn.commit()
    return conn


def get_propellers_list():
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
    if not prop_link:
        return None

    url = f"https://database.tytorobotics.com{prop_link}" if prop_link.startswith('/') else prop_link

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)

        test_links = []
        try:
            page.wait_for_load_state('networkidle', timeout=20000)

            try:
                length_select = page.locator('select').filter(has_text="100")
                if length_select.count() > 0:
                    length_select.first.select_option(label="100")
                    page.wait_for_timeout(1500)
                else:
                    show_100_btn = page.locator('a:has-text("100"), button:has-text("100")').first
                    show_100_btn.click()
                    page.wait_for_timeout(1500)
            except Exception:
                pass

            all_links = page.eval_on_selector_all('a', 'elements => elements.map(el => el.getAttribute("href"))')

            for link in all_links:
                if not link:
                    continue
                if '/tests/' in link and 'upload' not in link and not link.rstrip('/').endswith('/tests'):
                    test_links.append(link)
        except Exception as e:
            print(f"  [!] Ошибка при поиске ссылок на тесты: {e}")
            return None

        if not test_links:
            print(f"  [!] Ссылки на тесты не найдены.")
            return None

        total_tests = len(test_links)
        print(f"  [*] Найдено тестов для проверки: {total_tests}")

        for i, test_link in enumerate(test_links, 1):
            test_url = f"https://database.tytorobotics.com{test_link}" if test_link.startswith('/') else test_link
            print(f"  [*] Проверяем тест {i} из {total_tests}...")

            try:
                page.goto(test_url, wait_until="domcontentloaded", timeout=30000)

                try:
                    page.wait_for_selector('table', timeout=15000)
                except Exception:
                    print(f"      -> Таблица не найдена, пропускаем.")
                    continue

                html_content = page.content()
                tables = pd.read_html(io.StringIO(html_content))
                target_table = None

                for df in tables:
                    if ('Rotation speed (rpm)' in df.columns and
                            'Thrust (kgf)' in df.columns and
                            'Mechanical power (W)' in df.columns):
                        target_table = df
                        break

                if target_table is not None:
                    target_table['Thrust (kgf)'] = pd.to_numeric(target_table['Thrust (kgf)'], errors='coerce')
                    target_table['Rotation speed (rpm)'] = pd.to_numeric(target_table['Rotation speed (rpm)'],
                                                                         errors='coerce')
                    target_table['Mechanical power (W)'] = pd.to_numeric(target_table['Mechanical power (W)'],
                                                                         errors='coerce')

                    clean_df = target_table.dropna(
                        subset=['Thrust (kgf)', 'Rotation speed (rpm)', 'Mechanical power (W)'])

                    if not clean_df.empty:
                        all_rows = []
                        for _, row in clean_df.iterrows():
                            all_rows.append({
                                'T': float(row['Thrust (kgf)']),
                                'RPM': float(row['Rotation speed (rpm)']),
                                'P': float(row['Mechanical power (W)'])
                            })

                        print(f"      -> Успех! Найдено {len(all_rows)} строк с валидными данными.")
                        return all_rows
                    else:
                        print(f"      -> Таблица есть, но нет валидных данных, пропускаем.")
                else:
                    print(f"      -> Нужная таблица не найдена, пропускаем.")
            except Exception as e:
                print(f"  [!] Ошибка при обработке теста {test_url}: {e}")
                continue

    except Exception as e:
        print(f"  [!] Общая ошибка при парсинге {url}: {e}")

    print(f"  [!] Не удалось найти подходящий тест.")
    return None


def main():
    print("Инициализация базы данных...")
    conn = init_db(DB_PATH)
    cursor = conn.cursor()

    print("Получение списка пропеллеров...")
    propellers = get_propellers_list()
    propellers.sort(key=lambda x: x['d'] if x['d'] else 0)
    print(f"Найдено {len(propellers)} пропеллеров в каталоге.")

    if not propellers:
        print("Список пропеллеров пуст.")
        conn.close()
        return


    with sync_playwright() as p:
        proxy_settings = {"server": PROXY_SERVER} if PROXY_SERVER else None
        browser = p.chromium.launch(headless=True, proxy=proxy_settings)
        page = browser.new_page()

        for prop in propellers:
            print(f"\n{'=' * 60}")
            print(f"Обработка пропеллера: {prop['name']}")

            # ОБЕРТЫВАЕМ ВСЮ РАБОТУ С БД В TRY-EXCEPT
            try:
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

                if not prop_id:
                    raise Exception("Не удалось получить ID пропеллера из БД")

                all_stats = get_test_stats_for_propeller(page, prop['link'])

                if all_stats and prop_id:
                    data_to_insert = []

                    for stats in all_stats:
                        T = float(stats['T'])
                        P = float(stats['P'])
                        RPM = float(stats['RPM'])

                        d = float(prop['d']) * 2.54 * 0.01
                        n = RPM / 60

                        if n > 0 and d > 0 and T > 0:
                            CT = T / (rho * n ** 2 * d ** 4)
                            CP = P / (rho * n ** 3 * d ** 5)
                            eta = 1 / (n ** 0.5 * d ** 2) * T ** 1.5 / P
                        else:
                            CT = CP = eta = 0

                        data_to_insert.append((prop_id, prop['name'], RPM, CT, CP, T, P, eta))

                    cursor.executemany('''
                        INSERT INTO props_stats (id, name, RPM, CT, CP, T, P, eta)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', data_to_insert)

                    print(f"  -> УСПЕХ: Записано {len(data_to_insert)} строк в БД.")
                else:
                    print(f"  -> НЕУДАЧА: Не удалось найти данные тестов")

            except Exception as e:
                # Если произошла ошибка при записи в БД, выводим её и откатываем транзакцию
                print(f"  [!] КРИТИЧЕСКАЯ ОШИБКА БД для '{prop['name']}': {e}")
                conn.rollback()  # Откатываем, чтобы "битая" транзакция не сломала следующие записи
                continue  # Переходим к следующему пропеллеру

            time.sleep(1.5)

        browser.close()

    # Фиксируем все успешные изменения в базе
    conn.commit()
    conn.close()
    print("\nГотово! Данные успешно сохранены в базу.")


if __name__ == "__main__":
    main()