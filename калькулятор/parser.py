from pathlib import Path


def get_files_by_substring(directory, substring):
    dir_path = Path(directory)

    # iterdir() возвращает все объекты в директории
    for file_path in dir_path.iterdir():
        if file_path.is_file() and substring in file_path.name:
            print(f"Найден файл: {file_path.name}")


# Запуск (ищем файлы, в названии которых есть слово "отчет")
get_files_by_substring('./my_folder', 'отчет')