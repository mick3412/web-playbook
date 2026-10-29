# Web Playbook（網站與介面手冊）

網站與介面的手把手手冊：從目的和內容架構，到設計系統、視覺、建置、無障礙與效能、SEO 和 AI 搜尋、上線和量測。文案從行銷手冊來，這本只管怎麼呈現和做出來。

不綁任何產品。產品的事實和限制寫在各產品專案的 `.agents/product-marketing.md`（產品設定檔），和其他手冊共用。

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
