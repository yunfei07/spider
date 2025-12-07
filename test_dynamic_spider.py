from src.crawler.spider import DynamicSpider
from src.crawler.auth import AuthManager
import os

def test_dynamic_crawl():
    spider = DynamicSpider(output_dir="pages_dynamic")
    spider.crawl(["https://example.com"], auto_login=False)
    
    files = os.listdir("pages_dynamic")
    print(f"Generated files: {files}")
    assert len(files) > 0

if __name__ == "__main__":
    test_dynamic_crawl()
