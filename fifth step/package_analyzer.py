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
        self.all_packages = set()

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
  python package_analyzer.py --package express --ascii-tree --graphviz
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

        parser.add_argument(
            '--graphviz',
            action='store_true',
            help='Сгенерировать описание графа на языке Graphviz'
        )

        parser.add_argument(
            '--output',
            type=str,
            help='Файл для сохранения Graphviz описания'
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
            "Graphviz вывод": "Включен" if args.graphviz else "Выключен",
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
        self.all_packages.add(start_package)

        try:
            dependencies = self.get_direct_dependencies(start_package)

            for dep_package, version in dependencies.items():
                self.dependency_graph[start_package].append((dep_package, version))
                self.all_packages.add(dep_package)
                self.build_dependency_graph_bfs(dep_package, current_depth + 1, current_path)

        except Exception as e:
            print(f"⚠️  Ошибка при обработке пакета {start_package}: {e}")

    def calculate_load_order(self, start_package):
        """Расчет порядка загрузки зависимостей"""
        in_degree = defaultdict(int)
        all_nodes = self.all_packages

        for node, deps in self.dependency_graph.items():
            for dep, _ in deps:
                in_degree[dep] += 1

        for node in all_nodes:
            if node not in in_degree:
                in_degree[node] = 0

        queue = deque([node for node in all_nodes if in_degree[node] == 0])
        load_order = []

        while queue:
            current = queue.popleft()
            load_order.append(current)

            for neighbor, _ in self.dependency_graph.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        self.load_order = load_order
        return load_order

    def generate_graphviz_dot(self, start_package):
        """
        Генерация описания графа на языке Graphviz DOT
        """
        dot_lines = [
            "digraph DependencyGraph {",
            "    rankdir=TB;",
            "    node [shape=box, style=filled, fillcolor=lightblue];",
            "    edge [color=darkgreen];",
            "",
            f'    // Граф зависимостей для пакета "{start_package}"',
            f'    // Глубина анализа: {self.args.max_depth}',
            f'    // Всего пакетов: {len(self.all_packages)}',
            ""
        ]

        # Добавляем узлы с особым оформлением для стартового пакета
        dot_lines.append(f'    "{start_package}" [fillcolor=orange, style="filled,bold"];')

        # Добавляем остальные узлы
        for package in self.all_packages:
            if package != start_package:
                dot_lines.append(f'    "{package}";')

        dot_lines.append("")

        # Добавляем ребра (зависимости)
        dot_lines.append("    // Зависимости между пакетами")
        for source, dependencies in self.dependency_graph.items():
            for target, version in dependencies:
                dot_lines.append(f'    "{source}" -> "{target}" [label="{version}"];')

        # Выделяем циклические зависимости красным цветом
        if self.cycle_detected:
            dot_lines.append("")
            dot_lines.append("    // Циклические зависимости")
            dot_lines.append('    edge [color=red, style=bold];')
            # Здесь можно добавить конкретные циклические зависимости

        dot_lines.append("}")

        dot_content = "\n".join(dot_lines)
        return dot_content

    def print_ascii_tree(self, start_package, current_node=None, prefix="", is_last=True):
        """
        Рекурсивное построение ASCII-дерева зависимостей
        """
        if current_node is None:
            current_node = start_package
            print(f"\n🌳 ASCII-ДЕРЕВО ЗАВИСИМОСТЕЙ ДЛЯ: {start_package}")
            print("=" * 50)

        # Выводим текущий узел
        connector = "└── " if is_last else "├── "
        print(f"{prefix}{connector}{current_node}")

        # Получаем зависимости текущего узла
        dependencies = self.dependency_graph.get(current_node, [])

        if not dependencies:
            return

        # Обновляем префикс для дочерних узлов
        new_prefix = prefix + ("    " if is_last else "│   ")

        # Рекурсивно выводим дочерние узлы
        for i, (dep, version) in enumerate(dependencies):
            is_last_child = i == len(dependencies) - 1
            version_info = f" ({version})" if version != "*" else ""
            self.print_ascii_tree(start_package, dep, new_prefix, is_last_child)

    def compare_with_npm_tree(self, start_package):
        """
        Сравнение нашего дерева с выводом npm ls
        """
        if self.args.test_repo:
            print("\n🔍 Сравнение с npm невозможно для тестового репозитория")
            return

        print(f"\n🔍 СРАВНЕНИЕ ВИЗУАЛИЗАЦИИ С NPM ДЛЯ ПАКЕТА '{start_package}'")

        try:
            # Создаем временный package.json
            test_package_json = {
                "name": "test-package",
                "version": "1.0.0",
                "dependencies": {
                    start_package: "latest"
                }
            }

            with open('temp_package.json', 'w') as f:
                json.dump(test_package_json, f)

            # Получаем дерево npm
            result = subprocess.run(
                ['npm', 'ls', '--prefix', '.'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode in [0, 1]:  # npm ls возвращает 1 при unmet dependencies
                print("\n📊 ВЫВОД NPM:")
                print(result.stdout)

                print("\n📊 НАША ВИЗУАЛИЗАЦИЯ:")
                self.print_ascii_tree(start_package)

                self.analyze_visualization_differences(result.stdout, start_package)
            else:
                print("⚠️  Ошибка выполнения npm ls")

        except Exception as e:
            print(f"⚠️  Ошибка сравнения: {e}")
        finally:
            if os.path.exists('temp_package.json'):
                os.remove('temp_package.json')

    def analyze_visualization_differences(self, npm_output, start_package):
        """
        Анализ различий в визуализации между нашим инструментом и npm
        """
        print("\n📝 АНАЛИЗ РАСХОЖДЕНИЙ В ВИЗУАЛИЗАЦИИ:")

        # Простой анализ на основе количества строк в выводе
        our_nodes = len(self.all_packages)
        npm_lines = len([line for line in npm_output.split('\n') if line.strip()])

        print(f"   - Узлов в нашем графе: {our_nodes}")
        print(f"   - Строк в выводе npm: {npm_lines}")

        if our_nodes < npm_lines - 5:  # Учитываем служебные строки npm
            print("   ❌ Наш анализ показывает меньше зависимостей чем npm")
            print("   📋 Возможные причины:")
            print("      - npm показывает devDependencies")
            print("      - npm включает peerDependencies")
            print("      - Разная глубина анализа")
            print("      - Разные версии пакетов")
        elif our_nodes > npm_lines + 5:
            print("   ❌ Наш анализ показывает больше зависимостей чем npm")
            print("   📋 Возможные причины:")
            print("      - npm объединяет дублирующиеся зависимости")
            print("      - Разные алгоритмы разрешения конфликтов")
        else:
            print("   ✅ Визуализация примерно соответствует npm")

    def demonstrate_visualization_cases(self):
        """
        Демонстрация визуализации для различных пакетов
        """
        demonstration_packages = ["A", "C", "E"]  # Из тестового репозитория

        print("\n" + "=" * 60)
        print("ДЕМОНСТРАЦИЯ ВИЗУАЛИЗАЦИИ ДЛЯ РАЗЛИЧНЫХ ПАКЕТОВ")
        print("=" * 60)

        original_max_depth = self.args.max_depth

        for i, package in enumerate(demonstration_packages, 1):
            print(f"\n📦 ПРИМЕР {i}: Визуализация для пакета '{package}'")
            print("-" * 50)

            # Сбрасываем состояние для нового пакета
            self.dependency_graph.clear()
            self.cycle_detected = False
            self.load_order = []
            self.all_packages.clear()

            # Строим граф
            self.build_dependency_graph_bfs(package)

            # ASCII-дерево
            if self.args.ascii_tree:
                self.print_ascii_tree(package)

            # Graphviz
            if self.args.graphviz:
                dot_content = self.generate_graphviz_dot(package)
                print(f"\n📊 Graphviz DOT для пакета '{package}':")
                print("=" * 40)
                print(dot_content)
                print("=" * 40)

                # Сохраняем в файл если указан output
                if self.args.output:
                    filename = f"{self.args.output}_{package}.dot"
                    with open(filename, 'w') as f:
                        f.write(dot_content)
                    print(f"💾 Graphviz описание сохранено в: {filename}")

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

            # Построение графа зависимостей
            self.build_dependency_graph_bfs(start_package)

            # Этап 4: Порядок загрузки (если нужен)
            if args.load_order:
                self.calculate_load_order(start_package)
                self.print_load_order(start_package)

            # Этап 5: Визуализация
            print(f"\n{'=' * 60}")
            print("ЭТАП 5: ВИЗУАЛИЗАЦИЯ ГРАФА ЗАВИСИМОСТЕЙ")
            print(f"{'=' * 60}")

            # ASCII-дерево
            if args.ascii_tree:
                self.print_ascii_tree(start_package)

            # Graphviz вывод
            if args.graphviz:
                dot_content = self.generate_graphviz_dot(start_package)
                print(f"\n📊 Graphviz DOT описание:")
                print("=" * 50)
                print(dot_content)
                print("=" * 50)

                # Сохранение в файл
                if args.output:
                    with open(args.output, 'w') as f:
                        f.write(dot_content)
                    print(f"💾 Graphviz описание сохранено в: {args.output}")

                print(f"\n💡 Для визуализации выполните:")
                print(f"   dot -Tpng {args.output or 'output.dot'} -o graph.png")
                print(f"   Или используйте онлайн инструмент: http://www.webgraphviz.com/")

            # Сравнение с npm
            if not args.test_repo and args.package:
                self.compare_with_npm_tree(start_package)

            # Демонстрация для тестового репозитория
            if args.test_repo:
                self.demonstrate_visualization_cases()

            print("\n✅ Все этапы выполнены успешно! Инструмент готов.")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            sys.exit(1)


if __name__ == "__main__":
    analyzer = PackageAnalyzer()
    analyzer.run()