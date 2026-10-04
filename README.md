# LoL 電競資訊速報

自動抓取 T1 / Faker / LPL / BLG / Worlds 近 7 天的新聞、Reddit、X 內容（含圖片），每小時更新；
網頁上每篇都能「生成貼文」（文字＋圖片＋標籤），也能一鍵生成彙整貼文。

## 部署
1. 解壓縮後，把資料夾內「所有檔案」（含隱藏的 .github 與 images 資料夾）上傳到 GitHub repository 根目錄，同名檔案選覆蓋。
2. Actions 分頁 → update-news → Run workflow（先手動跑一次）。
3. Settings → Pages → Source 選 Deploy from a branch → main / (root)。

## X（Twitter）
官方沒有免費讀取，預設不抓。若你有自己的 RSS 橋接服務，到 Settings → Secrets and variables → Actions → Variables
新增 X_FEED_TEMPLATE，例如 https://你的橋接網址/{handle}/rss。沒設定也能用，網頁上可用「加入 X 貼文」手動貼連結。

## 自訂
- 搜尋關鍵字 / Reddit 版面 / X 帳號：fetch_news.py 開頭的設定
- 貼文標籤與彙整篇數：index.html 開頭的 HASHTAGS、BASE_TAGS、DIGEST_COUNT
