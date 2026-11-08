# 待試與複查清單

> 由 `python3 pb.py build` 產生。`pb.py review` 會依日期和實戰紀錄提出建議。

## 待試與爭議的做法

| 代號 | 狀態 | 要點 | 複查條件 |
|---|---|---|---|
| S2-01 | 待試 | 給 AI 2–3 張參考截圖，只借結構、網格和字體，不抄文字 | — |
| S3-05 | 待試 | 版面的 7 條網格原則 | — |
| CO-01 | 待試 | 交代 AI 寫目標不寫步驟，學方法不學口氣 | — |
| CO-02 | 待試 | 把參考變成風格說明：拆解、勾選、寫規則、套用（Give AI My Taste） | — |
| S1-01 | 待試 | 一頁只有一個主軸 | — |
| S3-01 | 待試 | 網站動效的三條底線 | — |
| S3-04 | 待試 | 讓網站有質感的互動：每一個都要解決一個問題，不是裝飾 | — |
| S3-06 | 待試 | 網頁 3D：用材質而不是面數做寫實，一頁只放一個 WebGL 重點 | — |
| S4-01 | 待試 | 開工前一次問齊真實素材，沒有就留空標明，不編 | — |
| S5-01 | 待試 | 深色和淺色模式都要量對比 | — |
| S5-02 | 待試 | 做完的網站用 5 段提示詞檢查：層級、AI 感、前 5 秒、設計師檢查、手機 | — |
| S5-03 | 待試 | 7 種一看就是 AI 做的網頁痕跡，逐項檢查 | — |
| S5-04 | 待試 | 檢查分三級：底線擋上線、習慣要寫理由才能留、加分不擋 | — |
| S5-05 | 待試 | 在真的瀏覽器裡用多種寬度截整頁檢查，不只看手機和桌機 | — |
| S6-01 | 待試 | 上線前做 AI 搜尋能見度健檢，上線後讀 Search Console | — |
| S6-02 | 待試 | 免費工具的關鍵字熱度只看方向，不能當真實搜尋量 | — |
| S7-01 | 待試 | 量測前先排除自己的瀏覽 | — |
| S8-01 | 待試 | SEO 修正先看證據，依影響和工作量排序，一次改一項 | — |
| S8-02 | 待試 | 關鍵字缺口：列出競品排得上、自己沒有的搜尋詞，依意圖分群，只挑和產品相符的 | — |

## 待試與待查的工具

| 代號 | 工具 | 狀態 | 何時用 | 複查條件 |
|---|---|---|---|---|
| T-01 | Google Search Console MCP（Suganthan） | 待試 | 讓 Claude 直接讀 Search Console 的搜尋數據：找出排名在第 2 頁、差一點就上首頁的關鍵字，建議要改哪一頁；29 個工具，每次回答附資料出處 | — |
| T-03 | GEO Optimizer | 待試 | 檢查網站對 ChatGPT、Perplexity、Google AI 摘要、Gemini、Claude 的能見度，給 0–100 分、九大類結果和修正建議 | — |
| T-05 | REA（Reverse Engineer Anything） | 待查 | 想知道別人網站的某個互動或效果怎麼做時 | 安裝前確認要分析的網站條款允許 |
| T-06 | Awesome DESIGN.md（VoltAgent） | 待試 | 要定設計系統、想看好的 DESIGN.md 怎麼寫時 | — |
| T-07 | Playwright CLI（Microsoft） | 待試 | 要批次截圖、查選擇器、錄測試時 | — |
| T-08 | Image to Code | 待查 | — | 找到正確出處時 |
| T-09 | Design DNA（zanwei） | 待試 | 有參考介面、想把風格量化成規格時 | — |
| T-14 | Motion Design 技能（LottieFiles） | 待試 | 要設計動效的時間、緩動、編排時 | — |
| T-15 | 網站設計參考圖庫（Land-book、Supahero、Pricing Pages、Social Proof Examples、Navbar Gallery、OG Image Gallery、Deck Gallery） | 待試 | 找版面參考時 | — |
| T-16 | logo-design-skill（kaankiziltug） | 待試 | 要做或改 Logo 時 | — |
| T-17 | ScrollCraft | 待查 | 要做捲動驅動的網站時 | 確認正確出處時 |
| T-18 | 設計靈感網站（scrolltide、navbar.gallery、footer.design、cta.gallery、minimal.gallery、60fps.design、collectui、landdding、Savee、Cosmos、Design Spells） | 待試 | 找特定元件或細節的參考時 | — |
| T-19 | 網頁動態元件庫（React Bits、Aceternity UI） | 待試 | 要動態文字、背景、區塊時 | — |
| T-20 | WebGL 特效（ShaderGradient、Liquid Logo、Liquid Glass JS、React Three Fiber） | 待試 | 首屏需要一個動態重點時 | — |
| T-22 | Hallmark | 待試 | 建新頁、改版既有頁、或只想檢查 AI 感時 | 做下一個網站時 |
| T-23 | Claude SEO | 待試 | 網站上線前後做 SEO 與 AI 搜尋健檢 | 網站上線前 |
| T-24 | localseoskills | 待試 | 做在地商家的 SEO：Google 商家檔案、評論、名錄、在地關鍵字、AI 在地搜尋 | 做在地商家網站時 |
| T-25 | All-In-One Free SEO Tool | 待試 | 要免費做關鍵字研究、關鍵字缺口、競品比較、AI 能見度、在地 SEO 時 | 網站上線前 |
| T-26 | PulsoIcon | 待試 | 按鈕、連結、分頁要有輕微的滑過動態圖示時 | 做下一個網站時 |
