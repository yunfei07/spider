from src.models.dsl import TestScenario

class Compiler:
    def compile(self, scenario: TestScenario) -> str:
        lines = []
        lines.append("import pytest")
        lines.append("from playwright.sync_api import Page, expect")
        lines.append("")
        lines.append(f"# Test Case: {scenario.name}")
        lines.append(f"# Description: {scenario.description or ''}")
        lines.append(f"def test_{scenario.name.lower().replace(' ', '_')}(page: Page):")
        
        for step in scenario.steps:
            if step.action == "goto" and step.value:
                lines.append(f"    # Step: Visit {step.value}")
                lines.append(f"    page.goto('{step.value}')")
            else:
                lines.append(f"    # Step: {step.action} {step.target or ''}")
                code = self._generate_step_code(step)
                lines.append(f"    {code}")
            lines.append("")
            
        return "\n".join(lines)

    def _generate_step_code(self, step) -> str:
        selector = step.selector or "UNRESOLVED_SELECTOR"
        
        # Handle cases where selector is a method call (e.g. get_by_...) vs a string
        target_str = f"page.{selector}" if selector.startswith("get_by") or selector.startswith("locator") else f"page.locator(\"{selector}\")"

        if step.action == "fill":
            return f"{target_str}.fill('{step.value}')"
        
        elif step.action == "click":
             return f"{target_str}.click()"
             
        elif step.action == "hover":
             return f"{target_str}.hover()"

        elif step.action == "press":
             # If target is provided, press on that element, otherwise global page keyboard
             if step.selector and step.selector != "UNRESOLVED_SELECTOR":
                 return f"{target_str}.press('{step.value}')"
             else:
                 return f"page.keyboard.press('{step.value}')"

        elif step.action == "upload_file":
             return f"{target_str}.set_input_files('{step.value}')"

        elif step.action == "handle_dialog":
             # Registers a dialog handler for the NEXT dialog to appear
             action = step.value.lower() if step.value else 'accept'
             return f"page.once('dialog', lambda dialog: dialog.{action}())"

        elif step.action == "exec_code":
             # Directly inject raw python code
             return f"{step.value}"

        elif step.action == "wait":
             try:
                 # Default to wait_for_timeout if value is number
                 val = int(step.value)
                 return f"page.wait_for_timeout({val})"
             except:
                 return f"page.wait_for_selector('{step.value or step.selector}')"
        
        elif step.action == "assert_visible":
            return f"expect({target_str}).to_be_visible()"

        elif step.action == "assert_title":
            return f"expect(page).to_have_title('{step.value}')"

        return f"# TODO: Implement action '{step.action}'"
