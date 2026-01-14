import undetected_chromedriver as uc
from browser_agent.agent import AutonomousBrowserAgent
from browser_agent.tools import BrowserTools
from ollama import Client


def create_driver():
    print("Запускаю браузер...")
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options)
    print("Браузер готов")
    return driver


def main():
    print("АВТОНОМНЫЙ БРАУЗЕРНЫЙ АГЕНТ")
    print("=" * 40)

    driver = create_driver()
    ollama = Client(host='http://localhost:11434')
    tools = BrowserTools(driver)
    agent = AutonomousBrowserAgent(ollama, tools)

    while True:
        print("\n" + "=" * 40)
        task = input("Введите задачу (или 'выход'): ").strip()

        if task.lower() in ['выход', 'exit', 'quit']:
            break

        if not task:
            continue

        print(f"\nВыполняю: {task}")

        try:
            result = agent.execute_task(task)
            print("\n" + "=" * 40)
            print("РЕЗУЛЬТАТ:")
            print(result)
        except Exception as e:
            print(f"Ошибка: {e}")

    driver.quit()
    print("\nЗавершено")


if __name__ == "__main__":
    main()