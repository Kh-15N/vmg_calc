import sqlite3
import requests
import pandas as pd
import numpy as np
import time
import re
import json
import io
from playwright.sync_api import sync_playwright

DB_PATH = "motors_data_base.db"

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
        CREATE TABLE IF NOT EXISTS motors (
            "id" INTEGER,
            "name" TEXT,
            "KV" REAL,
            "weight" REAL,
            "source" INTEGER,
            PRIMARY KEY("id" AUTOINCREMENT)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS motors_stats (
            "id" INTEGER,
            "name" TEXT NOT NULL,
            "RPM" REAL,
            "Voltage" REAL,
            "Current" REAL,
            "Electrical_Power" REAL,
            "Mechanical_Power" REAL,
            "Torque" REAL,
            "Thrust" REAL,
            "is_restored" INTEGER
        )
    ''')
    conn.commit()
    return conn


def get_motors_list():
    url = "https://database.tytorobotics.com/motors"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    proxies = {"http": PROXY_SERVER, "https": PROXY_SERVER} if PROXY_SERVER else None

    try:
        response = requests.get(url, headers=headers, proxies=proxies, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"[!] Ошибка сети при получении списка моторов: {e}")
        return []

    html = response.text
    motors = []

    match = re.search(r'\[\s*\{\s*"name"\s*:\s*"[^"]*motor[^"]*"', html, re.IGNORECASE)
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
                    kv_val = measures.get('kv', {}).get('value') if 'kv' in measures else None
                    weight_val = measures.get('weight', {}).get('value') if 'weight' in measures else None

                    motors.append({
                        'name': item.get('title') or item.get('name'),
                        'kv': parse_float(kv_val),
                        'weight': parse_float(weight_val),
                        'link': item.get('link')
                    })
            except json.JSONDecodeError as e:
                print(f"[!] Ошибка декодирования JSON: {e}")

    return motors


def find_column(columns, substrings):
    for col in columns:
        col_clean = re.sub(r'[^\w]', '', col.lower())
        for sub in substrings:
            if sub in col_clean:
                return col
    return None


def get_test_stats_for_motor(page, motor_link):
    """Перебирает тесты, сохраняет все реальные точки и добавляет восстановленные между ними."""
    if not motor_link:
        return None

    url = f"https://database.tytorobotics.com{motor_link}" if motor_link.startswith('/') else motor_link

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
                    rpm_col = find_column(df.columns, ['rotationspeed', 'rpm'])
                    voltage_col = find_column(df.columns, ['voltage'])
                    current_col = find_column(df.columns, ['current'])
                    elec_power_col = find_column(df.columns, ['electricalpower'])
                    mech_power_col = find_column(df.columns, ['mechanicalpower'])

                    if all([rpm_col, voltage_col, current_col, elec_power_col, mech_power_col]):
                        target_table = df
                        target_table._cols = {
                            'rpm': rpm_col, 'voltage': voltage_col, 'current': current_col,
                            'elec_power': elec_power_col, 'mech_power': mech_power_col
                        }

                        torque_col = find_column(df.columns, ['torque'])
                        thrust_col = find_column(df.columns, ['thrust'])
                        if torque_col: target_table._cols['torque'] = torque_col
                        if thrust_col: target_table._cols['thrust'] = thrust_col
                        break

                if target_table is not None:
                    cols = target_table._cols

                    for key, col_name in cols.items():
                        target_table[col_name] = pd.to_numeric(target_table[col_name], errors='coerce')

                    subset_cols = [cols['rpm'], cols['mech_power']]
                    clean_df = target_table.dropna(subset=subset_cols).copy()

                    if not clean_df.empty:
                        # Сортируем по RPM
                        clean_df = clean_df.sort_values(by=cols['rpm']).reset_index(drop=True)

                        # Маппинг ключей на названия колонок в БД
                        db_cols_map = {
                            'voltage': 'Voltage',
                            'current': 'Current',
                            'elec_power': 'Electrical_Power',
                            'mech_power': 'Mechanical_Power',
                            'torque': 'Torque',
                            'thrust': 'Thrust'
                        }

                        all_rows = []

                        # Проходим по всем парам соседних реальных точек
                        for idx in range(len(clean_df) - 1):
                            row_curr = clean_df.iloc[idx]
                            row_next = clean_df.iloc[idx + 1]

                            rpm_curr = float(row_curr[cols['rpm']])
                            rpm_next = float(row_next[cols['rpm']])

                            # Добавляем текущую реальную точку
                            real_point = {'RPM': rpm_curr, 'is_restored': 0}
                            for key, col_name in cols.items():
                                if key == 'rpm': continue
                                db_col = db_cols_map.get(key, key.capitalize())
                                val = row_curr[col_name]
                                real_point[db_col] = float(val) if pd.notna(val) else 0.0
                            all_rows.append(real_point)

                            # Генерируем промежуточные точки, если разница достаточно большая
                            diff = rpm_next - rpm_curr
                            if diff > 0:
                                if diff > 100:
                                    step = 100.0
                                else:
                                    # Если разница меньше 100, делим пополам для одной промежуточной точки
                                    step = diff / 2.0

                                # Генерируем точки от rpm_curr + step до rpm_next (не включая)
                                interp_rpm = rpm_curr + step
                                while interp_rpm < rpm_next - 0.1:  # -0.1 для защиты от float-погрешностей
                                    # Линейная интерполяция
                                    weight = (interp_rpm - rpm_curr) / diff
                                    restored_point = {'RPM': interp_rpm, 'is_restored': 1}

                                    for key, col_name in cols.items():
                                        if key == 'rpm': continue
                                        db_col = db_cols_map.get(key, key.capitalize())

                                        val_curr = float(row_curr[col_name]) if pd.notna(row_curr[col_name]) else 0.0
                                        val_next = float(row_next[col_name]) if pd.notna(row_next[col_name]) else 0.0

                                        interp_val = val_curr + weight * (val_next - val_curr)
                                        restored_point[db_col] = interp_val

                                    all_rows.append(restored_point)
                                    interp_rpm += step

                        # Добавляем последнюю реальную точку
                        last_row = clean_df.iloc[-1]
                        last_point = {'RPM': float(last_row[cols['rpm']]), 'is_restored': 0}
                        for key, col_name in cols.items():
                            if key == 'rpm': continue
                            db_col = db_cols_map.get(key, key.capitalize())
                            val = last_row[col_name]
                            last_point[db_col] = float(val) if pd.notna(val) else 0.0
                        all_rows.append(last_point)

                        real_count = sum(1 for r in all_rows if r['is_restored'] == 0)
                        restored_count = sum(1 for r in all_rows if r['is_restored'] == 1)
                        print(f"      -> Успех! Реальных точек: {real_count}, восстановленных: {restored_count}.")
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

    print("Получение списка моторов...")
    motors = get_motors_list()
    print(f"Найдено {len(motors)} моторов в каталоге.")

    if not motors:
        print("Список моторов пуст.")
        conn.close()
        return


    with sync_playwright() as p:
        proxy_settings = {"server": PROXY_SERVER} if PROXY_SERVER else None
        browser = p.chromium.launch(headless=True, proxy=proxy_settings)
        page = browser.new_page()

        for motor in motors:
            print(f"\n{'=' * 60}")
            print(f"Обработка мотора: {motor['name']}")

            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO motors (name, KV, weight, source)
                    VALUES (?, ?, ?, 5)
                    RETURNING id
                ''', (motor['name'], motor['kv'], motor['weight']))

                result = cursor.fetchone()
                if result:
                    motor_id = result[0]
                else:
                    cursor.execute('SELECT id FROM motors WHERE name = ?', (motor['name'],))
                    res = cursor.fetchone()
                    motor_id = res[0] if res else None

                if not motor_id:
                    raise Exception("Не удалось получить ID мотора из БД")

                all_stats = get_test_stats_for_motor(page, motor['link'])

                if all_stats and motor_id:
                    data_to_insert = []

                    for stats in all_stats:
                        data_to_insert.append((
                            motor_id,
                            motor['name'],
                            stats['RPM'],
                            stats.get('Voltage', 0.0),
                            stats.get('Current', 0.0),
                            stats.get('Electrical_Power', 0.0),
                            stats.get('Mechanical_Power', 0.0),
                            stats.get('Torque', 0.0),
                            stats.get('Thrust', 0.0),
                            stats.get('is_restored', 1)
                        ))

                    cursor.executemany('''
                        INSERT INTO motors_stats (id, name, RPM, Voltage, Current, Electrical_Power, Mechanical_Power, Torque, Thrust, is_restored)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', data_to_insert)

                    print(f"  -> УСПЕХ: Записано {len(data_to_insert)} строк в БД.")
                else:
                    print(f"  -> НЕУДАЧА: Не удалось найти данные тестов")

            except Exception as e:
                print(f"  [!] КРИТИЧЕСКАЯ ОШИБКА БД для '{motor['name']}': {e}")
                conn.rollback()
                continue

            time.sleep(1.5)

        browser.close()

    conn.commit()
    conn.close()
    print("\nГотово! Данные успешно сохранены в базу.")


if __name__ == "__main__":
    main()