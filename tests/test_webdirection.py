"""Website direction alignment (bin/webdirection.py) and the web review stages.

    python3 -m unittest discover -s tests -p test_webdirection.py
Synthetic references (no network). Tile rendering skips where Playwright, Pillow or Chrome is missing.
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bin"))
import webdirection as W  # noqa: E402

try:
    import playwright  # noqa: F401
    from PIL import Image, ImageChops
    OK = Path("/Applications/Google Chrome.app").exists()
except ImportError:
    OK = False


def fake_ref(root: Path, name: str, bg: str, white: float, contrast: float, colours: list, anims: int) -> str:
    d = root / name
    (d / "shots").mkdir(parents=True)
    m = {"網址": f"https://{name}.example", "全頁": {"底色": bg, "留白比例": white, "色彩面積": colours, "60-30-10": [0.6, 0.3, 0.1]},
         "首屏": {"留白比例": white}, "字": {"內文到最大": contrast, "字體（依字數）": [{"字體": "Serif Display" if name == "c" else "Sans", "占比": 1}]},
         "動態": {"動畫數（載入時）": anims}}
    (d / "measure.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    for w in (1440, 375):
        (d / "shots" / f"w{w}_fold.png").write_bytes(b"")
    return str(d)


def pb(*args):
    return subprocess.run([sys.executable, str(REPO / "pb.py"), *args], capture_output=True, text=True, cwd=REPO)


class Pairs(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.refs = [fake_ref(self.tmp, "a", "#0a0a0a", 0.55, 4.8, [{"色": "#0a0a0a", "占比": 0.9}], 80),
                     fake_ref(self.tmp, "b", "#ffffff", 0.60, 3.0, [{"色": "#ffffff", "占比": 0.5}, {"色": "#ff3366", "占比": 0.3}], 10),
                     fake_ref(self.tmp, "c", "#ffffff", 0.90, 2.5, [{"色": "#ffffff", "占比": 0.95}], 0)]

    def test_each_pair_splits_its_axis(self):
        prs = W.pairs(W.load_refs(self.refs))
        self.assertEqual(len(prs), len(W.AXES))
        for p, ax in zip(prs, W.AXES):
            if p.get("略過"):
                continue
            k = ax["特徵"]
            self.assertLess(p["低"]["特徵"][k], p["高"]["特徵"][k], ax["id"])
            self.assertGreaterEqual(p["差"], 0.8)

    def test_page_is_local(self):
        r = pb("direction", "--web", "page", *self.refs, "--need", "test", "--out", str(self.tmp / "out"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("只在本機開", (self.tmp / "out" / "webdirection.html").read_text(encoding="utf-8"))

    def test_picks_map_to_parameters_and_flips_change_something(self):
        picks = {"二選一": {"亮暗": "亮", "留白": "多", "反差": "大", "色彩": "都可以"}, "參考牆": {self.refs[2]: {"判": "要", "點": ["字體"]}}}
        d = W.direction(picks)
        self.assertEqual((d["tone"], d["區塊間距"], d["標題字級"]), ("light", 160, 80))
        self.assertEqual(d["字體"]["標題"], "Fraunces")              # the liked reference is set in a serif
        for ax in ("色彩", "亮暗", "動態"):
            alt = W.direction(picks, [ax])
            self.assertNotEqual(W.describe(alt), W.describe(d), ax)


@unittest.skipUnless(OK, "Playwright, Pillow or Chrome missing")
class Tiles(unittest.TestCase):
    def test_three_tiles_differ_and_choose_writes_the_card(self):
        tmp = Path(tempfile.mkdtemp())
        refs = [fake_ref(tmp, n, bg, w, c, [{"色": bg, "占比": 0.9}], a) for n, bg, w, c, a in (("a", "#0a0a0a", .5, 4.8, 80), ("b", "#ffffff", .6, 3, 10), ("c", "#ffffff", .9, 2.5, 0))]
        picks = tmp / "picks.json"
        picks.write_text(json.dumps({"需求": "t", "參考": refs, "二選一": {"亮暗": "亮", "留白": "多"}, "參考牆": {}}, ensure_ascii=False), encoding="utf-8")
        r = pb("direction", "--web", "tiles", str(picks), "--headline", "A calm place", "--sub", "Sub line", "--cta", "Start")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        shots = [Image.open(tmp / f"tile{i}_w1440.png").convert("L") for i in (1, 2, 3)]
        for i in range(3):
            for j in range(i + 1, 3):
                self.assertIsNotNone(ImageChops.difference(shots[i], shots[j]).getbbox(), f"tile {i + 1} and {j + 1} look the same")
        self.assertEqual(pb("direction", "--web", "choose", str(picks), "1").returncode, 0)
        seed = (tmp / "DESIGN.seed.md").read_text(encoding="utf-8")
        self.assertTrue(seed.startswith("---") and "primary:" in seed)
        self.assertEqual(json.loads((tmp / "direction.json").read_text(encoding="utf-8"))["選的方向"], 1)


class BrandLock(unittest.TestCase):
    def test_an_existing_brand_keeps_its_colour_and_type(self):
        d = W.direction({"二選一": {"亮暗": "暗", "反差": "大"}, "參考牆": {}})
        brand = {"colors": {"background": "#F5F0E6", "text": "#111111", "accent": "#C9A45C"}, "fonts_web": {"heading": "Bodoni Moda", "body": "IBM Plex Sans"}}
        d = W.lock_brand(d, brand)
        self.assertEqual((d["色盤"]["background"], d["色盤"]["accent"], d["tone"]), ("#F5F0E6", "#C9A45C", "light"))   # the brand wins over the dark pick
        self.assertIn("serif", d["字體"]["標題棧"])
        self.assertEqual(d["標題字級"], 80)                                                                          # the rest of the picks still apply
        self.assertIn("鎖定", W.describe(d))


class ReviewStages(unittest.TestCase):
    def test_every_web_stage_has_a_checklist_and_a_parser_choice(self):
        C = json.loads((REPO / "data" / "review_checklists.json").read_text(encoding="utf-8"))
        src = (REPO / "pb.py").read_text(encoding="utf-8")
        choices = re.search(r'--stage", choices=\[([^\]]+)\]', src).group(1)
        for st in ("web", "web-ia", "web-wire", "web-code", "web-a11y", "web-launch"):
            self.assertIn(f'"{st}"', choices)
            self.assertIn("1", C[st])
            self.assertTrue(C[st]["1"]["看"])
        for two in ("web", "web-ia", "web-wire"):
            self.assertIn("2", C[two])

    def test_decision_windows_are_in_the_stages(self):
        S = (REPO / "data" / "stages.json").read_text(encoding="utf-8")
        for w in "ABCDEF":
            self.assertIn(f"決策窗 {w}", S)


if __name__ == "__main__":
    unittest.main()
