import os
import json
from playwright.sync_api import sync_playwright
from src.crawler.auth import AuthManager
from src.crawler.extractor import PageExtractor

class Crawler:
    def __init__(self, output_dir: str = "pages", auth_manager: AuthManager = None):
        self.output_dir = output_dir
        self.auth_manager = auth_manager
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def crawl(self, urls: list, login_url: str = None, username: str = None, password: str = None, auto_login: bool = True):
        """
        Crawls the given URLs and saves element definitions.
        urls: List of strings OR List of dicts {'url': ..., 'name': ...}
        If login credentials are provided and auto_login is True, attempts login first.
        """
        state_file = None
        
        # 1. Handle Login if needed
        if auto_login and login_url and username and password and self.auth_manager:
            print("Performing login sequence...")
            self.auth_manager.login(login_url, username, password)
            state_file = self.auth_manager.get_state_path()

        # 2. Crawl Pages
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Create context with storage state if available
            if state_file:
                print(f"Loading storage state from {state_file}")
                context = browser.new_context(storage_state=state_file)
            else:
                context = browser.new_context()
                
            page = context.new_page()

            for item in urls:
                # Normalization
                if isinstance(item, str):
                    url = item
                    custom_name = None
                else:
                    url = item.get('url')
                    custom_name = item.get('name')

                try:
                    print(f"Crawling {url}...")
                    page.goto(url)
                    page.wait_for_load_state("networkidle")
                    
                    # Extract Elements
                    extractor = PageExtractor(page)
                    elements = extractor.extract_elements()
                    
                    # Generate Page Name
                    title = page.title()
                    if custom_name:
                         safe_name = custom_name
                    else:
                         safe_name = "".join([c if c.isalnum() else "_" for c in title]).strip("_").lower() or "untitled_page"
                    
                    # Save to JSON
                    output_data = {
                        "url": url,
                        "title": title,
                        "elements": elements
                    }
                    
                    filename = os.path.join(self.output_dir, f"{safe_name}.json")
                    with open(filename, "w", encoding='utf-8') as f:
                        json.dump(output_data, f, indent=2, ensure_ascii=False)
                        
                    print(f"Saved {len(elements)} elements to {filename}")
                    
                except Exception as e:
                    print(f"Error crawling {url}: {e}")
            
            browser.close()
