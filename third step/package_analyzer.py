#!/usr/bin/env python3
import argparse
import sys
import os
import json
import urllib.request
import urllib.error
from collections import deque, defaultdict


class PackageAnalyzer:
    def __init__(self):
        self.args = None
        self.dependencies = {}
        self.dependency_graph = defaultdict(list)
        self.visited = set()
        self.cycle_detected = False

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
        """
        try:
            package_url = f"{registry_url}/{package_name}"

            print(f"Запрос информации о пакете: {package_url}")

            req = urllib.request.Request(
                package_url,
                headers={'User-Agent': 'PackageAnalyzer/1.0'}
            )

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
        """
        try:
            if 'dist-tags' in package_data and 'latest' in package_data['dist-tags']:
                latest_version = package_data['dist-tags']['latest']
            else:
                versions = list(package_data.get('versions', {}).keys())
                if not versions:
                    return {}
                latest_version = versions[-1]

            version_data = package_data['versions'].get(latest_version, {})

            dependencies = {}

            if 'dependencies' in version_data:
                dependencies.update(version_data['dependencies'])

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

    def build_dependency_graph_bfs(self, start_package, current_depth=0, path=None):
        """
        Построение графа зависимостей с помощью BFS с рекурсией
        """
        if path is None:
            path = []

        # Проверка максимальной глубины
        if current_depth >= self.args.max_depth:
            return

        # Проверка циклических зависимостей
        if start_package in path:
            print(f"⚠️  Обнаружена циклическая зависимость: {' -> '.join(path + [start_package])}")
            self.cycle_detected = True
            return

        # Помечаем пакет как посещенный на текущем пути
        current_path = path + [start_package]

        # Получаем зависимости для текущего пакета
        try:
            dependencies = self.get_direct_dependencies(start_package)

            for dep_package, version in dependencies.items():
                # Добавляем зависимость в граф
                self.dependency_graph[start_package].append((dep_package, version))

                # Рекурсивно строим граф для зависимостей
                self.build_dependency_graph_bfs(dep_package, current_depth + 1, current_path)

        except Exception as e:
            print(f"⚠️  Ошибка при обработке пакета {start_package}: {e}")

    def print_dependency_graph(self, start_package):
        """
        Вывод графа зависимостей
        """
        if not self.dependency_graph:
            print("Граф зависимостей пуст")
            return

        print(f"\n=== ГРАФ ЗАВИСИМОСТЕЙ ДЛЯ ПАКЕТА '{start_package}' (глубина: {self.args.max_depth}) ===")

        total_dependencies = 0
        for package, deps in self.dependency_graph.items():
            print(f"\n📦 {package}:")
            for dep, version in deps:
                print(f"   └── {dep} ({version})")
                total_dependencies += 1

        print(f"\n📊 Статистика графа:")
        print(f"   - Узлов: {len(self.dependency_graph)}")
        print(f"   - Зависимостей: {total_dependencies}")
        print(f"   - Циклические зависимости: {'Да' if self.cycle_detected else 'Нет'}")

    def demonstrate_test_cases(self):
        """
        Демонстрация различных случаев работы с тестовым репозиторием
        """
        test_cases = [
            {
                "name": "Простой граф без циклов",
                "package": "A",
                "max_depth": 3
            },
            {
                "name": "Граф с ограниченной глубиной",
                "package": "A",
                "max_depth": 1
            },
            {
                "name": "Пакет без зависимостей",
                "package": "G",
                "max_depth": 3
            }
        ]

        print("\n" + "=" * 60)
        print("ДЕМОНСТРАЦИЯ РАБОТЫ С ТЕСТОВЫМ РЕПОЗИТОРИЕМ")
        print("=" * 60)

        original_max_depth = self.args.max_depth

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n🧪 ТЕСТ {i}: {test_case['name']}")
            print("-" * 40)

            # Временно меняем настройки для теста
            self.args.max_depth = test_case['max_depth']
            self.dependency_graph.clear()
            self.cycle_detected = False

            # Строим граф
            self.build_dependency_graph_bfs(test_case['package'])
            self.print_dependency_graph(test_case['package'])

        # Восстанавливаем оригинальную глубину
        self.args.max_depth = original_max_depth

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

            # Определяем стартовый пакет
            start_package = args.package if args.package else "A"

            # Этап 2: Получение прямых зависимостей
            dependencies = self.get_direct_dependencies(start_package)
            self.print_direct_dependencies(dependencies, start_package)

            # Этап 3: Построение полного графа зависимостей
            print(f"\n{'=' * 60}")
            print("ЭТАП 3: ПОСТРОЕНИЕ ГРАФА ЗАВИСИМОСТЕЙ")
            print(f"{'=' * 60}")

            self.build_dependency_graph_bfs(start_package)
            self.print_dependency_graph(start_package)

            # Демонстрация тестовых случаев для тестового репозитория
            if args.test_repo:
                self.demonstrate_test_cases()

            print("\n✅ Этап 3 выполнен успешно! Граф зависимостей построен.")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            sys.exit(1)


if __name__ == "__main__":
    analyzer = PackageAnalyzer()
    analyzer.run()