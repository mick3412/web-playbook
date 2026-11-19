#!/usr/bin/env python3
"""Reference-site teardown (參考網站拆解) and rebuild comparison.

  teardown.py <url> [--out DIR] [--pages URL ...] [--no-tools] [--only a,b]
      capture  4 widths full-page + first screen; computed styles, fonts, grids, effects, animations (one browser pass)
      tools    designlang, dembrandt (+ webanalyze, siteone-crawler, SingleFile when installed); missing tools are listed, never fatal
      measure  spacing unit and scale, type ratio, whitespace, colour areas (60-30-10), grids, effects → measure.json
      report   summary.md: what was measured, by what, and what could not be measured
  teardown.py compare <teardown DIR> <url> [--out DIR]
      the same capture and measure on the rebuild, then pixel, SSIM per region and system-measure deltas → compare.json

Rules (widths, tools, thresholds, DESIGN.md chapters, limits) live in data/teardown_rules.json.
Only for learning a reference: structure, rhythm and system are borrowed; copy, images, logos and font files are not.
"""
from __future__ import annotations
import argparse, json, re, shutil, statistics, subprocess, sys, time, datetime as dt
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RULES = json.loads((REPO / "data" / "teardown_rules.json").read_text(encoding="utf-8"))
VENDOR = Path.home() / "Dev Projects" / "playbook-bench" / "web" / "vendor"

PROBE = r"""
() => {
  const px = v => { const n = parseFloat(v); return isNaN(n) ? null : Math.round(n * 10) / 10; };
  const els = [...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; }).slice(0, 6000);
  const spacing = [], fonts = [], radii = [], colors = [], grids = [], effects = Counter(), trans = [];
  function Counter() { const m = {}; return { add: k => m[k] = (m[k] || 0) + 1, out: () => m }; }
  for (const e of els) {
    const s = getComputedStyle(e);
    for (const k of ['marginTop', 'marginBottom', 'paddingTop', 'paddingBottom', 'paddingLeft', 'paddingRight', 'rowGap', 'columnGap']) { const v = px(s[k]); if (v && v > 0 && v < 400) spacing.push(v); }
    const hasText = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1);
    if (hasText) fonts.push({ size: px(s.fontSize), lh: s.lineHeight === 'normal' ? null : px(s.lineHeight), weight: +s.fontWeight, family: s.fontFamily.split(',')[0].replace(/["']/g, '').trim(), ls: s.letterSpacing, tag: e.tagName.toLowerCase(), chars: e.textContent.trim().length });
    const r = px(s.borderTopLeftRadius); if (r) radii.push(r);
    if (hasText) colors.push(s.color);
    if (s.backgroundColor && s.backgroundColor !== 'rgba(0, 0, 0, 0)') colors.push(s.backgroundColor);
    if (s.display === 'grid' && s.gridTemplateColumns !== 'none') grids.push(s.gridTemplateColumns.split(' ').length);
    if (s.backdropFilter && s.backdropFilter !== 'none') effects.add('backdrop-filter');
    if (s.filter && s.filter !== 'none') effects.add('filter');
    if (s.mixBlendMode && s.mixBlendMode !== 'normal') effects.add('mix-blend-mode');
    if (s.maskImage && s.maskImage !== 'none' || s.webkitMaskImage && s.webkitMaskImage !== 'none') effects.add('mask');
    if (/gradient/.test(s.backgroundImage)) effects.add(/conic|radial/.test(s.backgroundImage) ? 'radial/conic gradient' : 'linear gradient');
    if (s.fontVariationSettings && s.fontVariationSettings !== 'normal') effects.add('variable font axes');
    if (s.transitionDuration && s.transitionDuration !== '0s') trans.push({ d: s.transitionDuration.split(',')[0], ease: s.transitionTimingFunction.split(',')[0], prop: s.transitionProperty.split(',')[0] });
    if (s.position === 'sticky') effects.add('sticky');
    for (const ps of ['::before', '::after']) { const q = getComputedStyle(e, ps); if (q.content === 'none' || q.content === 'normal') continue;   // glows and grain often live on pseudo elements
      if (/gradient/.test(q.backgroundImage)) effects.add(/conic|radial/.test(q.backgroundImage) ? 'radial/conic gradient' : 'linear gradient');
      if (q.backdropFilter && q.backdropFilter !== 'none') effects.add('backdrop-filter'); if (q.filter && q.filter !== 'none') effects.add('filter');
      if (q.mixBlendMode && q.mixBlendMode !== 'normal') effects.add('mix-blend-mode'); if (q.maskImage && q.maskImage !== 'none') effects.add('mask'); }
  }
  const canv = [...document.querySelectorAll('canvas')]; if (canv.length) effects.add('canvas×' + canv.length);
  if (window.THREE || [...document.scripts].some(s => /three(\.min)?\.js|webgl|ogl|pixi/i.test(s.src))) effects.add('WebGL library');
  if (document.querySelector('video')) effects.add('video');
  const anims = document.getAnimations().slice(0, 300).map(a => { const t = a.effect && a.effect.getTiming ? a.effect.getTiming() : {}; let kf = []; try { kf = a.effect.getKeyframes().map(k => Object.keys(k).filter(x => !['offset', 'easing', 'composite', 'computedOffset'].includes(x))).flat(); } catch (e) {}
    return { kind: a.constructor.name, name: a.animationName || a.transitionProperty || '', duration: t.duration, delay: t.delay, easing: t.easing, iterations: t.iterations, props: [...new Set(kf)].slice(0, 6), target: a.effect && a.effect.target ? (a.effect.target.tagName || '').toLowerCase() + (a.effect.target.className && typeof a.effect.target.className === 'string' ? '.' + a.effect.target.className.split(' ')[0] : '') : '' }; });
  let gsap = null;
  if (window.gsap) { try { gsap = { version: window.gsap.version, tweens: window.gsap.globalTimeline.getChildren(true, true, false).slice(0, 200).map(t => ({ duration: t.duration(), delay: t.delay(), ease: t.vars && String(t.vars.ease || ''), props: Object.keys(t.vars || {}).filter(k => !['ease', 'duration', 'delay', 'onComplete', 'scrollTrigger', 'stagger'].includes(k)).slice(0, 6), stagger: t.vars && t.vars.stagger || null })),
      triggers: window.ScrollTrigger ? window.ScrollTrigger.getAll().slice(0, 100).map(s => ({ start: s.vars && String(s.vars.start || ''), end: s.vars && String(s.vars.end || ''), scrub: s.vars && s.vars.scrub || false, pin: !!(s.vars && s.vars.pin) })) : [] }; } catch (e) { gsap = { error: String(e) }; } }
  const faces = [...document.fonts].filter(f => f.status === 'loaded').map(f => ({ family: f.family.replace(/["']/g, ''), weight: f.weight, style: f.style }));
  const libs = { gsap: !!window.gsap, lenis: !!(window.Lenis || window.lenis), framer: !!document.querySelector('[data-framer-component-type],[data-projection-id]'), three: !!window.THREE, react: !!document.querySelector('[data-reactroot],#__next,#root'), next: !!window.__NEXT_DATA__ || !!document.querySelector('#__next') };
  const W = document.documentElement.clientWidth;
  const maxw = [...document.querySelectorAll('body *')].slice(0, 3000).map(e => getComputedStyle(e).maxWidth).filter(v => v.endsWith('px')).map(px).filter(v => v > 400 && v < 2400);
  return { title: document.title, lang: document.documentElement.lang, width: W, height: document.documentElement.scrollHeight, bg: getComputedStyle(document.body).backgroundColor,
           spacing, fonts, radii, colors, grids, effects: effects.out(), transitions: trans.slice(0, 400), animations: anims, gsap, faces, libs, maxWidths: maxw };
}
"""


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- capture (one browser, every width)
def capture(url: str, out: Path) -> dict:
    from playwright.sync_api import sync_playwright
    shots, raw = {}, None
    (out / "shots").mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        for w in RULES["寬度"]:
            pg = b.new_page(viewport={"width": w, "height": 900 if w > 800 else 812}, device_scale_factor=1)
            pg.goto(url, wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(RULES["等待毫秒"])
            pg.screenshot(path=str(out / "shots" / f"w{w}_fold.png"))
            if w == RULES["量測寬度"]:
                raw = pg.evaluate(PROBE)           # entrance animations are still listed before any scroll
            h = pg.evaluate("document.documentElement.scrollHeight")
            for y in range(0, min(h, 20000), 600):   # scroll through so lazy content and scroll animations fire
                pg.evaluate(f"window.scrollTo(0, {y})")
                pg.wait_for_timeout(120)
            if w == RULES["量測寬度"]:
                after = pg.evaluate("() => document.getAnimations().length")
                raw["animations_after_scroll"] = after
            pg.evaluate("window.scrollTo(0, 0)")
            pg.wait_for_timeout(500)
            pg.screenshot(path=str(out / "shots" / f"w{w}_full.png"), full_page=True)
            shots[w] = {"fold": f"shots/w{w}_fold.png", "full": f"shots/w{w}_full.png", "高": h}
            pg.close()
        b.close()
    raw["shots"] = shots
    (out / "raw.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return raw


# ---------------------------------------------------------------- external tools (each optional, never fatal)
def run_tools(url: str, out: Path, only: set | None) -> dict:
    res = {}
    for name, t in RULES["外部工具"].items():
        if only and name not in only:
            continue
        cmd = [c.replace("{url}", url).replace("{out}", str(out)).replace("{vendor}", str(VENDOR)) for c in t["指令"]]
        exe = cmd[0]
        if exe not in ("npx",) and not (shutil.which(exe) or Path(exe).is_file()):
            res[name] = {"狀態": "沒裝", "用途": t["用途"]}
            continue
        d = out / "tools" / name
        d.mkdir(parents=True, exist_ok=True)
        (out / "site").mkdir(exist_ok=True)
        (out / "freeze").mkdir(exist_ok=True)
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=t["秒"])
            (d / "log.txt").write_text((r.stdout or "")[-20000:] + "\n---\n" + (r.stderr or "")[-5000:], encoding="utf-8")
            if name == "webanalyze" and r.stdout.strip():
                (d / "tech.json").write_text(r.stdout, encoding="utf-8")
            res[name] = {"狀態": "完成" if r.returncode == 0 else f"失敗 rc={r.returncode}", "秒": round(time.time() - t0), "用途": t["用途"]}
        except subprocess.TimeoutExpired:
            res[name] = {"狀態": f"逾時（{t['秒']} 秒）", "用途": t["用途"]}
        log(f"  {name}：{res[name]['狀態']}")
    return res


# ---------------------------------------------------------------- measure
def rgb(s: str):
    m = re.findall(r"[\d.]+", s or "")
    return tuple(int(float(x)) for x in m[:3]) if len(m) >= 3 else None


def spacing_system(vals: list[float]) -> dict:
    v = [round(x) for x in vals if x >= 4]          # 1–3 px are hairlines and icon nudges, not the spacing system
    if not v:
        return {"級距": None, "說明": "量不到間距"}
    share = {u: round(sum(1 for x in v if x % u == 0) / len(v), 3) for u in RULES["量測"]["間距級距候選"]}
    unit = max((u for u, s in share.items() if s >= RULES["量測"]["間距級距門檻"]), default=None)
    top = [k for k, _ in Counter(v).most_common(12)]
    off = sorted({x for x in v if unit and x % unit}) if unit else []
    return {"級距": unit, "各級距符合率": share, "常用值": sorted(top), "不在級距上": {"占比": round(1 - share.get(unit, 0), 2) if unit else None, "值": off[:12]}, "樣本數": len(v)}


def type_scale(fonts: list[dict]) -> dict:
    """Body = the size most characters are set in; the scale = distinct steps from body to the largest heading.
    A modular-scale fit is not used: with many close steps any small ratio fits, which says nothing."""
    import math
    by_chars = Counter()
    for f in fonts:
        if f.get("size"):
            by_chars[round(f["size"])] += min(f.get("chars", 1), 400)
    if not by_chars:
        return {"說明": "量不到字級"}
    body = by_chars.most_common(1)[0][0]
    sizes = sorted({round(f["size"]) for f in fonts if f.get("size") and round(f["size"]) >= body})
    steps = []
    for x in sizes:                       # merge sizes within 6 % (rendering noise and one-offs)
        if not steps or x / steps[-1] > 1.06:
            steps.append(x)
    ratios = [round(b / a, 3) for a, b in zip(steps, steps[1:])]
    top = steps[-1]
    fam = Counter()
    for f in fonts:
        if f.get("family"):
            fam[f["family"]] += min(f.get("chars", 1), 400)
    lh = [f["lh"] / f["size"] for f in fonts if f.get("lh") and f.get("size") and round(f["size"]) == body]
    heads = sorted({round(f["size"]) for f in fonts if f.get("tag") in ("h1", "h2", "h3")}, reverse=True)[:4]
    near = min(RULES["量測"]["字級比例候選"].items(), key=lambda kv: abs(kv[1] - statistics.median(ratios))) if ratios else ("—", 0)
    return {"內文字級": body, "字級階（≥內文）": steps, "相鄰比例": ratios, "相鄰比例中位數": round(statistics.median(ratios), 3) if ratios else None,
            "最接近的音程": near[0], "內文到最大": round(top / body, 2), "階數": len(steps), "標題字級": heads,
            "字體（依字數）": [{"字體": k, "占比": round(n / sum(fam.values()), 2)} for k, n in fam.most_common(4)],
            "內文行高倍數": round(statistics.median(lh), 2) if lh else None}


def image_metrics(path: Path, bg: tuple | None) -> dict:
    from PIL import Image
    im = Image.open(path).convert("RGB")
    small = im.resize((max(1, im.width // 4), max(1, im.height // 4)))
    px = list(small.getdata())
    if not bg:
        bg = Counter(px).most_common(1)[0][0]
    tol = RULES["量測"]["背景容差"]
    near = sum(1 for p in px if all(abs(p[i] - bg[i]) <= tol for i in range(3)))
    q = small.quantize(colors=RULES["量測"]["色彩數"], method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: RULES["量測"]["色彩數"] * 3]
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(n for n, _ in counts)
    merged: list[list] = []                      # [rgb, share]; shades closer than 24 (RGB distance) are one colour role
    for n, i in counts:
        c = tuple(pal[i * 3:i * 3 + 3])
        hit = next((m for m in merged if sum((c[k] - m[0][k]) ** 2 for k in range(3)) ** 0.5 < 24), None)
        if hit:
            hit[1] += n
        else:
            merged.append([c, n])
    merged.sort(key=lambda m: -m[1])
    areas = [{"色": "#%02x%02x%02x" % m[0], "占比": round(m[1] / total, 3)} for m in merged]
    return {"留白比例": round(near / len(px), 3), "底色": "#%02x%02x%02x" % bg, "色彩面積": areas,
            "60-30-10": [round(sum(a["占比"] for a in areas[:1]), 2), round(sum(a["占比"] for a in areas[1:3]), 2), round(sum(a["占比"] for a in areas[3:]), 2)]}


def measure(raw: dict, out: Path) -> dict:
    W = RULES["量測寬度"]
    bg = rgb(raw.get("bg", ""))
    if bg == (0, 0, 0) and "rgba(0, 0, 0, 0)" in raw.get("bg", ""):
        bg = None
    shot = raw["shots"].get(W) or raw["shots"].get(str(W))    # keys turn into strings once raw.json is reloaded
    fold = image_metrics(out / shot["fold"], bg)
    full = image_metrics(out / shot["full"], bg)
    tr = Counter((t["d"], t["ease"]) for t in raw.get("transitions", []))
    anims = raw.get("animations", [])
    m = {
        "網址": raw.get("url"), "量測寬度": W, "頁高": raw.get("height"), "標題": raw.get("title"),
        "間距": spacing_system(raw.get("spacing", [])),
        "字": type_scale(raw.get("fonts", [])),
        "圓角": [k for k, _ in Counter(round(r) for r in raw.get("radii", [])).most_common(6)],
        "首屏": fold, "全頁": full,
        "版面": {"網格欄數": dict(Counter(raw.get("grids", [])).most_common(6)), "內容最大寬": [k for k, _ in Counter(round(v) for v in raw.get("maxWidths", [])).most_common(4)]},
        "特效": raw.get("effects", {}),
        "動態": {
            "轉場（常見）": [{"時長": d, "緩動": e, "次數": n} for (d, e), n in tr.most_common(6)],
            "動畫數（載入時）": len(anims), "動畫數（捲動後）": raw.get("animations_after_scroll"),
            "動畫樣本": anims[:20], "GSAP": raw.get("gsap"), "函式庫": raw.get("libs"),
            "說明": "CSS／WAAPI 動畫與 GSAP 讀得到；requestAnimationFrame、canvas、WebGL 動畫讀不到，要錄影逐格（animation-reverse-engineering）",
        },
        "字型檔": raw.get("faces", [])[:20],
    }
    (out / "measure.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return m


# ---------------------------------------------------------------- tool outputs, condensed for cross-checking
def tool_summary(out: Path) -> dict:
    """What the tools say, condensed for the cross-check against our own measurements."""
    s = {}
    dl = list((out / "tools" / "designlang").rglob("*-design-tokens.json"))
    if dl:
        try:
            p = json.loads(dl[0].read_text(encoding="utf-8")).get("primitive", {})
            val = lambda d: [v.get("$value") for v in d.values() if isinstance(v, dict)]
            s["designlang"] = {"間距": val(p.get("spacing", {})), "字級": val(p.get("fontSize", {})), "圓角": val(p.get("radius", {})),
                               "字體": val(p.get("fontFamily", {}))[:4], "檔": str(dl[0].relative_to(out))}
        except Exception as e:  # noqa: BLE001
            s["designlang"] = {"錯誤": str(e)}
    db = list((out / "tools" / "dembrandt").rglob("*.tokens.json"))
    if db:
        s["dembrandt"] = {"檔": str(db[0].relative_to(out))}
    tech = out / "tools" / "webanalyze" / "tech.json"
    if tech.is_file():
        try:
            names = []
            for line in tech.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("{"):
                    names += [f"{m['app_name']}（{'、'.join(m['app'].get('category_names') or [])}）" for m in json.loads(line).get("matches", [])]
            s["技術棧"] = sorted(set(names))
        except Exception as e:  # noqa: BLE001
            s["技術棧錯誤"] = str(e)
    return s


def cross_check(m: dict, ts: dict) -> list[str]:
    """Our measurements against designlang's tokens: agreement is evidence, disagreement is listed, never silently picked."""
    out = []
    dl = ts.get("designlang", {})
    if dl.get("間距"):
        px = [int(float(str(v).rstrip("px"))) for v in dl["間距"] if str(v).rstrip("px").replace(".", "").isdigit()]
        unit = m["間距"].get("級距")
        ok = bool(px) and unit and all(v % unit == 0 for v in px)
        out.append(f"間距：量到級距 {unit}，designlang {px} → {'一致' if ok else '不一致，DESIGN.md 寫明採哪個與原因'}")
    if dl.get("字級"):
        theirs = sorted({int(float(str(v).rstrip("px"))) for v in dl["字級"] if str(v).rstrip("px").replace(".", "").isdigit()})
        ours = m["字"].get("字級階（≥內文）", [])
        common = [x for x in ours if any(abs(x - t) <= 1 for t in theirs)]
        out.append(f"字級：量到 {ours}，designlang {theirs} → 重疊 {len(common)}/{len(ours)}")
    return out


def report(url: str, out: Path, m: dict, tools: dict, ts: dict) -> Path:
    sp, ty, fo, fu = m["間距"], m["字"], m["首屏"], m["全頁"]
    lines = [f"# 拆解：{m.get('標題') or url}", "", f"網址：{url}｜日期：{dt.date.today()}｜量測寬度 {m['量測寬度']}px｜頁高 {m['頁高']}px", "",
             "只供內部學習：借結構、節奏、系統；文案、圖片、商標、字體檔不帶走。這份資料只在本機。", "",
             "## 量到的（teardown 量測，DESIGN.md 標「量」）", "",
             f"- 間距級距：{sp.get('級距') or '看不出單一級距'}（符合率 {sp.get('各級距符合率')}）；常用值 {sp.get('常用值')}；不在級距上 {sp.get('不在級距上')}",
             f"- 字級：內文 {ty.get('內文字級')}px（依字數）；階 {ty.get('字級階（≥內文）')}，相鄰比例中位數 {ty.get('相鄰比例中位數')}（近 {ty.get('最接近的音程')}）；內文到最大 ×{ty.get('內文到最大')}；標題 {ty.get('標題字級')}；內文行高 ×{ty.get('內文行高倍數')}",
             f"- 字體（依字數）：{', '.join(f['字體'] + ' ' + str(f['占比']) for f in ty.get('字體（依字數）', []))}",
             f"- 圓角常用：{m['圓角']}",
             f"- 留白比例：首屏 {fo['留白比例']}、全頁 {fu['留白比例']}（底色 {fu['底色']}）",
             f"- 色彩面積（全頁）60-30-10 實際：{fu['60-30-10']}；前 4 色 {[a['色'] + ' ' + str(a['占比']) for a in fu['色彩面積'][:4]]}",
             f"- 版面：網格欄數 {m['版面']['網格欄數']}；內容最大寬 {m['版面']['內容最大寬']}",
             f"- 特效：{m['特效'] or '無'}",
             f"- 動態：載入時 {m['動態']['動畫數（載入時）']} 個動畫、捲動後 {m['動態']['動畫數（捲動後）']} 個；常見轉場 {[(t['時長'], t['緩動']) for t in m['動態']['轉場（常見）'][:3]]}；GSAP {'有' if m['動態']['GSAP'] else '無'}；函式庫 {[k for k, v in (m['動態']['函式庫'] or {}).items() if v]}",
             "", "## 外部工具（DESIGN.md 標「工具」）", ""]
    lines += [f"- {k}：{v['狀態']}｜{v['用途']}" for k, v in tools.items()]
    if ts.get("技術棧"):
        lines += ["", "技術棧：" + "、".join(ts["技術棧"])]
    xc = cross_check(m, ts)
    if xc:
        lines += ["", "## 交叉驗證（我們量的 vs 工具給的）", ""] + [f"- {x}" for x in xc]
    lines += ["", "## 量不到（要看截圖或錄影，DESIGN.md 標「目測」）", "",
              "- 氛圍、品牌感、視覺重心：看 shots/ 的首屏與全頁截圖",
              "- requestAnimationFrame、canvas、WebGL 動畫：錄影後用 animation-reverse-engineering 逐格",
              "- 互動狀態細節（hover、focus）：designlang 的 form-states 與 motion 檔",
              "", "## 下一步", "",
              "1. 照 data/teardown_rules.json「DESIGN.md」的章節寫 DESIGN.md：每個值標出處（量／工具／目測），Don't 段列禁用的預設美學。",
              "2. `npx -y @google/design.md lint DESIGN.md` 要通過（designlang 自己產的 DESIGN.md 不合規格，只當證據）。",
              "3. 和負責人逐項標「借、不借、改成我們的值」，寫進參考表（S2-04）與設計系統（G2.4）。",
              "4. 重建後：`pb.py teardown compare <這個資料夾> <重建網址>`，再 `pb.py review-pack --stage web`。"]
    p = out / "summary.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------- compare
def ssim(a, b) -> float:
    import numpy as np
    a = a.astype("float64"); b = b.astype("float64")
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    def blocks(x):
        h, w = (x.shape[0] // 8) * 8, (x.shape[1] // 8) * 8
        return x[:h, :w].reshape(h // 8, 8, w // 8, 8)
    A, B = blocks(a), blocks(b)
    ma, mb = A.mean(axis=(1, 3)), B.mean(axis=(1, 3))
    va, vb = A.var(axis=(1, 3)), B.var(axis=(1, 3))
    cov = ((A - ma[:, None, :, None]) * (B - mb[:, None, :, None])).mean(axis=(1, 3))
    s = ((2 * ma * mb + c1) * (2 * cov + c2)) / ((ma ** 2 + mb ** 2 + c1) * (va + vb + c2))
    return float(s.mean())


def compare_images(p1: Path, p2: Path) -> dict:
    import numpy as np
    from PIL import Image
    a = Image.open(p1).convert("L"); b = Image.open(p2).convert("L")
    h = min(a.height, b.height, 2400)
    a = np.array(a.crop((0, 0, a.width, h)).resize((a.width // 2, h // 2)))
    b = np.array(b.crop((0, 0, b.width, h)).resize((b.width // 2, h // 2)))
    if a.shape != b.shape:
        b = np.array(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    diff = float((abs(a.astype(int) - b.astype(int)) > 255 * RULES["比對"]["像素差門檻"]).mean())
    cols, rows = RULES["比對"]["SSIM 分區"]
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            ys, ye = r * a.shape[0] // rows, (r + 1) * a.shape[0] // rows
            xs, xe = c * a.shape[1] // cols, (c + 1) * a.shape[1] // cols
            row.append(round(ssim(a[ys:ye, xs:xe], b[ys:ye, xs:xe]), 3))
        grid.append(row)
    return {"像素差比例": round(diff, 3), "SSIM 整體": round(ssim(a, b), 3), "SSIM 分區（列×欄）": grid}


def system_delta(m1: dict, m2: dict) -> list[dict]:
    lim = RULES["比對"]["系統差門檻"]
    rows = []
    def add(item, a, b, ok, note=""):
        rows.append({"項目": item, "參考": a, "重建": b, "判": "PASS" if ok else "差", "說明": note})
    u = m1["間距"].get("級距")
    fit = (m2["間距"].get("各級距符合率") or {}).get(u, (m2["間距"].get("各級距符合率") or {}).get(str(u), 0)) if u else 0
    add("間距在參考級距上", f"{u}px", f"{round(fit * 100)}% 的值是 {u} 的倍數", bool(u) and fit >= RULES["量測"]["間距級距門檻"], "重建的級距可以更粗（8 也在 4 的系統裡）")
    r1, r2 = m1["字"].get("相鄰比例中位數"), m2["字"].get("相鄰比例中位數")
    add("字級相鄰比例", r1, r2, bool(r1 and r2) and abs(r1 - r2) <= RULES["比對"]["系統差門檻"]["字級比例"])
    c1, c2 = m1["字"].get("內文到最大"), m2["字"].get("內文到最大")
    add("內文到最大字級倍數", c1, c2, bool(c1 and c2) and abs(c1 - c2) / c1 <= 0.25, "標題和內文的反差")
    for k, part in (("首屏留白", "首屏"), ("全頁留白", "全頁")):
        a, b = m1[part]["留白比例"], m2[part]["留白比例"]
        add(k, a, b, abs(a - b) <= lim["留白比例"])
    a, b = m1["全頁"]["60-30-10"][0], m2["全頁"]["60-30-10"][0]
    add("主色占比", a, b, abs(a - b) <= lim["主色占比"])
    add("內文行高倍數", m1["字"].get("內文行高倍數"), m2["字"].get("內文行高倍數"),
        bool(m1["字"].get("內文行高倍數") and m2["字"].get("內文行高倍數") and abs(m1["字"]["內文行高倍數"] - m2["字"]["內文行高倍數"]) <= 0.15))
    e1, e2 = set(m1.get("特效", {})), set(m2.get("特效", {}))
    add("特效種類", sorted(e1), sorted(e2), not (e1 - e2), ("重建缺 " + "、".join(sorted(e1 - e2))) if e1 - e2 else "")
    add("動態數（載入）", m1["動態"]["動畫數（載入時）"], m2["動態"]["動畫數（載入時）"], (m1["動態"]["動畫數（載入時）"] > 0) == (m2["動態"]["動畫數（載入時）"] > 0))
    return rows


def cmd_compare(a) -> int:
    ref = Path(a.ref)
    m1 = json.loads((ref / "measure.json").read_text(encoding="utf-8"))
    out = Path(a.out or ref / "compare")
    out.mkdir(parents=True, exist_ok=True)
    log(f"擷取重建頁 {a.url} …")
    raw = capture(a.url, out)
    raw["url"] = a.url
    m2 = measure(raw, out)
    pix = {w: compare_images(ref / f"shots/w{w}_fold.png", out / f"shots/w{w}_fold.png") for w in RULES["寬度"]}
    sysd = system_delta(m1, m2)
    res = {"參考": str(ref), "重建": a.url, "第一層 像素與第二層 SSIM（首屏，各寬度）": pix, "第三層 系統量測差": sysd,
           "第四層": "新代理兩輪評審：`pb.py review-pack --stage web --stills <這裡的 shots> --brief …`",
           "說明": RULES["比對"]["說明"]}
    (out / "compare.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    from PIL import Image
    for w in RULES["寬度"]:
        A, B = Image.open(ref / f"shots/w{w}_fold.png"), Image.open(out / f"shots/w{w}_fold.png")
        c = Image.new("RGB", (A.width + B.width + 16, max(A.height, B.height)), "white"); c.paste(A, (0, 0)); c.paste(B, (A.width + 16, 0))
        c.save(out / f"side_w{w}.jpg", quality=85)
    log("\n系統量測差（換內容重建時最有用）：")
    for r in sysd:
        log(f"  {r['判']:4} {r['項目']}：參考 {r['參考']}｜重建 {r['重建']} {r['說明']}")
    log("\n首屏 SSIM（只在照原版面重建時有意義）：" + "、".join(f"{w}px {v['SSIM 整體']}" for w, v in pix.items()))
    log(f"\n並排圖：{out}/side_w*.jpg；結果：{out / 'compare.json'}")
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "compare":
        ap = argparse.ArgumentParser(prog="pb.py teardown compare")
        ap.add_argument("ref"); ap.add_argument("url"); ap.add_argument("--out")
        return cmd_compare(ap.parse_args(argv[1:]))
    ap = argparse.ArgumentParser(prog="pb.py teardown")
    ap.add_argument("url"); ap.add_argument("--out"); ap.add_argument("--no-tools", action="store_true"); ap.add_argument("--only", help="comma list of tools to run")
    a = ap.parse_args(argv)
    host = re.sub(r"^https?://", "", a.url).split("/")[0]
    out = Path(a.out or f"teardown-{host}-{dt.date.today()}")
    out.mkdir(parents=True, exist_ok=True)
    log(f"擷取 {a.url}（{', '.join(map(str, RULES['寬度']))}px）…")
    raw = capture(a.url, out)
    raw["url"] = a.url
    m = measure(raw, out)
    tools = {} if a.no_tools else (log("外部工具：") or run_tools(a.url, out, set(a.only.split(",")) if a.only else None))
    ts = tool_summary(out)
    p = report(a.url, out, m, tools, ts)
    log(f"\n完成：{p}\n量測：{out / 'measure.json'}｜截圖：{out / 'shots'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
