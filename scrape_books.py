"""books.toscrape.com から書籍のタイトル・価格・在庫状況を集めて Markdown に保存する。

使い方:
    python scrape_books.py               # 全ページ（50ページ・1000冊）
    python scrape_books.py --max-pages 3 # 先頭3ページだけ
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

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/"
USER_AGENT = "python-automation-book-scraper/1.0"
TIMEOUT = 10  # 秒
WAIT_MIN, WAIT_MAX = 1.0, 3.0  # リクエスト間の待機時間（秒）

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
LOG_DIR = ROOT / "logs"

logger = logging.getLogger("scrape_books")


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler(LOG_DIR / "scrape_books.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


class Fetcher:
    """robots.txt の確認と、リクエスト間のランダム待機をまとめて行う。"""

    def __init__(self, session: requests.Session):
        self.session = session
        self.robots = RobotFileParser()
        self.has_requested = False

    def get(self, url: str) -> requests.Response:
        """待機してから GET する。接続エラー・HTTPエラーは呼び出し元へ投げる。"""
        if self.has_requested:
            wait = random.uniform(WAIT_MIN, WAIT_MAX)
            logger.info("%.1f 秒待機", wait)
            time.sleep(wait)
        self.has_requested = True
        logger.info("GET %s", url)
        response = self.session.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        response.encoding = "utf-8"  # 指定しないと「£」が文字化けする
        return response

    def load_robots(self) -> None:
        robots_url = urljoin(BASE_URL, "robots.txt")
        logger.info("GET %s", robots_url)
        self.has_requested = True
        response = self.session.get(robots_url, timeout=TIMEOUT)
        # urllib.robotparser.RobotFileParser.read() と同じ扱いにする
        if response.status_code in (401, 403):
            self.robots.disallow_all = True
            logger.warning("robots.txt が %d のため、全パスを禁止として扱う", response.status_code)
        elif 400 <= response.status_code < 500:
            self.robots.allow_all = True
            logger.info("robots.txt が存在しない（%d）ため、全パスを許可として扱う", response.status_code)
        else:
            response.raise_for_status()
            self.robots.parse(response.text.splitlines())
            logger.info("robots.txt を読み込んだ")

    def allowed(self, url: str) -> bool:
        return self.robots.can_fetch(USER_AGENT, url)


def parse_books(html: str) -> tuple[list[dict], str | None]:
    """一覧ページから書籍情報と「次のページ」の相対URLを取り出す。"""
    soup = BeautifulSoup(html, "html.parser")
    books = []
    for article in soup.select("article.product_pod"):
        books.append({
            # 画面上のタイトルは省略されるので、title 属性から完全なタイトルを取る
            "title": article.h3.a["title"],
            "price": article.select_one("p.price_color").get_text(strip=True),
            "availability": article.select_one("p.availability").get_text(strip=True),
        })
    next_link = soup.select_one("li.next > a")
    return books, (next_link["href"] if next_link else None)


def scrape(fetcher: Fetcher, max_pages: int | None) -> list[dict]:
    books = []
    url = BASE_URL
    page = 0
    while url and (max_pages is None or page < max_pages):
        if not fetcher.allowed(url):
            logger.warning("robots.txt で禁止されているためスキップ: %s", url)
            break
        page += 1
        response = fetcher.get(url)
        page_books, next_href = parse_books(response.text)
        books.extend(page_books)
        logger.info("%d ページ目: %d 冊（累計 %d 冊）", page, len(page_books), len(books))
        url = urljoin(response.url, next_href) if next_href else None
    return books


def to_markdown(books: list[dict], scraped_at: datetime) -> str:
    in_stock = sum(1 for b in books if b["availability"] == "In stock")
    lines = [
        f"# 書籍一覧（{scraped_at:%Y-%m-%d}）",
        "",
        f"- 取得元: {BASE_URL}",
        f"- 取得日時: {scraped_at:%Y-%m-%d %H:%M:%S}",
        f"- 件数: {len(books)} 冊（在庫あり {in_stock} 冊）",
        "",
        "| No. | タイトル | 価格 | 在庫状況 |",
        "|---:|---|---:|---|",
    ]
    for i, b in enumerate(books, start=1):
        title = b["title"].replace("|", "\\|")  # 表が崩れないようにエスケープ
        lines.append(f"| {i} | {title} | {b['price']} | {b['availability']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="books.toscrape.com の書籍情報を Markdown に保存する")
    parser.add_argument("--max-pages", type=int, default=None, help="取得する最大ページ数（省略時は全ページ）")
    args = parser.parse_args()

    setup_logging()
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    fetcher = Fetcher(session)

    try:
        fetcher.load_robots()
        books = scrape(fetcher, args.max_pages)
    except requests.exceptions.RequestException as e:
        # 接続エラー・タイムアウト・HTTPエラーはログに残して終了する
        logger.error("接続エラーが発生したため終了します: %s", e)
        return 1

    scraped_at = datetime.now()
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"books_{scraped_at:%Y%m%d}.md"
    out_path.write_text(to_markdown(books, scraped_at), encoding="utf-8")
    logger.info("%d 冊を %s に保存しました", len(books), out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
