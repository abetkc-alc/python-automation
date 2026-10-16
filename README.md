# python-automation

Python による自動化スクリプト置き場。

- リモート: https://github.com/abetkc-alc/python-automation

## 作業記録

### 2026-10-17
- `python-automation` フォルダを作成
- `git init`（ブランチ: `main`）し、リモート `origin` を https://github.com/abetkc-alc/python-automation.git に設定
- この README.md と `.gitignore`（Python 用）を作成して初回コミット・プッシュ

### 2026-10-17（2）
- Python 3.12.10 で仮想環境 `.venv` を作成
- `.venv/` は `.gitignore` に登録済み（初回コミット時に追加済み）なので、GitHub には上がらない

### 2026-10-17（3）
- `requests` と `beautifulsoup4` を `.venv` にインストールし、`requirements.txt` に書き出した
- `scrape_books.py` を追加（books.toscrape.com の書籍タイトル・価格・在庫状況を取得）
  - 結果は `output/books_YYYYMMDD.md` に Markdown の表で保存
  - robots.txt を読み込み、禁止パスにはアクセスしない（今は robots.txt が 404 なので全パス許可として扱う）
  - リクエストの間に 1〜3 秒のランダムな待機を入れる
  - 接続エラー・タイムアウト・HTTPエラーは `logs/scrape_books.log` に出力して終了（終了コード 1）
- 全 50 ページを実行し、1000 冊を `output/books_20261017.md` に保存（所要時間 約2分）
- 存在しないホストで接続エラー時の終了、robots.txt の禁止判定もテストで確認
- `.gitignore` に `logs/` を追加

## 仮想環境の使い方
```powershell
# 有効化（PowerShell）
.venv\Scripts\Activate.ps1
# 無効化
deactivate
```
- 新しいPCでクローンした場合は `py -m venv .venv` で作り直し、`pip install -r requirements.txt` でライブラリを入れる

## スクリプト一覧
| ファイル | 内容 |
|---|---|
| `scrape_books.py` | books.toscrape.com の書籍タイトル・価格・在庫状況を Markdown に保存 |

### scrape_books.py の使い方
```powershell
.venv\Scripts\Activate.ps1
python scrape_books.py               # 全ページ（約2分）
python scrape_books.py --max-pages 3 # 先頭3ページだけ
```

## 運用ルール
- 作業が終わったら、この README の「作業記録」に日付と内容を追記してから commit → `git push`
