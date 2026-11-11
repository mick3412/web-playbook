---
description: 開一件新工作，從開案開始
argument-hint: "<名稱> <行銷網站|登陸頁|應用介面|設計系統|文件與說明頁>"
---

用 web-playbook 開一件新工作。參數：$ARGUMENTS（第一個是名稱，第二個是類型；缺類型就問我）。

執行 `python3 "$(cat ~/.config/web-playbook/home)/pb.py" start "<名稱>" --type <類型>`，然後照技能的格式回覆「現在／下一步／工具／注意／提升」五行。

接著把我的需求用一兩句話寫下來，跑 `python3 "$(cat ~/.config/web-playbook/home)/pb.py" plan "<需求>"`（專案有規則檔就加 `--rules <檔案>`），給我 2–3 個方案：每個方案寫適合什麼、各階段用到的代號、還缺什麼素材、主要風險，並推薦一個。我選好後用 `plan "<需求>" --pick <編號> --save` 存起來，再從 0.1 開始問我需要的資訊。
