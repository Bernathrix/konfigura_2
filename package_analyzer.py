import argparse
import sys
import os


class PackageAnalyzer:
    def __init__(self):
        self.args = None

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

            # Сохранение аргументов для использования в следующих этапах
            self.args = args

            print("Этап 1 выполнен успешно! Конфигурация применена.")

        except argparse.ArgumentError as e:
            print(f"Ошибка парсинга аргументов: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
            sys.exit(1)


if __name__ == "__main__":
    analyzer = PackageAnalyzer()
    analyzer.run()