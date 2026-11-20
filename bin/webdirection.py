#!/usr/bin/env python3
"""Website direction alignment (決策窗 C 方向): agree on the site's look with things you can see, before the design system.

  page    <teardown dir> <teardown dir> <teardown dir> ... --need "需求" [--out DIR]
          this-or-that pairs built from the references' teardown measurements (one axis each), plus a reference wall
  tiles   picks.json --headline "…" --sub "…" --cta "…" [--out DIR]
          picks → 3 directions → 3 first-screen style tiles in our own words (local HTML), screenshots at 1440 and 375, step-3 page
  choose  picks.json N
          writes 方向卡 direction.json and DESIGN.seed.md (Overview + tokens to start DESIGN.md from)

The references come from `pb.py teardown <url>` (measure.json + shots). Pages stay local: the screenshots are other people's work.
Axes, mappings and palettes live in data/webdirection_rules.json.
"""
from __future__ import annotations
import argparse, html, json, math, re, sys, datetime as dt
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RULES = json.loads((REPO / "data" / "webdirection_rules.json").read_text(encoding="utf-8"))
AXES = RULES["軸"]


def lum(hexc: str) -> float:
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def features(m: dict) -> dict:
    vivid = sum(a["占比"] for a in m["全頁"]["色彩面積"] if saturation(a["色"]) > 0.35 and lum(a["色"]) > 0.08)   # photos add many colours but few vivid areas
    return {"亮度": round(lum(m["全頁"]["底色"]), 3), "留白": m["首屏"]["留白比例"], "反差": m["字"].get("內文到最大") or 1,
            "鮮豔": round(vivid, 3), "動態": round(math.log1p(m["動態"]["動畫數（載入時）"] or 0), 2)}


def load_refs(dirs: list[str]) -> list[dict]:
    refs = []
    for d in dirs:
        p = Path(d)
        m = json.loads((p / "measure.json").read_text(encoding="utf-8"))
        if m.get("被擋"):
            print(f"略過 {p.name}：拆解時被機器人驗證擋下，量測不能用")
            continue
        fonts = [f["字體"] for f in m["字"].get("字體（依字數）", [])]
        refs.append({"名": p.name, "網址": m.get("網址") or "", "目錄": str(p.resolve()), "特徵": features(m), "字體": fonts[:2],
                     "色": [a["色"] for a in m["全頁"]["色彩面積"][:5]], "首屏": str((p / "shots" / "w1440_fold.png").resolve()),
                     "手機": str((p / "shots" / "w375_fold.png").resolve())})
    if len(refs) < 3:
        sys.exit(f"可用的參考站只有 {len(refs)} 個，至少要 3 個（先 `pb.py teardown <網址> --no-tools` 拆解）")
    return refs


def pairs(refs: list[dict]) -> list[dict]:
    """For each axis, the two references farthest apart on it and closest on the others (z-scored across the references)."""
    import statistics
    keys = [a["特徵"] for a in AXES]
    st = {k: (statistics.mean(r["特徵"][k] for r in refs), statistics.pstdev(r["特徵"][k] for r in refs) or 1) for k in keys}
    z = lambda r, k: (r["特徵"][k] - st[k][0]) / st[k][1]
    out = []
    for a in AXES:
        k = a["特徵"]
        best = None
        for i, x in enumerate(refs):
            for y in refs[i + 1:]:
                gap = abs(z(x, k) - z(y, k))
                rest = sum(abs(z(x, o) - z(y, o)) for o in keys if o != k)
                score = gap - 0.35 * rest
                if gap >= 0.8 and (best is None or score > best[0]):
                    best = (score, x, y, gap, {o: round(z(x, o) - z(y, o), 1) for o in keys if o != k and abs(z(x, o) - z(y, o)) > 1})
        if not best:
            out.append({"軸": a["id"], "略過": "參考站在這一軸差不多，換一組參考或請負責人直接選"})
            continue
        _, x, y, gap, off = best
        lo, hi = (x, y) if x["特徵"][k] <= y["特徵"][k] else (y, x)
        out.append({"軸": a["id"], "問": a["問"], "低": {"標籤": a["低"], **lo}, "高": {"標籤": a["高"], **hi}, "差": round(gap, 2), "其他還差": off})
    return out


CSS = """:root{--bg:#f6f4ef;--ink:#1d1d1f;--mute:#6b6b70;--line:#d9d6cf;--acc:#2f5bd3;--card:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--ink:#ececef;--mute:#9a9aa2;--line:#33333a;--acc:#7da2ff;--card:#1d1d21}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,"PingFang TC",sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 90px}h1{font-size:24px;margin:0 0 4px}h2{font-size:19px;margin:32px 0 8px}.sub{color:var(--mute)}
.pair,.w{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;margin:14px 0}.q{font-weight:600;margin-bottom:8px}
.lr{display:grid;grid-template-columns:1fr 1fr;gap:12px}.opt{border:2px solid transparent;border-radius:10px;padding:6px;cursor:pointer;background:var(--bg)}.opt.on{border-color:var(--acc)}
.opt img,.w img{width:100%;border-radius:6px;display:block}.meta{font-size:12px;color:var(--mute);margin-top:6px}.warn{font-size:12px;color:#b26a00}
button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:5px 13px;cursor:pointer}button.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.btns{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}.wall{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.aspects{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px;font-size:13px}.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px}
.bar{position:sticky;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:10px;display:flex;gap:10px;justify-content:center;align-items:center}"""

JS = r"""
const D = window.DATA; let S = {}; try { S = JSON.parse(localStorage.getItem(D.store) || '{}'); } catch (e) {}
S.二選一 = S.二選一 || {}; S.參考牆 = S.參考牆 || {};
const save = () => { try { localStorage.setItem(D.store, JSON.stringify(S)); } catch (e) {} window.PICKS = {需求: D.need, 參考: D.refs.map(r => r.目錄), 二選一: S.二選一, 參考牆: S.參考牆, 選: S.選 || null}; };
const img = p => `<img loading="lazy" src="file://${p}">`;
(D.pairs || []).forEach(p => { const box = document.getElementById('pairs'); const c = document.createElement('div'); c.className = 'pair';
  if (p.略過) { c.innerHTML = `<div class="q">${p.軸}</div><div class="meta">${p.略過}</div>`; box.appendChild(c); return; }
  c.innerHTML = `<div class="q">${p.軸}｜${p.問}</div><div class="lr"></div><div class="btns"><button data-v="都可以">都可以</button><button data-v="都不要">都不要</button></div>` + (Object.keys(p.其他還差).length ? `<div class="warn">這一對除了「${p.軸}」，還在 ${Object.keys(p.其他還差).join('、')} 上有差；請只看「${p.軸}」。</div>` : '');
  const lr = c.querySelector('.lr'); const opts = [];
  const sides = Math.random() < 0.5 ? [p.低, p.高] : [p.高, p.低];
  sides.forEach(x => { const o = document.createElement('div'); o.className = 'opt'; o.innerHTML = img(x.首屏) + `<div class="meta"><b>${x.標籤}</b>｜${x.名}</div>`; o.onclick = () => set(x.標籤); lr.appendChild(o); opts.push([o, x.標籤]); });
  function set(v) { S.二選一[p.軸] = v; opts.forEach(([o, t]) => o.classList.toggle('on', t === v)); c.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); save(); }
  c.querySelectorAll('button').forEach(b => b.onclick = () => set(b.dataset.v)); if (S.二選一[p.軸]) set(S.二選一[p.軸]); box.appendChild(c); });
(D.refs || []).forEach(r => { const box = document.getElementById('wall'); if (!box) return; const c = document.createElement('div'); c.className = 'w'; const st = S.參考牆[r.目錄] || {判: '', 點: []};
  c.innerHTML = img(r.首屏) + `<div class="meta">${r.名}｜${r.網址}｜字體 ${r.字體.join('、')}</div><div class="btns"><button data-v="要">要</button><button data-v="不要">不要</button></div><div class="aspects">${D.aspects.map(a => `<label><input type="checkbox" value="${a}" ${st.點.includes(a) ? 'checked' : ''}> ${a}</label>`).join('')}</div>`;
  c.querySelectorAll('button').forEach(b => { b.classList.toggle('on', st.判 === b.dataset.v); b.onclick = () => { st.判 = b.dataset.v; S.參考牆[r.目錄] = st; c.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); save(); }; });
  c.querySelectorAll('input').forEach(i => i.onchange = () => { st.點 = [...c.querySelectorAll('input:checked')].map(x => x.value); if (st.點.length && !st.判) st.判 = '要'; S.參考牆[r.目錄] = st; save(); }); box.appendChild(c); });
(D.tiles || []).forEach((t, i) => { const box = document.getElementById('tiles'); const c = document.createElement('div'); c.className = 'w';
  c.innerHTML = img(t.桌機) + `<div style="display:grid;grid-template-columns:1fr 2fr;gap:8px;margin-top:8px">${img(t.手機)}<div><div class="q">方向 ${i + 1}：${t.名稱}</div><div class="meta">${t.說明}</div><div class="meta"><a href="file://${t.網頁}" target="_blank">開啟這個樣片（看得到動態）</a></div><div class="btns"><button>選這個</button></div></div></div>`;
  const b = c.querySelector('button'); b.classList.toggle('on', S.選 === i + 1); b.onclick = () => { S.選 = i + 1; document.querySelectorAll('#tiles button').forEach(x => x.classList.toggle('on', x === b)); save(); }; box.appendChild(c); });
document.getElementById('dl').onclick = () => { save(); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(window.PICKS, null, 1)], {type: 'application/json'})); a.download = 'picks.json'; a.click(); };
save();
"""


def page(need: str, refs: list[dict], prs: list[dict] | None, out: Path, tiles: list[dict] | None = None) -> Path:
    data = {"need": need, "store": "webdir:" + re.sub(r"\W+", "", need)[:40], "refs": refs, "pairs": prs or [], "tiles": tiles or [], "aspects": RULES["參考牆要的點"]}
    body = ("<h2>3. 用我們的文案做的 3 個方向</h2><p class='sub'>同一個首屏，三種方向（上：桌機 1440，下左：手機 375）。選一個、下載 picks.json 交回。</p><div class='tiles' id='tiles'></div>" if tiles else
            "<h2>1. 二選一</h2><p class='sub'>每題只比一件事：點比較像你要的那一邊，沒差就選「都可以」。</p><div id='pairs'></div>"
            "<h2>2. 參考牆</h2><p class='sub'>每個參考標要或不要，勾要的是哪一點。</p><div class='wall' id='wall'></div>")
    doc = (f"<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>網站方向對齊</title><style>{CSS}</style></head>"
           f"<body><main><h1>網站方向對齊</h1><div class='sub'>需求：{html.escape(need)}｜參考截圖是別人的作品，這頁只在本機開</div>{body}</main>"
           f"<div class='bar'><span class='sub'>選擇會自動存在這個瀏覽器</span><button id='dl' class='on'>下載 picks.json</button></div>"
           f"<script>window.DATA = {json.dumps(data, ensure_ascii=False)};</script><script>{JS}</script></body></html>")
    out.mkdir(parents=True, exist_ok=True)
    p = out / ("webdirection_tiles.html" if tiles else "webdirection.html")
    p.write_text(doc, encoding="utf-8")
    return p


# ---------------------------------------------------------------- picks → directions → tiles
def free_font(name: str) -> str:
    T = RULES["字體替代"]
    low = name.lower()
    hit = next((v for k, v in T["對照"].items() if k in low), None)
    return hit or (T["襯線預設"] if "serif" in low.replace("sans-serif", "") else T["無襯線預設"])


def direction(picks: dict, flip: list[str] | None = None, borrow: str | None = None) -> dict:
    d = json.loads(json.dumps(RULES["預設"]))
    d["依據"] = {}
    liked = [borrow] if borrow else [r for r, v in picks.get("參考牆", {}).items() if v.get("判") == "要"]
    for a in AXES:
        v = picks.get("二選一", {}).get(a["id"])
        if a["id"] in (flip or []):
            v = a["高"] if v == a["低"] else a["低"] if v == a["高"] else next(s for s in (a["高"], a["低"]) if a["換算"][s] != {k: d.get(k) for k in a["換算"][s]})
        if v in (a["低"], a["高"]):
            d.update(a["換算"][v])
            d["依據"][a["id"]] = v
    d["色盤"] = dict(RULES["色盤"]["暗" if d["tone"] == "dark" else "亮"])
    for r in liked:                            # borrow the liked reference's most saturated colour as the accent, if it has one
        m = json.loads((Path(r) / "measure.json").read_text(encoding="utf-8"))
        sat = [a["色"] for a in m["全頁"]["色彩面積"] if saturation(a["色"]) > 0.25 and lum(a["色"]) > 0.08 and a["占比"] < 0.4]
        names = [f["字體"] for f in m["字"].get("字體（依字數）", [])[:2]]
        wants_font = "字體" in picks.get("參考牆", {}).get(r, {}).get("點", []) or any("serif" in n.lower().replace("sans-serif", "") for n in names)
        if names and wants_font and not flip:   # the owner liked this reference's type (or it is set in a serif): take its look, in a free face
            ff = free_font(names[0])
            serif = ff in ("Fraunces",) or "serif" in names[0].lower().replace("sans-serif", "")
            d["字體"].update({"標題": ff, "標題棧": f"'{ff}', {'Georgia, serif' if serif else 'sans-serif'}", "原字": names[0]})
            d["依據"]["字體"] = f"{ff}（代 {names[0]}，取自 {Path(r).name}）"
        if borrow:   # what this reference measurably has: texture, surfaces, dark blocks, mono labels
            fx = m.get("特效", {})
            bgc = m["全頁"]["底色"]
            others = [a for a in m["全頁"]["色彩面積"] if a["色"] != bgc]
            ink = next((a for a in others if lum(a["色"]) < 0.12), None)
            surf = next((a["色"] for a in others if lum(a["色"]) > 0.7 and saturation(a["色"]) < 0.2), None)
            hi = next((a["色"] for a in others if lum(a["色"]) > 0.8 and saturation(a["色"]) >= 0.1), None)
            d["借"] = {"光暈": bool(fx.get("radial/conic gradient")), "霧面": bool(fx.get("backdrop-filter")),
                      "影像動態": any(k.startswith(("canvas", "WebGL", "video")) for k in fx),
                      "深色區塊": ink["色"] if ink and ink["占比"] >= 0.25 else None, "表面色": surf, "亮點色": hi,
                      "等寬標籤": any(re.search(r"mono|code|courier", n, re.I) for n in names)}
            d["依據"]["借用"] = "、".join(k for k, v in d["借"].items() if v)
        if sat and not flip:
            d["色盤"]["accent"] = sat[0]
            d["依據"]["強調色"] = f"取自 {Path(r).name}"
            break
    d["色盤"]["accent"] = d.get("強調色覆寫") or d["色盤"]["accent"]
    return d


def saturation(hexc: str) -> float:
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    mx, mn = max(r, g, b), min(r, g, b)
    return 0 if mx == 0 else (mx - mn) / mx


def describe(d: dict) -> str:
    b = d["依據"]
    return "；".join([f"{'暗' if d['tone'] == 'dark' else '亮'}底", f"留白 {b.get('留白', '中')}（區塊間距 {d['區塊間距']}px）", f"字級反差 {b.get('反差', '中')}（標題 {d['標題字級']}px）",
                     f"色彩 {b.get('色彩', '收斂')}", f"動態 {b.get('動態', '少')}", f"字體 {d['字體']['標題']}"] + (["色彩與字體鎖定為現行品牌"] if d["依據"].get("品牌鎖定") else []) + ([f"強調色{b['強調色']}"] if b.get("強調色") else []) + ([f"借：{b['借用']}"] if b.get("借用") else []))


def tile_html(d: dict, headline: str, sub: str, cta: str, brand: str | None = None, points: list | None = None) -> str:
    c = d["色盤"]
    vivid = d.get("色彩") == "繽紛"
    anim = d.get("動態") == "多"
    B = d.get("借", {})
    feats = [(p.split("：")[0], p.split("：", 1)[1]) if "：" in p else ("", p) for p in points] if points else RULES["樣片文案"]["特色"]
    cards = "".join(f"<div class='card{' v' + str(i) if vivid else ''}'><b>{html.escape(t)}</b><p>{html.escape(x)}</p></div>" for i, (t, x) in enumerate(feats))
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;510;600&family=Fraunces:opsz,wght@9..144,400;9..144,600{''.join('&family=' + x.replace(' ', '+') + ':wght@400;500;600' for x in {d['字體']['標題'], d['字體']['內文']} if x not in ('Inter', 'Fraunces'))}&display=swap" rel="stylesheet"><style>
:root{{--bg:{c['background']};--fg:{c['foreground']};--mute:{c['muted']};--line:{c['border']};--acc:{c['accent']}}}
*{{box-sizing:border-box;margin:0}}body{{background:var(--bg);color:var(--mute);font:400 16px/1.6 {d['字體']['內文棧']}}}
.w{{max-width:1200px;margin:0 auto;padding:0 32px}}nav{{display:flex;align-items:center;gap:28px;height:72px;font-size:14px;border-bottom:1px solid var(--line)}}
nav b{{color:var(--fg);margin-right:auto;font:600 18px {d['字體']['標題棧']}}}.cta{{background:{'var(--acc)' if vivid else 'var(--fg)'};color:var(--bg);padding:8px 18px;border-radius:{d['圓角']}px;font-weight:510}}
.hero{{padding:{d['區塊間距']}px 0 {int(d['區塊間距'] * .6)}px}}h1{{color:var(--fg);font:{d['標題字重']} {d['標題字級']}px/1.05 {d['字體']['標題棧']};letter-spacing:{d['字距']};max-width:900px}}
.hero p{{margin-top:24px;max-width:560px;font-size:18px}}.hero .cta{{display:inline-block;margin-top:32px}}
.band{{height:{'10px' if vivid else '1px'};background:{'linear-gradient(90deg,var(--acc),#ffb547,#3ddc97)' if vivid else 'var(--line)'}}}
.row{{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;padding:{int(d['區塊間距'] * .5)}px 0}}.card{{border:1px solid var(--line);border-radius:{d['圓角']}px;padding:24px}}.card b{{color:var(--fg);font:600 18px {d['字體']['標題棧']}}}.card p{{margin-top:8px;font-size:15px}}
.v0{{background:color-mix(in srgb,var(--acc) 14%,transparent)}}.v1{{background:color-mix(in srgb,#ffb547 18%,transparent)}}.v2{{background:color-mix(in srgb,#3ddc97 16%,transparent)}}
{'.hero h1,.hero p,.hero .cta{animation:up .9s cubic-bezier(.2,.7,.2,1) both}.hero p{animation-delay:.12s}.hero .cta{animation-delay:.24s}@keyframes up{from{opacity:0;transform:translateY(24px)}}.card{transition:transform .2s}.card:hover{transform:translateY(-4px)}' if anim else ''}
@media (max-width:700px){{h1{{font-size:{max(34, int(d['標題字級'] * .55))}px}}.row{{grid-template-columns:1fr}}nav span{{display:none}}.hero{{padding:{int(d['區塊間距'] * .55)}px 0 40px}}}}
{texture_css(B, c)}
</style></head><body>{'<div class="glow"></div>' if B.get('光暈') else ''}{'<div class="mesh"></div>' if B.get('影像動態') else ''}<div class="w"><nav><b>{html.escape(brand or RULES['樣片文案']['品牌'])}</b><span>{'</span><span>'.join(RULES['樣片文案']['導覽'])}</span><a class="cta">{html.escape(cta)}</a></nav>
<section class="hero">{'<p class="eyebrow">' + html.escape(RULES['樣片文案'].get('標籤', 'INDEPENDENT · 2026')) + '</p>' if B.get('等寬標籤') else ''}<h1>{html.escape(headline)}</h1><p>{html.escape(sub)}</p><a class="cta">{html.escape(cta)}</a></section></div><div class="band"></div>{'<div class="dark"><div class="w"><section class="row">' + cards + '</section></div></div>' if B.get('深色區塊') else '<div class="w"><section class="row">' + cards + '</section></div>'}</body></html>"""


def texture_css(B: dict, c: dict) -> str:
    """Measured borrowings drawn as CSS: glow (radial gradients), frosted cards (backdrop-filter), a moving mesh where the reference has
    canvas, WebGL or video, a dark band (≥25 % dark area), a surface colour for cards, a highlight colour and mono labels."""
    out = []
    if B.get("光暈"):
        out.append(".glow{position:absolute;left:50%;top:-180px;width:900px;height:600px;margin-left:-200px;background:radial-gradient(closest-side,color-mix(in srgb,var(--acc) 22%,transparent),transparent);pointer-events:none;z-index:-1}")
    if B.get("影像動態"):
        out.append(".mesh{position:absolute;inset:0 0 auto 0;height:640px;z-index:-2;background:radial-gradient(40% 60% at 80% 30%,color-mix(in srgb,var(--acc) 26%,transparent),transparent),radial-gradient(35% 50% at 60% 70%,"
                   + (B.get("亮點色") or "#dfe7ff") + ",transparent);filter:blur(8px);animation:drift 12s ease-in-out infinite alternate}@keyframes drift{to{transform:translate(-40px,20px) scale(1.05)}}")
    if B.get("霧面"):
        out.append(".card{background:color-mix(in srgb,var(--bg) 60%,transparent);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px)}")
    if B.get("表面色"):
        out.append(f".card{{background:{B['表面色']};border-color:transparent}}")
    if B.get("亮點色"):
        out.append(f"h1{{text-decoration:underline;text-decoration-color:{B['亮點色']};text-decoration-thickness:.32em;text-underline-offset:-.16em;text-decoration-skip-ink:none}}")
    if B.get("深色區塊"):
        out.append(f".dark{{background:{B['深色區塊']};color:#b9bcc6}}.dark .card{{border-color:#2a2c36;background:transparent}}.dark .card b{{color:#fff}}")
    if B.get("等寬標籤"):
        out.append(".eyebrow{font:500 12px 'JetBrains Mono',monospace;letter-spacing:.08em;color:var(--mute);margin-bottom:20px}")
    out.append("body{position:relative;overflow-x:hidden}")
    return "\n".join(out)


def shoot(html_path: Path) -> tuple[str, str]:
    from playwright.sync_api import sync_playwright
    outs = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        for w, h in ((1440, 900), (375, 812)):
            pg = b.new_page(viewport={"width": w, "height": h})
            pg.goto("file://" + str(html_path.resolve()), wait_until="load")
            pg.wait_for_timeout(1600)   # fonts and entrance animations settle
            o = html_path.with_name(html_path.stem + f"_w{w}.png")
            pg.screenshot(path=str(o))
            outs.append(str(o.resolve()))
            pg.close()
        b.close()
    return outs[0], outs[1]


def flexible(picks: dict) -> list[str]:
    weak = [a["id"] for a in AXES if picks.get("二選一", {}).get(a["id"]) in (None, "都可以")]
    return weak + [x for x in ("亮暗", "色彩", "留白", "反差") if x not in weak]


def lock_brand(d: dict, brand: dict) -> dict:
    """An existing brand wins over the picks for colour and type (project rules come first); only layout, contrast, motion and texture vary.
    Reads a brand file shaped like {"colors": {primary, background, accent, muted?, text?}, "fonts": {heading, body}} (fonts_web wins when present)."""
    c, f = brand.get("colors", {}), brand.get("fonts_web") or brand.get("fonts", {})
    pal = d["色盤"]
    pal.update({k: v for k, v in {"background": c.get("background"), "foreground": c.get("text") or c.get("primary"), "muted": c.get("muted"),
                                   "border": c.get("secondary"), "accent": c.get("accent")}.items() if v})
    d["tone"] = "dark" if lum(pal["background"]) < 0.3 else "light"
    if f.get("heading"):
        serif = any(x in f["heading"].lower() for x in ("fraunces", "bodoni", "garamond", "serif", "spectral", "playfair"))
        d["字體"].update({"標題": f["heading"], "標題棧": f"'{f['heading']}', {'Georgia, serif' if serif else 'sans-serif'}"})
    if f.get("body"):
        d["字體"].update({"內文": f["body"], "內文棧": f"'{f['body']}', sans-serif"})
    d["依據"]["品牌鎖定"] = "色彩與字體照現行品牌"
    d.pop("強調色覆寫", None)
    d["依據"].pop("強調色", None)   # the brand's accent replaced any borrowed one
    return d


def cmd_tiles(a) -> int:
    picks = json.loads(Path(a.picks).read_text(encoding="utf-8"))
    out = Path(a.out or Path(a.picks).parent)
    out.mkdir(parents=True, exist_ok=True)
    liked = [r for r, v in picks.get("參考牆", {}).items() if v.get("判") == "要"]
    weak = [x["id"] for x in AXES if picks.get("二選一", {}).get(x["id"]) in (None, "都可以")]
    if not weak and len(liked) >= 2:   # every axis decided: never reverse the owner's picks; vary by which liked reference lends type and colour
        variants = [(f"照你的選擇＋借 {Path(r).name}", [], r) for r in liked[:3]]
    else:
        fx = flexible(picks)
        variants = [("照你的選擇", [], None), (f"改 {fx[0]}", [fx[0]], None), (f"改 {fx[1]}、{fx[2]}", [fx[1], fx[2]], None)]
    tiles = []
    for i, (name, flip, borrow) in enumerate(variants, 1):
        d = direction(picks, flip, borrow)
        if a.brand_lock:
            d = lock_brand(d, json.loads(Path(a.brand_lock).read_text(encoding="utf-8")))
        f = out / f"tile{i}.html"
        f.write_text(tile_html(d, a.headline, a.sub, a.cta, a.brand, a.point), encoding="utf-8")
        big, small = shoot(f)
        (out / f"direction{i}.json").write_text(json.dumps({"方向": i, "名稱": name, "說明": describe(d), **d}, ensure_ascii=False, indent=1), encoding="utf-8")
        tiles.append({"名稱": name, "說明": describe(d), "桌機": big, "手機": small, "網頁": str(f.resolve())})
        print(f"方向 {i}（{name}）：{describe(d)}")
    refs = [{"目錄": r} for r in picks.get("參考", [])]
    p = page(picks.get("需求", ""), refs, None, out, tiles)
    print(f"\n第 3 步頁面：{p}（選一個、下載 picks.json，再 `pb.py direction --web choose picks.json N`）")
    return 0


def cmd_choose(a) -> int:
    out = Path(a.out or Path(a.picks).parent)
    d = json.loads((out / f"direction{a.n}.json").read_text(encoding="utf-8"))
    picks = json.loads(Path(a.picks).read_text(encoding="utf-8"))
    liked = {Path(k).name: v.get("點", []) for k, v in picks.get("參考牆", {}).items() if v.get("判") == "要"}
    card = {"方向卡": "web-v1", "日期": dt.date.today().isoformat(), "需求": picks.get("需求", ""), "選的方向": a.n, "說明": d["說明"],
            "色盤": d["色盤"], "字體": d["字體"], "標題字級": d["標題字級"], "區塊間距": d["區塊間距"], "圓角": d["圓角"], "動態": d.get("動態"), "借用": {k: v for k, v in d.get("借", {}).items() if v},
            "二選一": picks.get("二選一", {}), "參考": {"要": liked, "不要": [Path(k).name for k, v in picks.get("參考牆", {}).items() if v.get("判") == "不要"]}}
    (out / "direction.json").write_text(json.dumps(card, ensure_ascii=False, indent=1), encoding="utf-8")
    c = d["色盤"]
    seed = f"""---
name: direction-{a.n}
colors:
  primary: "{c['accent']}"
  background: "{c['background']}"
  foreground: "{c['foreground']}"
  muted: "{c['muted']}"
  border: "{c['border']}"
typography:
  heading:
    fontFamily: {d['字體']['標題']}
    fontSize: {d['標題字級']}px
    fontWeight: {d['標題字重']}
  body:
    fontFamily: {d['字體']['內文']}
    fontSize: 16px
    lineHeight: 1.6
spacing:
  section: {d['區塊間距']}px
rounded:
  md: {d['圓角']}px
---

# Overview

Direction chosen in 決策窗 C ({dt.date.today()}): {d['說明']}. References liked: {', '.join(f'{k}（{"、".join(v) or "整體"}）' for k, v in liked.items()) or 'none'}.
Borrowed and measured from the reference: {', '.join(k for k, v in d.get('借', {}).items() if v) or 'nothing'}{' (mono labels: JetBrains Mono)' if d.get('借', {}).get('等寬標籤') else ''}.
Fill in the remaining chapters from the teardown evidence (pb.py teardown) and mark every value 量／工具／目測.
"""
    (out / "DESIGN.seed.md").write_text(seed, encoding="utf-8")
    print(f"已寫出方向卡 {out / 'direction.json'} 與 {out / 'DESIGN.seed.md'}\n{d['說明']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pb.py direction --web")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("page"); s.add_argument("refs", nargs="+"); s.add_argument("--need", required=True); s.add_argument("--out", default="webdirection")
    s = sub.add_parser("tiles"); s.add_argument("picks"); s.add_argument("--headline", required=True); s.add_argument("--sub", required=True); s.add_argument("--cta", required=True); s.add_argument("--out")
    s.add_argument("--brand", help="brand name in the nav"); s.add_argument("--brand-lock", help="a brand file (colors, fonts): keep the product's colour and type, vary the rest"); s.add_argument("--point", action="append", help="a card line, 「標題：內文」 (repeat, up to 3)")
    s = sub.add_parser("choose"); s.add_argument("picks"); s.add_argument("n", type=int); s.add_argument("--out")
    a = ap.parse_args(argv)
    if a.cmd == "page":
        refs = load_refs(a.refs)
        prs = pairs(refs)
        for p in prs:
            print(f"{p['軸']}：" + (p.get("略過") or f"{p['低']['名']}（{p['低']['標籤']}）vs {p['高']['名']}（{p['高']['標籤']}）｜差 {p['差']} 個標準差" + (f"｜其他還差 {p['其他還差']}" if p["其他還差"] else "")))
        print(f"\n頁面：{page(a.need, refs, prs, Path(a.out)).resolve()}（本機瀏覽器開，不發佈）")
        return 0
    return cmd_tiles(a) if a.cmd == "tiles" else cmd_choose(a)


if __name__ == "__main__":
    sys.exit(main())
