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
    python3 pb.py run-log --entries S6-03,S3-01,T-05 --result 有效 [--name <production>] [--note ...]
    python3 pb.py trials [--name <production>] [--save]   the open items this piece of work tests, by stage (--type X previews)
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
import subprocess
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

ENGINE_VERSION = "1.2"
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
              "實用度", "狀態", "內建於", "複查條件", "測試方法", "試法", "情境", "更新日"]
TOOL_COLS = ["id", "工具", "網址", "階段", "步驟", "素材類型", "何時用", "做什麼", "需求", "授權", "授權等級", "費用", "實用度", "狀態",
             "安裝方式", "複查條件", "測試方法", "試法", "情境", "查證日"]
SOURCE_COLS = ["id", "資源", "位置", "收錄日", "備註"]
RUN_COLS = ["日期", "作品", "產品", "類型", "條目id", "結果", "備註"]
RECIPE_COLS = ["id", "名稱", "適用需求", "素材類型", "項目", "不適用", "情境", "更新日"]
TRIAL_KINDS = ["桌上", "實戰"]          # 桌上: a sample kit is enough to judge it; 實戰: needs a real audience
BENCH_WORK = "桌上試驗"                  # run-log --bench records under this name
PLAN_OPTIONS = 3
BASE_RECIPE = "R-00"                     # items every piece of work applies; never offered as an option

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


def recipes() -> list[dict]:
    return read_csv(DATA / "recipes.csv", RECIPE_COLS)


def bench_groups() -> dict[str, list[str]]:
    p = DATA / "bench.json"
    return json.loads(p.read_text(encoding="utf-8")).get("groups", {}) if p.is_file() else {}


# ---------------------------------------------------------------- situation facets (data/facets.json)
SHARED_DIMS = ("色彩方案", "字體性格", "形狀語言", "線條", "深度與光影", "紋理", "版面密度", "構成", "動態性格")
MOTION_DIMS = {"運鏡", "過場", "剪輯節奏", "主體動作與表演", "動態圖像"}
IMAGE_WORDS = re.compile(r"圖卡|縮圖|輪播|海報|封面|貼文圖|單張|carousel|thumbnail|poster", re.I)
_cache: dict = {}


def shared() -> dict:
    """data/shared.json: situation facets, design attributes and styles shared by all four books."""
    if "shared" not in _cache:
        p = DATA / "shared.json"
        _cache["shared"] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"分面": {}, "關聯": [], "衝突": [], "設計屬性": {}, "風格": {}}
    return _cache["shared"]


def media() -> list[str]:
    return CONF.get("媒材", [])


def attr_dim_of(name: str) -> str | None:
    """Which shared design attribute a value belongs to (values are unique per attribute, not across)."""
    for dim, vals in shared()["設計屬性"].items():
        if name in vals:
            return dim
    return None


def landing(x: dict, medium: str) -> dict[str, list[str]]:
    """A shared value's local values for one medium: its own 落地, else the union of its design attributes' 落地."""
    own = x.get("落地", {}).get(medium, {}).get("值")
    if own:
        return {d: list(v) for d, v in own.items()}
    out: dict[str, list[str]] = {}
    for dim, vals in x.get("設計屬性", {}).items():
        for v in vals:
            for d, xs in shared()["設計屬性"].get(dim, {}).get(v, {}).get("落地", {}).get(medium, {}).get("值", {}).items():
                out.setdefault(d, [])
                out[d] += [y for y in xs if y not in out[d]]
    if medium == "圖片":
        out = {d: v for d, v in out.items() if d not in MOTION_DIMS}
    return out


def localize(x: dict, medium: str, writing_keys: list[str]) -> dict:
    """A shared style or attribute value in the shape a book's vocabulary uses, for one medium."""
    lw = x.get("落地", {}).get(medium, {}).get("寫法", {})
    attrs_en = [shared()["設計屬性"][d][v]["英文"] for d, vs in x.get("設計屬性", {}).items() for v in vs if v in shared()["設計屬性"].get(d, {})]
    feat = x.get("特徵", {})
    generic = {"AI 生成": ", ".join([x["英文"], *attrs_en]), "設計提示詞": ", ".join([x["英文"], *attrs_en]),
               "程式動畫": "依特徵做：" + "；".join(f"{k} {v}" for k, v in feat.items() if v != "—") if feat else x["英文"],
               "程式實作": "依數值做：" + "、".join(f"{k} {v}" for k, v in x.get("數值", {}).items()) if x.get("數值") else "—", "實拍": "—"}
    nums = x.get("數值", {})
    return {"英文": x["英文"], "定義": x.get("定義", ""), "效果": x.get("效果", ""),
            "參數": "；".join(f"{k} {v if not isinstance(v, list) else '／'.join(map(str, v))}" for k, v in nums.items()) or "見子類",
            "數值": nums, "寫法": {k: lw.get(k) or generic.get(k, x["英文"]) for k in writing_keys}, "對應": [], "來源": x.get("來源", []),
            **{k: x[k] for k in ("上層", "同義詞", "專有名稱", "特徵", "易混淆", "設計屬性", "用語", "對應") if x.get(k)},
            "預設": landing(x, medium), "落地": x.get("落地", {}), "共用": True}


def vocab(medium: str | None = None) -> dict:
    """The book's vocabulary plus the shared style and design attributes, localized to this book's (or the given) medium."""
    key = f"vocab:{medium}"
    if key in _cache:
        return _cache[key]
    p = DATA / "vocab.json"
    V = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"維度": {}, "衝突": [], "調性預設": {}}
    if V["維度"] and media():
        medium = medium or media()[0]
        wk = sorted({k for vals in V["維度"].values() for x in vals.values() for k in x.get("寫法", {})})
        S = shared()
        for dim, vals in S["設計屬性"].items():
            V["維度"].setdefault(dim, {k: localize(x, medium, wk) for k, x in vals.items()})
        V["維度"].setdefault("風格", {k: localize(x, medium, wk) for k, x in S["風格"].items()})
    _cache[key] = V
    return V


def term_words(x: dict) -> list[str]:
    """Every name a value goes by in its 用語 table (English, Simplified Chinese, other names) — all of them call it up."""
    t = x.get("用語", {})
    return list(t.get("英文", [])) + ([t["簡中"]] if t.get("簡中") else []) + list(t.get("其他說法", []))


def facet_dict() -> dict:
    """Shared facets and design vocabulary first, then this book's own facets.json (its 工作項目, plus 停用分面／停用同義詞),
    then this book's vocabulary dimensions. English terms count as synonyms, so "whip pan" finds 過場=甩鏡."""
    if "facets" in _cache:
        return _cache["facets"]
    S = shared()
    F = {"分面": json.loads(json.dumps(S["分面"])), "關聯": list(S["關聯"]), "衝突": list(S["衝突"])}
    p = DATA / "facets.json"
    B = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    F["分面"].update(B.get("分面", {}))
    F["關聯"] += B.get("關聯", [])
    F["衝突"] += B.get("衝突", [])
    def as_facet(vals: dict) -> dict:
        return {k: {"同義詞": list(dict.fromkeys(w for w in ([x["英文"]] if x.get("英文") else []) + x.get("同義詞", []) + term_words(x) if w and w != k)),
                    **({"上層": x["上層"]} if x.get("上層") else {})} for k, x in vals.items()}
    for dim, vals in S["設計屬性"].items():
        F["分面"].setdefault(dim, as_facet(vals))
    F["分面"].setdefault("風格", as_facet(S["風格"]))
    for dim, vals in vocab()["維度"].items():
        if dim not in F["分面"]:
            F["分面"][dim] = as_facet(vals)
    for f in B.get("停用分面", []):
        F["分面"].pop(f, None)
    for f, vals in B.get("停用同義詞", {}).items():
        for v, words in vals.items():
            if v in F["分面"].get(f, {}):
                F["分面"][f][v]["同義詞"] = [w for w in F["分面"][f][v].get("同義詞", []) if w not in words]
    _cache["facets"] = F
    return F


def parse_ctx(text: str) -> dict[str, set[str]]:
    """「目的=名單、信任建立；調性=安靜高級」→ {"目的": {...}, "調性": {...}}"""
    out: dict[str, set[str]] = {}
    for part in re.split(r"[；;]", text or ""):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        vals = set(split(v))
        if k.strip() and vals:
            out.setdefault(k.strip(), set()).update(vals)
    return out


def ctx_text(ctx: dict[str, set[str]]) -> str:
    return "；".join(f"{k}={'、'.join(sorted(v))}" for k, v in ctx.items() if v)


def expand(facet: str, vals: set[str], F: dict) -> set[str]:
    """A value matches itself, every ancestor and every descendant, so neither a coarse nor a fine tag is missed."""
    tree = F["分面"].get(facet, {})
    parent = {v: m.get("上層") for v, m in tree.items()}
    out = set(vals)
    for v in vals:
        p = parent.get(v)
        while p and p not in out:
            out.add(p)
            p = parent.get(p)
    grew = True
    while grew:
        kids = {v for v, p in parent.items() if p in out and v not in out}
        out |= kids
        grew = bool(kids)
    return out


def term_in(word: str, low: str) -> bool:
    """Chinese terms match as substrings; Latin terms only as whole words, so "ig" does not fire inside "design"."""
    w = word.lower()
    if not w:
        return False
    if re.fullmatch(r"[a-z0-9][a-z0-9 .+/&'-]*", w):
        return re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", low) is not None
    return w in low


def term_spans(word: str, low: str) -> list[tuple[int, int]]:
    w = word.lower()
    if not w:
        return []
    if re.fullmatch(r"[a-z0-9][a-z0-9 .+/&'-]*", w):
        return [m.span() for m in re.finditer(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", low)]
    return [m.span() for m in re.finditer(re.escape(w), low)]


def suggest_ctx(text: str, F: dict) -> dict[str, set[str]]:
    """Facet values the text names. Longest match wins: a word inside a longer matched word does not count
    (「dolly zoom」 is not also Zoom the meeting app, 「新野獸派」 is not also 野獸派)."""
    low = text.lower()
    hits: list[tuple[int, int, str, str]] = []
    for facet, vals in F["分面"].items():
        for v, m in vals.items():
            for w in [v, *m.get("同義詞", [])]:
                hits += [(a, b, facet, v) for a, b in term_spans(w, low)]
    out: dict[str, set[str]] = {}
    latin = lambda a, b: re.fullmatch(r"[a-z0-9 .+/&'-]+", low[a:b]) is not None
    for a, b, facet, v in hits:
        if any(a2 <= a and b <= b2 and (b2 - a2) > (b - a) and v2 != v and (f2 == facet or (latin(a, b) and latin(a2, b2)))
               for a2, b2, f2, v2 in hits):
            continue        # inside a longer match of the same facet, or an English word inside a longer English phrase
        out.setdefault(facet, set()).add(v)
    for facet, vals in out.items():  # keep the most specific value: drop ancestors of other matches
        tree = F["分面"][facet]
        anc = set()
        for v in vals:
            p = tree[v].get("上層")
            while p:
                anc.add(p)
                p = tree.get(p, {}).get("上層")
        out[facet] = vals - anc
    return out


def value_overlap(row_ctx: dict[str, set[str]], need: dict[str, set[str]], F: dict) -> int:
    """How many of the need's values the row carries (each value counts with its ancestors and descendants)."""
    return sum(1 for facet, vals in need.items() for v in vals if expand(facet, {v}, F) & row_ctx.get(facet, set()))


def facet_score(row_ctx: dict[str, set[str]], need: dict[str, set[str]], F: dict) -> float:
    """+1 per need facet the row shares a value with; a facet the row does not tag is neutral; a mismatch costs 0.25."""
    s = 0.0
    for facet, vals in need.items():
        if facet not in row_ctx:
            continue
        hit = bool(expand(facet, vals, F) & row_ctx[facet])
        if facet == "限制":   # a row tagged with a limit works under it; not sharing one is no penalty
            s += 1.0 if hit else 0.0
        else:
            s += 1.0 if hit else -0.25
    return s


def conflict(row: dict, need: dict[str, set[str]], F: dict) -> str | None:
    row_ctx = parse_ctx(row.get("情境", ""))
    for c in F.get("衝突", []):
        if c["限制"] in need.get("限制", set()):
            col, val = c["排除"].split("=", 1)
            have = row_ctx.get(col, set()) | set(split(row.get(col, "")))
            if val in have:
                return f"限制「{c['限制']}」排除 {c['排除']}"
    return None


def tone_advice(need: dict[str, set[str]], F: dict) -> tuple[dict[str, list[str]], list[str]]:
    """Suggested tones with their reasons, plus warnings when the need picks a tone a relation advises against."""
    sug: dict[str, list[str]] = {}
    warn: list[str] = []
    for rel in F.get("關聯", []):
        facet, val = rel["if"].split("=", 1)
        if val not in need.get(facet, set()):
            continue
        for t in rel.get("建議", {}).get("調性", []):
            sug.setdefault(t, []).append(rel["if"])
        for t in rel.get("避開", {}).get("調性", []):
            if t in need.get("調性", set()):
                warn.append(f"{rel['if']} 建議避開「{t}」")
    return sug, warn


def validate_facets(F: dict, rows: list[tuple[str, str]]) -> list[str]:
    errors: list[str] = []
    tree = F.get("分面", {})
    for facet, vals in tree.items():
        seen: dict[str, str] = {}
        for v, m in vals.items():
            p = m.get("上層")
            if p and p not in vals:
                errors.append(f"facets.json {facet}/{v}: 上層「{p}」不在同一分面")
            hop, cur = 0, p
            while cur and hop < 20:
                cur = vals.get(cur, {}).get("上層"); hop += 1
            if hop >= 20:
                errors.append(f"facets.json {facet}/{v}: 上層形成循環")
            for w in [v, *m.get("同義詞", [])]:
                if w in seen and seen[w] != v:
                    errors.append(f"facets.json {facet}: 「{w}」同時對應 {seen[w]} 和 {v}")
                seen[w] = v
    for rel in F.get("關聯", []) + [{"if": c["排除"]} for c in F.get("衝突", []) if c["排除"].split("=")[0] in tree]:
        facet, val = rel["if"].split("=", 1)
        if val not in tree.get(facet, {}):
            errors.append(f"facets.json 關聯：「{rel['if']}」不在字典裡")
        for kind in ("建議", "避開"):
            for f2, vs in rel.get(kind, {}).items():
                errors += [f"facets.json 關聯 {rel['if']}：{f2}=「{x}」不在字典裡" for x in vs if x not in tree.get(f2, {})]
    for c in F.get("衝突", []):
        if c["限制"] not in tree.get("限制", {}):
            errors.append(f"facets.json 衝突：限制「{c['限制']}」不在字典裡")
    for tag, text in rows:
        for facet, vals in parse_ctx(text).items():
            if facet not in tree:
                errors.append(f"{tag}: 情境分面「{facet}」不在 facets.json")
                continue
            errors += [f"{tag}: 情境 {facet}=「{v}」不在 facets.json" for v in vals if v not in tree[facet]]
        if text and not parse_ctx(text):
            errors.append(f"{tag}: 情境格式要像「目的=名單、信任建立；調性=安靜高級」")
    return errors


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
        if r["狀態"] == "待試":
            if not r["測試方法"]:
                errors.append(f"{tag}: 待試 needs 測試方法（何時：…｜怎麼做：…｜看什麼：…｜有效＝…）")
            if not r["複查條件"]:
                errors.append(f"{tag}: 待試 needs 複查條件 (a date or a trigger)")
            if r["試法"] not in TRIAL_KINDS:
                errors.append(f"{tag}: 待試 needs 試法 {TRIAL_KINDS}")
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
        if t["狀態"] == "待試" and not t["測試方法"]:
            errors.append(f"{tag}: 待試 needs 測試方法（何時：…｜怎麼做：…｜看什麼：…｜有效＝…）")
        if t["狀態"] in ("待試", "待查") and not t["複查條件"]:
            errors.append(f"{tag}: {t['狀態']} needs 複查條件 (a date or a trigger)")
        if t["狀態"] == "待試" and t["試法"] not in TRIAL_KINDS:
            errors.append(f"{tag}: 待試 needs 試法 {TRIAL_KINDS}")
        for a in split(t["素材類型"]) or ["(empty)"]:
            if a not in assets:
                errors.append(f"{tag}: 素材類型「{a}」must be one of {assets}")
    for r in runs():
        if r["結果"] not in RESULTS:
            errors.append(f"runs.csv {r['作品']}: 結果「{r['結果']}」must be one of {RESULTS}")
    status = {r["id"]: r["狀態"] for r in entries()} | {t["id"]: t["狀態"] for t in tools()}
    rseen: set[str] = set()
    for rc in recipes():
        tag = rc["id"]
        if not re.fullmatch(r"R-\d{2,}", tag) or tag in rseen:
            errors.append(f"recipes.csv {tag}: id must be R-NN and unique")
        rseen.add(tag)
        if not rc["名稱"] or not split(rc["適用需求"]) or not split(rc["項目"]):
            errors.append(f"recipes.csv {tag}: 名稱, 適用需求 and 項目 are required")
        for a in split(rc["素材類型"]):
            if a not in assets:
                errors.append(f"recipes.csv {tag}: 素材類型「{a}」must be one of {assets}")
        for i in split(rc["項目"]):
            if i not in status:
                errors.append(f"recipes.csv {tag}: 項目 {i} does not exist")
            elif status[i] in ("避開", "未採用"):
                errors.append(f"recipes.csv {tag}: 項目 {i} is {status[i]}")
    for g, ids in bench_groups().items():
        for i in ids:
            if i not in status:
                errors.append(f"bench.json {g}: {i} does not exist")
    ctx_rows = [(r["id"], r["情境"]) for r in entries()] + [(t["id"], t["情境"]) for t in tools()] + \
               [(f"recipes.csv {rc['id']}", rc["情境"]) for rc in recipes()]
    errors += validate_facets(facet_dict(), ctx_rows)
    A = audit_report(reach=False)
    errors += [f"情境：{i} 沒有標工作項目" for i in A["no_work"]] + [f"情境：{d}（上層和下層一起標）" for d in A["dupes"]] + \
              [f"情境：{d}" for d in A["selfc"]]
    V = vocab()
    for tone, dims in V.get("調性預設", {}).items():
        for dim, vals in dims.items():
            errors += [f"vocab.json 調性預設 {tone}：{dim}「{x}」不在語彙裡" for x in vals if x not in V["維度"].get(dim, {})]
    if V["維度"]:   # shared values must land on values this book really has
        own = json.loads((DATA / "vocab.json").read_text(encoding="utf-8"))["維度"] if (DATA / "vocab.json").is_file() else {}
        S = shared()
        for kind, group in [("設計屬性", S["設計屬性"]), ("風格", {"風格": S["風格"]})]:
            for dim, vals in group.items():
                for k, x in vals.items():
                    for m in media():
                        for d, xs in x.get("落地", {}).get(m, {}).get("值", {}).items():
                            errors += [f"shared.json {kind}/{k}：{m} 落地 {d}「{y}」不在本書語彙" for y in xs if d in own and y not in own[d]]
                    for d, vs in x.get("設計屬性", {}).items():
                        errors += [f"shared.json 風格/{k}：設計屬性 {d}「{y}」不存在" for y in vs if y not in S["設計屬性"].get(d, {})]
    for dim, vals in V["維度"].items():
        for k, x in vals.items():
            for name in x.get("專有名稱", []):
                for how, text in x.get("寫法", {}).items():
                    if name.lower() in text.lower():
                        errors.append(f"vocab.json {dim}/{k}：寫法「{how}」出現專有名稱「{name}」；提示詞要寫特徵，不寫工作室或作者名稱")
    for c in V.get("衝突", []):
        for side in (c["a"], c["b"]):
            dim, val = side.split("=", 1)
            if val not in V["維度"].get(dim, {}):
                errors.append(f"vocab.json 衝突：「{side}」不在語彙裡")
    return errors


def unused_by_recipes() -> list[dict]:
    """Live items no recipe points to: candidates for a recipe, a merge, or demotion."""
    used = {i for rc in recipes() for i in split(rc["項目"])}
    live = [r for r in entries() if r["狀態"] in ("已內建", "採用", "待試")] + \
           [t for t in tools() if t["狀態"] in ("已整合", "已安裝", "待試")]
    return [r for r in live if r["id"] not in used]


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
            if t["測試方法"]:
                out.append(f"  - 測試方法：{t['測試方法']}")
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


def brief(key: str, asset: str | None, checked: set[str], work: str | None = None) -> str:
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
    if work and s:
        chosen = plan_ids_for_stage(work, str(s["id"]))
        if chosen:
            lines.insert(2, "方案項目：" + "；".join(f"{r['id']} {item_name(r)[:24]}{mark(r)}" for r in chosen))
        picked = trial_pick(asset, work, checked).get(str(s["id"]), ([], []))[0]
        if picked:
            lines.append("這一步要測：" + "；".join(f"{r['id']}（{how(r)}）" for r in picked) + "；完成後用 run-log 記結果")
    return "\n".join(lines)


# ---------------------------------------------------------------- trials: which open (待試) items this piece of work tests
TRIALS_PER_STAGE = 3
TOOL_TRIALS_PER_WORK = 2


def how(r: dict) -> str:
    """The 怎麼做 part of a test method, short enough for one line."""
    m = re.search(r"怎麼做：([^｜]+)", r["測試方法"])
    return (m[1] if m else r["測試方法"])[:60]


def trial_pick(asset: str | None, work: str, checked: set[str]) -> dict[str, tuple[list[dict], list[dict]]]:
    """Per stage: (picked, later). At most TRIALS_PER_STAGE per stage and TOOL_TRIALS_PER_WORK tools in all,
    best rated first, entries before tools; skips what this work already logged or ticked off."""
    st = stages()
    logged = {i for r in runs() if r["作品"] == work for i in split(r["條目id"])}
    rows = [r for r in entries() + tools() if r["狀態"] == "待試" and for_asset(r, asset)
            and r["id"] not in logged and r["id"] not in checked]
    by_stage: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_stage[(split(r["階段"]) or [""])[0]].append(r)
    out: dict[str, tuple[list[dict], list[dict]]] = {}
    tools_used = 0
    for k in stage_keys(st) + sorted(set(by_stage) - set(stage_keys(st))):
        # real work goes to what only real work can test; 桌上 items are cleared on the bench
        group = sorted(by_stage.get(k, []), key=lambda r: (r.get("試法") != "實戰", rating_key(r)[0], r["id"].startswith("T-"), r["id"]))
        picked, later = [], []
        for r in group:
            is_tool = r["id"].startswith("T-")
            if len(picked) < TRIALS_PER_STAGE and (not is_tool or tools_used < TOOL_TRIALS_PER_WORK):
                picked.append(r)
                tools_used += is_tool
            else:
                later.append(r)
        if picked or later:
            out[k] = (picked, later)
    return out


def trials_text(work: str, asset: str | None, checked: set[str]) -> str:
    st = stages()
    plan = trial_pick(asset, work, checked)
    out = [f"# 測試清單：{work}" + (f"（{asset}）" if asset else ""), "",
           f"> 由 `pb.py trials` 產生，{today()}。每階段最多測 {TRIALS_PER_STAGE} 項、整支作品最多試 {TOOL_TRIALS_PER_WORK} 個工具；"
           "做到那一步時照測試方法做，作品完成後用 `pb.py run-log --entries <代號> --result 有效|無效|需調整 --note \"<量到的結果>\"` 記下。", ""]
    total = 0
    for k, (picked, later) in plan.items():
        s = stage_by_key(st, k)
        out.append(f"## {s['id']} {s['name']}" if s else f"## {k}")
        out.append("")
        for r in picked:
            name = r.get("要點") or r.get("工具")
            out.append(f"- [ ] **{r['id']}** {name}（{r['實用度']}）")
            out.append(f"  - {r['測試方法']}")
            total += 1
        if later:
            out.append("- 之後再測：" + "、".join(f"{r['id']}" for r in later))
        out.append("")
    out.append(f"這支作品要測 {total} 項。" if total else "這支作品沒有可測的待試項目。")
    return "\n".join(out) + "\n"


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
    out += ["## 待試與爭議的做法", "", "| 代號 | 狀態 | 要點 | 複查條件 | 測試方法 |", "|---|---|---|---|---|"]
    out += [f"| {r['id']} | {r['狀態']} | {cell(r['要點'])} | {cell(r['複查條件']) or '—'} | {cell(r['測試方法']) or '—'} |" for r in sorted(es, key=rating_key)]
    out += ["", "## 待試與待查的工具", "", "| 代號 | 工具 | 狀態 | 何時用 | 複查條件 | 測試方法 |", "|---|---|---|---|---|---|"]
    out += [f"| {t['id']} | {t['工具']} | {t['狀態']} | {cell(t['何時用'])} | {cell(t['複查條件']) or '—'} | {cell(t['測試方法']) or '—'} |" for t in ts]
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


# ---------------------------------------------------------------- plan: from a free-text need to option packages
def item_name(r: dict) -> str:
    return r.get("要點") or r.get("工具") or ""


def similar_tools(text: str, top: int = 5) -> list[tuple[float, dict]]:
    q = grams(text)
    scored = []
    for t in tools():
        if t["狀態"] in ("避開", "未採用"):
            continue
        g = grams(t["工具"] + t["何時用"] + t["做什麼"])
        scored.append((round(len(q & g) / max(1, len(q | g)), 3), t))
    return sorted(scored, key=lambda x: -x[0])[:top]


def load_rules(path: str | None) -> list[str]:
    """A project's rule file, one rule per line (# comments allowed):
    `欄位=值` leaves out rows whose field equals the value (e.g. 費用=付費, 授權等級=未標);
    a plain keyword leaves out rows whose name (要點 or 工具) or 觸發 mentions it."""
    if not path:
        return []
    out = []
    for line in Path(path).expanduser().read_text(encoding="utf-8").splitlines():
        line = re.sub(r"^\s*[-*]?\s*(排除[:：])?\s*", "", line.split("#", 1)[0]).strip()
        if line:
            out.append(line)
    return out


def broken_rule(r: dict, rules: list[str]) -> str | None:
    name = " ".join(r.get(c, "") for c in ("要點", "工具", "觸發")).lower()
    for k in rules:
        if "=" in k:
            col, val = (x.strip() for x in k.split("=", 1))
            if r.get(col, "").strip() == val:
                return k
        elif k.lower() in name:
            return k
    return None


def mark(r: dict) -> str:
    kind = f"・{r['試法']}" if r["狀態"] == "待試" and r.get("試法") else ""
    return f"〔{r['狀態']}{kind}〕"


def plan_options(need: str, asset: str | None = None, rules: list[str] | None = None, facets: str | None = None) -> dict:
    """Score recipes against the need (words plus situation facets), fill each with its items,
    leave out what the project's rules or the need's limits forbid, and suggest matching items the recipe lacks."""
    rules = rules or []
    F = facet_dict()
    need_ctx = parse_ctx(facets) if facets else suggest_ctx(need, F)
    rows = {r["id"]: r for r in entries()} | {t["id"]: t for t in tools()}
    q = grams(need)
    scored = []
    for rc in recipes():
        if rc["id"] == BASE_RECIPE or (asset and not for_asset(rc, asset)):
            continue
        terms = split(rc["適用需求"])
        g = grams(rc["名稱"] + "".join(terms))
        s = len(q & g) / max(1, len(q | g)) + 0.2 * sum(1 for t in terms if t and t.lower() in need.lower())
        s += 0.15 * facet_score(parse_ctx(rc["情境"]), need_ctx, F)
        if s > 0.03:
            scored.append((round(s, 3), rc))
    scored.sort(key=lambda x: -x[0])
    pool: dict[str, float] = {}
    for s, r in similar_rows(need, 40):
        if for_asset(r, asset) and r["狀態"] in SHOWN:
            pool[r["id"]] = s
    for s, r in similar_tools(need, 20):
        if for_asset(r, asset):
            pool[r["id"]] = max(pool.get(r["id"], 0), s)
    if need_ctx:
        for r in list(entries()) + list(tools()):
            if r["狀態"] in ("避開", "未採用", "參考", "待查") or not for_asset(r, asset):
                continue
            row_ctx = parse_ctx(r["情境"])
            fs = facet_score(row_ctx, need_ctx, F)
            if fs > 0:   # same facet score: the row matching more of the need's values comes first
                pool[r["id"]] = pool.get(r["id"], 0) + 0.12 * fs + 0.03 * value_overlap(row_ctx, need_ctx, F)
    matched = [rows[i] for i, s in sorted(pool.items(), key=lambda x: -x[1]) if s >= 0.08 and i in rows]
    excluded: dict[str, tuple[dict, str]] = {}

    def keep(r: dict) -> bool:
        k = broken_rule(r, rules) or conflict(r, need_ctx, F)
        if k:
            excluded[r["id"]] = (r, k)
        return not k

    options = []
    for s, rc in scored:
        if len(options) >= PLAN_OPTIONS:
            break
        why = conflict(rc, need_ctx, F)
        if why:
            excluded[rc["id"]] = (dict(rc, 要點="配方：" + rc["名稱"]), why)
            continue
        items = [r for r in (rows[i] for i in split(rc["項目"]) if i in rows) if keep(r)]
        ids = {r["id"] for r in items}
        extras = [r for r in matched if r["id"] not in ids and keep(r)][:6]
        options.append({"id": rc["id"], "名稱": rc["名稱"], "適用需求": rc["適用需求"], "不適用": rc["不適用"],
                        "score": s, "items": items, "extras": extras})
    if not options and matched:
        items = [r for r in matched if keep(r)][:20]
        options.append({"id": "自組", "名稱": "沒有對應的配方，依需求比對組成", "適用需求": need, "不適用": "",
                        "score": 0, "items": items, "extras": []})
    tones, warns = tone_advice(need_ctx, F)
    return {"need": need, "asset": asset, "options": options, "excluded": list(excluded.values()),
            "ctx": need_ctx, "ctx_from": "指定" if facets else "從需求文字推測", "tones": tones, "warns": warns}


def stage_label(st: dict, r: dict) -> str:
    k = (split(r["階段"]) or ["其他"])[0]
    s = stage_by_key(st, k)
    return f"{s['id']} {s['name']}" if s else k


def plan_text(res: dict) -> str:
    st = stages()
    order = {k: i for i, k in enumerate(stage_keys(st))}
    out = [f"# 方案：{res['need']}" + (f"（{res['asset']}）" if res["asset"] else ""), ""]
    if res.get("ctx"):
        out.append(f"分面表（{res['ctx_from']}）：{ctx_text(res['ctx'])}")
    if res.get("tones") and "調性" not in res.get("ctx", {}):
        out.append("推測調性：" + "；".join(f"{t}（{'、'.join(w)}）" for t, w in sorted(res["tones"].items(), key=lambda x: -len(x[1]))[:4]))
    for w in res.get("warns", []):
        out.append(f"提醒：{w}")
    if res.get("ctx") or res.get("tones") or res.get("warns"):
        out.append("")
    if not res["options"]:
        out.append("找不到對應的配方或條目。換個說法再試，或用 `pb.py card 0` 從頭照階段走。")
    for n, o in enumerate(res["options"], 1):
        out.append(f"## 方案 {n}：{o['id']} {o['名稱']}" + (f"（符合度 {o['score']:.2f}）" if o["score"] else ""))
        out.append(f"適合：{o['適用需求']}" + (f"｜不適用：{o['不適用']}" if o["不適用"] else ""))
        by: dict[str, list[dict]] = defaultdict(list)
        for r in o["items"]:
            by[stage_label(st, r)].append(r)
        for lab in sorted(by, key=lambda x: order.get(x.split(" ")[0], 99)):
            out.append(f"- {lab}：" + "；".join(f"{r['id']} {item_name(r)[:28]}{mark(r)}" for r in by[lab]))
        if o["extras"]:
            out.append("- 也可以加：" + "；".join(f"{r['id']} {item_name(r)[:28]}{mark(r)}" for r in o["extras"]))
        out.append("")
    if res["excluded"]:
        out.append("排除：" + "；".join(f"{r['id']} {item_name(r)[:20]}（規則：{k}）" for r, k in res["excluded"]))
        out.append("")
    base = next((rc for rc in recipes() if rc["id"] == BASE_RECIPE), None)
    if base and res["options"]:
        n = len(split(base["項目"]))
        out.append(f"每個方案都另外套用 {BASE_RECIPE} {base['名稱']}（{n} 項：核准、授權、資安、協作習慣），`pb.py show` 各代號或看 data/recipes.csv。")
    if res["options"]:
        out.append("沒列出的階段照底座 " + BASE_RECIPE + " 和階段卡（`pb.py card <階段>`）做，不是跳過。")
        out.append("下一步：`pb.py blueprint \"<需求>\"` 產出完整計畫書（交付規格、逐階段步驟與過關、核准點、待試、風險、跨本交接、成效）；"
                   "選好方案用 `pb.py plan \"<需求>\" --pick <編號> --save` 記進作品。")
        V = vocab()
        if V["維度"] and V.get("規格卡"):
            unit = V["規格卡"].get("單位", "區塊")
            out.append(f"要精準規格：`pb.py spec --from \"<需求>\"`（有作品單加 `--work W01`），存成卡片補每一{unit}，再跑 `pb.py spec <卡>`。")
        elif V["維度"]:
            out.append("要精準規格：`pb.py spec --from \"<需求>\"`（有作品單加 `--work W01`）；分鏡後每鏡補內容，再跑 `pb.py spec <卡>`。")
    return "\n".join(out) + "\n"


def plan_ids_for_stage(work: str | None, key: str) -> list[dict]:
    if not work:
        return []
    item = load_state()["items"].get(work, {})
    ids = (item.get("plan") or {}).get("ids", [])
    rows = {r["id"]: r for r in entries()} | {t["id"]: t for t in tools()}
    return [rows[i] for i in ids if i in rows and key in split(rows[i]["階段"])]


# ---------------------------------------------------------------- spec cards: one shot spec → three sets of instructions
SPEC_META = {"編號", "秒數", "內容", "台詞", "備註", "過場到下一鏡", "英文描述", "畫面類型"}
SHOT_KINDS = ("實拍", "AI 生成", "動態圖形")      # 動態圖形 = screen graphics, UI, text cards: no camera or light
CAMERA_DIMS = {"運鏡", "視角與機位", "鏡頭與攝影機", "布光"}
SPEC_SINGLE_DIMS = {"風格", "景別", "視角與機位", "運鏡", "過場", "氛圍", "剪輯節奏"}          # one value per shot
SPEC_CONTENT_DIMS = {"動態圖像", "聲音設計", "文字與字幕", "主體動作與表演", "材質描寫"}  # tone presets only suggest these
PROMPT_ORDER = ["風格", "景別", "視角與機位", "運鏡", "鏡頭與攝影機", "主體", "構圖", "布光", "色彩", "質感", "材質描寫", "氛圍"]
REVIEW_HOW = {"景別": "抽格總覽看取景範圍", "視角與機位": "看定格的鏡頭高度與角度", "運鏡": "逐格條看位移方向和速度",
              "鏡頭與攝影機": "定格看景深、透視和格率", "構圖": "定格疊三分線檢查主體位置", "布光": "定格看光向、光比和陰影邊緣",
              "色彩": "和參考定格並排比色", "質感": "放大 200% 看顆粒和高光", "氛圍": "整鏡看完說得出同樣的感覺",
              "主體動作與表演": "看表演是否照寫", "剪輯節奏": "量每鏡秒數", "過場": "看過場中間那一格（S6-02）",
              "動態圖像": "逐格條看進場時長、緩動和錯開", "文字與字幕": "檢查安全區、行長、逐字時間", "聲音設計": "量響度並戴耳機和手機各聽一次（S7-09）",
              "材質描寫": "放大看材質反光", "風格": "抽三格對照它的六項特徵（線條、色彩、形狀、深度與光影、字體、動態），再和最容易混淆的那一種比一次"}


def num_text(x: dict, lead: str = "；") -> str:
    """A value's structured numbers as a short string, for shooting lists and review tables."""
    nums = {k: v for k, v in x.get("數值", {}).items() if k != "判準"}
    if not nums:
        return ""
    return lead + "（" * (lead == " ") + "、".join(f"{k} {'／'.join(map(str, v)) if isinstance(v, list) else v}" for k, v in nums.items()) + "）" * (lead == " ")


def as_list(x) -> list[str]:
    return [x] if isinstance(x, str) else list(x or [])


def spec_conf(V: dict) -> dict:
    """The card's shape. Production uses the built-in shot card; another book describes its own in vocab.json 「規格卡」."""
    c = V.get("規格卡")
    if not c:
        return {"清單": "鏡頭", "全域": "全片", "單位": "鏡", "欄位": SPEC_META, "單選": SPEC_SINGLE_DIMS, "內容": SPEC_CONTENT_DIMS}
    return {**c, "欄位": set(c.get("欄位", [])) | {"編號", "內容", "備註"}, "單選": set(c.get("單選", [])), "內容": set(c.get("內容", []))}


def spec_check(card: dict, V: dict) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    dims = V["維度"]
    C = spec_conf(V)
    meta = C["欄位"]
    def check_vals(where: str, d: dict):
        for k, val in d.items():
            if k in meta and k != "過場到下一鏡":
                continue
            dim = "過場" if k == "過場到下一鏡" else k
            if dim not in dims:
                errors.append(f"{where}：沒有「{k}」這個維度（`pb.py vocab` 看清單）")
                continue
            errors.extend(f"{where}：{dim}「{x}」不在語彙裡" for x in as_list(val) if x not in dims[dim])
    check_vals(C["全域"], card.get(C["全域"], {}))
    shots = card.get(C["清單"], [])
    for s in shots:
        check_vals(f"第 {s.get('編號', '?')} {C['單位']}", s)
        have = {f"{('過場' if k == '過場到下一鏡' else k)}={x}" for k, v in {**card.get(C["全域"], {}), **s}.items()
                if k not in meta or k == "過場到下一鏡" for x in as_list(v)}
        for c in V.get("衝突", []):
            if c["a"] in have and c["b"] in have:
                warns.append(f"第 {s.get('編號', '?')} {C['單位']}：{c['a']} 和 {c['b']} 衝突（{c['說明']}）")
    total = round(sum(float(s.get("秒數", 0)) for s in shots), 2)
    if card.get("片長") and abs(total - float(card["片長"])) > 0.2:
        errors.append(f"每鏡秒數加總 {total} 秒，和片長 {card['片長']} 秒不符")
    for s in [card, *shots]:
        if s.get("畫面類型") and s["畫面類型"] not in SHOT_KINDS:
            errors.append(f"畫面類型「{s['畫面類型']}」要是 {'、'.join(SHOT_KINDS)} 之一")
    tone = card.get("調性")
    if tone and tone not in V.get("調性預設", {}):
        errors.append(f"調性「{tone}」沒有預設規格")
    return errors, warns


def spec_fill(card: dict, V: dict) -> list[dict]:
    """Each shot's full spec: shot values first, then 全片, then the tone's presets (marked 預設)."""
    preset = V.get("調性預設", {}).get(card.get("調性", ""), {})
    C = spec_conf(V)
    out = []
    for s in card.get(C["清單"], []):
        full: dict[str, tuple[list[str], str]] = {}
        for k, v in s.items():
            if k not in C["欄位"]:
                full[k] = (as_list(v), "指定")
        if "過場到下一鏡" in s:
            full["過場"] = (as_list(s["過場到下一鏡"]), "指定")
        for k, v in card.get(C["全域"], {}).items():
            full.setdefault(k, (as_list(v), C["全域"]))
        last = s is card.get(C["清單"], [])[-1]
        kind = shot_kind(card, s)
        hints = {}
        for k, v in preset.items():
            if kind == "動態圖形" and k in CAMERA_DIMS:   # no camera or lights in screen graphics
                continue
            if k in C["內容"]:                  # depends on what the shot holds: suggest, never apply
                if k not in full:
                    hints[k] = as_list(v)
                continue
            if k == "過場" and last:
                continue
            full.setdefault(k, (as_list(v)[:1] if k in C["單選"] else as_list(v)[:2], "預設"))
        out.append({"shot": s, "full": full, "hints": hints, "kind": kind})
    return out


def shot_kind(card: dict, s: dict) -> str:
    return s.get("畫面類型") or card.get("畫面類型") or ""


def filled_conflicts(rows: list[dict], V: dict, unit: str) -> list[str]:
    """Conflicts that only appear once tone presets are filled in (spec_check already covers values written on the card)."""
    out = []
    for r in rows:
        have = {f"{d}={x}": src for d, (vals, src) in r["full"].items() for x in vals}
        for c in V.get("衝突", []):
            if c["a"] in have and c["b"] in have and "預設" in (have[c["a"]], have[c["b"]]):
                out.append(f"第 {r['shot'].get('編號', '?')} {unit}：{c['a']}（{have[c['a']]}）和 {c['b']}（{have[c['b']]}）衝突（{c['說明']}）")
    return out


def spec_render_generic(card: dict, V: dict) -> str:
    """A book's own card (vocab.json 「規格卡」): values shared by every unit print once, then each unit's own values,
    one section per writing style the card names, then the review table."""
    dims, C = V["維度"], spec_conf(V)
    rows = spec_fill(card, V)
    errors, warns = spec_check(card, V)
    warns += filled_conflicts(rows, V, C["單位"])
    order = list(dims)
    pairs = [{(d, x, src) for d, (vals, src) in r["full"].items() for x in vals} for r in rows]
    shared = set.intersection(*pairs) if pairs else set()
    def sort(items):
        return sorted(items, key=lambda t: (order.index(t[0]) if t[0] in order else 99, t[1]))
    out = [f"# 規格：{card.get('名稱') or card.get('頁面') or card.get('片名', '未命名')}", "",
           "｜".join(f"{k} {card[k]}" for k in C.get("表頭", []) if card.get(k)), ""]
    out += [f"警告：{w}" for w in warns] + ([""] if warns else [])
    for sec in C.get("輸出", []):
        out += [f"## {sec['標題']}", ""]
        if sec.get("說明"):
            out += [sec["說明"], ""]
        def emit(head, items):
            if sec.get("格式") == "段落":
                parts = [dims[d][x]["寫法"].get(sec["寫法"]) or dims[d][x]["英文"] for d, x, _ in items]
                out.append(head + ("\n  " + "; ".join(p for p in parts if p and p != "—") + "." if parts else ""))
            else:
                out.append(head)
                for d, x, src in items:
                    w = dims[d][x]["寫法"].get(sec["寫法"], "")
                    if w and w != "—":
                        out.append(f"  - {d}＝{x}（{src}）：{w}｜參數 {dims[d][x]['參數']}")
        if shared:
            emit(f"- 全部{C['單位']}共用", sort(shared))
        for r, own in zip(rows, pairs):
            s = r["shot"]
            emit(f"- {C['單位']} {s.get('編號')}「{s.get('名稱', '')}」" + (f"：{s['內容']}" if s.get("內容") else ""), sort(own - shared))
            if s.get("文案"):
                out.append(f"  - 文案：{s['文案']}")
            if s.get("備註"):
                out.append(f"  - 備註：{s['備註']}")
            if r.get("hints"):
                out.append("  - 可考慮（調性建議，沒自動套用）：" + "；".join(f"{k}＝{'、'.join(v)}" for k, v in r["hints"].items()))
        out.append("")
    out += ["## 審查對照表", "", f"| {C['單位']} | 維度 | 規格 | 來源 | 怎麼檢查 |", "|---|---|---|---|---|"]
    def rows_of(label, items):
        by = {}
        for d, x, src in sort(items):
            by.setdefault((d, src), []).append(x)
        return [f"| {label} | {d} | {'、'.join(xs)} | {src} | {C.get('審查', {}).get(d, '對照規格')} |" for (d, src), xs in by.items()]
    if shared:
        out += rows_of("全部", shared)
    for r, own in zip(rows, pairs):
        out += rows_of(str(r["shot"].get("編號")), own - shared)
    return "\n".join(out) + "\n"


def spec_render(card: dict, V: dict) -> str:
    dims = V["維度"]
    fps = float(card.get("格率", 30))
    errors, warns = spec_check(card, V)
    if errors:
        return "規格卡有錯，先修正：\n" + "\n".join(f"- {e}" for e in errors) + "\n"
    if V.get("規格卡"):
        return spec_render_generic(card, V)
    rows = spec_fill(card, V)
    kinds = sorted({r["kind"] for r in rows if r["kind"]})
    out = [f"# 規格：{card.get('片名', '未命名')}", "",
           f"畫幅 {card.get('畫幅', '—')}｜格率 {card.get('格率', 30)}｜片長 {card.get('片長', '—')} 秒｜調性 {card.get('調性', '—')}"
           + (f"｜畫面類型 {'、'.join(kinds)}" if kinds else ""), ""]
    warns += filled_conflicts(rows, V, "鏡")
    out += [f"警告：{w}" for w in warns] + ([""] if warns else [])
    def en(dim, vals):
        return [dims[dim][x]["寫法"]["AI 生成"] if dims[dim][x]["寫法"]["AI 生成"] not in ("", "—") else dims[dim][x]["英文"] for x in vals]
    out += ["## 一、AI 生成提示詞（英文，固定順序：景別→視角→運鏡→鏡頭→主體→構圖→布光→色彩→質感→氛圍）", ""]
    for r in rows:
        s, full = r["shot"], r["full"]
        if r["kind"] == "動態圖形":
            out.append(f"- 第 {s.get('編號')} 鏡：動態圖形，不用 AI 生成，看第二部分")
            continue
        parts = []
        for dim in PROMPT_ORDER:
            if dim == "主體":
                subj = s.get("英文描述") or s.get("內容", "")
                act = en("主體動作與表演", full["主體動作與表演"][0]) if "主體動作與表演" in full else []
                parts += [x for x in [subj, *act] if x]
            elif dim in full and dim in dims:
                parts += en(dim, full[dim][0])
        out.append(f"- 第 {s.get('編號')} 鏡（{s.get('秒數')} 秒）：{', '.join(parts)}.")
    out += ["", "負面描述（直接列不要的東西，不寫 no）：watermark, extra text, distorted hands, warped face, flicker", ""]
    out += ["## 二、程式動畫規格（HyperFrames／Remotion，照 S3-21 四段）", "",
            f"① 基本要求：{card.get('畫幅', '—')}、{int(fps)} fps；字型與色碼讀品牌設定，找不到就停下回報；先給每鏡關鍵格定格，核准後再輸出。", ""]
    frame = 0
    for r in rows:
        s, full = r["shot"], r["full"]
        n = round(float(s.get("秒數", 0)) * fps)
        out.append(f"- 第 {s.get('編號')} 鏡：第 {frame}–{frame + n - 1} 格（{n} 格）｜{s.get('內容', '')}")
        if s.get("台詞"):
            out.append(f"  - 台詞：{s['台詞']}")
        if s.get("備註"):
            out.append(f"  - 備註：{s['備註']}")
        if "文字與字幕" in full and "大字在頭後" in full["文字與字幕"][0]:
            out.append("  - 圖層：背景 → 大字 → 去背的人 → 字幕（S5-32）")
        for dim in ["風格"]:
            for x in full.get(dim, ([], ""))[0]:
                d = dims[dim][x]
                out.append(f"  - 風格＝{x}（{full[dim][1]}）：{d['寫法']['程式動畫']}")
                if d.get("特徵"):
                    out.append("    特徵：" + "；".join(f"{k} {v}" for k, v in d["特徵"].items()))
        for dim in ["運鏡", "動態圖像", "文字與字幕", "過場", "聲音設計", "色彩", "質感"]:
            if dim in full:
                for x in full[dim][0]:
                    d = dims[dim][x]
                    code = d["寫法"]["程式動畫"]
                    mp = (" " + " ".join(d["對應"])) if d["對應"] else ""
                    out.append(f"  - {dim}＝{x}（{full[dim][1]}）：{code if code not in ('', '—') else d['定義']}｜參數 {d['參數']}{mp}")
        if r.get("hints"):
            out.append("  - 可考慮（調性建議，沒自動套用）：" + "；".join(f"{k}＝{'、'.join(v)}" for k, v in r["hints"].items()))
        frame += n
    out += ["", "② 對時間：觸發點用逐字時間（S5-16，每個字對到音量起點）。③ 去背：需要時草稿用 u2net、定稿用 birefnet-portrait（T-13）。④ 做不好時，每次只改一個參數。", ""]
    out += ["## 三、實拍拍攝單（給負責人）", ""]
    if card.get("數值"):
        out += ["全片生效數值（場景或風格定的，優先於下面各值的通用範圍）：" + "、".join(f"{k} {v}" for k, v in card["數值"].items()), ""]
    for r in rows:
        s, full = r["shot"], r["full"]
        items = [f"{dim}：{x}（{dims[dim][x]['寫法']['實拍']}{num_text(dims[dim][x])}）" for dim in ["景別", "視角與機位", "運鏡", "鏡頭與攝影機", "構圖", "布光"]
                 if dim in full for x in full[dim][0] if dims[dim][x]["寫法"]["實拍"] not in ("", "—")]
        if r["kind"] in ("動態圖形", "AI 生成"):
            items = []
        out.append(f"- 第 {s.get('編號')} 鏡：" + ("；".join(items) or "無實拍需求（全程式或素材）"))
    out += ["", "## 四、審片對照表", "", "| 鏡 | 維度 | 規格 | 來源 | 怎麼檢查 |", "|---|---|---|---|---|"]
    for r in rows:
        for dim, (vals, src) in r["full"].items():
            spec = "、".join(x + num_text(dims[dim][x], " ") for x in vals)
            out.append(f"| {r['shot'].get('編號')} | {dim} | {spec} | {src} | {REVIEW_HOW.get(dim, '對照規格')} |")
    return "\n".join(out) + "\n"


GRAPHIC_FAMILIES = {"動漫", "插畫", "3D", "平面設計", "極簡", "粗獷", "質感擬物", "編輯排版", "科技", "有機柔和"}
PER_VALUE_KEYS = {"時長格", "時長秒", "對齊", "緩動", "間隔格", "位移%畫面高", "速度°每秒", "速度", "寬px", "項目數", "停留秒", "延遲ms", "位置", "鍵盤", "手機"}


def family_of(dim: dict, v: str) -> str:
    while dim.get(v, {}).get("上層"):
        v = dim[v]["上層"]
    return v


def spec_from(need: str, V: dict, work: dict | None = None) -> dict:
    """Draft a spec card from a need: values the need names (指定) > work order (作品單) > scene preset (場景) > tone preset (調性)
    > style (風格) > design attributes (設計屬性). Shared values land in this book's medium (圖片 when the need is a still image).
    A lower layer never overwrites a higher one; where it disagrees on a one-value dimension it is offered as an option."""
    F = facet_dict()
    low = need.lower()
    medium = "圖片" if "圖片" in media() and IMAGE_WORDS.search(need) else (media()[0] if media() else "")
    if medium and medium != (media() or [""])[0]:
        V = vocab(medium)
    dims, C = V["維度"], spec_conf(V)
    sug = suggest_ctx(need, F)
    if work:   # the work order's facets and design genes count as if the need had named them
        for f, vals in parse_ctx(work.get("情境", "")).items():
            sug.setdefault(f, set()).update(vals)
        for f, vals in work.get("設計基因", {}).items():
            sug.setdefault(f, set()).update(as_list(vals))
    if medium == "圖片":
        dims = {d: v for d, v in dims.items() if d not in MOTION_DIMS}
    given = {d: sorted(vs) for d, vs in sug.items() if d in dims and d != "風格" and d not in SHARED_DIMS}
    layers: list[tuple[str, dict, dict]] = [("指定" if not work else f"指定／{'策略卡' if work.get('編號') == '策略卡' else '作品單'}", given, {})]
    scenes = [k for k, sc in V.get("場景預設", {}).items() if any(term_in(w, low) for w in [k, *sc.get("同義詞", [])])]
    layers += [(f"場景：{k}", V["場景預設"][k]["預設"], V["場景預設"][k].get("數值", {})) for k in scenes]
    tones = [t for t in sorted(sug.get("調性", set())) if t in V.get("調性預設", {})]
    layers += [(f"調性：{t}", V["調性預設"][t], {}) for t in tones]
    sdim = "風格"
    styles = sorted(sug.get(sdim, set())) if sdim in dims else []
    layers += [(f"風格：{st}", {sdim: [st], **dims[sdim][st].get("預設", {})}, dims[sdim][st].get("數值", {})) for st in styles]
    attrs = [(d, v) for d in SHARED_DIMS for v in sorted(sug.get(d, set())) if d in dims and v in dims[d]]
    layers += [(f"設計屬性：{v}", {d: [v], **dims[d][v].get("預設", {})}, dims[d][v].get("數值", {})) for d, v in attrs]
    named = {d: list(dims[d])[:4] for d in dims if d != sdim and d not in SHARED_DIMS and term_in(d, low) and d not in layers[0][1]}
    if named:   # the need names a whole dimension ("要通過無障礙"): bring its first values
        layers.insert(1, ("指定（整個維度）", named, {}))
    chosen: dict[str, list[tuple[str, str]]] = {}      # dim → [(value, layer it came from)]
    hints: dict[str, list[str]] = {}
    options: list[str] = []
    for label, dmap, _ in layers:
        for d, vals in dmap.items():
            vals = as_list(vals)
            if d not in dims or not vals:
                continue
            if label.startswith("調性") and d in C["內容"]:
                hints.setdefault(d, [x for x in vals if x not in hints.get(d, [])])
                continue
            keep = vals[:1] if d in C["單選"] else vals[:4] if label == "指定（整個維度）" else vals[:2]
            have_d = [x for x, _ in chosen.get(d, [])]
            if not have_d:
                chosen[d] = [(x, label) for x in keep]
            elif not set(keep) & set(have_d):
                if d in C["單選"]:
                    options.append(f"{d}：{'、'.join(have_d)}（{chosen[d][0][1]}）或 {'、'.join(keep)}（{label}）")
                elif len(have_d) < 3:
                    chosen[d].append((keep[0], label))
    have = {f"{d}={x}" for d, pairs in chosen.items() for x, _ in pairs}
    warns = [f"{c['a']} 和 {c['b']} 衝突：{c['說明']}" for c in V.get("衝突", []) if c["a"] in have and c["b"] in have]
    numbers = [(f"{d}＝{x}", dims[d][x].get("數值", {}), src) for d, pairs in chosen.items() for x, src in pairs
               if dims[d][x].get("數值") and d != "風格" and d not in SHARED_DIMS]     # shared values already count as their own layer
    # one effective number per key: scene > style > the value's general range; disagreements are noted, not hidden
    effective: dict[str, tuple[str, str, list[str]]] = {}
    ranked = [(label, nums) for label, _, nums in layers if nums and label.startswith("場景")] + \
             [(label, nums) for label, _, nums in layers if nums and label.startswith(("風格", "設計屬性"))] + [(f"{n}", nums) for n, nums, _ in numbers]
    for label, nums in ranked:
        for k, v in nums.items():
            if k in ("判準", "說明", "畫面類型"):
                continue
            v = "／".join(map(str, v)) if isinstance(v, list) else str(v)
            if k in PER_VALUE_KEYS and "＝" in label:      # a duration or alignment belongs to its own value
                k = f"{k}（{label.split('＝', 1)[1]}）"
            if k not in effective:
                effective[k] = (v, label, [])
            elif v != effective[k][0]:
                effective[k][2].append(f"{label} 寫 {v}")
    kind = ""
    if styles and "影片" in media():
        fam = family_of(dims["風格"], styles[0])
        kind = ("AI 生成" if re.search(r"\bai\b|生成|生圖", low) else "動態圖形") if fam in GRAPHIC_FAMILIES else "實拍"
    if any(nums.get("畫面類型") for _, _, nums in layers):
        kind = next(nums["畫面類型"] for _, _, nums in layers if nums.get("畫面類型"))
    full = {d: [x for x, _ in pairs] if d not in C["單選"] else pairs[0][0] for d, pairs in chosen.items()}
    if V.get("規格卡"):
        card = {(C.get("表頭") or ["頁面"])[0]: need[:24], "調性": tones[0] if tones else "", C["全域"]: full,
                C["清單"]: [{"編號": 1, "名稱": "（第一個" + C["單位"] + "）", "內容": ""}, {"編號": 2, "名稱": "", "內容": ""}]}
    else:
        m = re.search(r"(\d+)\s*秒", need)
        length = int(m[1]) if m else 15
        n = 3 if length >= 9 else 1
        card = {"片名": need[:24], "畫幅": "直式 9:16" if re.search(r"reels|shorts|直式|tiktok|限動|9:16", low) else "16:9",
                "格率": 24 if any("24" in str(nums.get("格率", "")) for _, nums, _ in numbers) else 30, "片長": length,
                "調性": tones[0] if tones else "", **({"畫面類型": kind} if kind else {}),
                "全片": full,
                "鏡頭": [{"編號": i + 1, "秒數": round(length / n, 2) if i < n - 1 else round(length - round(length / n, 2) * (n - 1), 2),
                          "內容": "（這一鏡發生什麼）"} for i in range(n)]}
    card["數值"] = {k: v for k, (v, src, _) in effective.items() if src.startswith(("場景", "風格", "設計屬性"))}
    if medium == "圖片" and "鏡頭" in card:
        card["素材類型"] = "圖片"
    unit = C["單位"]
    return {"medium": medium, "unit": unit, "card": card, "chosen": chosen, "hints": hints, "options": options, "warns": warns, "numbers": numbers, "effective": effective,
            "scenes": scenes, "tones": tones, "styles": styles, "kind": kind, "attrs": [v for _, v in attrs]}


def spec_from_text(need: str, R: dict) -> str:
    def fmt(nums: dict) -> str:
        return "、".join(f"{k} {'／'.join(map(str, v)) if isinstance(v, list) else v}" for k, v in nums.items())
    out = [f"# 規格卡草稿：{need}", ""]
    out.append("推測：" + "；".join(x for x in [f"媒材 {R['medium']}" if R.get("medium") else "", f"場景 {'、'.join(R['scenes'])}" if R["scenes"] else "",
                                               f"調性 {'、'.join(R['tones'])}" if R["tones"] else "",
                                               f"風格 {'、'.join(R['styles'])}" if R["styles"] else "",
                                               f"設計屬性 {'、'.join(R['attrs'])}" if R.get("attrs") else "",
                                               f"畫面類型 {R['kind']}" if R["kind"] else ""] if x) if any(
        [R["scenes"], R["tones"], R["styles"], R["kind"]]) else "推測：沒有對到場景、調性或畫風；值只來自需求明寫的部分")
    out += ["", "| 維度 | 值（來源） |", "|---|---|"]
    out += [f"| {d} | {'、'.join(f'{x}（{src}）' for x, src in pairs)} |" for d, pairs in R["chosen"].items()]
    if R["effective"]:
        out += ["", "## 生效數值（製作和審查都照這些；場景＞風格＞語彙的通用範圍）", "", "| 參數 | 值 | 依據 | 其他層的說法 |", "|---|---|---|---|"]
        out += [f"| {k} | {v} | {src} | {'；'.join(alt) or '—'} |" for k, (v, src, alt) in R["effective"].items()]
    crit = [(n, nums["判準"]) for n, nums, _ in R["numbers"] if nums.get("判準")]
    if crit:
        out += ["", "沒有單一數字的值，照這些判準：" + "；".join(f"{n}：{c}" for n, c in crit)]
    if R["options"]:
        out += ["", "## 要選一個（兩層預設不一致，沒有自動覆蓋）", ""] + [f"- {o}" for o in R["options"]]
    if R["warns"]:
        out += ["", "## 衝突", ""] + [f"- {w}" for w in R["warns"]]
    if R["hints"]:
        out += ["", "可考慮（調性建議，沒自動套用）：" + "；".join(f"{k}＝{'、'.join(v)}" for k, v in R["hints"].items())]
    out += ["", f"下一步：把草稿存成卡片（加 `--out 卡.json`），補每一{R['unit']}的內容與要改的值，再跑 `pb.py spec 卡.json`。"]
    return "\n".join(out) + "\n"


def spec_template(V: dict) -> dict:
    if V.get("規格卡", {}).get("範本"):
        return V["規格卡"]["範本"]
    tone = next(iter(V.get("調性預設", {})), "")
    return {"片名": "（片名）", "畫幅": "直式 9:16", "格率": 30, "片長": 10, "調性": tone, "畫面類型": "實拍",
            "全片": {"色彩": [], "質感": []},
            "鏡頭": [{"編號": 1, "秒數": 5, "內容": "（這一鏡發生什麼）", "英文描述": "", "台詞": "", "景別": "", "運鏡": "", "過場到下一鏡": ""},
                     {"編號": 2, "秒數": 5, "內容": "", "景別": ""}]}


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
    ts = {t["id"]: t for t in tools()}
    tup = [i for i, c in by_entry.items() if i in ts and c["有效"] >= 2 and c["無效"] == 0 and ts[i]["狀態"] in ("待試", "待查")]
    tdown = [i for i, c in by_entry.items() if i in ts and c["無效"] >= 2 and ts[i]["狀態"] not in ("未採用", "避開")]
    if tup:
        out += ["## 建議把工具改成已安裝或已整合（實戰有效兩次以上）"] + [f"- {i} {ts[i]['工具']}：有效 {by_entry[i]['有效']} 次" for i in tup]
    if tdown:
        out += ["## 建議把工具改成未採用（實戰無效兩次以上）"] + [f"- {i} {ts[i]['工具']}：無效 {by_entry[i]['無效']} 次" for i in tdown]
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
    print(f"OK：{len(entries())} 條做法、{len(tools())} 個工具、{len(recipes())} 個配方、{len(sources())} 個來源、{len(runs())} 筆實戰紀錄")
    untagged = [r for r in entries() + tools() if r["情境"] == "" and r["狀態"] not in ("避開", "未採用")]
    if facet_dict()["分面"] and untagged:
        print(f"提醒：{len(untagged)} 個項目還沒標情境（`pb.py facets` 看各值的使用數）。")
    broad = audit_report(reach=False)["broad"] if facet_dict()["分面"] else []
    if broad:
        print(f"提醒：{len(broad)} 個標籤值太廣（{'、'.join(v for v, _ in broad)}），改標更具體的值；`pb.py facets --audit` 看完整健檢。")
    unused = unused_by_recipes()
    if recipes() and unused:
        print(f"提醒：{len(unused)} 個採用或待試的項目沒被任何配方用到（`pb.py plan --unused` 看清單）。")
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
        work = state.get("current") if state.get("current") in state["items"] else None
        if work:
            checked = set(state["items"][work]["checked"])
        print(brief(a.stage, a.type, checked, work) if stage_by_key(st, a.stage) else render_card(a.stage, a.type))
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
    print(brief(str(a.stage), a.type, set(), a.name))
    return 0


def cmd_status(a) -> int:
    state = load_state()
    if not state["items"]:
        print("這個專案沒有作品。用 `pb.py start <名稱> --type <類型>` 開一支。")
        return 0
    name, item = pick(state, a.name)
    print(status_text(name, item))
    print()
    print(brief(str(item["stage"]), item["type"], set(item["checked"]), name))
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
    print(brief(str(item["stage"]), item["type"], set(item["checked"]), name))
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
        print(f"交付完成。接著做第 {last['id']} 階段{last['name']}：`pb.py card {last['id']}`，再用 `pb.py run-log` 記下這支作品用過哪些條目和工具（做法代號、T- 工具代號都可以）、效果如何。")
        todo = [r["id"] for picked, _ in trial_pick(item["type"], name, set(item["checked"])).values() for r in picked]
        if todo:
            print("這支作品排定要測、還沒記結果的待試項目：" + "、".join(todo) + "。測過的用 run-log 記下；沒測到的不用記，會排到下一支。")
        logged = {i for r in runs() if r["作品"] == name for i in split(r["條目id"])}
        planned = [i for i in (item.get("plan") or {}).get("ids", []) if i not in logged]
        if planned:
            print("方案裡用過、還沒記結果的項目：" + "、".join(planned) + "。用過的記有效、無效或需調整；沒用到的不用記。")
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
    known = {r["id"] for r in entries()} | {t["id"] for t in tools()}
    bad = [i for i in ids if i not in known]
    if bad:
        sys.exit(f"不認得這些代號：{bad}")
    if a.result not in RESULTS:
        sys.exit(f"結果要是其中之一：{RESULTS}")
    state = load_state()
    name = BENCH_WORK if a.bench else (a.name or state.get("current") or "")
    kind = state["items"].get(name, {}).get("type", "")
    product = "bench" if a.bench else (a.product or project_dir().name)
    append_csv(DATA / "runs.csv", RUN_COLS, [{"日期": today(), "作品": name, "產品": product, "類型": kind,
                                               "條目id": ",".join(ids), "結果": a.result, "備註": a.note or ""}])
    print(f"記下了：{name}｜{','.join(ids)}｜{a.result}")
    return 0


def cmd_trials(a) -> int:
    state = load_state()
    if a.type and not a.name:
        work, asset, checked = "（預覽）", a.type, set()
    else:
        work, item = pick(state, a.name)
        asset, checked = item["type"], set(item["checked"])
    text = trials_text(work, asset, checked)
    print(text, end="")
    if a.save and work != "（預覽）":
        path = state_path().parent / f"trials-{slug(work)}.md"
        path.write_text(text, encoding="utf-8")
        print(f"\n存到 {path}")
    return 0


def cmd_plan(a) -> int:
    if a.unused:
        rows = unused_by_recipes()
        for r in sorted(rows, key=lambda r: (r["階段"], r["id"])):
            print(f"{r['id']}  {item_name(r)}{mark(r)}")
        print(f"共 {len(rows)} 項沒被配方用到。")
        return 0
    work = load_work(a.work) if a.work else None
    if work and not a.need:
        a.need = work["作品"]
    if not a.need:
        sys.exit("用法：pb.py plan \"<需求>\" [--type 類型] [--rules 規則檔] [--work W01] [--pick N --save]")
    if work and not a.facets:   # the work order's situation plus its design genes
        genes = {d: set(as_list(v)) for d, v in work.get("設計基因", {}).items()}
        a.facets = ctx_text({**suggest_ctx(a.need, facet_dict()), **parse_ctx(work.get("情境", "")), **genes})
        print(f"作品單 {work['編號']}（{work['堆疊']}，策略：{work['策略']}）\n")
    state = load_state()
    cur = state["items"].get(state.get("current") or "", {})
    asset = a.type or cur.get("type")
    res = plan_options(a.need, asset, load_rules(a.rules), a.facets)
    if getattr(a, "json", False):
        print(json.dumps({"options": [{"id": o["id"], "名稱": o["名稱"], "score": o["score"], "適用需求": o["適用需求"]} for o in res["options"]]},
                         ensure_ascii=False))
        return 0
    print(plan_text(res), end="")
    if a.save:
        if not res["options"]:
            sys.exit("沒有方案可以存。")
        n = a.pick or 1
        if not 1 <= n <= len(res["options"]):
            sys.exit(f"--pick 要在 1 到 {len(res['options'])} 之間")
        name, item = pick(state, a.name)
        o = res["options"][n - 1]
        ids = [r["id"] for r in o["items"]]
        item["plan"] = {"need": a.need, "recipe": o["id"], "ids": ids, "date": today()}
        event(item, f"plan {o['id']}")
        save_state(state)
        print(f"\n已把方案 {n}（{o['id']} {o['名稱']}，{len(ids)} 項）記進作品「{name}」。")
    return 0


def bench_text(group: str | None, stage: str | None, batch: int) -> str:
    logged = {i for r in runs() if r["作品"] == BENCH_WORK for i in split(r["條目id"])}
    rows = {r["id"]: r for r in entries() + tools()
            if r["狀態"] == "待試" and r.get("試法") == "桌上" and r["id"] not in logged}
    out = [f"# 桌上試驗（{today()}）", "",
           "> 用樣本素材測；記錄用 `pb.py run-log --bench --entries <代號> --result 有效|無效|需調整 --note \"<結果>\"`。"
           "同一組一次比完，只留一個。", ""]
    n = 0
    groups = {g: [i for i in ids if i in rows] for g, ids in bench_groups().items() if not group or group in g}
    for g, ids in groups.items():
        if not ids or n >= batch:
            continue
        out.append(f"## 比較組：{g}")
        for i in ids:
            out.append(f"- [ ] **{i}** {item_name(rows[i])}（{rows[i]['實用度']}）：{how(rows[i])}")
        out.append("")
        n += len(ids)
    if not group:
        in_group = {i for ids in bench_groups().values() for i in ids}
        singles = sorted((r for i, r in rows.items() if i not in in_group and (not stage or stage in split(r["階段"]))),
                         key=lambda r: (split(r["階段"])[0] if split(r["階段"]) else "z", rating_key(r)))
        if singles and n < batch:
            out.append("## 單項")
            for r in singles[: batch - n]:
                out.append(f"- [ ] **{r['id']}** {item_name(r)}（{r['實用度']}）：{how(r)}")
                n += 1
            out.append("")
    left = len(rows) - n
    out.append(f"這一批 {n} 項；桌上可測的還有 {left} 項沒排到。")
    return "\n".join(out) + "\n"


def cmd_bench(a) -> int:
    print(bench_text(a.group, a.stage, a.batch), end="")
    return 0


LIVE = ("已內建", "採用", "待試", "已整合", "已安裝")
BROAD_SHARE = 0.15


def facet_tree_dupes(ctx: dict[str, set[str]], F: dict) -> list[str]:
    """Values tagged together with one of their ancestors (the ancestor adds nothing)."""
    out = []
    for f, vals in ctx.items():
        tree = F["分面"].get(f, {})
        for v in vals:
            p = tree.get(v, {}).get("上層")
            while p:
                if p in vals:
                    out.append(f"{f}={p} 和 {v}")
                p = tree.get(p, {}).get("上層")
    return out


def audit_report(F: dict | None = None, reach: bool = True) -> dict:
    """Tag health: coverage, too-broad values, values a need can't trigger, and items that tags alone can't call up."""
    F = F or facet_dict()
    live = [r for r in entries() + tools() if r["狀態"] in LIVE] + [r for r in recipes() if r["id"] != BASE_RECIPE]
    used: Counter = Counter()
    no_work, dupes, untagged, selfc = [], [], [], []
    for r in live:
        ctx = parse_ctx(r["情境"])
        if not ctx:
            untagged.append(r["id"])
        elif "工作項目" in F["分面"] and "工作項目" not in ctx:
            no_work.append(r["id"])
        dupes += [f"{r['id']}：{d}" for d in facet_tree_dupes(ctx, F)]
        why = conflict(r, ctx, F)
        if why:
            selfc.append(f"{r['id']}：自己的標籤互相衝突（{why}）")
        for f, vs in ctx.items():
            for v in vs:
                used[(f, v)] += 1
    n = max(1, len(live))
    broad = [(f"{f}={v}", c) for (f, v), c in used.most_common() if c / n > BROAD_SHARE and c > 12]   # more than two screens of extras
    deaf = []
    for (f, v) in used:
        hit = suggest_ctx(v, F).get(f, set())
        if not (expand(f, {v}, F) & hit):
            deaf.append(f"{f}={v}")
    unreachable = []
    base = set(split(next((rc["項目"] for rc in recipes() if rc["id"] == BASE_RECIPE), "")))   # applied to every plan
    if reach:
        for r in live:
            if r["id"].startswith("R-") or not r["情境"] or r["id"] in base:
                continue
            res = plan_options("", facets=ctx_text(parse_ctx(r["情境"])))
            shown = {x["id"] for o in res["options"] for x in o["items"] + o["extras"]}
            if r["id"] not in shown:
                unreachable.append(r["id"])
    tagged = [r for r in live if r["情境"]]
    return {"live": len(live), "tagged": len(tagged), "untagged": untagged, "no_work": no_work, "dupes": dupes, "selfc": selfc,
            "avg": round(sum(len(parse_ctx(r["情境"])) for r in tagged) / max(1, len(tagged)), 2),
            "broad": broad, "deaf": sorted(deaf), "unreachable": unreachable,
            "reach_rate": round(1 - len(unreachable) / max(1, len([r for r in tagged if not r["id"].startswith("R-") and r["id"] not in base])), 3)}


def cmd_facets(a) -> int:
    F = facet_dict()
    if a.audit:
        A = audit_report(F)
        print(f"在用項目 {A['live']}，已標 {A['tagged']}，平均 {A['avg']} 個分面")
        print(f"可調用率（只用自己的標籤當需求，有沒有出現在方案裡；{BASE_RECIPE} 的項目每次都套用，不計）：{A['reach_rate']:.0%}")
        for title, xs in (("沒標情境", A["untagged"]), ("缺工作項目", A["no_work"]), ("上層和下層一起標", A["dupes"]), ("標籤自相衝突", A["selfc"]),
                          ("過廣的值（超過 15% 且超過 12 項共用）", [f"{v}（{c}）" for v, c in A["broad"]]),
                          ("需求寫了名稱或同義詞也推不出來的值", A["deaf"]), ("叫不出來的項目", A["unreachable"])):
            print(f"\n{title}：{len(xs)}" + ("\n- " + "\n- ".join(xs) if xs else ""))
        return 0
    if a.suggest:
        print(ctx_text(suggest_ctx(a.suggest, F)) or "（沒有對到任何分面值）")
        return 0
    rows = entries() + tools()
    used: Counter = Counter()
    for r in rows:
        for f, vs in parse_ctx(r["情境"]).items():
            for v in vs:
                used[(f, v)] += 1
    for facet, vals in F["分面"].items():
        print(f"{facet}：" + "、".join(f"{v}（{used[(facet, v)]}）" + (f"⊂{m['上層']}" if m.get("上層") else "") for v, m in vals.items()))
    tagged = sum(1 for r in rows if r["情境"])
    print(f"\n已標情境 {tagged}/{len(rows)} 項；括號是標了這個值的項目數。")
    return 0


def terms_table(dim: str, vals: dict) -> list[str]:
    out = [f"## {dim}", "", "| 中文 | 英文 | 簡中 | 其他說法 | 參照 |", "|---|---|---|---|---|"]
    for k, x in vals.items():
        t = x.get("用語", {})
        out.append(f"| {k} | {'、'.join(t.get('英文', []) or [x.get('英文', '')])} | {t.get('簡中', '')} | {'、'.join(t.get('其他說法', []))} | "
                   f"{'、'.join(x.get('對應', []))} |")
    return out + [""]


def cmd_vocab(a) -> int:
    V = vocab()
    if not V["維度"]:
        print("這本手冊沒有製作語彙（data/vocab.json）。")
        return 0
    if a.terms:
        dims = list(V["維度"]) if (a.all or not a.dim) else [a.dim]
        missing = [d for d in dims if d not in V["維度"]]
        if missing:
            sys.exit(f"沒有「{missing[0]}」；有：{'、'.join(V['維度'])}")
        text = "\n".join(["# 用語對照表（" + NAME + "）", "", "英文、簡中和其他說法都會被當成同義詞：需求用哪一種寫法，都叫得出同一個值。", ""]
                         + [line for d in dims for line in terms_table(d, V["維度"][d])])
        if a.out:
            Path(a.out).expanduser().write_text(text + "\n", encoding="utf-8")
            print(f"已寫到 {a.out}（{len(dims)} 個維度）")
        else:
            print(text)
        return 0
    if a.tone:
        p = V.get("調性預設", {}).get(a.tone)
        if not p:
            sys.exit(f"沒有「{a.tone}」的預設；有：{'、'.join(V.get('調性預設', {}))}")
        for dim, vals in p.items():
            print(f"{dim}：{'、'.join(vals)}")
        return 0
    if not a.dim:
        for dim, vals in V["維度"].items():
            print(f"{dim}（{len(vals)}）：{'、'.join(vals)}")
        print(f"\n看某一維：pb.py vocab {next(iter(V['維度']))}；看調性預設：pb.py vocab --tone {next(iter(V.get('調性預設', {})), '安靜高級')}")
        return 0
    vals = V["維度"].get(a.dim)
    if not vals:
        sys.exit(f"沒有「{a.dim}」；有：{'、'.join(V['維度'])}")
    for k, x in vals.items():
        mp = (" " + " ".join(x["對應"])) if x["對應"] else ""
        up = f"（屬於 {x['上層']}）" if x.get("上層") else ""
        print(f"{k}{up}｜{x['英文']}｜{x['定義']}｜效果：{x['效果']}｜參數：{x['參數']}{mp}")
        if x.get("數值"):
            print("  數值：" + "、".join(f"{a} {b if not isinstance(b, list) else '／'.join(map(str, b))}" for a, b in x["數值"].items()))
        if x.get("易混淆"):
            print(f"  最容易混淆：{x['易混淆']}")
    return 0


def cmd_spec(a) -> int:
    V = vocab()
    if not V["維度"]:
        sys.exit("這本手冊沒有製作語彙（data/vocab.json）。")
    if a.template:
        print(json.dumps(spec_template(V), ensure_ascii=False, indent=1))
        return 0
    if a.need or a.work:
        work = load_work(a.work) if a.work else None
        need = a.need or work["作品"]
        note = f"作品單 {work['編號']}（策略：{work['策略']}）" if work else ""
        if not work:   # called on its own: reuse the project's strategy card when there is one, else ask at most three questions
            c = strategy_card()
            if c:
                ctx = {k: set(c[k]) for k in ("受眾", "調性") if c.get(k)}
                work = {"情境": ctx_text(ctx), "設計基因": c.get("設計基因", {}), "編號": "策略卡"}
                note = f"沿用策略卡（{c['目的']}）：受眾、調性和設計基因照策略卡"
        R = spec_from(need, V, work)
        if note:
            print(note + "\n")
        print(spec_from_text(need, R), end="")
        if not work:
            known = suggest_ctx(need, facet_dict())
            for d, pairs in R.get("chosen", {}).items():
                known.setdefault(d, {x for x, _ in pairs})
            rt = rounds_text(*question_rounds(need, known, "spec", question_recs(known, None, R)))
            if rt:
                print("\n沒有策略卡，這一輪先問（分輪；上面的草稿先照預設）：\n" + "\n".join(rt))
        if a.out:
            Path(a.out).expanduser().write_text(json.dumps(R["card"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"已寫出規格卡草稿 {a.out}")
        return 0
    if not a.card:
        sys.exit("用法：pb.py spec <規格卡.json> [--out 檔案]；空白範本：pb.py spec --template")
    card = json.loads(Path(a.card).expanduser().read_text(encoding="utf-8"))
    text = spec_render(card, V)
    if a.out:
        Path(a.out).expanduser().write_text(text, encoding="utf-8")
        print(f"已寫到 {a.out}")
    else:
        print(text, end="")
    return 1 if text.startswith("規格卡有錯") else 0


def cmd_probe(a) -> int:
    """Raw footage → inventory and draft spec card; reference video → breakdown card. Only books that ship bin/video_probe.py."""
    tool = DATA.parent / "bin" / "video_probe.py"
    if not tool.is_file():
        sys.exit("這本手冊沒有影片量測工具（bin/video_probe.py 在 production-playbook）。")
    if not a.args:
        sys.exit("用法：pb.py probe footage <毛片> [--asr-python <有 faster-whisper 的 python>] [--lang zh] [--out 資料夾]\n"
                 "      pb.py probe breakdown <參考片> [--out 資料夾]；填好拆解卡後 pb.py probe breakdown --to-spec <拆解卡>")
    return subprocess.call([sys.executable, str(tool), *a.args])


# ---------------------------------------------------------------- strategy → work orders (all books read <project>/.strategy/)
BOOK_OF_MEDIUM = {"影片": "production-playbook", "圖片": "production-playbook", "網站": "web-playbook", "文案": "marketing-playbook", "程式": "engineering-playbook"}
HORIZON = ("短期", "中期", "長期")


def strategy_dir() -> Path:
    start = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
    for d in (start, *start.parents):
        if (d / ".strategy" / "策略卡.json").is_file():
            return d / ".strategy"
    return start / ".strategy"


def strategy_card() -> dict | None:
    p = strategy_dir() / "策略卡.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def strategy_from(goal: str) -> dict:
    """A strategy card draft: goal and KPI, audience, platform roles, a short/mid/long content stack and the design genes.
    Only what the goal states or the shared rules give; anything else becomes a question."""
    S, F = shared(), facet_dict()
    rules = S.get("策略", {})
    ctx = suggest_ctx(goal, F)
    purposes = sorted(ctx.get("目的", set())) or []
    platforms = sorted(ctx.get("平台", set()))
    tones = sorted(ctx.get("調性", set()))
    kpi = re.findall(r"\d[\d,]*\s*(?:筆|位|人|個|%|萬|元|次|則|支|篇)[^，。；,;]*", goal)
    period = re.findall(r"[一二三四五六七八九十\d]+\s*(?:個月|週|周|天|季|年)", goal)
    now, later = question_rounds(goal, ctx, "strategy", question_recs(ctx))
    questions = [f"Q{i}｜{n['id']}：{n['問']}｜建議：{n['建議'] or '沒有建議，這要你決定'}" for i, n in enumerate(now, 1)]
    if later:
        questions.append("下一輪（等上面的答案）：" + "、".join(n["id"] for n in later))
    stack: dict[str, list[dict]] = {h: [] for h in HORIZON}
    for pur in purposes or []:
        for h in HORIZON:
            for item in rules.get("目的堆疊", {}).get(pur, {}).get(h, []):
                if platforms and item["平台"] not in platforms and not any(expand("平台", {pl}, F) & {item["平台"]} for pl in platforms) \
                        and item["平台"] not in ("網站", "Email"):
                    continue
                if item not in stack[h]:
                    stack[h].append({**item, "目的": pur})
    used_platforms = sorted({i["平台"] for h in HORIZON for i in stack[h]} | set(platforms))
    roles = {pl: rules.get("平台角色", {}).get(pl, {"角色": "（請補：這個平台負責漏斗哪一段）"}) for pl in used_platforms}
    genes: dict[str, list[str]] = {}
    for t in tones:
        g = rules.get("調性設計基因", {}).get(t, {})
        for st in g.get("風格", []):
            genes.setdefault("風格", []).append(st)
        for d, vs in g.get("設計屬性", {}).items():
            genes.setdefault(d, [])
            genes[d] += [v for v in vs if v not in genes[d]]
    for d in SHARED_DIMS + ("風格",):
        if ctx.get(d):
            genes[d] = sorted(ctx[d])
    cites = {}
    for h in HORIZON:
        for item in stack[h]:
            res = plan_options(item["形式"], facets=ctx_text({"平台": {item["平台"]}, "目的": {item["目的"]}}))
            if res["options"] and res["options"][0]["id"] != "自組":
                cites[item["形式"]] = res["options"][0]["id"]
    return {"目的": goal, "目的分面": purposes, "指標": kpi, "期限": period, "受眾": sorted(ctx.get("受眾", set())),
            "產業": sorted(ctx.get("產業", set())), "調性": tones, "平台角色": roles, "內容堆疊": stack, "設計基因": genes,
            "代號": cites, "待補問題": questions, "規則檔": "", "建立日": dt.date.today().isoformat(), "手冊": NAME}


def strategy_text(c: dict) -> str:
    out = [f"# 策略卡草稿：{c['目的']}", ""]
    out.append(f"目的：{'、'.join(c['目的分面']) or '（待補）'}｜指標：{'；'.join(c['指標']) or '（待補）'}｜期限：{'、'.join(c['期限']) or '（待補）'}")
    out.append(f"受眾：{'、'.join(c['受眾']) or '（待補）'}｜產業：{'、'.join(c['產業']) or '—'}｜調性：{'、'.join(c['調性']) or '（待補）'}")
    out += ["", "## 平台角色", ""] + [f"- {pl}：{r.get('角色')}（漏斗 {'、'.join(r.get('漏斗', [])) or '—'}）" for pl, r in c["平台角色"].items()]
    out += ["", "## 內容堆疊", ""]
    for h in HORIZON:
        items = c["內容堆疊"].get(h, [])
        out.append(f"- {h}：" + ("；".join(f"{i['形式']}（{i['平台']}，{i['媒材']}→{i['手冊']}手冊{'，' + c['代號'][i['形式']] if i['形式'] in c['代號'] else ''}）" for i in items) or "（待補）"))
    out += ["", "## 設計基因（所有媒材共用）", ""]
    out += [f"- {d}：{'、'.join(v)}" for d, v in c["設計基因"].items()] or ["- （待補：先定調性，或直接指定風格）"]
    if c["待補問題"]:
        out += ["", "## 這一輪要問（分輪；沒有答案前不編，答「是」就照建議）", ""] + [f"- {q}" for q in c["待補問題"]]
    out += ["", "下一步：存成策略卡（`--save`），再用 `pb.py strategy --works` 拆成作品單。"]
    return "\n".join(out) + "\n"


def works_from(c: dict) -> list[dict]:
    out = []
    n = 0
    for h in HORIZON:
        for i in c["內容堆疊"].get(h, []):
            n += 1
            ctx = {"目的": {i["目的"]}, "平台": {i["平台"]}, "篇幅": {i["篇幅"]}}
            if c.get("受眾"):
                ctx["受眾"] = set(c["受眾"])
            if c.get("調性"):
                ctx["調性"] = set(c["調性"])
            book = BOOK_OF_MEDIUM.get(i["媒材"], "")
            out.append({"編號": f"W{n:02d}", "作品": i["形式"], "堆疊": h, "媒材": i["媒材"], "手冊": book, "平台": i["平台"],
                        "情境": ctx_text(ctx), "設計基因": c.get("設計基因", {}), "策略": c["目的"],
                        "下一步": f"在 {book} 跑 `pb.py plan \"{i['形式']}\" --work W{n:02d}`，再 `pb.py spec --from \"{i['形式']}\" --work W{n:02d}`"
                        if book in ("production-playbook", "web-playbook") else f"在 {book} 跑 `pb.py plan \"{i['形式']}\" --work W{n:02d}`"})
    return out


def load_work(ref: str) -> dict:
    p = Path(ref)
    if not p.is_file():
        p = strategy_dir() / "作品單" / f"{ref}.json"
    if not p.is_file():
        sys.exit(f"找不到作品單 {ref}（先跑 `pb.py strategy --works`）")
    return json.loads(p.read_text(encoding="utf-8"))


def cmd_strategy(a) -> int:
    if a.works:
        c = strategy_card()
        if not c:
            sys.exit("還沒有策略卡：先跑 `pb.py strategy --from \"<目的>\" --save`。")
        W = works_from(c)
        d = strategy_dir() / "作品單"
        d.mkdir(parents=True, exist_ok=True)
        for w in W:
            (d / f"{w['編號']}.json").write_text(json.dumps(w, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"- {w['編號']}｜{w['堆疊']}｜{w['作品']}｜{w['媒材']} → {w['手冊']}｜{w['下一步']}")
        print(f"\n已寫出 {len(W)} 張作品單到 {d}")
        return 0
    if not a.goal:
        c = strategy_card()
        print(strategy_text(c) if c else "還沒有策略卡。用法：pb.py strategy --from \"<目的，含期限與數字>\" [--save]")
        return 0
    c = strategy_from(a.goal)
    print(strategy_text(c), end="")
    if a.save:
        d = strategy_dir()
        d.mkdir(parents=True, exist_ok=True)
        (d / "策略卡.json").write_text(json.dumps(c, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        (d / "策略卡.md").write_text(strategy_text(c), encoding="utf-8")
        print(f"已存到 {d / '策略卡.json'}")
    return 0


def cmd_style(a) -> int:
    """One style across media: features, design attributes, numbers and how it lands in video, image and web; plus this book's items."""
    S, F = shared(), facet_dict()
    if not a.name:
        fams = [k for k, x in S["風格"].items() if not x.get("上層")]
        for f in fams:
            print(f"{f}：" + "、".join(k for k, x in S["風格"].items() if x.get("上層") == f))
        return 0
    name = a.name if a.name in S["風格"] else next(iter(suggest_ctx(a.name, F).get("風格", [])), None)
    if not name:
        sys.exit(f"沒有「{a.name}」這個風格；`pb.py style` 列出全部")
    x = S["風格"][name]
    tagged = [r for r in entries() + tools() if r["狀態"] in LIVE and expand("風格", {name}, F) & parse_ctx(r["情境"]).get("風格", set())]
    if a.items:
        print(f"{NAME}：" + ("、".join(f"{r['id']} {item_name(r)}" for r in tagged) or "沒有標這個風格的項目"))
        return 0
    print(f"# 風格：{name}" + (f"（屬於 {x['上層']}）" if x.get("上層") else "") + f"｜{x['英文']}\n\n{x.get('定義', '')}")
    if x.get("特徵"):
        print("\n## 共用特徵\n\n" + "\n".join(f"- {k}：{v}" for k, v in x["特徵"].items()))
    if x.get("設計屬性"):
        print("\n## 設計屬性（共用數值）\n")
        for d, vs in x["設計屬性"].items():
            for v in vs:
                nums = S["設計屬性"][d][v].get("數值", {})
                print(f"- {d}＝{v}：" + "、".join(f"{k} {'／'.join(map(str, n)) if isinstance(n, list) else n}" for k, n in nums.items()))
    if x.get("數值"):
        print("\n風格本身的數值：" + "、".join(f"{k} {'／'.join(map(str, n)) if isinstance(n, list) else n}" for k, n in x["數值"].items()))
    print("\n## 各媒材怎麼落地\n")
    for m in ("影片", "圖片", "網站"):
        vals = landing(x, m)
        how = x.get("落地", {}).get(m, {}).get("寫法", {})
        src = "自有落地" if x.get("落地", {}).get(m) else "由設計屬性推出"
        print(f"- {m}（{src}）：" + ("；".join(f"{d}＝{'、'.join(v)}" for d, v in vals.items()) or "—"))
        for k, w in how.items():
            if w and w != "—":
                print(f"  - {k}：{w}")
    if x.get("易混淆"):
        print(f"\n最容易混淆：{x['易混淆']}")
    if x.get("專有名稱"):
        print(f"專有名稱只當檢索詞，提示詞不要寫：{'、'.join(x['專有名稱'])}")
    print(f"\n本書標了這個風格的項目：" + ("、".join(r["id"] for r in tagged) or "沒有"))
    return 0


# ---------------------------------------------------------------- blueprint: one production / development plan from a need
SIBLINGS = ("production-playbook", "marketing-playbook", "web-playbook", "engineering-playbook")
BOOK_ZH = {"production-playbook": "影片", "marketing-playbook": "行銷", "web-playbook": "網站", "engineering-playbook": "開發"}


def sibling_options(need: str, facets: str | None) -> list[tuple[str, dict]]:
    """Other books' best recipe for the same need (their own engine and data, via the paths saved by `setup`)."""
    out = []
    for book in SIBLINGS:
        if book == NAME:
            continue
        f = Path.home() / ".config" / book / "home"
        home = Path(f.read_text().strip()) if f.is_file() else None
        if not home or not (home / "pb.py").is_file():
            continue
        args = [sys.executable, str(home / "pb.py"), "plan", need, "--json"] + (["--facets", facets] if facets else [])
        env = {k: v for k, v in os.environ.items() if k != CONF["home_env"]}
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=60, env=env, cwd=home)
            opts = json.loads(r.stdout or "{}").get("options", [])
        except Exception:
            continue
        if opts and opts[0]["id"] not in ("自組", BASE_RECIPE) and opts[0]["score"] >= 0.3:
            out.append((book, opts[0]))
    return out


# ---------------------------------------------------------------- questions in rounds (S49 grilling): ask only what is unblocked
def question_tree(use: str) -> list[dict]:
    p = DATA / "facets.json"
    own = json.loads(p.read_text(encoding="utf-8")).get("提問樹") if p.is_file() else None
    tree = (own or shared().get("提問樹", {})).get("節點", [])
    return [n for n in tree if use in n.get("用在", [use])]


def question_rounds(need: str, ctx: dict[str, set[str]], use: str, recs: dict[str, str] | None = None) -> tuple[list[dict], list[dict]]:
    """(this round, later). A node is settled when the need or its facets already answer it; this round holds the unsettled
    nodes whose prerequisites are all settled, each with a recommended answer the user can accept with 是."""
    tree = question_tree(use)
    low = need.lower()
    def settled(n: dict) -> bool:
        if n.get("分面") and (ctx.get(n["分面"]) or (n.get("或") and ctx.get(n["或"]))):
            return True
        return any(w.lower() in low for w in n.get("文字", []))
    done = {n["id"] for n in tree if settled(n)}
    open_ = [n for n in tree if n["id"] not in done]
    now = [n for n in open_ if all(p in done for p in n.get("前提", []))]
    later = [n for n in open_ if n not in now]
    out = []
    for n in now:
        rec = None if n.get("不給建議") else (recs or {}).get(n["id"])
        out.append({**n, "建議": rec})
    return out, later


def rounds_text(now: list[dict], later: list[dict]) -> list[str]:
    if not now:
        return []
    out = []
    for i, n in enumerate(now, 1):
        out.append(f"❓ Q{i}｜{n['id']}：{n['問']}")
        out.append(f"   ➡️ " + (f"建議：{n['建議']}" if n.get("建議") else "沒有建議，這要你決定（不會替你編）"))
    out.append("答「是」就照建議；不同就直接寫答案。把答案加進需求再跑一次，會算出下一輪。")
    if later:
        out.append("下一輪（等上面的答案）：" + "、".join(n["id"] for n in later))
    return out


def question_recs(ctx: dict[str, set[str]], chosen: dict | None = None, spec: dict | None = None) -> dict[str, str]:
    """Recommended answers: the chosen recipe's own tags, the spec draft's values, tone relations, platform specs."""
    F, S = facet_dict(), shared()
    recs: dict[str, str] = {}
    rctx = parse_ctx(next((rc["情境"] for rc in recipes() if chosen and rc["id"] == chosen.get("id")), "")) if chosen else {}
    for f, vals in rctx.items():
        if vals:
            recs[f] = "、".join(sorted(vals)) + f"（推薦配方 {chosen['id']} 的設定）"
    if spec:
        for d, pairs in spec.get("chosen", {}).items():
            recs.setdefault(d, "、".join(x for x, _ in pairs) + f"（{pairs[0][1]}）")
    tones, _ = tone_advice(ctx, F)
    if tones:
        best = sorted(tones.items(), key=lambda x: -len(x[1]))[0]
        recs.setdefault("調性", f"{best[0]}（依 {'、'.join(best[1])}）")
    for p in sorted(ctx.get("平台", set())):
        spec_p = S.get("平台規格", {}).get(p, {})
        if spec_p.get("長度") or spec_p.get("尺寸"):
            recs.setdefault("篇幅", f"{spec_p.get('長度') or spec_p.get('尺寸')}（{p} 的慣例）")
    for g in sorted(ctx.get("目的", set())):
        if g in S.get("提問樹", {}).get("指標建議", {}):
            recs.setdefault("指標", S["提問樹"]["指標建議"][g] + "；數字和期限由你定")
    V = vocab()
    for d in ("工作類型", "驗收方式", "風險等級"):
        if recs.get(d) is None and spec and d in spec.get("chosen", {}):
            recs[d] = "、".join(x for x, _ in spec["chosen"][d])
    if spec and "工作類型" in spec.get("chosen", {}):
        t = spec["chosen"]["工作類型"][0][0]
        recs.setdefault("風險等級", "有硬停止（agent、MCP、hook 會動到外部或權限）" if t in ("agent", "MCP", "hook")
                        else "可還原；但只要會寄信或發訊息、安裝套件、碰密鑰、刪資料或動正式環境，就算硬停止")
        how = V["維度"].get("工作類型", {}).get(t, {}).get("寫法", {}).get("驗收")
        if how:
            recs["完成的定義"] = how
    return recs


def B_need(need: str) -> str:
    return need.split("；指標 ")[0]


def blueprint(need: str, work: dict | None = None, pick_n: int = 1, rules: list[str] | None = None) -> dict:
    F = facet_dict()
    card = strategy_card()
    source = "需求"
    ctx = suggest_ctx(need, F)
    if work:
        ctx = {**ctx, **parse_ctx(work.get("情境", ""))}
        for d, v in work.get("設計基因", {}).items():
            ctx[d] = set(as_list(v))
        source = f"作品單 {work.get('編號', '')}"
    elif card:
        for k in ("受眾", "調性"):
            if card.get(k) and k not in ctx:
                ctx[k] = set(card[k])
        for d, v in card.get("設計基因", {}).items():
            ctx.setdefault(d, set(as_list(v)))
        source = "需求＋沿用策略卡"
    facets = ctx_text(ctx) if ctx else None
    res = plan_options(need, None, rules or [], facets)
    opts = [o for o in res["options"] if o["id"] != "自組"] or res["options"]
    chosen = opts[min(max(pick_n, 1), len(opts)) - 1] if opts else None
    V = vocab()
    spec = spec_from(need, V, work or ({"情境": ctx_text({k: v for k, v in ctx.items() if k in ("受眾", "調性")}), "設計基因": card.get("設計基因", {}), "編號": "策略卡"} if card else None)) if V["維度"] else None
    known = dict(ctx)
    for d, pairs in (spec or {}).get("chosen", {}).items():
        known.setdefault(d, {x for x, _ in pairs})
    if card and card.get("指標"):
        need = need + "；指標 " + "、".join(card["指標"])
    now, later = question_rounds(need, known, "blueprint", question_recs(ctx, chosen, spec))
    return {"need": B_need(need), "source": source, "ctx": ctx, "rounds": (now, later), "res": res, "chosen": chosen, "opts": opts, "spec": spec,
            "siblings": sibling_options(need, facets), "card": card, "work": work}


def blueprint_text(B: dict) -> str:
    st, rows = stages(), {r["id"]: r for r in entries() + tools()}
    S = shared()
    o, res = B["chosen"], B["res"]
    out = [f"# 計畫書：{B['need']}", "", f"手冊：{NAME}｜依據：{B['source']}｜日期：{today()}", ""]
    # 1
    out += ["## 1. 需求與情境", "", f"- 分面：{ctx_text(B['ctx']) or '（沒有推測到分面）'}"]
    rt = rounds_text(*B["rounds"])
    if rt:
        out += ["", "**這一輪要問（分輪：只問前提都已確定的）**", ""] + rt
    out.append("")
    # 2
    out += ["## 2. 推薦方案", ""]
    if o:
        out.append(f"- **{o['id']} {o['名稱']}**（符合度 {o['score']:.2f}）：{o['適用需求']}" + (f"｜不適用：{o['不適用']}" if o.get("不適用") else ""))
        out += [f"- 備選：{x['id']} {x['名稱']}（{x['score']:.2f}）" for x in B["opts"] if x is not o][:2]
    else:
        out.append("- 沒有對應的配方：照階段卡從頭走（`pb.py card 0`），並考慮新增配方。")
    out.append("")
    # 3
    out += ["## 3. 交付物與規格", ""]
    plats = [p for p in sorted(B["ctx"].get("平台", set())) if p in S.get("平台規格", {})]
    for p in plats:
        out.append(f"- {p}：" + "；".join(f"{k} {v}" for k, v in S["平台規格"][p].items()))
    if B["ctx"].get("篇幅"):
        out.append(f"- 篇幅：{'、'.join(sorted(B['ctx']['篇幅']))}")
    R = B["spec"]
    if R:
        bits = ([f"媒材 {R['medium']}"] if R.get("medium") else []) + ([f"風格 {'、'.join(R['styles'])}"] if R.get("styles") else [])
        out.append("- 規格（`spec --from`）：" + ("；".join(bits) or "依本書規格卡"))
        for k, (v, src, alt) in list(R["effective"].items())[:12]:
            out.append(f"  - {k}：{v}（{src}）")
        for x in R["options"]:
            out.append(f"  - 要選：{x}")
        out.append("  - 完整規格：`pb.py spec --from \"<需求>\"" + (f" --work {B['work']['編號']}" if B.get("work") else "") + " --out 卡.json`，補內容後 `pb.py spec 卡.json`")
    if not plats and not R:
        out.append("- （這本沒有數值規格；交付物依推薦方案的第 0 階段定）")
    out.append("")
    # 4
    out += ["## 4. 逐階段步驟", ""]
    base = next((rc for rc in recipes() if rc["id"] == BASE_RECIPE), None)
    base_ids = split(base["項目"]) if base else []
    mine = [r for r in (o["items"] if o else [])] + [r for r in (o["extras"] if o else [])]
    for s in st["stages"]:
        k = str(s["id"])
        own = [r for r in mine if (split(r["階段"]) or [""])[0] == k]
        b = [rows[i] for i in base_ids if i in rows and (split(rows[i]["階段"]) or [""])[0] == k]
        line = "；".join(f"{r['id']} {item_name(r)[:26]}{mark(r)}" for r in own) or ("照底座 " + BASE_RECIPE + "：" + "；".join(f"{r['id']} {item_name(r)[:20]}" for r in b[:4]) if b else "照階段卡做")
        out.append(f"- **{s['id']} {s['name']}**：{s.get('purpose', '')}")
        out.append("  - 步驟：" + "／".join(f"{x['id']} {x['name']}" for x in s.get("steps", [])))
        out.append(f"  - 項目：{line}")
        if s.get("gates"):
            out.append("  - 過關：" + "；".join(f"{g['id']} {g['text']}" for g in s["gates"]))
    out.append("")
    # 5
    approve = [r for r in mine + [rows[i] for i in base_ids if i in rows]
               if "需要人核准" in r.get("情境", "") or "核准" in (r.get("要點") or "")]
    out += ["## 5. 要負責人提供的與核准點", ""]
    out += [f"- {r['id']} {item_name(r)[:40]}" for r in {r['id']: r for r in approve}.values()][:8] or ["- 第 0 階段過關前，請負責人確認目的、範圍和素材來源"]
    if B["rounds"][0]:
        out.append("- 回答第 1 節這一輪的問題（答「是」就照建議）")
    out.append("")
    # 6
    out += ["## 6. 這件作品順便測的待試項目", ""]
    ids = {r["id"] for r in mine}
    picked = [r for k, (p, _) in trial_pick(None, "blueprint", set()).items() for r in p if r["id"] in ids]
    pending = [r for r in mine if r["狀態"] == "待試" and r.get("試法") == "實戰" and r not in picked]
    for r in (picked + pending)[:6]:
        out.append(f"- {r['id']} {item_name(r)[:30]}：{(r.get('測試方法') or '照條目的測試方法')[:120]}")
    if not picked and not pending:
        out.append("- 這個方案沒有實戰待試項目")
    out.append("")
    # 7
    out += ["## 7. 風險", ""]
    risks = [f"排除：{r['id']} {item_name(r)[:20]}（{k}）" for r, k in res.get("excluded", [])]
    risks += [f"提醒：{w}" for w in res.get("warns", [])]
    if R:
        risks += [f"規格衝突：{w}" for w in R.get("warns", [])]
        if R.get("medium") == "圖片":
            risks.append("靜態圖：不帶運鏡、過場")
    if o and o.get("不適用"):
        risks.append(f"不適用情況：{o['不適用']}")
    out += [f"- {x}" for x in risks] or ["- 沒有偵測到衝突或排除項"]
    out.append("")
    # 8
    out += ["## 8. 跨本交接", ""]
    out += [f"- {BOOK_ZH.get(b, b)}手冊 {x['id']} {x['名稱']}（符合度 {x['score']:.2f}）：`playbook plan {BOOK_ZH.get(b, b)} \"{B['need']}\"`"
            for b, x in B["siblings"]] or ["- 其他手冊沒有符合度 ≥ 0.3 的配方"]
    out.append("")
    # 9
    out += ["## 9. 成效與回顧", ""]
    c = B.get("card")
    out.append(f"- 指標：{'；'.join(c['指標'])}（策略卡）" if c and c.get("指標") else "- 指標：（待補：這件作品用什麼數字算成功）")
    out.append("- 完成時：`pb.py done` 列出方案裡還沒記結果的項目，用 `pb.py run-log` 記有效、無效或需調整")
    return "\n".join(out) + "\n"


def cmd_blueprint(a) -> int:
    work = load_work(a.work) if a.work else None
    need = a.need or (work["作品"] if work else None)
    if not need:
        sys.exit("用法：pb.py blueprint \"<需求>\" [--work W01] [--pick N] [--rules 規則檔] [--save]")
    B = blueprint(need, work, a.pick or 1, load_rules(a.rules))
    text = blueprint_text(B)
    print(text, end="")
    if a.save:
        d = strategy_dir() / "計畫"
        d.mkdir(parents=True, exist_ok=True)
        name = (work["編號"] + "-" if work else "") + re.sub(r"[\\/:*?\"<>|\s]+", "_", need)[:40]
        (d / f"{name}.md").write_text(text, encoding="utf-8")
        print(f"\n已存到 {d / (name + '.md')}")
        if B["chosen"] and B["chosen"]["id"] != "自組":
            import contextlib, io
            ns = argparse.Namespace(unused=False, need=need, type=None, rules=a.rules, pick=(B["opts"].index(B["chosen"]) + 1), save=True,
                                    name=None, facets=ctx_text(B["ctx"]) or None, work=None, json=False)
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    cmd_plan(ns)
                print(f"也已把 {B['chosen']['id']} 記進目前的作品（`card --brief` 會先列方案項目）。")
            except SystemExit:
                print(f"還沒有進行中的作品，所以只存了計畫書；`pb.py start <名稱>` 開案後再跑一次 `--save` 就會記進作品。")
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
    p.add_argument("--bench", action="store_true", help="a 桌上 test with the sample kit, not a real piece of work")
    p.set_defaults(fn=cmd_run_log)
    p = sub.add_parser("plan")
    p.add_argument("need", nargs="?")
    p.add_argument("--type")
    p.add_argument("--rules", help="a project's rule file: one excluded keyword per line")
    p.add_argument("--pick", type=int)
    p.add_argument("--save", action="store_true")
    p.add_argument("--name")
    p.add_argument("--unused", action="store_true", help="list live items no recipe uses")
    p.add_argument("--facets", help="the need as facets: 目的=名單；調性=安靜高級 (default: guessed from the text)")
    p.add_argument("--work", help="a work order from `strategy --works` (W01 or a path): its facets and design genes become the need")
    p.add_argument("--json", action="store_true", help="print the options as JSON (used by blueprint across books)")
    p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("blueprint", help="a full production / development plan from a need or a work order")
    p.add_argument("need", nargs="?")
    p.add_argument("--work")
    p.add_argument("--pick", type=int)
    p.add_argument("--rules")
    p.add_argument("--save", action="store_true")
    p.set_defaults(fn=cmd_blueprint)
    p = sub.add_parser("vocab")
    p.add_argument("dim", nargs="?")
    p.add_argument("--tone")
    p.add_argument("--terms", action="store_true", help="the 中文／英文／簡中／其他說法 table")
    p.add_argument("--all", action="store_true")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_vocab)
    p = sub.add_parser("spec")
    p.add_argument("card", nargs="?")
    p.add_argument("--out")
    p.add_argument("--template", action="store_true")
    p.add_argument("--from", dest="need", help="draft a spec card from a need: scene, tone and style presets with their numbers")
    p.add_argument("--work", help="a work order from `strategy --works` (W01 or a path)")
    p.set_defaults(fn=cmd_spec)
    p = sub.add_parser("style", help="one shared style across video, image and web")
    p.add_argument("name", nargs="?")
    p.add_argument("--items", action="store_true", help="only list this book's items tagged with the style")
    p.set_defaults(fn=cmd_style)
    p = sub.add_parser("strategy", help="goal → strategy card → work orders for each book")
    p.add_argument("--from", dest="goal")
    p.add_argument("--save", action="store_true")
    p.add_argument("--works", action="store_true")
    p.set_defaults(fn=cmd_strategy)
    p = sub.add_parser("probe", help="measure raw footage (footage) or break down a reference video (breakdown)")
    p.add_argument("args", nargs=argparse.REMAINDER)
    p.set_defaults(fn=cmd_probe)
    p = sub.add_parser("facets")
    p.add_argument("--suggest", help="guess the facets of a need from its words")
    p.add_argument("--audit", action="store_true", help="tag health: coverage, broad values, deaf values, unreachable items")
    p.set_defaults(fn=cmd_facets)
    p = sub.add_parser("bench")
    p.add_argument("--group")
    p.add_argument("--stage")
    p.add_argument("--batch", type=int, default=12)
    p.set_defaults(fn=cmd_bench)
    sub.add_parser("review").set_defaults(fn=cmd_review)
    p = sub.add_parser("trials")
    p.add_argument("--name")
    p.add_argument("--type", help="preview for a type without an open piece of work")
    p.add_argument("--save", action="store_true")
    p.set_defaults(fn=cmd_trials)
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
