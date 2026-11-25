# 6 SEO 與 AI 搜尋

讓搜尋引擎和 AI 助手讀得懂、引用得到。

**這一步要產出：** SEO 紀錄

## 要做

- [ ] **6.1 結構化資料**：依頁面類型加 schema；不加產品沒有的評價標記
  - 幾種做法：(a) marketing-playbook:schema 技能
  - 結構化資料要和頁面上看得到的文字一致；不需要特別的 AI 標記（S6-05）
- [ ] **6.2 meta 與分享預覽**：標題、描述、分享預覽圖（OG）每頁都有
- [ ] **6.3 sitemap 與索引**：sitemap、robots、canonical；不想被收錄的頁加 noindex
  - AI 爬蟲不跑 JavaScript：重要內容和圖片要在原始 HTML 裡（S6-03）
- [ ] **6.4 AI 搜尋健檢**：跑一次 AI 搜尋能見度健檢，修完再上線
  - 幾種做法：(a) GEO Optimizer；(b) marketing-playbook:ai-seo 技能；(c) marketing-playbook:seo-audit 技能
  - 上線前做 AI 搜尋能見度健檢，上線後讀 Search Console（S6-01，待試）
  - 寫成 AI 會引用的段落：H2 用問句，第一句直接回答（S6-04，待試）

## 用什麼工具

- **Claude SEO**（T-23）：網站上線前後做 SEO 與 AI 搜尋健檢

**這一步可以試的新工具：**
- GEO Optimizer（T-03，待試）：檢查網站對 ChatGPT、Perplexity、Google AI 摘要、Gemini、Claude 的能見度，給 0–100 分、九大類結果和修正建議；複查條件：下一支走到 6.4 AI 搜尋健檢 的作品
  - 測試方法：部署到預覽網址後，對公開網址跑一次（它不接受 localhost）
- geo-seo-claude（T-35，未採用）：做 AI 搜尋能見度健檢時；複查條件：做長文或 FAQ 頁、要評段落可引用度時
  - 測試方法：何時：做 AI 搜尋健檢｜怎麼做：跟 Claude SEO 對同一網站各跑一次｜看什麼：建議的差異和可做性｜有效＝有 Claude SEO 沒給的可做建議才留

## 要注意

- （目前沒有記錄）

## 讓品質更好、更獨特

- （目前沒有記錄）

## 背景知識

- 免費工具的關鍵字熱度只看方向，不能當真實搜尋量（S6-02）

## 過關條件 → 下一步

- [ ] G6.1 健檢跑過、問題修完

→ 下一步：**7 上線**

每條後面的代號可以用 `pb.py show <代號>` 看完整做法、原因和來源。
