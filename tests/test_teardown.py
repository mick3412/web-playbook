"""Reference-site teardown (bin/teardown.py) on a local test page: measurements, motion, pseudo-element effects, compare.

    python3 -m unittest tests.test_teardown
No network: --no-tools, file:// page. Skips where Playwright or Chrome is missing.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bin"))

try:
    import playwright  # noqa: F401
    import numpy  # noqa: F401
    import PIL  # noqa: F401
    OK = Path("/Applications/Google Chrome.app").exists()
except ImportError:
    OK = False

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;background:#101010;color:#ddd;font:16px/1.5 Georgia,serif}
section{padding:64px 32px;margin:0 0 32px} h1{font-size:64px;margin:0 0 24px} h2{font-size:32px;margin:0 0 16px} h3{font-size:20px;margin:0 0 8px}
p{margin:0 0 16px} .card{padding:24px;border-radius:8px;background:#181818} .hero{position:relative}
.hero::before{content:"";position:absolute;inset:0;background:radial-gradient(circle,#335,transparent)}
.spin{width:40px;height:40px;background:#c93;animation:s 2s linear infinite} @keyframes s{to{transform:rotate(360deg)}}
a{transition:color .2s ease-out}
</style></head><body>
<section class="hero"><h1>Heading one</h1><p>Body text that is long enough to count as the body size for the measurement, repeated so it wins by characters. Body text that is long enough to count as the body size.</p><div class="spin"></div></section>
<section><h2>Heading two</h2><div class="card"><h3>Card</h3><p>More body text set at sixteen pixels, so the body size is clear. <a href="#">A link</a></p></div></section>
</body></html>"""


def run(*args):
    return subprocess.run([sys.executable, str(REPO / "pb.py"), "teardown", *args], capture_output=True, text=True, cwd=REPO)


@unittest.skipUnless(OK, "Playwright, numpy, Pillow or Chrome missing")
class Teardown(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        (cls.tmp / "page.html").write_text(PAGE, encoding="utf-8")
        cls.url = "file://" + str(cls.tmp / "page.html")
        cls.out = cls.tmp / "td"
        r = run(cls.url, "--out", str(cls.out), "--no-tools")
        assert r.returncode == 0, r.stdout + r.stderr
        cls.m = json.loads((cls.out / "measure.json").read_text(encoding="utf-8"))

    def test_evidence_files(self):
        for w in (375, 768, 1280, 1440):
            self.assertTrue((self.out / "shots" / f"w{w}_fold.png").is_file())
        self.assertIn("## 量不到", (self.out / "summary.md").read_text(encoding="utf-8"))

    def test_spacing_and_type(self):
        self.assertEqual(self.m["間距"]["級距"], 8)                     # every value is a multiple of 8
        t = self.m["字"]
        self.assertEqual(t["內文字級"], 16)                              # by characters, not by element count
        self.assertEqual(t["字級階（≥內文）"], [16, 20, 32, 64])
        self.assertEqual(t["內文到最大"], 4.0)

    def test_motion_and_pseudo_effects(self):
        self.assertGreaterEqual(self.m["動態"]["動畫數（載入時）"], 1)  # the CSS keyframe spin
        self.assertIn("radial/conic gradient", self.m["特效"])           # lives on ::before
        self.assertTrue(any(t["時長"] == "0.2s" for t in self.m["動態"]["轉場（常見）"]))

    def test_compare_with_itself_passes(self):
        r = run("compare", str(self.out), self.url, "--out", str(self.tmp / "cmp"))
        self.assertEqual(r.returncode, 0, r.stderr)
        c = json.loads((self.tmp / "cmp" / "compare.json").read_text(encoding="utf-8"))
        self.assertTrue(all(x["判"] == "PASS" for x in c["第三層 系統量測差"]), c["第三層 系統量測差"])
        self.assertGreater(c["第一層 像素與第二層 SSIM（首屏，各寬度）"]["1440"]["SSIM 整體"], 0.95)


class Rules(unittest.TestCase):
    def test_rules_name_every_chapter_and_boundary(self):
        R = json.loads((REPO / "data" / "teardown_rules.json").read_text(encoding="utf-8"))
        self.assertEqual(R["DESIGN.md"]["章節"][0].split("（")[0], "Overview")
        self.assertTrue(any("不帶走" in x for x in R["界線"]))
        C = json.loads((REPO / "data" / "review_checklists.json").read_text(encoding="utf-8"))
        self.assertEqual(set(C["web"]), {"名稱", "1", "2"})


if __name__ == "__main__":
    unittest.main()
