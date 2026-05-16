"""
utils.py – Вспомогательные функции (цвета, ввод, getpass, меню)
"""
import os
import sys
import platform
from getpass import getpass
from colorama import init, Fore, Style

init(autoreset=True)

class ConsoleUI:
    @staticmethod
    def clear_screen():
        if platform.system() == "Windows":
            os.system('cls')
        else:
            os.system('clear')

    @staticmethod
    def print_colored(text, color=Fore.WHITE, style=Style.NORMAL):
        print(f"{style}{color}{text}{Style.RESET_ALL}")

    @staticmethod
    def print_header(text):
        print("\n" + "="*50)
        ConsoleUI.print_colored(text.center(50), Fore.CYAN, Style.BRIGHT)
        print("="*50)

    @staticmethod
    def print_menu(options, title=None):
        if title:
            ConsoleUI.print_header(title)
        for i, option in enumerate(options, 1):
            ConsoleUI.print_colored(f"{i}. {option}", Fore.YELLOW)
        print()

    @staticmethod
    def get_input(prompt, color=Fore.GREEN):
        ConsoleUI.print_colored(prompt, color)
        return input("> ").strip()

    @staticmethod
    def get_password(prompt="Введите пароль: "):
        ConsoleUI.print_colored(prompt, Fore.GREEN)
        return getpass("")

    @staticmethod
    def get_multiline_input(prompt="Введите текст (пустая строка для завершения):"):
        ConsoleUI.print_colored(prompt, Fore.GREEN)
        lines = []
        while True:
            line = input()
            if line.strip() == "":
                break
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def print_success(message):
        ConsoleUI.print_colored(f"✓ {message}", Fore.GREEN)

    @staticmethod
    def print_error(message):
        ConsoleUI.print_colored(f"✗ {message}", Fore.RED)

    @staticmethod
    def print_info(message):
        ConsoleUI.print_colored(f"ℹ {message}", Fore.BLUE)

    @staticmethod
    def print_warning(message):
        ConsoleUI.print_colored(f"⚠ {message}", Fore.YELLOW)