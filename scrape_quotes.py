"""quotes.toscrape.com/js から名言と著者名を Playwright で集めて Markdown に保存する。

JavaScript で描画されるページなので、requests + BeautifulSoup ではなく実ブラウザで取得する。
ブラウザは画面に表示して実行する。

使い方:
    python scrape_quotes.py               # 全ページ（10ページ・100件）
    python scrape_quotes.py --max-pages 2 # 先頭2ページだけ
"""

import argparse
import logging
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

BASE_URL = "https://quotes.toscrape.com/"
START_URL = urljoin(BASE_URL, "js/")
USER_AGENT = "python-automation-quote-scraper/1.0"
TIMEOUT_MS = 15_000
WAIT_MIN, WAIT_MAX = 1.0, 3.0  # リクエスト間の待機時間（秒）

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
LOG_DIR = ROOT / "logs"

logger = logging.getLogger("scrape_quotes")


class ConnectionFailed(Exception):
    """接続できなかった、または HTTP エラーが返ってきた。"""


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler(LOG_DIR / "scrape_quotes.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


class Fetcher:
    """robots.txt の確認と、リクエスト間のランダム待機をまとめて行う。"""

    def __init__(self, page: Page):
        self.page = page
        self.robots = RobotFileParser()
        self.has_requested = False

    def wait(self) -> None:
        if self.has_requested:
            wait = random.uniform(WAIT_MIN, WAIT_MAX)
            logger.info("%.1f 秒待機", wait)
            time.sleep(wait)
        self.has_requested = True

    def load_robots(self) -> None:
        robots_url = urljoin(BASE_URL, "robots.txt")
        self.wait()
        logger.info("GET %s", robots_url)
        try:
            response = self.page.request.get(robots_url, timeout=TIMEOUT_MS)
        except PlaywrightError as e:
            raise ConnectionFailed(f"{robots_url}: {e}") from e
        # urllib.robotparser.RobotFileParser.read() と同じ扱いにする
        if response.status in (401, 403):
            self.robots.disallow_all = True
            logger.warning("robots.txt が %d のため、全パスを禁止として扱う", response.status)
        elif 400 <= response.status < 500:
            self.robots.allow_all = True
            logger.info("robots.txt が存在しない（%d）ため、全パスを許可として扱う", response.status)
        elif not response.ok:
            raise ConnectionFailed(f"{robots_url}: HTTP {response.status}")
        else:
            self.robots.parse(response.text().splitlines())
            logger.info("robots.txt を読み込んだ")

    def allowed(self, url: str) -> bool:
        return self.robots.can_fetch(USER_AGENT, url)

    def goto(self, url: str) -> None:
        """待機してからページを開き、名言が描画されるまで待つ。"""
        self.wait()
        logger.info("GET %s", url)
        try:
            response = self.page.goto(url, timeout=TIMEOUT_MS)
        except PlaywrightError as e:
            raise ConnectionFailed(f"{url}: {e}") from e
        if response is None or not response.ok:
            raise ConnectionFailed(f"{url}: HTTP {response.status if response else '応答なし'}")
        self.page.wait_for_selector("div.quote", timeout=TIMEOUT_MS)


def parse_quotes(page: Page) -> list[dict]:
    quotes = []
    for quote in page.locator("div.quote").all():
        quotes.append({
            "text": quote.locator("span.text").inner_text().strip(),
            "author": quote.locator("small.author").inner_text().strip(),
        })
    return quotes


def scrape(fetcher: Fetcher, max_pages: int | None, screenshot_path: Path) -> list[dict]:
    page = fetcher.page
    quotes = []
    url = START_URL
    page_no = 0
    while url and (max_pages is None or page_no < max_pages):
        if not fetcher.allowed(url):
            logger.warning("robots.txt で禁止されているためスキップ: %s", url)
            break
        page_no += 1
        fetcher.goto(url)
        if page_no == 1:
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info("スクリーンショットを %s に保存しました", screenshot_path)
        page_quotes = parse_quotes(page)
        quotes.extend(page_quotes)
        logger.info("%d ページ目: %d 件（累計 %d 件）", page_no, len(page_quotes), len(quotes))
        next_link = page.locator("li.next > a")
        url = urljoin(page.url, next_link.get_attribute("href")) if next_link.count() else None
    return quotes


def to_markdown(quotes: list[dict], scraped_at: datetime, screenshot_name: str) -> str:
    authors = len({q["author"] for q in quotes})
    lines = [
        f"# 名言一覧（{scraped_at:%Y-%m-%d}）",
        "",
        f"- 取得元: {START_URL}",
        f"- 取得日時: {scraped_at:%Y-%m-%d %H:%M:%S}",
        f"- 件数: {len(quotes)} 件（著者 {authors} 人）",
        f"- 1ページ目のスクリーンショット: [{screenshot_name}]({screenshot_name})",
        "",
        "| No. | 名言 | 著者 |",
        "|---:|---|---|",
    ]
    for i, q in enumerate(quotes, start=1):
        text = q["text"].replace("|", "\\|")  # 表が崩れないようにエスケープ
        author = q["author"].replace("|", "\\|")
        lines.append(f"| {i} | {text} | {author} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="quotes.toscrape.com/js の名言を Markdown に保存する")
    parser.add_argument("--max-pages", type=int, default=None, help="取得する最大ページ数（省略時は全ページ）")
    args = parser.parse_args()

    setup_logging()
    started_at = datetime.now()
    OUTPUT_DIR.mkdir(exist_ok=True)
    screenshot_path = OUTPUT_DIR / f"quotes_{started_at:%Y%m%d}.png"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # ブラウザを画面に表示する
        try:
            page = browser.new_page(user_agent=USER_AGENT)
            fetcher = Fetcher(page)
            fetcher.load_robots()
            quotes = scrape(fetcher, args.max_pages, screenshot_path)
        except ConnectionFailed as e:
            logger.error("接続エラーが発生したため終了します: %s", e)
            return 1
        finally:
            browser.close()

    scraped_at = datetime.now()
    out_path = OUTPUT_DIR / f"quotes_{started_at:%Y%m%d}.md"
    out_path.write_text(to_markdown(quotes, scraped_at, screenshot_path.name), encoding="utf-8")
    logger.info("%d 件を %s に保存しました", len(quotes), out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
