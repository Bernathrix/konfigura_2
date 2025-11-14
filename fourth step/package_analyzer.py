#!/usr/bin/env python3
import argparse
import sys
import os
import json
import urllib.request
import urllib.error
from collections import deque, defaultdict
import subprocess


class PackageAnalyzer:
    def __init__(self):
        self.args = None
        self.dependencies = {}
        self.dependency_graph = defaultdict(list)
        self.visited = set()
        self.cycle_detected = False
        self.load_order = []

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
  python package_analyzer.py --test-repo test_data.json --package A --load-order
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

        parser.add_argument(
            '--load-order',
            action='store_true',
            help='Вывести порядок загрузки зависимостей'
        )

        return parser.parse_args()

    def validate_arguments(self, args):
        """Валидация аргументов командной строки"""
        errors = []

        if not args.package and not args.test_repo:
            errors.append("Необходимо указать либо --package, либо --test-repo")

        if args.package and args.test_repo:
            errors.append("Указаны оба параметра --package и --test-repo. Используйте только один")

        if args.max_depth < 1:
            errors.append("Максимальная глубина должна быть положительным числом")
        elif args.max_depth > 10:
            print("Предупреждение: большая глубина анализа может привести к длительному выполнению")

        if args.url and not args.url.startswith(('http://', 'https://')):
            errors.append("URL должен начинаться с http:// или https://")

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
            "Порядок загрузки": "Включен" if args.load_order else "Выключен",
            "Максимальная глубина": args.max_depth
        }

        for key, value in config.items():
            print(f"{key}: {value}")
        print("=" * 50)

    def fetch_package_info(self, package_name, registry_url):
        """Получение информации о пакете из npm registry"""
        try:
            package_url = f"{registry_url}/{package_name}"

            req = urllib.request.Request(
                package_url,
                headers={'User-Agent': 'PackageAnalyzer/1.0'}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    return json.loads(response.read().decode('utf-8'))
                else:
                    raise Exception(f"HTTP {response.status}: {response.reason}")

        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise Exception(f"Пакет '{package_name}' не найден в репозитории")
            else:
                raise Exception(f"Ошибка HTTP {e.code}: {e.reason}")
        except Exception as e:
            raise Exception(f"Ошибка получения информации о пакете: {e}")

    def extract_dependencies(self, package_data):
        """Извлечение зависимостей из данных пакета"""
        try:
            if 'dist-tags' in package_data and 'latest' in package_data['dist-tags']:
                latest_version = package_data['dist-tags']['latest']
            else:
                versions = list(package_data.get('versions', {}).keys())
                if not versions:
                    return {}
                latest_version = versions[-1]

            version_data = package_data['versions'].get(latest_version, {})
            return version_data.get('dependencies', {})

        except Exception as e:
            raise Exception(f"Ошибка извлечения зависимостей: {e}")

    def load_test_repository(self, file_path):
        """Загрузка тестового репозитория из файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise Exception(f"Ошибка загрузки тестового репозитория: {e}")

    def get_direct_dependencies(self, package_name):
        """Получение прямых зависимостей для пакета"""
        if self.args.test_repo:
            test_data = self.load_test_repository(self.args.test_repo)
            dependencies = test_data.get(package_name, [])
            return {dep: "*" for dep in dependencies} if dependencies else {}
        else:
            package_data = self.fetch_package_info(package_name, self.args.url)
            return self.extract_dependencies(package_data)

    def build_dependency_graph_bfs(self, start_package, current_depth=0, path=None):
        """Построение графа зависимостей с помощью BFS с рекурсией"""
        if path is None:
            path = []

        if current_depth >= self.args.max_depth:
            return

        if start_package in path:
            print(f"⚠️  Обнаружена циклическая зависимость: {' -> '.join(path + [start_package])}")
            self.cycle_detected = True
            return

        current_path = path + [start_package]

        try:
            dependencies = self.get_direct_dependencies(start_package)

            for dep_package, version in dependencies.items():
                self.dependency_graph[start_package].append((dep_package, version))
                self.build_dependency_graph_bfs(dep_package, current_depth + 1, current_path)

        except Exception as e:
            print(f"⚠️  Ошибка при обработке пакета {start_package}: {e}")

    def calculate_load_order(self, start_package):
        """
        Расчет порядка загрузки зависимостей с помощью топологической сортировки
        """
        print(f"\n📋 РАСЧЕТ ПОРЯДКА ЗАГРУЗКИ ДЛЯ ПАКЕТА '{start_package}'")

        # Строим граф входящих степеней
        in_degree = defaultdict(int)
        all_nodes = set()

        # Собираем все узлы и вычисляем входящие степени
        for node, deps in self.dependency_graph.items():
            all_nodes.add(node)
            for dep, _ in deps:
                all_nodes.add(dep)
                in_degree[dep] += 1

        # Добавляем узлы без входящих зависимостей
        for node in all_nodes:
            if node not in in_degree:
                in_degree[node] = 0

        # Алгоритм Кана (топологическая сортировка)
        queue = deque([node for node in all_nodes if in_degree[node] == 0])
        load_order = []

        while queue:
            current = queue.popleft()
            load_order.append(current)

            for neighbor, _ in self.dependency_graph.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Проверка на циклы (если остались узлы с ненулевой степенью)
        remaining_nodes = [node for node in all_nodes if in_degree[node] > 0]
        if remaining_nodes:
            print("⚠️  Обнаружены циклические зависимости, полный порядок загрузки невозможен")
            print(f"   Циклические узлы: {remaining_nodes}")

        self.load_order = load_order
        return load_order

    def print_load_order(self, start_package):
        """Вывод порядка загрузки зависимостей"""
        if not self.load_order:
            print("Порядок загрузки не рассчитан")
            return

        print(f"\n=== ПОРЯДОК ЗАГРУЗКИ ЗАВИСИМОСТЕЙ ===")

        # Фильтруем порядок, начиная с зависимостей (исключая стартовый пакет)
        dependencies_order = [pkg for pkg in self.load_order if pkg != start_package]

        print(f"Стартовый пакет: {start_package}")
        print(f"\nПорядок загрузки зависимостей:")

        for i, package in enumerate(dependencies_order, 1):
            print(f"{i:2d}. {package}")

        print(f"\nФинальная загрузка: {start_package}")
        print(f"Всего зависимостей для загрузки: {len(dependencies_order)}")

    def compare_with_npm(self, start_package):
        """
        Сравнение порядка загрузки с реальным менеджером пакетов npm
        """
        if self.args.test_repo:
            print("\n🔍 Сравнение с npm невозможно для тестового репозитория")
            return

        print(f"\n🔍 СРАВНЕНИЕ С REAL NPM ДЛЯ ПАКЕТА '{start_package}'")

        try:
            # Создаем временный package.json для тестирования
            test_package_json = {
                "name": "test-package",
                "version": "1.0.0",
                "dependencies": {
                    start_package: "latest"
                }
            }

            with open('temp_package.json', 'w') as f:
                json.dump(test_package_json, f)

            # Запускаем npm ls для получения дерева зависимостей
            result = subprocess.run(
                ['npm', 'ls', '--json', '--prefix', '.'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                npm_data = json.loads(result.stdout)
                self.analyze_npm_comparison(npm_data, start_package)
            else:
                print("⚠️  NPM не доступен или произошла ошибка")
                print(f"   Ошибка: {result.stderr}")

        except subprocess.TimeoutExpired:
            print("⚠️  Таймаут выполнения npm команды")
        except Exception as e:
            print(f"⚠️  Ошибка сравнения с npm: {e}")
        finally:
            # Удаляем временный файл
            if os.path.exists('temp_package.json'):
                os.remove('temp_package.json')

    def analyze_npm_comparison(self, npm_data, start_package):
        """Анализ различий между нашим расчетом и npm"""
        print("📊 АНАЛИЗ РАСХОЖДЕНИЙ:")

        # Извлекаем зависимости из npm вывода
        npm_dependencies = set()

        def extract_npm_deps(node, depth=0):
            if 'dependencies' in node:
                for dep_name, dep_info in node['dependencies'].items():
                    npm_dependencies.add(dep_name)
                    extract_npm_deps(dep_info, depth + 1)

        if 'dependencies' in npm_data:
            extract_npm_deps(npm_data['dependencies'].get(start_package, {}))

        # Наши рассчитанные зависимости
        our_dependencies = set(self.load_order) - {start_package}

        print(f"   - Зависимостей в npm: {len(npm_dependencies)}")
        print(f"   - Зависимостей в нашем анализе: {len(our_dependencies)}")

        # Анализ различий
        missing_in_our = npm_dependencies - our_dependencies
        extra_in_our = our_dependencies - npm_dependencies

        if missing_in_our:
            print(f"   ❌ Отсутствуют в нашем анализе: {sorted(missing_in_our)}")

        if extra_in_our:
            print(f"   ❌ Лишние в нашем анализе: {sorted(extra_in_our)}")

        if not missing_in_our and not extra_in_our:
            print("   ✅ Порядок загрузки полностью совпадает с npm!")
        else:
            print("\n   📝 Причины расхождений:")
            print("      - Разные версии пакетов")
            print("      - Peer dependencies не учитываются")
            print("      - Optional dependencies не учитываются")
            print("      - Разная глубина анализа")
            print("      - Алгоритмы разрешения зависимостей")

    def demonstrate_load_order_cases(self):
        """Демонстрация различных случаев порядка загрузки"""
        test_cases = [
            {
                "name": "Простой граф - линейные зависимости",
                "package": "A",
                "max_depth": 3
            },
            {
                "name": "Граф с множественными зависимостями",
                "package": "C",
                "max_depth": 3
            },
            {
                "name": "Граф с циклами (частичный порядок)",
                "package": "E",
                "max_depth": 3
            }
        ]

        print("\n" + "=" * 60)
        print("ДЕМОНСТРАЦИЯ ПОРЯДКА ЗАГРУЗКИ")
        print("=" * 60)

        original_max_depth = self.args.max_depth

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n🧪 ТЕСТ {i}: {test_case['name']}")
            print("-" * 40)

            self.args.max_depth = test_case['max_depth']
            self.dependency_graph.clear()
            self.cycle_detected = False
            self.load_order = []

            # Строим граф и рассчитываем порядок
            self.build_dependency_graph_bfs(test_case['package'])
            self.calculate_load_order(test_case['package'])
            self.print_load_order(test_case['package'])

        self.args.max_depth = original_max_depth

    def run(self):
        """Основной метод запуска приложения"""
        try:
            args = self.parse_arguments()

            errors = self.validate_arguments(args)
            if errors:
                print("Ошибки конфигурации:")
                for error in errors:
                    print(f"  - {error}")
                sys.exit(1)

            self.print_configuration(args)
            self.args = args

            start_package = args.package if args.package else "A"

            # Этапы 2-3: Получение зависимостей и построение графа
            dependencies = self.get_direct_dependencies(start_package)
            self.build_dependency_graph_bfs(start_package)

            # Этап 4: Порядок загрузки
            if args.load_order:
                print(f"\n{'=' * 60}")
                print("ЭТАП 4: ПОРЯДОК ЗАГРУЗКИ ЗАВИСИМОСТЕЙ")
                print(f"{'=' * 60}")

                load_order = self.calculate_load_order(start_package)
                self.print_load_order(start_package)

                # Сравнение с реальным npm (только для реальных пакетов)
                if not args.test_repo and args.package:
                    self.compare_with_npm(start_package)

                # Демонстрация для тестового репозитория
                if args.test_repo:
                    self.demonstrate_load_order_cases()

            print("\n✅ Этап 4 выполнен успешно! Порядок загрузки рассчитан.")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            sys.exit(1)


if __name__ == "__main__":
    analyzer = PackageAnalyzer()
    analyzer.run()