import argparse
import sys
import os
import yaml

# Add project root to sys.path to ensure imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.resolver.resolver import MultiPageResolver
from src.compiler.compiler import Compiler
from src.llm.parser import LLMParser

from src.crawler.spider import DynamicSpider
from src.crawler.auth import AuthManager
from src.providers.api import APIProvider

def process_generate(args):
    """Handler for generate command"""
    prompts = []
    
    # Check source
    if args.source == 'cli':
        if not args.prompt:
            print("Error: --prompt is required when source is 'cli'")
            return
        prompts.append({"prompt": args.prompt, "id": "cli"})
    elif args.source == 'api':
        if not args.api_url:
            print("Error: --api-url is required when source is 'api'")
            return
        provider = APIProvider(args.api_url)
        prompts = provider.get_cases()
    
    if not prompts:
        print("No cases found.")
        return

    print(f"Loading metadata from {args.pages_dir}...")
    resolver = MultiPageResolver(args.pages_dir)
    llm_parser = LLMParser()
    compiler = Compiler()

    for idx, item in enumerate(prompts):
        prompt_text = item['prompt']
        print(f"\n[{idx+1}/{len(prompts)}] Processing: '{prompt_text[:50]}...'")
        
        try:
            # 1. Parse NL to DSL
            scenario = llm_parser.parse(prompt_text)
            
            # 2. Resolve Selectors
            resolved_scenario = resolver.resolve_scenario(scenario)
            
            # 3. Compile to Code
            code = compiler.compile(resolved_scenario)
            
            # Save
            safe_name = scenario.name.lower().replace(' ', '_')
            output_filename = f"test_{safe_name}.py"
            with open(output_filename, "w") as f:
                f.write(code)
            print(f"Saved to {output_filename}")
            
        except Exception as e:
            print(f"Error processing case: {e}")


def process_crawl(args):
    """Handler for crawl command"""
    urls = []
    if args.urls:
        urls = args.urls.split(',')
    elif args.url_file:
        file_ext = os.path.splitext(args.url_file)[1].lower()
        if file_ext in ['.yaml', '.yml']:
            try:
                with open(args.url_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, list):
                        urls = data # Expects [{'name': '...', 'url': '...'}, ...]
                    else:
                        print("Error: YAML file must contain a list of entries.")
                        return
            except Exception as e:
                print(f"Error reading YAML: {e}")
                return
        else:
            with open(args.url_file, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
            
    if not urls:
        print("Error: No URLs provided.")
        return

    # Parse auto_login
    auto_login_bool = args.auto_login.lower() == 'true'

    auth_manager = AuthManager()
    crawler = DynamicSpider(output_dir=args.output_dir, auth_manager=auth_manager)
    
    crawler.crawl(
        urls=urls,
        login_url=args.login_url,
        username=args.username,
        password=args.password,
        auto_login=auto_login_bool,
        ignore_https_errors=args.ignore_https_errors
    )

def main():
    print("Starting CLI...")
    parser = argparse.ArgumentParser(description="AI Test Agent CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # ... (generate parser) ...
    parser_gen = subparsers.add_parser("generate", help="Generate Playwright scripts")
    parser_gen.add_argument("prompt", nargs="?", help="Natural language test case (for cli mode)")
    parser_gen.add_argument("--pages-dir", default="pages", help="Path to pages directory")
    parser_gen.add_argument("--source", choices=['cli', 'api'], default='cli', help="Source of test cases")
    parser_gen.add_argument("--api-url", help="API URL for fetching cases")
    
    # Command: crawl
    parser_crawl = subparsers.add_parser("crawl", help="Crawl web pages for elements")
    parser_crawl.add_argument("--urls", help="Comma-separated list of URLs")
    parser_crawl.add_argument("--url-file", help="File containing list of URLs (txt or yaml)")
    parser_crawl.add_argument("--output-dir", default="pages", help="Output directory for json files")
    parser_crawl.add_argument("--login-url", help="Login page URL")
    parser_crawl.add_argument("--username", help="Login username")
    parser_crawl.add_argument("--password", help="Login password")
    parser_crawl.add_argument("--auto-login", choices=['true', 'false'], default='true', help="Enable/Disable auto-login")
    parser_crawl.add_argument("--ignore-https-errors", action="store_true", help="Ignore HTTPS certificate errors")

    args = parser.parse_args()
    print(f"Command: {args.command}")

    if args.command == "generate":
        process_generate(args)
    elif args.command == "crawl":
        process_crawl(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
