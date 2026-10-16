import sqlite3


def find_matching_engines(prop_db_path, motor_db_path, min_thrust, max_thrust, rpm_tolerance, power_tolerance):
    """
    Ищет винт по тяге, берет первый найденный и подбирает к нему двигатели
    по допускам оборотов и мощности.
    """
    conn = sqlite3.connect(prop_db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, name, RPM, P 
            FROM props_stats
            WHERE T > ? and T < ? 
            ORDER BY eta DESC
            LIMIT 1
        """, (min_thrust, max_thrust,))

        prop = cursor.fetchone()

        if not prop:
            print(f"Винт не найден.")
            return []

        prop_id, prop_name, prop_rpm, prop_power = prop
        print(f"   Винт: '{prop_name}' (ID: {prop_id})")
        print(f"   Обороты: {prop_rpm}, Мощность: {prop_power}\n")

    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
    finally:
        conn.close()

    conn = sqlite3.connect(motor_db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT ms.id, ms.name, ms.RPM, ms.Mechanical_Power, Electrical_Power, m.weight
            FROM motors_stats ms
            LEFT JOIN motors m ON ms.id = m.id
            WHERE ABS(ms.RPM - ?) <= ? 
              AND ABS(ms.Mechanical_Power - ?) <= ?
            ORDER BY ms.Electrical_power
            limit 20
        """, (prop_rpm, rpm_tolerance, prop_power, power_tolerance))

        engines = cursor.fetchall()

        if not engines:
            print("Подходящие двигатели не найдены.")
            return []


        print(f"Найдено подходящих двигателей: {len(engines)}")
        print("-" * 50)
        print(f"{'ID':<5} | {'Название':<40} | {'Обороты':<10} | {'Мощность':<20} | {'Масса':<5} | ... ")
        print("-" * 50)

        for eng in engines:
            eng_id, eng_name, eng_rpm, eng_power, electrical_power, weight = eng
            # rpm_diff = abs(eng_rpm - prop_rpm)
            # power_diff = abs(eng_power - prop_power)
            if weight is None:
                weight = 0
            print(f"{eng_id:<5} | {eng_name:<40} | {eng_rpm:<10} | {eng_power:<20} | {weight:<5}")

        return engines

    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
    finally:
        conn.close()


find_matching_engines(
    prop_db_path = "/home/su-15/Документы/3 курс/инжпрак/калькулятор/props_data_base.db",
    motor_db_path = "/home/su-15/Документы/3 курс/инжпрак/калькулятор/motors_data_base.db",
    min_thrust = 1.0,
    max_thrust = 1.5,
    rpm_tolerance=200,
    power_tolerance=20.0
)