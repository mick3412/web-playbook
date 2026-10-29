---
description: 把新資料丟進 inbox 並收錄
argument-hint: "<網址或檔案路徑> [為什麼有用]"
---

照 web-playbook 技能的「收錄流程」處理：$ARGUMENTS

先 `inbox add`，再讀內容、拆成條目、用 `similar` 比對既有條目（合併／新增／爭議），最後 build、check、log、commit。新增或合併前先把候選條目列給我確認。
