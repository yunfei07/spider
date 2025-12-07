from playwright.sync_api import Page, Locator
from typing import List, Dict, Any
import hashlib

class PageExtractor:
    def __init__(self, page: Page):
        self.page = page

    def extract_elements(self) -> List[Dict[str, Any]]:
        """
        Extracts interactive elements from the current page state.
        Returns a list of dictionaries matching the JSON schema.
        """
        elements = []
        
        # Define strategies for different element types
        # 1. Buttons
        buttons = self.page.get_by_role("button").all()
        for btn in buttons:
            if self._is_valid_element(btn):
                el_data = self._extract_element_data(btn, "button")
                if el_data: elements.append(el_data)
        
        # 2. Inputs (Text, Password, Email, etc.)
        inputs = self.page.locator("input:not([type='hidden']):not([type='submit']):not([type='button'])").all()
        for inp in inputs:
            if self._is_valid_element(inp):
                el_data = self._extract_element_data(inp, "input")
                # Refine type based on attribute
                type_attr = inp.get_attribute("type") or "text"
                el_data["type"] = type_attr
                if el_data: elements.append(el_data)
        
        # 3. Links (that look like navigation)
        # Filter logic: Must have href, and text content should be non-empty
        links = self.page.locator("a[href]").all()
        for link in links:
             if self._is_valid_element(link) and link.text_content().strip():
                 el_data = self._extract_element_data(link, "link")
                 if el_data: elements.append(el_data)
                 
        # 4. Textareas
        textareas = self.page.locator("textarea").all()
        for error in textareas:
             if self._is_valid_element(error):
                 el_data = self._extract_element_data(error, "textarea")
                 if el_data: elements.append(el_data)

        # Deduplicate based on data-testid or name
        unique_elements = self._deduplicate(elements)
        return unique_elements

    def _is_valid_element(self, locator: Locator) -> bool:
        try:
            # Check for ignore attribute
            if locator.get_attribute("data-crawler-ignore"):
                return False
                
            return locator.is_visible() and locator.is_enabled()
        except:
            return False

    def _extract_element_data(self, locator: Locator, tag_type: str) -> Dict[str, Any]:
        try:
            # Basic Attributes
            text = locator.text_content() or ""
            text = text.strip()[:50] # Truncate long text
            
            # Attributes
            testid = locator.get_attribute("data-testid") or ""
            name_attr = locator.get_attribute("name") or ""
            id_attr = locator.get_attribute("id") or ""
            placeholder = locator.get_attribute("placeholder") or ""
            role = locator.get_attribute("role") or tag_type
            class_attr = locator.get_attribute("class") or ""
            
            # Construct Name (Heuristic)
            friendly_name = text or placeholder or name_attr or id_attr or testid or "Unnamed Element"
            
            return {
                "id": id_attr,
                "name": friendly_name,
                "tag": tag_type, # Simplified tag
                "text": text,
                "role": role,
                "data-testid": testid,
                "class": class_attr,
                "placeholder": placeholder
            }
        except:
            return None

    def _deduplicate(self, elements: List[Dict]) -> List[Dict]:
        """
        Simple deduplication. If multiple elements have exact same robust selectors, keep one.
        """
        seen = set()
        unique = []
        for el in elements:
            # signature: tag + name + testid + role
            sig = f"{el['tag']}_{el['name']}_{el['data-testid']}_{el['role']}"
            if sig not in seen:
                seen.add(sig)
                unique.append(el)
        return unique
