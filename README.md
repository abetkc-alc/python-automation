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

## 仮想環境の使い方
```powershell
# 有効化（PowerShell）
.venv\Scripts\Activate.ps1
# 無効化
deactivate
```
- 新しいPCでクローンした場合は `py -m venv .venv` で作り直す

## スクリプト一覧
| ファイル | 内容 |
|---|---|
| （まだなし） | |

## 運用ルール
- 作業が終わったら、この README の「作業記録」に日付と内容を追記してから commit → `git push`
