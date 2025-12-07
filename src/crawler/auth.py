from playwright.sync_api import sync_playwright, Page, BrowserContext
import json
import os
import time

class AuthManager:
    def __init__(self, state_file: str = "auth.json"):
        self.state_file = state_file

    def login(self, login_url: str, username: str, password: str, 
              username_selector: str = "input[name='username']", 
              password_selector: str = "input[name='password']",
              submit_selector: str = "button[type='submit']"):
        """
        Performs login and saves state to file.
        Selector defaults are generic, can be overridden.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) # Headless=False to see what happens, or for debugging
            context = browser.new_context()
            page = context.new_page()
            
            print(f"Navigating to {login_url}...")
            page.goto(login_url)
            page.wait_for_load_state("networkidle")
            
            # Simple heuristic login
            try:
                # Try to fill username
                if page.locator(username_selector).count() > 0:
                    print(f"Filling username with {username_selector}...")
                    page.fill(username_selector, username)
                else:
                    # Fallback strategies could go here (e.g. searching by label 'Username')
                    print(f"Warning: Username selector {username_selector} not found. Trying heuristic...")
                    page.get_by_label("Username").or_(page.get_by_placeholder("Username")).first.fill(username)

                # Try to fill password
                if page.locator(password_selector).count() > 0:
                    print(f"Filling password with {password_selector}...")
                    page.fill(password_selector, password)
                else:
                    print(f"Warning: Password selector {password_selector} not found. Trying heuristic...")
                    page.get_by_label("Password").or_(page.get_by_placeholder("Password")).first.fill(password)
                
                # Click submit
                if page.locator(submit_selector).count() > 0:
                     print(f"Clicking submit with {submit_selector}...")
                     page.click(submit_selector)
                else:
                     print(f"Warning: Submit selector {submit_selector} not found. Trying heuristic...")
                     page.get_by_role("button", name="Login").or_(page.get_by_role("button", name="Sign in")).first.click()
                
                print("Waiting for navigation...")
                page.wait_for_load_state("networkidle")
                
                # Check if login was successful? For now assume yes if no error.
                # In real world, we check if we are redirected or if login form is gone.
                
                print(f"Saving state to {self.state_file}...")
                context.storage_state(path=self.state_file)
                
            except Exception as e:
                print(f"Login failed: {e}")
                
            finally:
                browser.close()

    def get_state_path(self) -> str:
        if os.path.exists(self.state_file):
            return self.state_file
        return None
