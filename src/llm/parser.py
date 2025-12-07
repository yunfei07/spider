import json
from openai import OpenAI
from src.models.dsl import TestScenario
from src.config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL, check_api_key

class LLMParser:
    def __init__(self):
        check_api_key()
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )

    def parse(self, natural_language_input: str) -> TestScenario:
        system_prompt = """
You are an expert AQE (Automated Quality Engineer). Your goal is to convert natural language test intent into a structured JSON Test Scenario.

Output Schema (JSON):
{
  "name": "Short test name",
  "description": "Description of what the test does",
  "steps": [
    {
      "action": "goto" | "fill" | "click" | "hover" | "press" | "upload_file" | "handle_dialog" | "wait" | "assert_visible" | "assert_title" | "exec_code",
      "target": "Description of element",
      "value": "Value for action",
      "page_context": "Inferred page name (e.g. 'login', 'home', 'cart'). Optional. Helps resolve element conflicts."
    }
  ]
}

Rules:
1. ONLY return valid JSON. Do not include markdown formatting like ```json.
2. For 'target', describe the element in natural language.
3. If the user input is in Chinese, please use Chinese for the 'target'.
4. 'page_context': Infer the logical page name if possible (e.g. if user says 'Login', context is 'login').
5. Supported actions:
   - 'goto': Navigate to URL. value = URL.
   - 'fill': Input text. target = element description, value = text.
   - 'click': Click element. target = element description.
   - 'hover': Hover over element. target = element description.
   - 'press': Press keyboard key. value = Key name (e.g., 'Enter', 'ArrowDown'). target = optional element to focus before pressing.
   - 'upload_file': Upload file. target = file input element, value = file path (e.g., 'data/photo.jpg').
   - 'handle_dialog': Handle dialog popup. value = 'accept' or 'dismiss'.
   - 'exec_code': Execute raw Python code. value = Valid Playwright Python (Sync API) code string. e.g. "page.route('**/*.png', lambda route: route.abort())".
   - 'wait': Wait for time. value = milliseconds (e.g. '2000').
   - 'assert_visible': Assert element is visible. target = element description.
   - 'assert_title': Assert page title. value = expected title text.
"""
        
        try:
            print(f"Calling LLM: {OPENAI_MODEL}...")
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": natural_language_input}
                ],
                temperature=0.0
            )
            
            content = response.choices[0].message.content.strip()
            # Clean up potential markdown formatting if the model disobeys
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            data = json.loads(content)
            print("Parsed JSON:", data)
            return TestScenario(**data)
            
        except Exception as e:
            print(f"Error calling OpenAI ({OPENAI_BASE_URL}): {e}")
            raise e
