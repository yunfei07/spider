import os
import json
import time
from playwright.sync_api import sync_playwright, Page
from src.crawler.auth import AuthManager
from src.crawler.extractor import PageExtractor
from src.crawler.safety import SafetyFilter
from src.crawler.strategies.table import TableStrategy

class DynamicSpider:
    def __init__(self, output_dir: str = "pages", auth_manager: AuthManager = None):
        self.output_dir = output_dir
        self.auth_manager = auth_manager
        self.safety = SafetyFilter()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def crawl(self, urls: list, login_url: str = None, username: str = None, password: str = None, auto_login: bool = True, ignore_https_errors: bool = False):
        state_file = None
        
        # 1. Login
        if auto_login and login_url and username and password and self.auth_manager:
            print("Performing login (DynamicSpider)...")
            self.auth_manager.login(login_url, username, password)
            state_file = self.auth_manager.get_state_path()

        # 2. Launch
        with sync_playwright() as p:
            # Use args=['--ignore-certificate-errors'] if ignore_https_errors is True?
            # Actually context.new_context(ignore_https_errors=True) is better.
            launch_args = []
            if ignore_https_errors:
                launch_args.append('--ignore-certificate-errors')
            
            browser = p.chromium.launch(headless=False, args=launch_args) 
            
            context_options = {}
            if state_file:
                context_options['storage_state'] = state_file
            if ignore_https_errors:
                context_options['ignore_https_errors'] = True

            context = browser.new_context(**context_options)
            
            page = context.new_page()

            for item in urls:
                if isinstance(item, str):
                    url = item
                    name = None
                else:
                    url = item.get('url')
                    name = item.get('name')
                
                try:
                    self._process_page(page, url, name)
                except Exception as e:
                    print(f"Error processing {url}: {e}")
            
            browser.close()

    def _process_page(self, page: Page, url: str, custom_name: str = None):
        print(f"Navigating to {url}...")
        page.goto(url)
        page.wait_for_load_state("networkidle")
        
        # 1. Table Optimization (Mark redundant rows)
        print("Applying Table Strategy...")
        table_strat = TableStrategy(page)
        table_strat.mark_redundant_rows()
        
        # 2. Static Extraction
        print("Static extraction...")
        extractor = PageExtractor(page)
        elements = extractor.extract_elements()
        
        # 3. Dynamic Exploration
        # Find potential triggers (e.g. buttons that are not 'submit' type, or have specific classes)
        # For safety, we rely on SafetyFilter
        print("Starting Dynamic Exploration...")
        
        # Heuristic: Find elements that might open dialogs or menus
        # e.g. role=button, combobox
        triggers = page.get_by_role("button").all()
        # Also maybe links that look like actions?
        
        new_elements = []
        
        # Limit interactions to avoid infinite loops or massive time
        interactions = 0
        max_interactions = self.safety.max_depth
        
        for trigger in triggers:
            if interactions >= max_interactions: break
            
            if not extractor._is_valid_element(trigger): continue
            
            # Check Safety
            data = extractor._extract_element_data(trigger, "button")
            if not data or not self.safety.is_safe(data):
                print(f"Skipping unsafe trigger: {data.get('name', 'Unknown')}")
                continue
                
            # Try Click
            try:
                print(f" interacting with {data['name']}...")
                trigger.hover()
                # trigger.click() # Danger! Clicking might navigate away.
                # Only click if we are sure it opens a dialog or dropdown?
                # Complex logic needed here.
                # For Phase 3 V1, let's implement 'hover' detection and 'dropdown' detection
                # Maybe only click if ari-haspopup?
                
                has_popup = trigger.get_attribute("aria-haspopup")
                expanded = trigger.get_attribute("aria-expanded")
                
                if has_popup or expanded == "false":
                    trigger.click(timeout=1000)
                    page.wait_for_timeout(500) # Wait for animation
                    
                    # Check for new elements (e.g. in dialog)
                    # We can scope search to role=dialog
                    dialogs = page.get_by_role("dialog").all()
                    for d in dialogs:
                        if d.is_visible():
                            print("  Dialog detected!")
                            # Extract elements IN dialog
                            # We need modified extractor to extract FROM locator
                            # For now, just re-scan whole page and look for new visible stuff?
                            # Or simpler: just extract everything again and deduplicate.
                            current_scan = extractor.extract_elements()
                            for el in current_scan:
                                # Mark context
                                el['dynamic_context'] = f"after_{data['name']}"
                                # Add if not present in main elements
                                # (Need better dedup logic based on id/selector)
                                new_elements.append(el)
                                
                            # Close dialog - try Esc
                            page.keyboard.press("Escape")
                            page.wait_for_timeout(500)
                            
                    interactions += 1
            except Exception as e:
                print(f"Interaction failed: {e}")
        
        # Merge elements
        # Simple merge
        final_elements = elements + new_elements
        # Dedup logic needed in Crawler really
        
        # Save
        title = page.title()
        safe_name = custom_name or "".join([c if c.isalnum() else "_" for c in title]).strip("_").lower() or "page"
        output_data = {
            "url": url,
            "title": title,
            "elements": final_elements
        }
        
        filename = os.path.join(self.output_dir, f"{safe_name}.json")
        with open(filename, "w", encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(final_elements)} elements to {filename}")
