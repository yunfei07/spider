from typing import List, Dict
import collections

class TableOptimizer:
    def optimize(self, elements: List[Dict]) -> List[Dict]:
        """
        Compresses repeating table rows into a single template row.
        """
        # Group elements by their potential row identifier
        # We need to rely on some path or parent info. 
        # Since our simple Extractor doesn't return full DOM path, 
        # we might need to rely on 'xpath' or 'selector' if we had it.
        # But 'extractor.py' currently returns flat info.
        
        # To strictly implement 'Table Optimization', we should ideally do this 
        # inside the extraction phase using Playwright to analyze the DOM structure 
        # BEFORE flattening to a list.
        
        # However, if we only have the list, we can try heuristics:
        # If we see many elements with same 'role', same 'tag', and 'class', 
        # appearing in sequence? Hard to say without hierarchy.
        
        # Revised Strategy: 
        # This optimizer should actually be part of the Extractor or take the Page object.
        # But for this modular design, let's assume we enhance the Extractor to return 
        # some structural hint, or we simply rely on the 'DynamicSpider' 
        # having a 'TableStrategy' that runs *on the page* before general extraction.
        
        pass

# Redefining approach: 
# Implement a strategy that uses Playwright Locator to find tables and filters them *before* extraction.
# Or, update PageExtractor to handle tables specifically.
# Let's write the TableStrategy as a "Page Processor".

from playwright.sync_api import Page

class TableStrategy:
    def __init__(self, page: Page):
        self.page = page

    def get_template_rows(self) -> List[str]:
        """
        Returns XPath/Selectors of rows that should be IGNORED (indexes > 0).
        """
        to_ignore = []
        
        # Find all tables
        tables = self.page.locator("table")
        count = tables.count()
        
        for i in range(count):
            table = tables.nth(i)
            # Find rows in tbody to avoid header
            rows = table.locator("tbody tr")
            row_count = rows.count()
            
            if row_count > 1:
                # We want to keep the first row (index 0) and ignore 1..N
                # But wait, we need to pass this info to the extractor.
                # The extractor iterates all buttons/inputs.
                # If a button is inside a row that we want to ignore, we must skip it.
                
                # Let's generate a selector for "rows to ignore"
                # e.g. "table:nth-of-type(1) tbody tr:nth-child(n+2)" implies skipping.
                # But css :nth-child(n+2) matches 2nd onwards. 
                pass
        return []

# Actually, the easiest way is:
# In PageExtractor, when we query `page.locator("button").all()`, we get A LOT of buttons.
# We can filter them using Python check: `if element is inside row > 1`.
# To do this efficiently, we can use JS evaluation or specific selectors.

# Let's update `extractor.py` to be `SmartExtractor` which incorporates TableStrategy internally?
# Or keep them separate.
# Let's implement `TableOptimizer` that works by "CSS Hiding" or "JS Tagging" trick?
# Technique: Inject JS to mark rows > 1 with `data-ignore="true"`, then Extractor ignores them.
# This is cleaner.

class TableStrategy:
    def __init__(self, page: Page):
        self.page = page

    def mark_redundant_rows(self):
        """
        Injects JS to mark redundant table rows (index > 0) with attribute `data-crawler-ignore`.
        """
        self.page.evaluate("""() => {
            const tables = document.querySelectorAll('table');
            tables.forEach(table => {
                const bodies = table.querySelectorAll('tbody');
                bodies.forEach(tbody => {
                    const rows = tbody.querySelectorAll('tr');
                    // Start from index 1 (second row)
                    for (let i = 1; i < rows.length; i++) {
                        rows[i].setAttribute('data-crawler-ignore', 'true');
                        // Also mark children
                        const children = rows[i].querySelectorAll('*');
                        children.forEach(c => c.setAttribute('data-crawler-ignore', 'true'));
                    }
                });
            });
            // Also handle role='grid'
            const grids = document.querySelectorAll('[role="grid"]');
            grids.forEach(grid => {
                 const rows = grid.querySelectorAll('[role="row"]');
                 // Heuristic: If many rows, assume header is first? Or look for rowgroup.
                 // Simple assume skip 1+
                 for (let i = 1; i < rows.length; i++) {
                        rows[i].setAttribute('data-crawler-ignore', 'true');
                        const children = rows[i].querySelectorAll('*');
                        children.forEach(c => c.setAttribute('data-crawler-ignore', 'true'));
                 }
            });
        }""")
