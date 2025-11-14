#!/usr/bin/env python3
import argparse
import sys
import os
import json
import urllib.request
import urllib.error


class PackageAnalyzer:
    def __init__(self):
        self.args = None
        self.dependencies = {}

    def parse_arguments(self):
        """Парсинг аргументов командной строки"""
        parser = argparse.ArgumentParser(
            description='Инструмент визуализации графа зависимостей npm пакетов',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog='''
Примеры использования:
  python package_analyzer.py --package react --url https://registry.npmjs.org
  python package_analyzer.py --test-repo test_data.json --max-depth 3
  python package_analyzer.py --package lodash --ascii-tree --max-depth 2
            '''
        )

        # Основные параметры
        parser.add_argument(
            '--package',
            type=str,
            help='Имя анализируемого пакета'
        )

        parser.add_argument(
            '--url',
            type=str,
            default='https://registry.npmjs.org',
            help='URL репозитория npm (по умолчанию: https://registry.npmjs.org)'
        )

        parser.add_argument(
            '--test-repo',
            type=str,
            help='Путь к файлу тестового репозитория'
        )

        parser.add_argument(
            '--ascii-tree',
            action='store_true',
            help='Режим вывода в формате ASCII-дерева'
        )

        parser.add_argument(
            '--max-depth',
            type=int,
            default=3,
            help='Максимальная глубина анализа зависимостей (по умолчанию: 3)'
        )

        return parser.parse_args()

    def validate_arguments(self, args):
        """Валидация аргументов командной строки"""
        errors = []

        # Проверка обязательных параметров
        if not args.package and not args.test_repo:
            errors.append("Необходимо указать либо --package, либо --test-repo")

        if args.package and args.test_repo:
            errors.append("Указаны оба параметра --package и --test-repo. Используйте только один")

        # Проверка глубины анализа
        if args.max_depth < 1:
            errors.append("Максимальная глубина должна быть положительным числом")
        elif args.max_depth > 10:
            print("Предупреждение: большая глубина анализа может привести к длительному выполнению")

        # Проверка URL
        if args.url and not args.url.startswith(('http://', 'https://')):
            errors.append("URL должен начинаться с http:// или https://")

        # Проверка файла тестового репозитория
        if args.test_repo and not os.path.exists(args.test_repo):
            errors.append(f"Файл тестового репозитория не найден: {args.test_repo}")

        return errors

    def print_configuration(self, args):
        """Вывод конфигурации в формате ключ-значение"""
        print("=== КОНФИГУРАЦИЯ АНАЛИЗАТОРА ЗАВИСИМОСТЕЙ ===")
        config = {
            "Анализируемый пакет": args.package or "Не указан",
            "URL репозитория": args.url,
            "Тестовый репозиторий": args.test_repo or "Не используется",
            "Режим ASCII-дерева": "Включен" if args.ascii_tree else "Выключен",
            "Максимальная глубина": args.max_depth
        }

        for key, value in config.items():
            print(f"{key}: {value}")
        print("=" * 50)

    def fetch_package_info(self, package_name, registry_url):
        """
        Получение информации о пакете из npm registry
        Без использования менеджеров пакетов и сторонних библиотек
        """
        try:
            # Формируем URL для получения информации о пакете
            package_url = f"{registry_url}/{package_name}"

            print(f"Запрос информации о пакете: {package_url}")

            # Создаем запрос с User-Agent для избежания блокировки
            req = urllib.request.Request(
                package_url,
                headers={'User-Agent': 'PackageAnalyzer/1.0'}
            )

            # Выполняем запрос
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return data
                else:
                    raise Exception(f"HTTP {response.status}: {response.reason}")

        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise Exception(f"Пакет '{package_name}' не найден в репозитории")
            else:
                raise Exception(f"Ошибка HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(f"Ошибка подключения: {e.reason}")
        except json.JSONDecodeError as e:
            raise Exception(f"Ошибка парсинга JSON: {e}")
        except Exception as e:
            raise Exception(f"Ошибка получения информации о пакете: {e}")

    def extract_dependencies(self, package_data):
        """
        Извлечение зависимостей из данных пакета
        Анализирует последнюю версию пакета
        """
        try:
            # Получаем информацию о последней версии
            if 'dist-tags' in package_data and 'latest' in package_data['dist-tags']:
                latest_version = package_data['dist-tags']['latest']
            else:
                # Если нет dist-tags, берем первую доступную версию
                versions = list(package_data.get('versions', {}).keys())
                if not versions:
                    return {}
                latest_version = versions[-1]

            # Получаем зависимости для последней версии
            version_data = package_data['versions'].get(latest_version, {})

            dependencies = {}

            # Извлекаем обычные зависимости
            if 'dependencies' in version_data:
                dependencies.update(version_data['dependencies'])

            # Извлекаем зависимости разработки (опционально)
            if 'devDependencies' in version_data:
                dependencies.update(version_data['devDependencies'])

            # Извлекаем peer dependencies
            if 'peerDependencies' in version_data:
                dependencies.update(version_data['peerDependencies'])

            print(f"Версия пакета: {latest_version}")
            print(f"Найдено зависимостей: {len(dependencies)}")

            return dependencies

        except KeyError as e:
            raise Exception(f"Отсутствует ожидаемое поле в данных пакета: {e}")
        except Exception as e:
            raise Exception(f"Ошибка извлечения зависимостей: {e}")

    def load_test_repository(self, file_path):
        """
        Загрузка тестового репозитория из файла
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                test_data = json.load(f)

            if not isinstance(test_data, dict):
                raise Exception("Тестовые данные должны быть словарем")

            return test_data

        except json.JSONDecodeError as e:
            raise Exception(f"Ошибка парсинга JSON файла: {e}")
        except Exception as e:
            raise Exception(f"Ошибка загрузки тестового репозитория: {e}")

    def get_direct_dependencies(self, package_name):
        """
        Получение прямых зависимостей для пакета
        """
        print(f"\n=== ПОЛУЧЕНИЕ ЗАВИСИМОСТЕЙ ДЛЯ ПАКЕТА: {package_name} ===")

        if self.args.test_repo:
            # Режим тестового репозитория
            test_data = self.load_test_repository(self.args.test_repo)
            dependencies = test_data.get(package_name, [])

            if not dependencies:
                print(f"Пакет '{package_name}' не найден в тестовом репозитории")
                return {}

            # Преобразуем список в словарь (имитация npm формата)
            dependencies_dict = {dep: "*" for dep in dependencies}
            return dependencies_dict
        else:
            # Режим реального репозитория
            package_data = self.fetch_package_info(package_name, self.args.url)
            dependencies = self.extract_dependencies(package_data)
            return dependencies

    def print_direct_dependencies(self, dependencies, package_name):
        """
        Вывод прямых зависимостей на экран
        """
        if not dependencies:
            print(f"Пакет '{package_name}' не имеет зависимостей")
            return

        print(f"\n=== ПРЯМЫЕ ЗАВИСИМОСТИ ПАКЕТА '{package_name}': ===")

        for i, (dep, version) in enumerate(dependencies.items(), 1):
            print(f"{i:2d}. {dep}: {version}")

        print(f"Всего прямых зависимостей: {len(dependencies)}")

    def run(self):
        """Основной метод запуска приложения"""
        try:
            # Парсинг аргументов
            args = self.parse_arguments()

            # Валидация
            errors = self.validate_arguments(args)
            if errors:
                print("Ошибки конфигурации:")
                for error in errors:
                    print(f"  - {error}")
                sys.exit(1)

            # Вывод конфигурации
            self.print_configuration(args)

            # Сохранение аргументов
            self.args = args

            # Получение зависимостей
            package_name = args.package if args.package else "A"  # Для тестового режима
            dependencies = self.get_direct_dependencies(package_name)

            # Вывод прямых зависимостей
            self.print_direct_dependencies(dependencies, package_name)

            # Сохранение для следующих этапов
            self.dependencies = dependencies

            print("\nЭтап 2 выполнен успешно! Прямые зависимости получены.")

        except Exception as e:
            print(f"Ошибка: {e}")
            sys.exit(1)


if __name__ == "__main__":
    analyzer = PackageAnalyzer()
    analyzer.run()