import sqlite3


def setup_database(db_name):
    # Подключаемся к базе данных (файл создастся автоматически, если его нет)
    # db_name = 'props_data_base.db'
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # SQL-запрос для создания таблицы
    # Поля: название (текст), обороты (целое число), CT и CP (вещественные числа)
    create_table_query = '''
        CREATE TABLE IF NOT EXISTS props_stats (
            id INTEGER,
            name TEXT NOT NULL,
            RPM INTEGER,
            CT FLOAT,
            CP FLOAT
        )
    '''

    try:
        cursor.execute(create_table_query)
        conn.commit()
        print(f"База данных '{db_name}' и таблица 'props_stats' успешно созданы/проверены.")
    except sqlite3.Error as e:
        print(f"Ошибка при создании таблицы: {e}")
    finally:
        conn.close()


def add_data(db_name, table_name, data):
    """Добавляет тестовые записи в базу данных"""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    try:
        cursor.executemany(f'''
            INSERT INTO {table_name} (name, RPM, CT, CP) 
            VALUES (?, ?, ?, ?)
        ''', data)
        conn.commit()
        print("Тестовые данные успешно добавлены.")
    except sqlite3.Error as e:
        print(f"Ошибка при вставке данных: {e}")
    finally:
        conn.close()


def read_data(db_name, table):
    """Выводит все записи из базы данных"""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    try:
        cursor.execute(f'SELECT * FROM {table}')
        rows = cursor.fetchall()

        print("\n--- Содержимое базы данных ---")
        print(f"{'ID':<5} | {'name':<25} | {'RPM':<10} | {'CT':<5} | {'CP':<5}")
        print("-" * 60)
        for row in rows:
            print(f"{row[0]:<5} | {row[1]:<25} | {row[2]:<10} | {row[3]:<5} | {row[4]:<5}")
    except sqlite3.Error as e:
        print(f"Ошибка при чтении данных: {e}")
    finally:
        conn.close()


setup_database("props_data_base.db")
test_data = [("test_prop", 2504, 0.0754, 0.0375)]
add_data("props_data_base.db", "props_stats", test_data)
#read_data("props_data_base.db", "props_stats")