from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time


class BrowserTools:
    def __init__(self, driver):
        self.driver = driver

    def _check_browser(self):
        """Проверяет, жив ли браузер."""
        try:
            self.driver.current_url
            return True
        except:
            return False

    def get_page_state(self) -> str:
        """Возвращает структурированное описание страницы."""
        if not self._check_browser():
            return '{"error": "Браузер закрыт"}'

        try:
            dom = self.driver.execute_script("""
                function analyzePage() {
                    const info = {
                        url: window.location.href,
                        title: document.title,
                        interactive: [],
                        visibleText: document.body.innerText.substring(0, 2000)
                    };

                    const elements = document.querySelectorAll(
                        'a, button, input, textarea, [role="button"], [role="link"]'
                    );

                    for (let i = 0; i < Math.min(elements.length, 30); i++) {
                        const el = elements[i];
                        const rect = el.getBoundingClientRect();
                        const text = el.innerText || el.value || el.placeholder || 
                                    el.getAttribute('aria-label') || el.title || '';

                        if (text.trim() || el.tagName === 'INPUT') {
                            info.interactive.push({
                                tag: el.tagName.toLowerCase(),
                                text: text.trim().substring(0, 80),
                                placeholder: el.placeholder || '',
                                visible: rect.top >= 0 && rect.left >= 0,
                                actionable: !el.disabled
                            });
                        }
                    }

                    return info;
                }
                return analyzePage();
            """)
            return str(dom)
        except Exception as e:
            return f'{{"error": "Анализ: {str(e)}"}}'

    def execute_action(self, action_type: str, target: str, value: str = "", context: dict = None) -> str:
        """Выполняет действие."""
        if not self._check_browser():
            return "Браузер закрыт"

        try:
            if action_type == "click":
                return self._click_element(target)
            elif action_type == "type":
                return self._type_text(target, value)
            elif action_type == "navigate":
                return self._navigate(target)
            elif action_type == "scroll":
                return self._scroll(target)
            elif action_type == "find":
                return self._find_element(target)
            else:
                return f"Неизвестное действие: {action_type}"
        except Exception as e:
            return f"Ошибка: {str(e)}"

    def _click_element(self, element_description: str) -> str:
        """Кликает на элемент."""
        if not element_description:
            return "Нет описания элемента"

        try:
            # Ищем по разным стратегиям
            strategies = [
                (By.XPATH, f"//*[text()='{element_description}']"),
                (By.XPATH, f"//*[contains(text(), '{element_description}')]"),
                (By.XPATH, f"//button[contains(., '{element_description}')]"),
                (By.XPATH, f"//a[contains(., '{element_description}')]"),
            ]

            for by, selector in strategies:
                try:
                    elements = self.driver.find_elements(by, selector)
                    for element in elements:
                        try:
                            if element.is_displayed() and element.is_enabled():
                                element.click()
                                time.sleep(0.5)
                                return f"Кликнул на: '{element_description}'"
                        except:
                            continue
                except:
                    continue

            return f"Элемент '{element_description}' не найден"
        except Exception as e:
            return f"Ошибка клика: {str(e)}"

    def _type_text(self, field_description: str, text: str) -> str:
        """Вводит текст в поле."""
        try:
            all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
            all_inputs += self.driver.find_elements(By.TAG_NAME, "textarea")

            for element in all_inputs:
                try:
                    if element.is_displayed() and element.is_enabled():
                        element.clear()
                        element.send_keys(text)
                        element.send_keys(Keys.RETURN)
                        time.sleep(2)
                        return f"Ввел '{text}' и нажал Enter"
                except:
                    continue

            return f"Не найдено поле для ввода"
        except Exception as e:
            return f"Ошибка ввода: {str(e)}"

    def _navigate(self, url: str) -> str:
        """Переходит по URL."""
        try:
            clean_url = url.strip()
            if not clean_url.startswith("http"):
                clean_url = "https://" + clean_url

            self.driver.get(clean_url)
            time.sleep(2)
            return f"Перешел на {self.driver.current_url}"
        except Exception as e:
            return f"Ошибка навигации: {str(e)}"

    def _scroll(self, direction: str) -> str:
        """Скроллит страницу."""
        try:
            if direction.lower() == "down":
                self.driver.execute_script("window.scrollBy(0, 400)")
            elif direction.lower() == "up":
                self.driver.execute_script("window.scrollBy(0, -400)")
            else:
                self.driver.execute_script("window.scrollBy(0, 400)")

            time.sleep(0.5)
            return f"Проскроллил {direction}"
        except:
            return "Ошибка скролла"

    def _find_element(self, element_description: str) -> str:
        """Находит элемент на странице."""
        try:
            strategies = [
                (By.XPATH, f"//*[contains(text(), '{element_description}')]"),
                (By.XPATH, f"//input[@placeholder='{element_description}']"),
            ]

            found = []
            for by, selector in strategies:
                try:
                    elements = self.driver.find_elements(by, selector)
                    for element in elements:
                        if element.is_displayed():
                            tag = element.tag_name
                            text = element.text or element.get_attribute("value") or ""
                            if text:
                                text = f" text='{text[:30]}'"
                            found.append(f"{tag}{text}")
                except:
                    continue

            if found:
                return f"Найдены элементы: {', '.join(found[:3])}"
            else:
                return f"Элементы '{element_description}' не найдены"

        except Exception as e:
            return f"Ошибка поиска: {str(e)}"