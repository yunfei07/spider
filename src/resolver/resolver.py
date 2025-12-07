import json
import os
import glob
from typing import List, Dict, Optional
from src.models.dsl import TestScenario

class MultiPageResolver:
    def __init__(self, pages_dir: str):
        self.pages_data = {} # { "login": [elements...], "home": [elements...] }
        self.all_elements_flat = []
        
        if not os.path.exists(pages_dir):
             print(f"Warning: Pages directory '{pages_dir}' not found.")
             return

        # Load all json files from the directory
        json_files = glob.glob(os.path.join(pages_dir, "*.json"))
        print(f"Loading {len(json_files)} page definitions from {pages_dir}...")
        
        for file_path in json_files:
            try:
                page_name = os.path.splitext(os.path.basename(file_path))[0]
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    elements = data.get("elements", [])
                    self.pages_data[page_name] = elements
                    
                    # Tag elements with their source page for debug/conflict resolution
                    for el in elements:
                        el['_source_page'] = page_name
                        self.all_elements_flat.append(el)
            except Exception as e:
                print(f"Error loading {file_path}: {e}")

    def resolve_scenario(self, scenario: TestScenario) -> TestScenario:
        print("Resolving selectors...")
        for step in scenario.steps:
            if step.target:
                # Pass page_context if available
                selector = self._resolve_selector(step.target, step.page_context)
                step.selector = selector # Assign to step.selector, not step.target
        return scenario

    def _resolve_selector(self, target_description: str, page_context: Optional[str] = None) -> str:
        # Strategy 1: Context-Aware Search (Priority)
        if page_context and page_context in self.pages_data:
            match = self._find_best_match(target_description, self.pages_data[page_context])
            if match:
                print(f"  - Resolved '{target_description}' -> {match} (in context '{page_context}')")
                return match
        
        # Strategy 2: Global Search (Fallback)
        # Flatten all elements for global search
        all_elements = []
        for elems in self.pages_data.values():
            all_elements.extend(elems)
            
        match = self._find_best_match(target_description, all_elements)
        if match:
            print(f"  - Resolved '{target_description}' -> {match} (global search)")
            return match
            
        print(f"  - WARNING: Could not resolve '{target_description}'")
        return f"get_by_text('{target_description}')"

    def _find_best_match(self, target_desc: str, elements: List[Dict]) -> Optional[str]:
        """
        Finds the best matching selector for a given description.
        Strategy:
        1. Heuristic Scoring (Keyword match)
        2. Semantic Search (Embeddings) - if Heuristic Score is low/zero
        """
        # 1. Heuristic Search
        heuristic_match, score = self._heuristic_search(target_desc, elements)
        if score >= 10: # High confidence
             return heuristic_match
             
        print(f"    - Heuristic score low ({score}). Trying Semantic Search...")
        
        # 2. Semantic Search
        try:
             return self._semantic_search(target_desc, elements)
        except Exception as e:
             print(f"    - Semantic search failed: {e}")
             return heuristic_match

    def _heuristic_search(self, target_desc: str, elements: List[Dict]) -> (Optional[str], int):
        best_match = None
        max_score = 0
        target_lower = target_desc.lower()

        for el in elements:
            score = 0
            name = el.get("name", "").lower()
            placeholder = el.get("placeholder", "").lower()
            role = el.get("role", "").lower()
            
            if target_lower == name: score += 10
            elif target_lower in name: score += 5
            elif name in target_lower and len(name) > 1: score += 5
            
            if target_lower == placeholder: score += 8
            elif target_lower in placeholder: score += 4
            elif placeholder in target_lower and len(placeholder) > 1: score += 4
            
            if target_lower in role: score += 2

            if score > max_score and score > 0:
                max_score = score
                best_match = self._build_selector(el)
        
        return best_match, max_score

    def _semantic_search(self, target_desc: str, elements: List[Dict]) -> Optional[str]:
        # Lazy import to avoid startup cost
        from openai import OpenAI
        import math
        from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_EMBEDDING_MODEL

        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        
        # 1. Get embedding for target
        resp = client.embeddings.create(input=target_desc, model=OPENAI_EMBEDDING_MODEL)
        target_vec = resp.data[0].embedding
        
        best_match = None
        max_sim = 0.0
        
        # 2. Compare with elements (In real app, cache these!)
        # We construct a synthetic description for each element
        candidates = []
        for el in elements:
            desc = f"{el.get('name', '')} {el.get('placeholder', '')} {el.get('role', '')} {el.get('text', '')}"
            candidates.append({"el": el, "desc": desc.strip()})
        
        if not candidates: return None

        # Batch embedding for candidates
        texts = [c["desc"] for c in candidates if c["desc"]]
        if not texts: return None
        
        embeddings = []
        batch_size = 5  # Safe limit for DashScope/OpenAI compatible APIs
        
        try:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                resp = client.embeddings.create(input=batch, model=OPENAI_EMBEDDING_MODEL)
                # Ensure order is preserved for extending
                batch_embeddings = [d.embedding for d in resp.data]
                embeddings.extend(batch_embeddings)
                
        except Exception as e:
            print(f"Embedding API error: {e}")
            return None

        for idx, vec in enumerate(embeddings):
            # Cosine similarity: (A . B) / (|A| * |B|)
            dot_product = sum(a*b for a,b in zip(target_vec, vec))
            magnitude_target = math.sqrt(sum(a*a for a in target_vec))
            magnitude_vec = math.sqrt(sum(b*b for b in vec))
            
            if magnitude_target == 0 or magnitude_vec == 0:
                sim = 0
            else:
                sim = dot_product / (magnitude_target * magnitude_vec)

            if sim > max_sim:
                max_sim = sim
                best_match = self._build_selector(candidates[idx]["el"])
        
        print(f"    - Semantic best match: {best_match} (sim: {max_sim:.4f})")
        if max_sim > 0.4: # Threshold (Cosine similarity is usually -1 to 1)
            return best_match
        return None

    def _build_selector(self, el: Dict) -> str:
        if el.get("data-testid"):
            return f"get_by_testid('{el['data-testid']}')"
        elif el.get("role") and el.get("name"):
            return f"get_by_role('{el['role']}', name='{el['name']}')"
        elif el.get("placeholder"):
            return f"get_by_placeholder('{el['placeholder']}')"
        elif el.get("tag") == "button" and el.get("text"):
                return f"get_by_role('button', name='{el['text']}')"
        else:
            if el.get("class"):
                    return f"locator('.{el['class'].replace(' ', '.')}')"
            else:
                    return f"locator('{el.get('tag', '*')}[name=\"{el.get('name', '')}\"]')"
