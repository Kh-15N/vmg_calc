import sqlite3 as sq
from pathlib import Path
import re




def get_files_by_substring(directory, substring):
    dir_path = Path(directory)
    file_list = []

    # iterdir() возвращает все объекты в директории
    for file_path in dir_path.iterdir():
        if file_path.is_file() and substring in file_path.name:
            file_list.append(file_path.name)
    return file_list

# проверка, что название файла корректное
def check_format(text):
    return bool(re.match(r"^(.+?)_(\d+)x(\d+)(.+)$", text))

# Устанавливаем соединение с базой данных
with sq.connect("props_data_base.db") as con:
    cur = con.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS props (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    D REAL,
    H REAL,
    source INTEGER)
    """)

# print(get_files_by_substring('/home/su-15/Документы/3 курс/инжпрак/prop/UIUC-propDB/volume-1/data', 'static'))
for i in range(1, 5):
    prop_list = get_files_by_substring(f'/home/su-15/Документы/3 курс/инжпрак/prop/UIUC-propDB/volume-{i}/data', 'static')
    with sq.connect("props_data_base.db") as con:
        cur = con.cursor()
        for prop in prop_list:
            if check_format(prop):
                parts = prop.split('_')
                brand, d_x_h = parts[:2]
                d, h = d_x_h.split('x')
                name = brand + "_" + d_x_h
                print(prop, name, d, h)
                cur.execute("""
                INSERT INTO props (name, D, H, source)
                VALUES (?, ?, ?, ?)""", (name, d, h, i))
            else:
                pass
