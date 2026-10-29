---
description: 開一件新工作，從開案開始
argument-hint: "<名稱> <行銷網站|登陸頁|應用介面|設計系統|文件與說明頁>"
---

用 web-playbook 開一件新工作。參數：$ARGUMENTS（第一個是名稱，第二個是類型；缺類型就問我）。

執行 `python3 "$(cat ~/.config/web-playbook/home)/pb.py" start "<名稱>" --type <類型>`，然後照技能的格式回覆「現在／下一步／工具／注意／提升」五行，接著從 0.1 開始問我需要的資訊。
