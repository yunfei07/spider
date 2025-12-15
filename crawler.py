from __future__ import annotations

import argparse
import logging
import os
import re
import time
from collections import deque
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


LOGGER = logging.getLogger("site_crawler")


def _format_netloc(hostname: str, port: Optional[int]) -> str:
    host = hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if port is None:
        return host
    return f"{host}:{port}"


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_url(url: str, *, keep_fragment: bool = False) -> Optional[str]:
    url = url.strip()
    if not url:
        return None

    split = urlsplit(url)
    scheme = split.scheme.lower()
    if scheme not in {"http", "https"}:
        return None

    hostname = split.hostname
    if not hostname:
        return None

    port = split.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    netloc = _format_netloc(hostname, port)
    path = split.path or "/"

    fragment = split.fragment if keep_fragment else ""
    normalized = urlunsplit((scheme, netloc, path, split.query, fragment))
    return normalized


def _extract_charset_from_bytes(body: bytes) -> Optional[str]:
    snippet = body[:4096].decode("ascii", errors="ignore")
    match = re.search(r"charset\s*=\s*['\"]?([a-zA-Z0-9._-]+)", snippet, flags=re.I)
    if not match:
        return None
    return match.group(1).strip().lower()


class HtmlTitleLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_title = False
        self._title_parts: list[str] = []
        self.links: list[str] = []
        self.base_href: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag == "a":
            href = attrs_dict.get("href", "").strip()
            if href:
                self.links.append(href)
            return

        if tag == "base" and self.base_href is None:
            href = attrs_dict.get("href", "").strip()
            if href:
                self.base_href = href
            return

        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)

    @property
    def title(self) -> str:
        return _normalize_text("".join(self._title_parts))


@dataclass(frozen=True)
class Page:
    url: str
    title: str


@dataclass(frozen=True)
class PlaywrightLogin:
    login_url: str
    username: str
    password: str
    username_selector: str
    next_selector: str
    password_selector: str
    submit_selector: str
    post_login_selector: Optional[str] = None


def fetch_url(
    url: str,
    *,
    timeout_s: float,
    user_agent: str,
    max_bytes: int,
) -> tuple[str, Optional[str], Optional[str], bytes]:
    req = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    with urlopen(req, timeout=timeout_s) as resp:
        final_url = resp.geturl()
        content_type = (resp.headers.get("Content-Type") or "").strip()
        charset = resp.headers.get_content_charset() or None
        body = resp.read(max_bytes + 1)
        if len(body) > max_bytes:
            body = body[:max_bytes]
        if charset is None:
            charset = _extract_charset_from_bytes(body)
        return final_url, content_type, charset, body


def _should_skip_href(href: str) -> bool:
    lowered = href.strip().lower()
    return lowered.startswith(("javascript:", "mailto:", "tel:", "data:"))


def _is_html_content_type(content_type: str) -> bool:
    if not content_type:
        return True
    lowered = content_type.lower()
    mime = lowered.split(";", 1)[0].strip()
    return "html" in mime


def crawl_site(
    start_url: str,
    *,
    max_pages: int,
    max_depth: Optional[int],
    timeout_s: float,
    delay_s: float,
    user_agent: str,
    keep_fragments: bool = False,
    max_bytes: int = 2 * 1024 * 1024,
) -> list[Page]:
    start_normalized = normalize_url(start_url, keep_fragment=keep_fragments)
    if not start_normalized:
        raise ValueError(f"Invalid start url: {start_url!r}")

    allowed_netloc = urlsplit(start_normalized).netloc
    queue: deque[tuple[str, int]] = deque([(start_normalized, 0)])
    seen: set[str] = {start_normalized}
    pages: list[Page] = []

    while queue and len(pages) < max_pages:
        requested_url, depth = queue.popleft()
        url = requested_url
        LOGGER.info("Fetch (%s/%s): %s", len(pages) + 1, max_pages, requested_url)

        try:
            final_url, content_type, charset, body = fetch_url(
                requested_url,
                timeout_s=timeout_s,
                user_agent=user_agent,
                max_bytes=max_bytes,
            )
        except HTTPError as exc:
            LOGGER.warning("HTTPError %s: %s", exc.code, url)
            continue
        except URLError as exc:
            LOGGER.warning("URLError: %s (%s)", url, exc.reason)
            continue

        final_normalized = normalize_url(final_url, keep_fragment=keep_fragments)
        if final_normalized:
            if final_normalized != url:
                seen.add(final_normalized)
            url = final_normalized

        current_netloc = urlsplit(url).netloc
        if current_netloc != allowed_netloc:
            if depth == 0 and len(pages) == 0:
                allowed_netloc = current_netloc
            else:
                LOGGER.debug("Skip redirected external: %s -> %s", requested_url, url)
                continue

        if content_type and not _is_html_content_type(content_type):
            LOGGER.debug("Skip non-HTML (%s): %s", content_type, url)
            continue

        encoding = charset or "utf-8"
        try:
            html_text = body.decode(encoding, errors="replace")
        except LookupError:
            html_text = body.decode("utf-8", errors="replace")

        parser = HtmlTitleLinkParser()
        try:
            parser.feed(html_text)
        except Exception:
            LOGGER.warning("HTML parse failed: %s", url)
            continue

        pages.append(Page(url=url, title=parser.title))

        base_for_links = parser.base_href or url
        for href in parser.links:
            if _should_skip_href(href):
                continue
            if href.strip().startswith("#") and not keep_fragments:
                continue
            next_abs = urljoin(base_for_links, href)
            next_norm = normalize_url(next_abs, keep_fragment=keep_fragments)
            if not next_norm:
                continue
            if urlsplit(next_norm).netloc != allowed_netloc:
                continue
            if next_norm in seen:
                continue
            next_depth = depth + 1
            if max_depth is not None and next_depth > max_depth:
                continue
            seen.add(next_norm)
            queue.append((next_norm, next_depth))

        if delay_s > 0:
            time.sleep(delay_s)

    return pages


def _playwright_auto_scroll(page: object, *, steps: int, delay_ms: int) -> None:
    # page is a Playwright Page; kept as object to avoid importing Playwright at module import time.
    page.evaluate(
        """
        async ({ steps, delayMs }) => {
          for (let i = 0; i < steps; i++) {
            window.scrollTo(0, document.body.scrollHeight);
            await new Promise(r => setTimeout(r, delayMs));
          }
        }
        """,
        {"steps": steps, "delayMs": delay_ms},
    )


def _playwright_extract_links(page: object) -> list[dict[str, str]]:
    return page.evaluate(
        """
        () => Array.from(document.querySelectorAll('a[href]'))
          .map(a => a.getAttribute('href') || '')
          .filter(Boolean)
          .map(raw => ({ raw, abs: new URL(raw, document.baseURI).href }))
        """
    )


def playwright_login(
    page: object,
    login: PlaywrightLogin,
    *,
    wait_until: str,
    timeout_ms: int,
) -> None:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError  # type: ignore

    LOGGER.info("Login: %s", login.login_url)
    page.goto(login.login_url, wait_until=wait_until, timeout=timeout_ms)
    page.locator(login.username_selector).first.fill(login.username)
    page.locator(login.next_selector).first.click()
    page.locator(login.password_selector).first.wait_for(state="visible", timeout=timeout_ms)
    page.locator(login.password_selector).first.fill(login.password)
    page.locator(login.submit_selector).first.click()
    if login.post_login_selector:
        page.locator(login.post_login_selector).first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
    try:
        page.wait_for_load_state(wait_until, timeout=timeout_ms)
    except PlaywrightTimeoutError:
        LOGGER.debug("Login wait_for_load_state timed out; continue.")


def crawl_site_playwright(
    start_url: str,
    *,
    max_pages: int,
    max_depth: Optional[int],
    timeout_s: float,
    delay_s: float,
    user_agent: str,
    wait_until: str,
    headless: bool,
    ignore_https_errors: bool,
    keep_fragments: bool,
    scroll: bool,
    scroll_steps: int,
    scroll_delay_ms: int,
    login: Optional[PlaywrightLogin],
) -> list[Page]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Playwright 未安装：请先执行 `pip install playwright`，并安装浏览器 `playwright install chromium`。"
        ) from exc

    if wait_until not in {"load", "domcontentloaded", "networkidle"}:
        raise ValueError(f"Invalid wait_until: {wait_until!r}")

    start_normalized = normalize_url(start_url, keep_fragment=keep_fragments)
    if not start_normalized:
        raise ValueError(f"Invalid start url: {start_url!r}")

    allowed_netloc = urlsplit(start_normalized).netloc
    queue: deque[tuple[str, int]] = deque([(start_normalized, 0)])
    seen: set[str] = {start_normalized}
    pages: list[Page] = []
    timeout_ms = int(timeout_s * 1000)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            ignore_https_errors=ignore_https_errors,
            user_agent=user_agent,
        )
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        page.set_default_navigation_timeout(timeout_ms)

        if login is not None:
            playwright_login(page, login, wait_until=wait_until, timeout_ms=timeout_ms)

        while queue and len(pages) < max_pages:
            requested_url, depth = queue.popleft()
            LOGGER.info("Goto (%s/%s): %s", len(pages) + 1, max_pages, requested_url)

            try:
                response = page.goto(requested_url, wait_until=wait_until, timeout=timeout_ms)
            except PlaywrightTimeoutError:
                LOGGER.warning("Timeout: %s", requested_url)
                continue
            except Exception as exc:
                LOGGER.warning("Goto failed: %s (%s)", requested_url, exc)
                continue

            url = page.url
            final_normalized = normalize_url(url, keep_fragment=keep_fragments)
            if final_normalized:
                if final_normalized != requested_url:
                    seen.add(final_normalized)
                url = final_normalized

            current_netloc = urlsplit(url).netloc
            if current_netloc != allowed_netloc:
                if depth == 0 and len(pages) == 0:
                    allowed_netloc = current_netloc
                else:
                    LOGGER.debug("Skip external: %s", url)
                    continue

            if response is not None:
                content_type = (response.headers.get("content-type") or "").strip()
                if content_type and not _is_html_content_type(content_type):
                    LOGGER.debug("Skip non-HTML (%s): %s", content_type, url)
                    continue

            if scroll:
                _playwright_auto_scroll(page, steps=scroll_steps, delay_ms=scroll_delay_ms)

            try:
                title = page.title()
            except Exception:
                title = ""
            pages.append(Page(url=url, title=_normalize_text(title)))

            try:
                raw_links = _playwright_extract_links(page)
            except Exception:
                raw_links = []

            for link in raw_links:
                raw = (link.get("raw") or "").strip()
                if not raw or raw == "#":
                    continue
                if _should_skip_href(raw):
                    continue
                if raw.startswith("#") and not keep_fragments:
                    continue
                abs_url = (link.get("abs") or "").strip()
                next_norm = normalize_url(abs_url, keep_fragment=keep_fragments)
                if not next_norm:
                    continue
                if urlsplit(next_norm).netloc != allowed_netloc:
                    continue
                if next_norm in seen:
                    continue
                next_depth = depth + 1
                if max_depth is not None and next_depth > max_depth:
                    continue
                seen.add(next_norm)
                queue.append((next_norm, next_depth))

            if delay_s > 0:
                time.sleep(delay_s)

        context.close()
        browser.close()

    return pages


def _yaml_quote(value: Optional[str]) -> str:
    if value is None:
        return "null"
    if value == "":
        return "''"
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def write_pages_yaml(pages: Iterable[Page], output_path: str) -> None:
    records = [{"url": page.url, "title": page.title} for page in pages]
    try:
        import yaml  # type: ignore
    except ImportError:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("---\n")
            for record in records:
                f.write(f"- url: {_yaml_quote(record.get('url'))}\n")
                f.write(f"  title: {_yaml_quote(record.get('title'))}\n")
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(records, f, allow_unicode=True, sort_keys=False)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从起始 URL 递归爬取同站点页面的 URL 和标题，并输出为 YAML。",
    )
    parser.add_argument("start_url", help="起始 URL，例如 https://example.com/")
    parser.add_argument("-o", "--output", default="site.yaml", help="输出 YAML 文件路径")
    parser.add_argument("--max-pages", type=int, default=1000, help="最多抓取页面数")
    parser.add_argument(
        "--max-depth",
        type=int,
        default=0,
        help="最大爬取深度（0 表示不限制）",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="请求超时（秒）")
    parser.add_argument("--delay", type=float, default=0.0, help="每次请求间隔（秒）")
    parser.add_argument(
        "--user-agent",
        default="SimpleSiteCrawler/1.0",
        help="HTTP User-Agent",
    )
    parser.add_argument(
        "--keep-fragment",
        action="store_true",
        help="保留 URL fragment（hash 路由的 SPA 需要）",
    )

    parser.add_argument(
        "--playwright",
        action="store_true",
        help="使用 Playwright（支持登录与 SPA 渲染）",
    )
    parser.add_argument(
        "--wait-until",
        default="networkidle",
        choices=["load", "domcontentloaded", "networkidle"],
        help="Playwright 导航等待条件",
    )
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Playwright 是否 headless（默认启用）",
    )
    parser.add_argument(
        "--ignore-https-errors",
        action="store_true",
        help="忽略 HTTPS 证书错误（内网自签名）",
    )
    parser.add_argument(
        "--scroll",
        action="store_true",
        help="每个页面自动滚动以触发懒加载",
    )
    parser.add_argument("--scroll-steps", type=int, default=6, help="自动滚动次数")
    parser.add_argument("--scroll-delay-ms", type=int, default=250, help="滚动间隔（毫秒）")

    login = parser.add_argument_group("登录（Playwright）")
    login.add_argument("--login-url", help="登录页 URL")
    login.add_argument("--username", help="用户名（或环境变量 CRAWLER_USERNAME）")
    login.add_argument("--password", help="密码（或环境变量 CRAWLER_PASSWORD）")
    login.add_argument("--username-selector", help="用户名输入框 selector")
    login.add_argument("--next-selector", help="下一步按钮 selector")
    login.add_argument("--password-selector", help="密码输入框 selector")
    login.add_argument("--submit-selector", help="立即登录按钮 selector")
    login.add_argument(
        "--post-login-selector",
        help="登录成功后等待出现的 selector（可选，用于判断登录完成）",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="输出更多日志")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    log_level = logging.WARNING
    if args.verbose >= 2:
        log_level = logging.DEBUG
    elif args.verbose >= 1:
        log_level = logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s %(message)s")

    max_depth: Optional[int] = None if args.max_depth <= 0 else args.max_depth
    keep_fragments: bool = bool(args.keep_fragment)

    try:
        use_playwright = bool(args.playwright or args.login_url)
        if use_playwright:
            login_conf: Optional[PlaywrightLogin] = None
            if args.login_url:
                username = args.username or os.environ.get("CRAWLER_USERNAME")
                password = args.password or os.environ.get("CRAWLER_PASSWORD")
                missing: list[str] = []
                if not username:
                    missing.append("username")
                if not password:
                    missing.append("password")
                if not args.username_selector:
                    missing.append("username_selector")
                if not args.next_selector:
                    missing.append("next_selector")
                if not args.password_selector:
                    missing.append("password_selector")
                if not args.submit_selector:
                    missing.append("submit_selector")
                if missing:
                    raise ValueError(
                        "登录参数缺失："
                        + ", ".join(missing)
                        + "（用户名/密码也可用环境变量 CRAWLER_USERNAME/CRAWLER_PASSWORD）"
                    )

                login_conf = PlaywrightLogin(
                    login_url=args.login_url,
                    username=username,
                    password=password,
                    username_selector=args.username_selector,
                    next_selector=args.next_selector,
                    password_selector=args.password_selector,
                    submit_selector=args.submit_selector,
                    post_login_selector=args.post_login_selector,
                )

            pages = crawl_site_playwright(
                args.start_url,
                max_pages=args.max_pages,
                max_depth=max_depth,
                timeout_s=args.timeout,
                delay_s=args.delay,
                user_agent=args.user_agent,
                wait_until=args.wait_until,
                headless=args.headless,
                ignore_https_errors=args.ignore_https_errors,
                keep_fragments=keep_fragments,
                scroll=args.scroll,
                scroll_steps=args.scroll_steps,
                scroll_delay_ms=args.scroll_delay_ms,
                login=login_conf,
            )
        else:
            pages = crawl_site(
                args.start_url,
                max_pages=args.max_pages,
                max_depth=max_depth,
                timeout_s=args.timeout,
                delay_s=args.delay,
                user_agent=args.user_agent,
                keep_fragments=keep_fragments,
            )
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted by user.")
        return 130
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        return 2
    except ValueError as exc:
        LOGGER.error("%s", exc)
        return 2

    write_pages_yaml(pages, args.output)
    print(f"Saved {len(pages)} pages to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
