import sqlite3 as sq
from pathlib import Path




def get_files_by_substring(directory, substring):
    dir_path = Path(directory)
    file_list = []

    # iterdir() возвращает все объекты в директории
    for file_path in dir_path.iterdir():
        if file_path.is_file() and substring in file_path.name:
            file_list.append(file_path.name)
    return file_list



def insert_data_from_file(db_path, table_name, device_id, device_name, file_path):
    """
    Читает данные из текстового файла и вставляет их в таблицу SQLite.

    :param db_path: Путь к файлу базы данных
    :param table_name: Имя таблицы для вставки
    :param device_id: Известный ID устройства (INTEGER)
    :param device_name: Известное название устройства (TEXT)
    :param file_path: Путь к текстовому файлу с данными
    """
    conn = sq.connect(db_path)
    cursor = conn.cursor()

    try:
        # Открываем файл и читаем строки
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        data_to_insert = []

        # Пропускаем первую строку (заголовок "RPM CT CP")
        for line in lines[1:]:
            # Разделяем строку по пробелам/табам
            parts = line.split()
            if len(parts) == 3:
                try:
                    rpm = int(parts[0])
                    ct = float(parts[1])
                    cp = float(parts[2])

                    # Формируем кортеж для вставки (id, name, RPM, CT, CP)
                    data_to_insert.append((device_id, device_name, rpm, ct, cp))
                except ValueError:
                    print(f"Предупреждение: не удалось преобразовать строку '{line.strip()}'")
                    continue

        # Массовая вставка данных
        cursor.executemany(f'''
            INSERT INTO {table_name} (ID, name, RPM, CT, CP) 
            VALUES (?, ?, ?, ?, ?)
        ''', data_to_insert)

        conn.commit()
        print(f"Успешно добавлено {len(data_to_insert)} записей для устройства '{device_name}' (ID: {device_id}).")

    except FileNotFoundError:
        print(f"Ошибка: Файл '{file_path}' не найден.")
    except sq.Error as e:
        print(f"Ошибка базы данных: {e}")
    except Exception as e:
        print(f"Произошла ошибка: {e}")
    finally:
        conn.close()



# Устанавливаем соединение с базой данных
# with sq.connect("props_data_base.db") as con:
#     cur = con.cursor()
#
#     cur.execute("""CREATE TABLE props (
#     name TEXT,
#     D REAL,
#     H REAL)
#     """)

# print(get_files_by_substring('/home/su-15/Документы/3 курс/инжпрак/prop/UIUC-propDB/volume-1/data', 'static'))

# prop_list = get_files_by_substring('/home/su-15/Документы/3 курс/инжпрак/prop/UIUC-propDB/volume-1/data', 'static')
# with sq.connect("props_stats.db") as con:
#     cur = con.cursor()
#     for prop in prop_list:
#         parts = prop.split('_')
#         brand, d_x_h = parts[:2]
#         d, h = d_x_h.split('x')
#         name = brand + "_" + d_x_h
#         print(prop, name, d, h)
#         insert_data_from_file()
