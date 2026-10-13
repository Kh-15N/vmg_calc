import sqlite3
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time


DB_PATH = "props_data_base.db"
rho = 1.225


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

    # Таблица с основными характеристиками пропеллера
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

    # Таблица с характеристиками из тестов
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
    """Получает список пропеллеров со страницы каталога."""
    url = "https://database.tytorobotics.com/propellers"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table')

    propellers = []
    if table and table.find('tbody'):
        rows = table.find('tbody').find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            # Ожидаемые колонки: Name | Tests | Weight (g) | Diameter (in) | Pitch (in) | Material
            if len(cols) >= 5:
                a_tag = cols[0].find('a')
                name = cols[0].get_text(strip=True)
                link = a_tag.get('href') if a_tag else None

                d_str = cols[3].get_text(strip=True)
                h_str = cols[4].get_text(strip=True)

                propellers.append({
                    'name': name,
                    'd': parse_float(d_str),
                    'h': parse_float(h_str),
                    'link': link
                })
    return propellers


def get_test_stats_for_propeller(prop_link):
    """Находит первый тест для пропеллера и возвращает макс. тягу, мощность и обороты."""
    if not prop_link:
        return None

    url = f"https://database.tytorobotics.com{prop_link}" if prop_link.startswith('/') else prop_link
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    try:
        # 1. Заходим на страницу пропеллера
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 2. Ищем ссылку на первый доступный тест
        test_link = None
        for a_tag in soup.find_all('a', href=True):
            if '/tests/' in a_tag['href']:
                test_link = a_tag['href']
                break

        if not test_link:
            return None

        test_url = f"https://database.tytorobotics.com{test_link}" if test_link.startswith('/') else test_link

        # 3. Парсим таблицы на странице теста с помощью pandas
        # lxml автоматически найдет все HTML-таблицы
        tables = pd.read_html(test_url)

        target_table = None
        for df in tables:
            # Ищем таблицу, содержащую нужные нам колонки
            if 'Rotation speed (rpm)' in df.columns and 'Thrust (kgf)' in df.columns:
                target_table = df
                break

        if target_table is not None:
            # Преобразуем целевые колонки в числовой формат (ошибки станут NaN)
            target_table['Thrust (kgf)'] = pd.to_numeric(target_table['Thrust (kgf)'], errors='coerce')
            target_table['Rotation speed (rpm)'] = pd.to_numeric(target_table['Rotation speed (rpm)'], errors='coerce')
            target_table['Mechanical power (W)'] = pd.to_numeric(target_table['Mechanical power (W)'], errors='coerce')

            # Отбрасываем строки, где нет числовых значений (например, заголовки или пустые ячейки)
            clean_df = target_table.dropna(subset=['Thrust (kgf)', 'Rotation speed (rpm)', 'Mechanical power (W)'])

            if not clean_df.empty:
                # Находим строку с максимальной тягой (Thrust) как репрезентативную точку
                max_thrust_idx = clean_df['Thrust (kgf)'].idxmax()
                row = clean_df.loc[max_thrust_idx]

                return {
                    'T': float(row['Thrust (kgf)']),
                    'RPM': float(row['Rotation speed (rpm)']),
                    'P': float(row['Mechanical power (W)'])
                }
    except Exception as e:
        print(f"  [!] Ошибка при парсинге {url}: {e}")

    return None


def main():
    print("Инициализация базы данных...")
    conn = init_db(DB_PATH)
    cursor = conn.cursor()

    print("Получение списка пропеллеров...")
    propellers = get_propellers_list()
    print(f"Найдено {len(propellers)} пропеллеров в каталоге.")

    # ВНИМАНИЕ: Для демонстрации ограничиваем обработку первыми 3 пропеллерами.
    # Уберите [:3], чтобы обработать всю базу (это займет значительное время).
    limit = 3
    print(f"Начало обработки (ограничено {limit} шт. для примера)...\n")

    for prop in propellers[:limit]:
        print(f"Обработка: {prop['name']}")

        # 1. Записываем базовые данные в props
        cursor.execute('''
            INSERT OR IGNORE INTO props (name, D, H, source)
            VALUES (?, ?, ?, 5)
            RETURNING id
        ''', (prop['name'], prop['d'], prop['h']))
        prop_id = cursor.fetchone()[0]

        # 2. Получаем статистику из тестов
        stats = get_test_stats_for_propeller(prop['link'])


        if stats:
            T = float(stats['T'])
            P = float(stats['P'])
            RPM = float(stats['RPM'])
            d = float(prop['d']) * 2.54 * 0.01
            n = RPM / 60
            CT = T / (rho * n**2 * d**4)
            CP = P / (rho * n**3 * d**5)
            eta = 1 / (n**0.5 * d**2) * T**1.5 / P
            cursor.execute('''
                INSERT INTO props_stats (id, name, RPM, CT, CP, T, P, eta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (prop_id, prop['name'], RPM, CT, CP, T, P, eta))
        else:
            print(f"  -> Не удалось найти данные тестов")

        # Вежливая задержка между запросами, чтобы не перегружать сервер и избежать блокировки
        time.sleep(1.5)

    conn.commit()
    conn.close()
    print("\nГотово! Данные успешно сохранены в базу.")


if __name__ == "__main__":
    main()