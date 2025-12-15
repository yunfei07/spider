# sandbox_crawler

使用 Python 从起始 URL 递归爬取同站点页面的 `url` 与 `title`，并输出为 YAML。

## 使用

```bash
python3 crawler.py https://example.com/ -o site.yaml
```

如果需要抓取 Vue/React 等 SPA（需要 JS 渲染）或需要登录后抓取，请使用 Playwright：

```bash
pip install playwright
playwright install chromium
```

常用参数：

- `--max-pages 1000`：最多抓取页面数（默认 1000）
- `--max-depth 0`：最大深度，0 表示不限制
- `--timeout 10`：请求超时（秒）
- `--delay 0.5`：每次请求间隔（秒）
- `-v / -vv`：输出更多日志
- `--playwright`：使用 Playwright（JS 渲染）
- `--scroll`：每页自动滚动触发懒加载
- `--keep-fragment`：保留 `#...`（hash 路由 SPA 需要）

## 输出格式

YAML 为列表，每一项包含 `url` 和 `title`：

```yaml
- url: 'https://example.com/'
  title: 'Example Domain'
```

说明：

- 默认只会抓取与起始 URL **同 netloc**（同域名+端口）的链接。
- 如已安装 `PyYAML`（`pip install pyyaml`），会使用 `yaml.safe_dump` 输出；否则使用内置的简易 YAML 写入器。

## Playwright（SPA / 登录）

SPA 示例（渲染后抓取）：

```bash
python3 crawler.py https://example.com/ -o site.yaml --playwright --scroll
```

如使用 hash 路由（例如 `/#/home`），请加 `--keep-fragment`：

```bash
python3 crawler.py https://example.com/#/ -o site.yaml --playwright --keep-fragment
```

登录后抓取（用户名 → 下一步 → 密码 → 立即登录）示例（selector 需按实际页面调整）：

```bash
export CRAWLER_USERNAME='your-username'
export CRAWLER_PASSWORD='your-password'

python3 crawler.py https://internal.example.com/ -o site.yaml --playwright \\
  --login-url https://internal.example.com/login \\
  --username-selector '#username' \\
  --next-selector 'button:has-text("下一步")' \\
  --password-selector '#password' \\
  --submit-selector 'button:has-text("立即登录")' \\
  --post-login-selector '#app'
```
