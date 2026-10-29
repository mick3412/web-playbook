#!/usr/bin/env python3
"""Playbook engine: one command for a handbook, its stage cards, progress tracking and intake.

The same file serves every playbook (production-playbook, marketing-playbook); playbook.json next to it names the
playbook, its state folder in the product's project and its environment variable. Keep the copies identical.

    python3 pb.py check                     validate data/ and confirm guide/ is up to date
    python3 pb.py build                     regenerate guide/ from data/
    python3 pb.py card 3 [--type 影片] [--brief]
    python3 pb.py start <name> --type 影片  open a production in the current project (<state_dir>/active.json)
    python3 pb.py status | check-off <ids> | advance | back <stage> | pause | resume | done | list | use <name>
    python3 pb.py hook prompt|session       one-line reminders for Claude Code hooks (never fails, prints nothing when idle)
    python3 pb.py inbox add <url|file> --note "..."   |   inbox list
    python3 pb.py similar "<text>"          find entries that say something close
    python3 pb.py next-id <stage>           next free entry id for a stage or track
    python3 pb.py run-log --entries S6-03,S3-01 --result 有效 [--name <production>] [--note ...]
    python3 pb.py review                    upgrade/downgrade/recheck suggestions from runs.csv and recheck conditions
    python3 pb.py log "<message>"           append a line to data/changelog.md
    python3 pb.py setup                     remember where this repo lives, so writes land here and not in a plugin cache

Only the standard library is used. data/*.csv and data/stages.json are the only hand-edited data; guide/ is generated.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import shutil
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

ENGINE_VERSION = "1.1"
SCRIPT_ROOT = Path(__file__).resolve().parent
CONF = json.loads((SCRIPT_ROOT / "playbook.json").read_text(encoding="utf-8"))
NAME = CONF["name"]
CONFIG_FILE = Path.home() / ".config" / NAME / "home"


def find_root() -> Path:
    """The repo that holds the data: the env var named in playbook.json, then the path saved by `setup`, then this folder."""
    for cand in (os.environ.get(CONF["home_env"]), CONFIG_FILE.read_text().strip() if CONFIG_FILE.is_file() else None):
        if cand and (Path(cand) / "data" / "stages.json").is_file():
            return Path(cand)
    return SCRIPT_ROOT


ROOT = find_root()
DATA = ROOT / "data"
GUIDE = ROOT / "guide"
ARCHIVE = ROOT / "archive"
INBOX = ROOT / "inbox"

ENTRY_COLS = ["id", "舊id", "階段", "步驟", "類型", "素材類型", "觸發", "要點", "做法", "為什麼", "來源", "證據",
              "實用度", "狀態", "內建於", "複查條件", "更新日"]
TOOL_COLS = ["id", "工具", "網址", "階段", "步驟", "素材類型", "何時用", "做什麼", "需求", "授權", "授權等級", "費用", "實用度", "狀態",
             "安裝方式", "複查條件", "查證日"]
SOURCE_COLS = ["id", "資源", "位置", "收錄日", "備註"]
RUN_COLS = ["日期", "作品", "產品", "類型", "條目id", "結果", "備註"]

TYPES = ["要做", "檢查", "工具", "提升", "陷阱", "知識"]
EVIDENCE = ["單一來源", "多來源", "實戰驗證"]
RATINGS = ["★★★", "★★", "★", "✗"]
STATUSES = ["已內建", "採用", "待試", "參考", "避開", "爭議"]
TOOL_STATUSES = ["已整合", "已安裝", "待試", "待查", "未採用", "避開"]
LICENSE_LEVELS = ["寬鬆", "本機限定", "特殊", "未標"]
COSTS = ["免費", "部分付費", "付費", "不明"]
RESULTS = ["有效", "無效", "需調整"]
TRACK_PREFIX = CONF["track_prefix"]
SHOWN = {"已內建", "採用", "待試", "爭議"}          # statuses listed in the main card sections
TRACKING_PARAMS = re.compile(r"^(utm_.*|fbclid|gclid|igshid|mcp_token|mc_cid|mc_eid|_hs.*|ref_src|si)$", re.I)


# ---------------------------------------------------------------- loading and validation
def today() -> str:
    return dt.date.today().isoformat()


def read_csv(path: Path, cols: list[str]) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != cols:
            sys.exit(f"{path.relative_to(ROOT)}: columns must be {cols}, got {reader.fieldnames}")
        return list(reader)


def write_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_ALL, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def append_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    new = not path.is_file()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_ALL, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerows(rows)


def stages() -> dict:
    return json.loads((DATA / "stages.json").read_text(encoding="utf-8"))


def entries() -> list[dict]:
    return read_csv(DATA / "entries.csv", ENTRY_COLS)


def tools() -> list[dict]:
    return read_csv(DATA / "tools.csv", TOOL_COLS)


def sources() -> list[dict]:
    return read_csv(DATA / "sources.csv", SOURCE_COLS)


def runs() -> list[dict]:
    return read_csv(DATA / "runs.csv", RUN_COLS)


def split(value: str) -> list[str]:
    return [v.strip() for v in re.split(r"[,，、]", value) if v.strip()]


def stage_keys(st: dict) -> list[str]:
    return [str(s["id"]) for s in st["stages"]] + list(st["tracks"])


def stage_by_key(st: dict, key: str) -> dict | None:
    for s in st["stages"]:
        if str(s["id"]) == str(key) or s["name"] == key:
            return s
    return None


def validate() -> list[str]:
    st = stages()
    errors: list[str] = []
    keys = stage_keys(st)
    step_ids = {step["id"] for s in st["stages"] for step in s["steps"]}
    gate_ids = [g["id"] for s in st["stages"] for g in s["gates"]]
    if len(gate_ids) != len(set(gate_ids)):
        errors.append("stages.json: duplicate gate id")
    assets = ["全部", *st["asset_types"]]
    src_ids = {s["id"] for s in sources()}
    seen: set[str] = set()
    archived = read_csv(ARCHIVE / "entries.csv", ENTRY_COLS + ["移出原因"]) if (ARCHIVE / "entries.csv").is_file() else []
    for r in entries() + archived:
        tag = r["id"]
        if tag in seen:
            errors.append(f"{tag}: duplicate id (entries and archive share one id space)")
        seen.add(tag)
    for r in entries():
        tag = r["id"]
        if r["階段"] not in keys:
            errors.append(f"{tag}: 階段「{r['階段']}」must be one of {keys}")
        elif r["階段"].isdigit():
            if not re.fullmatch(rf"S{r['階段']}-\d{{2,}}", tag):
                errors.append(f"{tag}: id must look like S{r['階段']}-NN for stage {r['階段']}")
            if r["步驟"] and r["步驟"] not in step_ids:
                errors.append(f"{tag}: 步驟「{r['步驟']}」is not in stages.json")
            if r["步驟"] and not r["步驟"].startswith(r["階段"] + "."):
                errors.append(f"{tag}: 步驟 {r['步驟']} does not belong to stage {r['階段']}")
        elif not tag.startswith(TRACK_PREFIX[r["階段"]] + "-"):
            errors.append(f"{tag}: id must start with {TRACK_PREFIX[r['階段']]}- for track {r['階段']}")
        for col, allowed in (("類型", TYPES), ("證據", EVIDENCE), ("實用度", RATINGS), ("狀態", STATUSES)):
            if r[col] not in allowed:
                errors.append(f"{tag}: {col}「{r[col]}」must be one of {allowed}")
        for a in split(r["素材類型"]):
            if a not in assets:
                errors.append(f"{tag}: 素材類型「{a}」must be one of {assets}")
        if not r["素材類型"]:
            errors.append(f"{tag}: 素材類型 is empty")
        if not split(r["觸發"]):
            errors.append(f"{tag}: 觸發 is empty")
        if not r["要點"] or not r["做法"]:
            errors.append(f"{tag}: 要點 and 做法 are required")
        for s in split(r["來源"]):
            if s not in src_ids:
                errors.append(f"{tag}: 來源 {s} is not in sources.csv")
        if r["狀態"] == "已內建" and not r["內建於"]:
            errors.append(f"{tag}: 已內建 needs 內建於")
        if r["狀態"] in ("避開",) and r["實用度"] != "✗":
            errors.append(f"{tag}: 避開 entries are rated ✗")
    tseen: set[str] = set()
    for t in tools():
        tag = t["id"]
        if tag in tseen:
            errors.append(f"{tag}: duplicate tool id")
        tseen.add(tag)
        for k in split(t["階段"]):
            if k not in keys:
                errors.append(f"{tag}: 階段「{k}」must be one of {keys}")
        for s in split(t["步驟"]):
            if s not in step_ids:
                errors.append(f"{tag}: 步驟「{s}」is not in stages.json")
        for col, allowed in (("授權等級", LICENSE_LEVELS), ("費用", COSTS), ("實用度", RATINGS), ("狀態", TOOL_STATUSES)):
            if t[col] not in allowed:
                errors.append(f"{tag}: {col}「{t[col]}」must be one of {allowed}")
        if not t["何時用"]:
            errors.append(f"{tag}: 何時用 is empty")
        for a in split(t["素材類型"]) or ["(empty)"]:
            if a not in assets:
                errors.append(f"{tag}: 素材類型「{a}」must be one of {assets}")
    for r in runs():
        if r["結果"] not in RESULTS:
            errors.append(f"runs.csv {r['作品']}: 結果「{r['結果']}」must be one of {RESULTS}")
    return errors


# ---------------------------------------------------------------- stage cards
def rating_key(r: dict) -> tuple:
    return (RATINGS.index(r["實用度"]) if r["實用度"] in RATINGS else 9, r["id"])


def for_asset(r: dict, asset: str | None) -> bool:
    kinds = split(r["素材類型"])
    return asset is None or "全部" in kinds or asset in kinds


def applies(step: dict, asset: str | None) -> bool:
    """A step with a `types` list only applies to those asset types."""
    return asset is None or not step.get("types") or asset in step["types"]


def open_steps_for(stage: dict, asset: str | None, checked: set[str]) -> list[dict]:
    return [x for x in stage["steps"] if applies(x, asset) and x["id"] not in checked]


def recheck_note(r: dict) -> str:
    """A condition-based recheck (not a date) that may hold now."""
    cond = r.get("複查條件", "")
    return f"；複查條件：{cond}" if cond and due(cond) is None else ""


def tag(r: dict) -> str:
    extra = {"待試": "，待試", "爭議": "，爭議", "參考": "，參考"}.get(r["狀態"], "")
    return f"（{r['id']}{extra}）"


def card_parts(key: str, asset: str | None = None) -> dict:
    st = stages()
    stage = stage_by_key(st, key)
    k = str(stage["id"]) if stage else key
    rows = [r for r in entries() if r["階段"] == k and for_asset(r, asset)]
    tl = [t for t in tools() if k in split(t["階段"]) and for_asset(t, asset)]
    return {
        "stage": stage,
        "key": k,
        "do": sorted([r for r in rows if r["類型"] in ("要做", "檢查") and r["狀態"] in SHOWN], key=rating_key),
        "tools_ready": [t for t in tl if t["狀態"] in ("已整合", "已安裝")],
        "tools_try": [t for t in tl if t["狀態"] in ("待試", "待查") or (t["狀態"] == "未採用" and t["複查條件"] and due(t["複查條件"]) is None)],
        "tool_entries": sorted([r for r in rows if r["類型"] == "工具" and r["狀態"] in SHOWN], key=rating_key),
        "watch": sorted([r for r in rows if r["類型"] == "陷阱" and r["狀態"] in SHOWN], key=rating_key),
        "avoid": sorted([r for r in rows if r["狀態"] == "避開"], key=rating_key),
        "level_up": sorted([r for r in rows if r["類型"] == "提升" and r["狀態"] in SHOWN], key=rating_key),
        "know": sorted([r for r in rows if r["類型"] == "知識" and r["狀態"] in SHOWN | {"參考"}], key=rating_key),
        "reference": sorted([r for r in rows if r["狀態"] == "參考" and r["類型"] != "知識"], key=rating_key),
    }


def render_card(key: str, asset: str | None = None) -> str:
    st = stages()
    p = card_parts(key, asset)
    s = p["stage"]
    out: list[str] = []
    if s:
        out += [f"# {s['id']} {s['name']}", "", s["purpose"], "", f"**這一步要產出：** {s['output']}", ""]
    else:
        out += [f"# {p['key']}（跨階段）", "", st["tracks"][p["key"]], ""]
    if asset:
        out += [f"_只列出和「{asset}」有關的條目。_", ""]
    out += ["## 要做", ""]
    by_step = defaultdict(list)
    for r in p["do"]:
        by_step[r["步驟"]].append(r)
    if s:
        for step in s["steps"]:
            if not applies(step, asset):
                by_step.pop(step["id"], None)
                continue
            out.append(f"- [ ] **{step['id']} {step['name']}**：{step['do']}")
            if step.get("ways"):
                out.append("  - 幾種做法：" + "；".join(f"({chr(97 + i)}) {w}" for i, w in enumerate(step["ways"])))
            for r in by_step.pop(step["id"], []):
                out.append(f"  - {'檢查：' if r['類型'] == '檢查' else ''}{r['要點']}{tag(r)}")
    for rows in by_step.values():
        for r in rows:
            out.append(f"- {'檢查：' if r['類型'] == '檢查' else ''}{r['要點']}{tag(r)}")
    out += ["", "## 用什麼工具", ""]
    for t in p["tools_ready"]:
        out.append(f"- **{t['工具']}**（{t['id']}）：{t['何時用']}")
    for r in p["tool_entries"]:
        out.append(f"- {r['要點']}{tag(r)}")
    if not p["tools_ready"] and not p["tool_entries"]:
        out.append("- （這一步沒有專用工具）")
    if p["tools_try"]:
        out += ["", "**這一步可以試的新工具：**"]
        for t in p["tools_try"]:
            out.append(f"- {t['工具']}（{t['id']}，{t['狀態']}）：{t['何時用']}{recheck_note(t)}")
    out += ["", "## 要注意", ""]
    for r in p["watch"]:
        out.append(f"- {r['要點']}{tag(r)}")
    for r in p["avoid"]:
        out.append(f"- 不要：{r['要點']}{tag(r)}")
    if not p["watch"] and not p["avoid"]:
        out.append("- （目前沒有記錄）")
    out += ["", "## 讓品質更好、更獨特", ""]
    out += [f"- {r['實用度']} {r['要點']}{tag(r)}" for r in p["level_up"]] or ["- （目前沒有記錄）"]
    if p["know"]:
        out += ["", "## 背景知識", ""] + [f"- {r['要點']}{tag(r)}" for r in p["know"]]
    if p["reference"]:
        out += ["", "## 參考（暫不行動）", ""] + [f"- {r['要點']}{tag(r)}" for r in p["reference"]]
    if s:
        out += ["", "## 過關條件 → 下一步", ""] + [f"- [ ] {g['id']} {g['text']}" for g in s["gates"]]
        nxt = stage_by_key(st, str(s["next"])) if s["next"] is not None else None
        out += ["", f"→ 下一步：**{nxt['id']} {nxt['name']}**" if nxt else "→ 這是最後一步：交付後回到 0 開下一支作品"]
    out += ["", "每條後面的代號可以用 `pb.py show <代號>` 看完整做法、原因和來源。", ""]
    return "\n".join(out)


def brief(key: str, asset: str | None, checked: set[str]) -> str:
    st = stages()
    p = card_parts(key, asset)
    s = p["stage"]
    open_steps = open_steps_for(s, asset, checked) if s else []
    nxt = stage_by_key(st, str(s["next"])) if s and s["next"] is not None else None
    tools_line = "、".join(f"{t['工具']}" for t in p["tools_ready"][:3]) or "（無專用工具）"
    # a condition-based hint stays only while its step is open and nobody has ticked the tool off as not applying
    open_ids = {x["id"] for x in open_steps}
    retry = sorted([t for t in p["tools_try"] if recheck_note(t) and t["id"] not in checked and (not t["步驟"] or open_ids & set(split(t["步驟"])))],
                   key=lambda t: RATINGS.index(t["實用度"]))
    if retry:
        tools_line += "；這一步可以試：" + "、".join(f"{t['工具']}（{t['複查條件']}；不適用就 check-off {t['id']}）" for t in retry[:2])
    watch = (p["watch"] + [dict(r, 要點="不要：" + r["要點"]) for r in p["avoid"]])[:2]
    up = p["level_up"][:2]
    lines = [
        f"現在：{s['id']} {s['name']}" + (f"，接著做 {open_steps[0]['id']} {open_steps[0]['name']}：{open_steps[0]['do']}" if open_steps else "，步驟都勾完了，檢查過關條件")
        + (f"（做法：{'／'.join(open_steps[0]['ways'])}）" if open_steps and open_steps[0].get("ways") else ""),
        f"下一步：{nxt['id']} {nxt['name']}" if nxt else "下一步：交付完成，做回顧",
        f"工具：{tools_line}",
        "注意：" + ("；".join(r["要點"] + f"（{r['id']}）" for r in watch) or "（無）"),
        "提升：" + ("；".join(r["要點"] + f"（{r['id']}）" for r in up) or "（無）"),
    ]
    return "\n".join(lines)


def build_pages() -> dict[Path, str]:
    st = stages()
    pages: dict[Path, str] = {}
    idx = [f"# {CONF['title']} 指南", "", "> 由 `python3 pb.py build` 從 `data/` 產生，不要手改。", "",
           "| 階段 | 產出 | 條目 | 卡片 |", "|---|---|---|---|"]
    counts = Counter(r["階段"] for r in entries())
    for s in st["stages"]:
        name = f"{s['id']:02d}-{s['name']}.md"
        pages[GUIDE / name] = render_card(str(s["id"]))
        idx.append(f"| {s['id']} {s['name']} | {s['output']} | {counts[str(s['id'])]} | [{name}]({name}) |")
    for t in st["tracks"]:
        pages[GUIDE / f"{t}.md"] = render_card(t)
        idx.append(f"| {t}（跨階段） | — | {counts[t]} | [{t}.md]({t}.md) |")
    idx += ["", "另見 [tools.md](tools.md)（全部工具）與 [watchlist.md](watchlist.md)（待試、待查、爭議、複查）。", ""]
    pages[GUIDE / "README.md"] = "\n".join(idx)
    pages[GUIDE / "tools.md"] = render_tools()
    pages[GUIDE / "watchlist.md"] = render_watchlist()
    return pages


def render_tools() -> str:
    st = stages()
    out = ["# 工具總覽", "", "> 由 `python3 pb.py build` 產生。依第一個階段分組；狀態：" + "、".join(TOOL_STATUSES) + "。", ""]
    groups = defaultdict(list)
    for t in tools():
        groups[split(t["階段"])[0] if t["階段"] else "其他"].append(t)
    for key in stage_keys(st) + ["其他"]:
        if key not in groups:
            continue
        s = stage_by_key(st, key)
        out += [f"## {s['id']} {s['name']}" if s else f"## {key}", "", "| 工具 | 狀態 | 費用 | 授權 | 何時用 |", "|---|---|---|---|---|"]
        for t in sorted(groups[key], key=lambda t: (TOOL_STATUSES.index(t["狀態"]), t["id"])):
            name = f"[{t['工具']}]({t['網址']})" if t["網址"].startswith("http") else t["工具"]
            out.append(f"| {name}（{t['id']}） | {t['狀態']} | {t['費用']} | {t['授權']}（{t['授權等級']}） | {cell(t['何時用'])} |")
        out.append("")
    return "\n".join(out)


def render_watchlist() -> str:
    out = ["# 待試與複查清單", "", "> 由 `python3 pb.py build` 產生。`pb.py review` 會依日期和實戰紀錄提出建議。", ""]
    es = [r for r in entries() if r["狀態"] in ("待試", "爭議")]
    ts = [t for t in tools() if t["狀態"] in ("待試", "待查")]
    out += ["## 待試與爭議的做法", "", "| 代號 | 狀態 | 要點 | 複查條件 |", "|---|---|---|---|"]
    out += [f"| {r['id']} | {r['狀態']} | {cell(r['要點'])} | {cell(r['複查條件']) or '—'} |" for r in sorted(es, key=rating_key)]
    out += ["", "## 待試與待查的工具", "", "| 代號 | 工具 | 狀態 | 何時用 | 複查條件 |", "|---|---|---|---|---|"]
    out += [f"| {t['id']} | {t['工具']} | {t['狀態']} | {cell(t['何時用'])} | {cell(t['複查條件']) or '—'} |" for t in ts]
    out.append("")
    return "\n".join(out)


def cell(text: str) -> str:
    return text.replace("|", "／").replace("\n", " ")


# ---------------------------------------------------------------- productions (<state_dir>/active.json in the product's project)
def project_dir() -> Path:
    start = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
    for d in (start, *start.parents):
        if (d / CONF["state_dir"] / "active.json").is_file():
            return d
    return start


def state_path() -> Path:
    return project_dir() / CONF["state_dir"] / "active.json"


def load_state() -> dict:
    p = state_path()
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"version": 1, "current": None, "items": {}}


def save_state(state: dict) -> None:
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pick(state: dict, name: str | None) -> tuple[str, dict]:
    name = name or state.get("current")
    if not name or name not in state["items"]:
        live = [n for n, it in state["items"].items() if it["status"] == "active"]
        if len(live) == 1 and not name:
            name = live[0]
        else:
            sys.exit("沒有指定作品。用 `pb.py list` 看有哪些，或 `pb.py start <名稱> --type <類型>` 開一支。")
    return name, state["items"][name]


def event(item: dict, text: str) -> None:
    item["updated"] = today()
    item.setdefault("history", []).append({"date": today(), "event": text})


def status_text(name: str, item: dict) -> str:
    st = stages()
    s = stage_by_key(st, str(item["stage"]))
    checked = set(item["checked"])
    open_steps = open_steps_for(s, item["type"], checked)
    open_gates = [g for g in s["gates"] if g["id"] not in checked]
    nxt = stage_by_key(st, str(s["next"])) if s["next"] is not None else None
    lines = [f"作品「{name}」（{item['type']}，{item['status']}）｜目前：{s['id']} {s['name']}｜產出：{s['output']}"]
    lines += ["還沒做的步驟：" + ("；".join(f"{x['id']} {x['name']}" for x in open_steps) or "（全部勾完）")]
    lines += ["還沒過的關：" + ("；".join(f"{g['id']} {g['text']}" for g in open_gates) or "（全部通過，可以 advance）")]
    lines += [f"下一步：{nxt['id']} {nxt['name']}" if nxt else "下一步：完成後做回顧（done）"]
    return "\n".join(lines)


def reminder(name: str, item: dict) -> str:
    st = stages()
    s = stage_by_key(st, str(item["stage"]))
    checked = set(item["checked"])
    open_steps = open_steps_for(s, item["type"], checked)
    open_gates = [g for g in s["gates"] if g["id"] not in checked]
    nxt = stage_by_key(st, str(s["next"])) if s["next"] is not None else None
    now = f"{s['id']} {s['name']}" + (f"（{open_steps[0]['id']} {open_steps[0]['name']}）" if open_steps else "")
    then = f"{nxt['id']} {nxt['name']}" if nxt else "回顧"
    return (f"▶ 作品 {name}（{item['type']}）｜目前：{now}｜下一步：{then}"
            f"｜未過關：{len(open_gates)} 項｜{NAME}：pb.py card {s['id']} --brief")


# ---------------------------------------------------------------- similarity
def grams(text: str) -> set[str]:
    text = re.sub(r"\s+", "", text.lower())
    return {text[i:i + 2] for i in range(len(text) - 1)}


def similar_rows(text: str, top: int = 5) -> list[tuple[float, dict]]:
    q = grams(text)
    scored = []
    for r in entries():
        g = grams(r["要點"] + r["做法"])
        score = len(q & g) / max(1, len(q | g))
        score += 0.15 * sum(1 for t in split(r["觸發"]) if t and t in text)
        scored.append((round(score, 3), r))
    return sorted(scored, key=lambda x: -x[0])[:top]


# ---------------------------------------------------------------- review
def due(cond: str) -> bool | None:
    m = re.fullmatch(r"(\d{4})-(\d{2})(?:-(\d{2}))?", cond.strip())
    if not m:
        return None
    y, mo, d = int(m[1]), int(m[2]), int(m[3] or 1)
    return dt.date(y, mo, d) <= dt.date.today()


def review_text() -> str:
    by_entry = defaultdict(Counter)
    for r in runs():
        for e in split(r["條目id"]):
            by_entry[e][r["結果"]] += 1
    es = {r["id"]: r for r in entries()}
    out: list[str] = []
    up = [e for e, c in by_entry.items() if e in es and c["有效"] >= 2 and c["無效"] == 0 and es[e]["狀態"] in ("待試", "參考", "採用")]
    down = [e for e, c in by_entry.items() if e in es and c["無效"] >= 2]
    settle = [e for e in by_entry if e in es and es[e]["狀態"] == "爭議"]
    if up:
        out += ["## 建議升級（實戰有效兩次以上）"] + [f"- {e} {es[e]['要點']}：有效 {by_entry[e]['有效']} 次；建議升為 ★★★，寫進技能或過關條件後改「已內建」" for e in up]
    if down:
        out += ["## 建議降級或改寫（實戰無效兩次以上）"] + [f"- {e} {es[e]['要點']}：無效 {by_entry[e]['無效']} 次" for e in down]
    if settle:
        out += ["## 爭議條目有實戰紀錄了，建議定案"] + [f"- {e} {es[e]['要點']}：{dict(by_entry[e])}" for e in settle]
    dated, conditional = [], []
    for kind, rows, open_states in (("做法", entries(), ("待試", "參考", "爭議")), ("工具", tools(), ("待試", "待查", "未採用"))):
        for r in rows:
            if r["狀態"] not in open_states or not r["複查條件"]:
                continue
            name = r.get("要點") or r.get("工具")
            flag = due(r["複查條件"])
            if flag:
                dated.append(f"- {kind} {r['id']} {name}：複查日 {r['複查條件']} 已到")
            elif flag is None:
                conditional.append(f"- {kind} {r['id']} {name}：{r['複查條件']}")
    if dated:
        out += ["## 複查日已到"] + dated
    if conditional:
        out += ["## 條件型複查（確認條件是否已成立）"] + conditional
    cutoff = dt.date.today() - dt.timedelta(days=183)
    stale = [r for r in entries() if r["狀態"] == "參考" and r["id"] not in by_entry and r["更新日"] and dt.date.fromisoformat(r["更新日"]) < cutoff]
    if stale:
        out += ["## 半年沒有動過的參考條目，建議移到 archive"] + [f"- {r['id']} {r['要點']}" for r in stale]
    pending = [p for p in INBOX.iterdir() if p.is_dir()] if INBOX.is_dir() else []
    if pending:
        out += ["## inbox 還有待收錄的資料"] + [f"- {p.name}" for p in sorted(pending)]
    return "\n".join(out) if out else "沒有需要處理的建議。"


# ---------------------------------------------------------------- commands
def cmd_check(_a) -> int:
    errors = validate()
    pages = build_pages() if not errors else {}
    stale = [p.name for p, text in pages.items() if not p.is_file() or p.read_text(encoding="utf-8") != text]
    if stale:
        errors.append("guide/ is out of date, run `pb.py build`: " + ", ".join(sorted(stale)))
    if ROOT != SCRIPT_ROOT:
        mine = json.loads((SCRIPT_ROOT / ".claude-plugin" / "plugin.json").read_text())["version"] if (SCRIPT_ROOT / ".claude-plugin" / "plugin.json").is_file() else None
        home = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
        if mine and mine != home:
            print(f"提醒：外掛快取是 {mine} 版，repo 是 {home} 版，請更新外掛。")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"OK：{len(entries())} 條做法、{len(tools())} 個工具、{len(sources())} 個來源、{len(runs())} 筆實戰紀錄")
    return 0


def cmd_build(_a) -> int:
    errors = validate()
    if errors:
        print("\n".join(errors))
        return 1
    GUIDE.mkdir(exist_ok=True)
    pages = build_pages()
    for old in GUIDE.glob("*.md"):
        if old not in pages:
            old.unlink()
    for p, text in pages.items():
        p.write_text(text, encoding="utf-8")
    print(f"wrote {len(pages)} pages in guide/")
    return 0


def cmd_card(a) -> int:
    st = stages()
    if not stage_by_key(st, a.stage) and a.stage not in st["tracks"]:
        sys.exit(f"沒有「{a.stage}」這個階段。可用：{stage_keys(st)}")
    if a.brief:
        state = load_state()
        checked = set()
        if state.get("current") in state["items"]:
            checked = set(state["items"][state["current"]]["checked"])
        print(brief(a.stage, a.type, checked) if stage_by_key(st, a.stage) else render_card(a.stage, a.type))
    else:
        print(render_card(a.stage, a.type))
    return 0


def cmd_show(a) -> int:
    for r in entries() + tools():
        if r["id"] == a.id:
            for k, v in r.items():
                if v:
                    print(f"{k}：{v}")
            return 0
    sys.exit(f"找不到 {a.id}")


def cmd_start(a) -> int:
    st = stages()
    if a.type not in st["asset_types"]:
        sys.exit(f"類型要是其中之一：{list(st['asset_types'])}")
    state = load_state()
    if a.name in state["items"]:
        sys.exit(f"已經有「{a.name}」了；用 `pb.py use {a.name}` 切換過去。")
    item = {"type": a.type, "stage": a.stage, "status": "active", "checked": [], "started": today(), "updated": today(), "history": []}
    event(item, f"開始，從 {a.stage} 開始")
    state["items"][a.name] = item
    state["current"] = a.name
    save_state(state)
    print(status_text(a.name, item))
    print()
    print(brief(str(a.stage), a.type, set()))
    return 0


def cmd_status(a) -> int:
    state = load_state()
    if not state["items"]:
        print("這個專案沒有作品。用 `pb.py start <名稱> --type <類型>` 開一支。")
        return 0
    name, item = pick(state, a.name)
    print(status_text(name, item))
    print()
    print(brief(str(item["stage"]), item["type"], set(item["checked"])))
    return 0


def cmd_check_off(a) -> int:
    state = load_state()
    name, item = pick(state, a.name)
    st = stages()
    # any stage's steps and gates are accepted, so work finished ahead of time can be ticked now
    valid = {x["id"] for s in st["stages"] for x in s["steps"]} | {g["id"] for s in st["stages"] for g in s["gates"]} | {r["id"] for r in entries()} | {t["id"] for t in tools()}
    known = [i for i in a.ids if i in valid]
    for i in a.ids:
        if i not in valid:
            print(f"略過 {i}：不是任何階段的步驟、過關條件，也不是條目或工具代號")
    if not known:
        return 1
    for i in known:
        if a.undo:
            item["checked"] = [c for c in item["checked"] if c != i]
        elif i not in item["checked"]:
            item["checked"].append(i)
    event(item, ("取消 " if a.undo else "勾選 ") + ",".join(known))
    save_state(state)
    print(status_text(name, item))
    return 0


def cmd_advance(a) -> int:
    state = load_state()
    name, item = pick(state, a.name)
    st = stages()
    s = stage_by_key(st, str(item["stage"]))
    missing = [g for g in s["gates"] if g["id"] not in item["checked"]]
    if missing:
        print(f"還不能離開 {s['id']} {s['name']}，這些過關條件還沒勾：")
        print("\n".join(f"- {g['id']} {g['text']}" for g in missing))
        print("確認做到了就用 `pb.py check-off <代號>` 勾掉。")
        return 1
    if s["next"] is None:
        print("這是最後一個階段了；用 `pb.py done` 完成作品。")
        return 1
    item["stage"] = s["next"]
    event(item, f"進到 {s['next']}")
    save_state(state)
    print(status_text(name, item))
    print()
    print(brief(str(item["stage"]), item["type"], set(item["checked"])))
    return 0


def cmd_back(a) -> int:
    state = load_state()
    name, item = pick(state, a.name)
    if not stage_by_key(stages(), a.stage):
        sys.exit(f"沒有階段 {a.stage}")
    item["stage"] = int(a.stage)
    event(item, f"退回 {a.stage}")
    save_state(state)
    print(status_text(name, item))
    return 0


def set_status(a, status: str) -> int:
    state = load_state()
    name, item = pick(state, a.name)
    item["status"] = status
    event(item, status)
    if status == "done" and state.get("current") == name:
        state["current"] = None
    save_state(state)
    print(f"作品「{name}」：{status}")
    if status == "done":
        last = stages()["stages"][-1]
        print(f"交付完成。接著做第 {last['id']} 階段{last['name']}：`pb.py card {last['id']}`，再用 `pb.py run-log` 記下這支作品用過哪些條目、效果如何。")
    return 0


def cmd_list(_a) -> int:
    state = load_state()
    if not state["items"]:
        print("這個專案沒有作品。")
    for n, it in state["items"].items():
        mark = "＊" if n == state.get("current") else "　"
        print(f"{mark}{n}（{it['type']}）：{it['status']}，階段 {it['stage']}，更新 {it['updated']}")
    return 0


def cmd_use(a) -> int:
    state = load_state()
    if a.name not in state["items"]:
        sys.exit(f"沒有「{a.name}」")
    state["current"] = a.name
    save_state(state)
    print(status_text(a.name, state["items"][a.name]))
    return 0


def cmd_hook(a) -> int:
    """Hooks must never break a session: any problem prints nothing and exits 0."""
    try:
        p = state_path()
        if not p.is_file():
            return 0
        state = json.loads(p.read_text(encoding="utf-8"))
        live = [(n, it) for n, it in state["items"].items() if it["status"] == "active"]
        if not live:
            return 0
        live.sort(key=lambda x: x[0] != state.get("current"))
        if a.kind == "session":
            print(f"進行中的作品（{NAME}）：")
            print("\n".join(reminder(n, it) for n, it in live))
            print("製作前先看目前階段的提醒：`pb.py status`；完整清單：`pb.py card <階段>`。")
        else:
            print(reminder(*live[0]))
    except Exception:  # noqa: BLE001 — a hook must stay silent rather than fail the user's prompt
        return 0
    return 0


def clean_url(url: str) -> str:
    u = urllib.parse.urlsplit(url)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True) if not TRACKING_PARAMS.match(k)]
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, urllib.parse.urlencode(q), ""))


def slug(text: str) -> str:
    s = re.sub(r"[^\w一-鿿]+", "-", text).strip("-").lower()
    return s[:48] or "item"


def cmd_inbox(a) -> int:
    INBOX.mkdir(exist_ok=True)
    if a.action == "list":
        items = sorted(p for p in INBOX.iterdir() if p.is_dir())
        if not items:
            print("inbox 是空的。")
        for p in items:
            meta = json.loads((p / "meta.json").read_text(encoding="utf-8"))
            print(f"{p.name}：{meta['source']}｜{meta.get('note', '')}")
        return 0
    src = a.source
    is_file = Path(src).expanduser().is_file()
    source = str(Path(src).expanduser().resolve()) if is_file else clean_url(src)
    base = Path(src).stem if is_file else (urllib.parse.urlsplit(source).netloc + urllib.parse.urlsplit(source).path)
    folder = INBOX / f"{today()}-{slug(base)}"
    n = 2
    while folder.exists():
        folder = INBOX / f"{today()}-{slug(base)}-{n}"
        n += 1
    folder.mkdir(parents=True)
    if is_file:
        (folder / "raw").mkdir()
        shutil.copy2(source, folder / "raw" / Path(source).name)
    meta = {"source": source, "added": today(), "note": a.note or "", "from_project": str(project_dir())}
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已放進 {folder.relative_to(ROOT)}。收錄時讀它、拆成條目，完成後刪掉這個資料夾。")
    return 0


def cmd_similar(a) -> int:
    for score, r in similar_rows(a.text, a.top):
        print(f"{score:.3f}  {r['id']}  {r['要點']}（{r['狀態']}）")
    return 0


def cmd_next_id(a) -> int:
    st = stages()
    key = a.stage
    prefix = f"S{key}" if key.isdigit() else TRACK_PREFIX.get(key)
    if not prefix or (key.isdigit() and not stage_by_key(st, key)):
        sys.exit(f"沒有「{key}」")
    archived = read_csv(ARCHIVE / "entries.csv", ENTRY_COLS + ["移出原因"]) if (ARCHIVE / "entries.csv").is_file() else []
    nums = [int(r["id"].rsplit("-", 1)[1]) for r in entries() + archived if r["id"].startswith(prefix + "-")]
    print(f"{prefix}-{(max(nums) if nums else 0) + 1:02d}")
    return 0


def cmd_run_log(a) -> int:
    ids = split(a.entries)
    known = {r["id"] for r in entries()}
    bad = [i for i in ids if i not in known]
    if bad:
        sys.exit(f"不認得這些代號：{bad}")
    if a.result not in RESULTS:
        sys.exit(f"結果要是其中之一：{RESULTS}")
    state = load_state()
    name = a.name or state.get("current") or ""
    kind = state["items"].get(name, {}).get("type", "")
    product = a.product or project_dir().name
    append_csv(DATA / "runs.csv", RUN_COLS, [{"日期": today(), "作品": name, "產品": product, "類型": kind,
                                               "條目id": ",".join(ids), "結果": a.result, "備註": a.note or ""}])
    print(f"記下了：{name}｜{','.join(ids)}｜{a.result}")
    return 0


def cmd_review(_a) -> int:
    print(review_text())
    return 0


def cmd_log(a) -> int:
    path = DATA / "changelog.md"
    if not path.is_file():
        path.write_text("# 變更紀錄\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"- {today()} {a.message}\n")
    print("已寫入 data/changelog.md")
    return 0


def cmd_setup(_a) -> int:
    if not (SCRIPT_ROOT / ".git").exists():
        sys.exit(f"請在 {NAME} 的 git repo 裡執行 setup（不是外掛快取）。")
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(str(SCRIPT_ROOT) + "\n")
    print(f"已記住手冊位置：{SCRIPT_ROOT}（{CONFIG_FILE}）")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pb.py", description=f"{CONF['title']} (engine {ENGINE_VERSION})")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    sub.add_parser("build").set_defaults(fn=cmd_build)
    p = sub.add_parser("card")
    p.add_argument("stage")
    p.add_argument("--type")
    p.add_argument("--brief", action="store_true")
    p.set_defaults(fn=cmd_card)
    p = sub.add_parser("show")
    p.add_argument("id")
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser("start")
    p.add_argument("name")
    p.add_argument("--type", required=True)
    p.add_argument("--stage", type=int, default=0)
    p.set_defaults(fn=cmd_start)
    for name, fn in (("status", cmd_status), ("advance", cmd_advance)):
        p = sub.add_parser(name)
        p.add_argument("--name")
        p.set_defaults(fn=fn)
    p = sub.add_parser("check-off")
    p.add_argument("ids", nargs="+")
    p.add_argument("--name")
    p.add_argument("--undo", action="store_true")
    p.set_defaults(fn=cmd_check_off)
    p = sub.add_parser("back")
    p.add_argument("stage")
    p.add_argument("--name")
    p.set_defaults(fn=cmd_back)
    for name, status in (("pause", "paused"), ("resume", "active"), ("done", "done")):
        p = sub.add_parser(name)
        p.add_argument("name", nargs="?")
        p.set_defaults(fn=lambda a, s=status: set_status(a, s))
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("use")
    p.add_argument("name")
    p.set_defaults(fn=cmd_use)
    p = sub.add_parser("hook")
    p.add_argument("kind", choices=["prompt", "session"])
    p.set_defaults(fn=cmd_hook)
    p = sub.add_parser("inbox")
    p.add_argument("action", choices=["add", "list"])
    p.add_argument("source", nargs="?")
    p.add_argument("--note")
    p.set_defaults(fn=cmd_inbox)
    p = sub.add_parser("similar")
    p.add_argument("text")
    p.add_argument("--top", type=int, default=5)
    p.set_defaults(fn=cmd_similar)
    p = sub.add_parser("next-id")
    p.add_argument("stage")
    p.set_defaults(fn=cmd_next_id)
    p = sub.add_parser("run-log")
    p.add_argument("--entries", required=True)
    p.add_argument("--result", required=True)
    p.add_argument("--name")
    p.add_argument("--product")
    p.add_argument("--note")
    p.set_defaults(fn=cmd_run_log)
    sub.add_parser("review").set_defaults(fn=cmd_review)
    p = sub.add_parser("log")
    p.add_argument("message")
    p.set_defaults(fn=cmd_log)
    sub.add_parser("setup").set_defaults(fn=cmd_setup)
    a = ap.parse_args(argv)
    if a.cmd == "inbox" and a.action == "add" and not a.source:
        ap.error("inbox add 需要網址或檔案")
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
