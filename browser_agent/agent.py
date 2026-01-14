import json
import re
import ast
import time
from typing import Optional, Callable


class AutonomousBrowserAgent:
    def __init__(self, ollama_client, browser_tools, user_input_callback: Optional[Callable[[str], str]] = None):
        self.ollama = ollama_client
        self.tools = browser_tools
        self.context = {
            'goal': '',
            'history': [],
            'current_page': '',
            'additional_info': {},
            'pending_question': None,
        }
        self.user_input_callback = user_input_callback or self._default_input_callback

    def _default_input_callback(self, question: str) -> str:
        """Стандартная функция для запроса ввода у пользователя."""
        print(f"\nАгент спрашивает: {question}")
        return input("Ваш ответ: ").strip()

    def execute_task(self, user_goal: str) -> str:
        """Автономное выполнение задачи."""
        self.context['goal'] = user_goal
        self.context['history'] = []
        self.context['additional_info'] = {}
        self.context['pending_question'] = None
        max_steps = 30

        print(f"\nЦель: {user_goal}")
        print("Начинаю выполнение...")

        for step in range(max_steps):
            print(f"\nШаг {step + 1}/{max_steps}")

            # Обработка ожидаемого ответа от пользователя
            if self.context['pending_question']:
                answer = self._handle_pending_question()
                if answer == "BACK_COMMAND":
                    print("   ↩️ Возвращаюсь назад...")
                    if self.context['history']:
                        self.context['history'].pop()
                    self.context['pending_question'] = None
                    continue
                elif answer:
                    print(f"   Получен ответ: {answer}")
                    # Сохраняем ответ
                    info_key = self.context['pending_question'].get('info_key', 'user_input')
                    self.context['additional_info'][info_key] = answer
                    self.context['history'].append({
                        'step': step,
                        'action': {'action': 'user_input', 'value': answer},
                        'result': f"Получен ответ: {answer}",
                    })

                self.context['pending_question'] = None

            # Получаем состояние страницы
            page_state = self.tools.get_page_state()
            self.context['current_page'] = page_state

            # Анализируем и решаем что делать
            page_info = self._parse_page_state(page_state)
            action = self._decide_next_action(page_info, step)

            # Если нужно спросить пользователя
            if action.get('needs_info'):
                self.context['pending_question'] = {
                    'question': action.get('question', ''),
                    'info_key': action.get('info_key',
                                           'additional_info')
                }
                print(f"\nТребуется уточнение: {action.get('question', '')}")
                continue

            print(f"   Действие: {action.get('action', '?')}({action.get('target', '?')})")
            if action.get('reasoning'):
                print(f"   Рассуждение: {action['reasoning'][:100]}...")
            if action.get('value'):
                print(f"   Значение: '{action['value'][:50]}...'")

            # Выполняем действие
            result = self.execute_action(action, page_info)
            print(f"   Результат: {result[:100]}...")

            # Сохраняем в историю
            self.context['history'].append({
                'step': step + 1,
                'action': action,
                'result': result,
            })

            # Проверяем завершение
            if self._should_stop(action, result, step, max_steps, page_info):
                print(f"\nЗавершаю выполнение на шаге {step + 1}")
                break

            time.sleep(1)

        return self._summarize_results()

    def _handle_pending_question(self) -> Optional[str]:
        """Обрабатывает ожидаемый вопрос к пользователю."""
        if not self.context['pending_question']:
            return None

        question_data = self.context['pending_question']
        question = question_data.get('question', '')

        if not question:
            return None

        try:
            print(f"\n{'=' * 60}")
            print(f"АГЕНТ СПРАШИВАЕТ:")
            print(f"   {question}")
            print(f"{'=' * 60}")

            answer = input("\nВаш ответ: ").strip()

            if answer.lower() in ['отмена', 'cancel', 'стоп']:
                raise KeyboardInterrupt("Пользователь отменил задачу")
            elif answer.lower() in ['назад', 'back', 'вернись']:
                return "BACK_COMMAND"

            return answer if answer else None
        except Exception as e:
            print(f"   Ошибка: {e}")
            return None

    def _parse_page_state(self, page_state_str: str) -> dict:
        """Парсит строку состояния в словарь."""
        if not page_state_str:
            return {"interactive": [], "visibleText": "", "url": "", "title": ""}

        try:
            if isinstance(page_state_str, str) and page_state_str.strip():
                return json.loads(page_state_str)
        except:
            try:
                return ast.literal_eval(page_state_str)
            except:
                pass

        return {"url": "", "title": "", "interactive": [], "visibleText": ""}

    def _decide_next_action(self, page_info: dict, step: int) -> dict:
        """ИИ решает, что делать дальше - полностью автономно."""
        try:
            url = page_info.get('url', 'неизвестен')
            title = page_info.get('title', '')

            # Форматируем элементы просто как текст
            elements_raw = page_info.get('interactive', [])
            elements_text = ""
            if elements_raw and isinstance(elements_raw, list):
                visible_elements = []
                for el in elements_raw[:10]:  # Берем только первые 10
                    if isinstance(el, dict) and el.get('visible') and el.get('actionable'):
                        text = el.get('text', '') or el.get('placeholder', '')
                        if text:
                            visible_elements.append(text[:30])

                if visible_elements:
                    elements_text = "Элементы: " + ", ".join(visible_elements)

            visible_text = page_info.get('visibleText', '')[:500]

            # Собираем контекст
            all_info = f"Цель пользователя: {self.context['goal']}\n"
            if self.context['additional_info']:
                all_info += "Известная информация:\n"
                for key, value in self.context['additional_info'].items():
                    all_info += f"- {key}: {value}\n"

            prompt = f"""
            Ты — автономный веб-агент. У тебя есть задача от пользователя.

            {all_info}

            Текущая страница:
            - URL: {url}
            - Заголовок: {title}
            - Текст на странице: {visible_text[:300]}...
            {elements_text}

            История последних действий:
            {self.context['history'][-3:] if self.context['history'] else 'Еще нет действий'}

            Проанализируй ситуацию и реши, что делать дальше. 
            Будь логичным и целеустремленным. Если не хватает информации для выполнения задачи - спроси у пользователя.
            Если можешь действовать - действуй.

            Возможные действия:
            - navigate("url") - перейти на другой сайт
            - type("описание поля", "текст") - ввести текст
            - click("текст элемента") - кликнуть на элемент
            - scroll("up/down") - прокрутить
            - find("что искать") - найти элемент
            - ask("вопрос") - спросить у пользователя

            Верни ответ в формате JSON:
            {{
                "reasoning": "Твои рассуждения о ситуации",
                "action": "navigate|type|click|scroll|find|ask",
                "target": "цель действия",
                "value": "текст для ввода (если нужно)",
                "needs_info": true/false,
                "question": "вопрос (если needs_info=true)",
                "info_key": "ключ для информации"
            }}
            """

            response = self.ollama.chat(
                model='deepseek-v3.1:671b-cloud',
                messages=[{'role': 'user', 'content': prompt}],
                options={'num_ctx': 8192, 'temperature': 0.2}
            )

            response_text = response['message']['content']
            print(f"   ИИ анализирует: {response_text[:150]}...")

            return self._parse_ai_response_simple(response_text)

        except Exception as e:
            print(f"   Ошибка анализа: {e}")
            # Простой fallback
            return {
                "reasoning": "Ошибка анализа",
                "action": "scroll",
                "target": "down",
                "value": "",
                "needs_info": False
            }

    def _parse_ai_response_simple(self, response_text: str) -> dict:
        """Простой парсинг ответа ИИ."""
        import json
        import re

        # Ищем JSON
        json_match = re.search(r'\{[\s\S]*\}', response_text, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                # Минимальная валидация
                if 'action' not in result:
                    result['action'] = 'scroll'
                if 'target' not in result:
                    result['target'] = ''
                if 'reasoning' not in result:
                    result['reasoning'] = 'Принято решение'
                if 'value' not in result:
                    result['value'] = ''
                if 'needs_info' not in result:
                    result['needs_info'] = False

                return result
            except:
                pass

        # Самый простой fallback
        return {
            "reasoning": "Анализирую страницу",
            "action": "scroll",
            "target": "down",
            "value": "",
            "needs_info": False
        }

    def execute_action(self, action: dict, page_info: dict = None) -> str:
        """Выполняет действие."""
        if not action:
            return "Нет действия"

        action_type = action.get('action', '')
        target = action.get('target', '')
        value = action.get('value', '')

        # Для ask просто возвращаем сообщение
        if action_type == "ask":
            return f"Запрошена информация: {action.get('question', '')}"

        # Исполняем через инструменты
        return self.tools.execute_action(action_type, target, value, self.context)

    def _should_stop(self, action: dict, result: str, step: int, max_steps: int, page_info: dict = None) -> bool:
        """Определяет, нужно ли остановиться."""
        if step >= max_steps - 1:
            return True

        # Если получили важную информацию от пользователя
        if action.get('action') == 'user_input':
            return False

        # Если видим успех
        result_lower = result.lower()
        if any(word in result_lower for word in ['успешн', 'перешел', 'нашел', 'ввел', 'кликнул']):
            # Даем еще пару шагов для завершения
            return step > max_steps - 5

        # Зацикливание
        if len(self.context['history']) >= 5:
            recent_actions = [h['action'].get('action', '') for h in self.context['history'][-5:]]
            if len(set(recent_actions)) == 1:
                print("   Возможное зацикливание")
                return True

        return False

    def _summarize_results(self) -> str:
        """Генерирует итоговый отчет."""
        total_steps = len(self.context['history'])
        current_url = "неизвестно"

        try:
            current_url = self.tools.driver.current_url
        except:
            pass

        report = f"""
ОТЧЕТ
Цель: {self.context['goal']}
Шагов: {total_steps}
URL: {current_url}

История:"""

        for i, entry in enumerate(self.context['history'], 1):
            action = entry['action']
            result = entry['result']

            if isinstance(action, dict):
                action_str = f"{action.get('action', '?')}({action.get('target', '?')})"
                if action.get('value'):
                    action_str += f" = '{action.get('value')}'"
            else:
                action_str = str(action)

            report += f"\n{i:2d}. {action_str}"
            report += f"\n    → {result[:60]}..."

        return report