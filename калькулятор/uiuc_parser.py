import sqlite3 as sq
from pathlib import Path
from math import sqrt, pi
import re

# from props_stats_table_creator import add_data, setup_database

db_name = "props_data_base.db"

rho = 1.225


# проверка, что название файла корректное
def check_format(text):
    return bool(re.match(r"^(.+?)_(\d+)x(\d+)(.+)$", text))

def get_files_by_substring(directory, substring):
    dir_path = Path(directory)
    file_list = []

    # iterdir() возвращает все объекты в директории
    for file_path in dir_path.iterdir():
        if file_path.is_file() and substring in file_path.name:
            file_list.append(file_path.name)
    return file_list


con = sq.connect("props_data_base.db")
cur = con.cursor()


cur.execute('''DELETE FROM props_stats''')

for i in range(1, 5):
    file_path = f'/home/su-15/Документы/3 курс/инжпрак/prop/UIUC-propDB/volume-{i}/data'
    prop_list = (get_files_by_substring(file_path, 'static'))



    for prop in prop_list:
        if check_format(prop):
            parts = prop.split('_')
            brand, d_x_h = parts[:2]
            d, h = d_x_h.split('x')
            prop_name = brand + "_" + d_x_h

            try:
                print(f"DEBUG: Ищем строку: '{prop_name}' (длина: {len(prop_name)})")
                cur.execute(f"SELECT id, name FROM props WHERE name = ?", (prop_name,))
                result = cur.fetchone()
                prop_id, prop_name = result

                if not result:
                    print(f"Ошибка: Устройство с name={prop_name} не найдено в таблице.")



                # Открываем файл и читаем строки
                with open(file_path + '/' + prop, 'r', encoding='utf-8') as file:
                    lines = file.readlines()

                data_to_insert = []
                d = float(d)
                # узкое место: часть пропеллеров имеют метрические размеры
                # условно считаем, что 57-ми дюймовых пропеллеров не существует
                if d < 57:
                    d = d * 2.54 * 0.01
                else:
                    d = d * 0.001
                # Пропускаем первую строку (заголовок "RPM CT CP")
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) == 3:
                        try:
                            rpm = float(parts[0])
                            ct = float(parts[1])
                            cp = float(parts[2])



                            T = ct * rho * (rpm / 60)**2 * (d)**4 / 9.81

                            P = cp * rho * (rpm / 60)**3 * (d)**5

                            eta = sqrt(2/pi) * ct**(3/2) / cp

                            data_to_insert.append((prop_id, prop_name, rpm, ct, cp, T, P, eta))
                        except ValueError:
                            print(f"Предупреждение: не удалось преобразовать строку '{line.strip()}'")
                            continue
                # 3. Массовая вставка данных в целевую таблицу




                cur.executemany(f'''
                    INSERT INTO props_stats (id, name, RPM, CT, CP, T, P, eta) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', data_to_insert)



            except FileNotFoundError:
                print(f"Ошибка: Файл '{file_path}' не найден.")
            except sq.Error as e:
                print(f"Ошибка базы данных: {e}")
            except Exception as e:
                print(f"Произошла ошибка: {e}")
        else:
            pass
con.commit()
con.close()