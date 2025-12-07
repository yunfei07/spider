

## 项目结构
src/
  ├── models/
  │   └── dsl.py       # 数据模型 (Pydantic)
  ├── llm/
  │   └── parser.py    # LLM 交互逻辑
  ├── resolver/
  │   └── resolver.py  # 元素定位逻辑 (含 Semantic Search)
  ├── compiler/
  │   └── compiler.py  # 代码生成逻辑
  ├── main.py          # CLI 入口
  └── config.py        # 配置文件


## 1. 简单爬取 (无需登录)
python src/main.py crawl --urls https://example.com --output-dir pages

## 2. 自动登录并批量爬取
python src/main.py crawl \
  --urls urls.txt \
  --login-url https://example.com/login \
  --username "admin" \
  --password "secret" \
  --auto-login true

## 3. 使用 YAML 配置文件 (需安装 PyYAML)
urls.yaml:
- name: "login_page"
  url: "https://example.com/login"
- name: "home_page"
  url: "https://example.com/home"

python src/main.py crawl --url-file urls.yaml