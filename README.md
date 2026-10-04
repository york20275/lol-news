# LoL 電競新聞速報

自動抓取 T1 / Faker / LPL / BLG / Worlds 近 7 天新聞（含圖片），每小時更新。

## 部署
1. 解壓縮後，把資料夾內「所有檔案」（含隱藏的 .github 資料夾）上傳到 GitHub repository 根目錄。
2. Actions 分頁 → update-news → Run workflow（先手動跑一次）。
3. Settings → Pages → Source 選 Deploy from a branch → main / (root)。
4. 網址：https://你的帳號.github.io/repository名稱/

## 自訂
- 搜尋關鍵字：fetch_news.py 的 QUERIES
- 額外媒體 RSS：fetch_news.py 的 EXTRA_FEEDS
- 保留天數：fetch_news.py 的 DAYS
