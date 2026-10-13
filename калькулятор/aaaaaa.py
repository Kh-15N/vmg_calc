print("aaaaaaaaaaaaaaaaaaaaaaaa")
import requests

# Список самых популярных локальных портов для VLESS / V2Ray / Clash / Shadowsocks
COMMON_PORTS = [10809, 10808, 7890, 1080, 10800, 1081, 1087, 8080]
TARGET_URL = "https://database.tytorobotics.com/propellers"


def test_proxy(proxy_url):
    """Пытается сделать запрос через указанный прокси."""
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        # timeout=5, чтобы не ждать вечно, если порт не тот
        response = requests.get(TARGET_URL, proxies=proxies, timeout=5,
                                headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            return True, response.text[:50]  # Возвращаем успех и кусок HTML для проверки
        else:
            return False, f"Статус: {response.status_code}"
    except requests.exceptions.ProxyError:
        return False, "Прокси отверг соединение"
    except requests.exceptions.ConnectTimeout:
        return False, "Таймаут подключения"
    except Exception as e:
        return False, str(e)[:50]


print("=== Тестирование подключения к сайту ===\n")

# 1. Тест БЕЗ прокси (прямое подключение)
print("[1] Пробуем подключиться НАПРЯМУЮ (без прокси)...")
try:
    r = requests.get(TARGET_URL, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
    print(f"    ✅ Успех! Сайт доступен напрямую. Прокси не нужен.")
    print(f"    Получено байт: {len(r.text)}")
except Exception as e:
    print(f"    ❌ Напрямую не работает: {type(e).__name__}")

print("\n[2] Перебираем локальные порты прокси (127.0.0.1)...")
working_proxy = None

for port in COMMON_PORTS:
    proxy_url = f"http://127.0.0.1:{port}"
    print(f"    -> Проверяем порт {port}...", end=" ")

    is_ok, msg = test_proxy(proxy_url)

    if is_ok:
        print(f"✅ РАБОТАЕТ! (Получено {len(msg)} символов HTML)")
        working_proxy = proxy_url
        break  # Нашли рабочий, дальше не ищем
    else:
        print(f"❌ ({msg})")

print("\n=== Результат ===")
if working_proxy:
    print(f"🎉 Найден рабочий прокси: {working_proxy}")
    print(f"Вставьте эту строку в основной скрипт в переменную MANUAL_PROXY:")
    print(f'MANUAL_PROXY = "{working_proxy}"')
else:
    print("😔 Ни один из стандартных портов не сработал.")
    print("\nКак узнать ваш точный порт:")
    print("1. Откройте ваш VLESS-клиент (v2rayN, Hiddify, Clash, NekoRay и т.д.).")
    print("2. Найдите настройки 'System Proxy', 'HTTP Port' или 'SOCKS5 Port'.")
    print("3. Обычно это порты: 10809 (HTTP), 10808 (SOCKS5) для v2rayN,")
    print("   или 7890 для Clash.")
    print("4. Если клиент использует SOCKS5, а не HTTP, напишите мне, и я добавлю поддержку SOCKS5.")

if __name__ == "__main__":
    main()