# Web Playbook（網站與介面手冊）

網站與介面的手把手手冊：從目的和內容架構，到設計系統、視覺、建置、無障礙與效能、SEO 和 AI 搜尋、上線和量測。文案從行銷手冊來，這本只管怎麼呈現和做出來。

不綁任何產品。產品的事實和限制寫在各產品專案的 `.agents/product-marketing.md`（產品設定檔），和其他手冊共用。

## 怎麼用這個智庫（先看這段）

接到需求時照這五步走，手冊裡收的做法、工具和配方才會真的被用上：

1. **接到需求**：`python3 pb.py plan "<需求一兩句話>"`（可加 `--type <類型>`；專案有規則檔就加 `--rules <檔案>`）。它會比對配方（`data/recipes.csv`）和所有條目、工具，列出最多 3 個方案，每個方案依階段列出代號和狀態。
2. **選方案**：把 2–3 個方案給使用者看，每個都寫適合什麼、用到哪些代號、還缺什麼、主要風險，推薦一個。選好後 `plan "<需求>" --pick <編號> --save`。
3. **逐階段做**：`card <階段> --brief` 會先列「方案項目」；回覆一律附代號。
4. **順便測**：`trials` 會在每階段排最多 3 個待試項目（實戰優先）；做到那一步就照它的測試方法測。
5. **收尾**：`done` 會列出方案裡還沒記結果的項目，用 `run-log` 記有效、無效或需調整；`review` 依結果建議升降級。

另外兩件事：

- **桌上試驗**：不需要真實作品就能判斷的待試項目（試法＝桌上），用 `bench` 一批一批拿樣本測，結果用 `run-log --bench` 記；同類工具在 `data/bench.json` 分成比較組，一次比完只留一個。
- **收錄新資料**時，每個新項目都要掛到一個配方（或寫明為什麼掛不上），並標試法（桌上或實戰）。`check` 會提醒沒被配方用到的項目，`plan --unused` 列出清單。

專案自己的規則永遠優先於手冊。

## 階段

| # | 階段 | 產出 |
|---|---|---|
| 0 | 開案 | 目的、受眾、範圍、技術 |
| 1 | 內容與架構 | 頁面地圖、核准的內容稿 |
| 2 | 設計方向 | 設計系統 tokens、線框 |
| 3 | 視覺設計 | 設計稿或可預覽的頁面 |
| 4 | 建置 | 可運作的頁面 |
| 5 | 品質 | 無障礙、效能的量測數字 |
| 6 | SEO 與 AI 搜尋 | 健檢紀錄 |
| 7 | 上線 | 上線紀錄，經人核准 |
| 8 | 量測與迭代 | 數字與結論 |
| 9 | 回顧與收錄 | 實戰紀錄 |

另有兩條跨階段軌道：**協作**、**工具**。類型：行銷網站、登陸頁、應用介面、設計系統、文件與說明頁；階段卡可以只顯示某一類的步驟和條目。每一步可以列出幾種做法。

每一步的「幾種做法」會點名這台電腦已有的技能和工具（例如 frontend-design、design-taste-frontend、web-design-guidelines、design:accessibility-review、better-design MCP，以及 marketing-playbook 的 schema、ai-seo、seo-audit），手冊本身不內附技能。

每個階段的完整清單在 [`guide/`](guide/README.md)，由資料自動產生。

## 安裝（Claude Code 外掛）

```bash
python3 pb.py setup                                   # 記住 repo 位置，寫入一律回到這裡
claude plugin marketplace add "<這個 repo 的路徑>"
claude plugin install web-playbook@web-playbook-local
```

裝好後在任何專案都有技能 `web-playbook`、斜線指令 `/web-start`、`/web-status`、`/web-next`、`/web-card`、`/web-add`、`/web-review`、`/web-pause`、`/web-done`，以及進行中工作的一行提醒。進度存在產品專案的 `.website/`。

## 共用引擎

`pb.py` 和其他手冊（production-playbook、marketing-playbook）是同一份程式，`playbook.json` 決定名稱、環境變數 `WEB_PLAYBOOK_HOME` 和進度資料夾。改引擎時所有手冊一起改，測試會檢查是否相同。
