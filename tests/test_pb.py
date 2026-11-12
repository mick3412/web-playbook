"""End-to-end tests for pb.py with this playbook's data. Each test works on a copy of the repo and an empty project folder.

    python3 -m unittest discover tests
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SIBLING = REPO.parent / "production-playbook" / "pb.py"


class PlaybookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "playbook"
        shutil.copytree(REPO, self.home, ignore=shutil.ignore_patterns(".git", "__pycache__", "inbox", "bench"))
        self.project = self.tmp / "product"
        self.project.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def pb(self, *args, ok=True):
        env = {**os.environ, "WEB_PLAYBOOK_HOME": str(self.home), "CLAUDE_PROJECT_DIR": str(self.project)}
        p = subprocess.run([sys.executable, str(self.home / "pb.py"), *args], capture_output=True, text=True, env=env, cwd=self.project)
        if ok is True:
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        elif ok is False:
            self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)
        return p.stdout

    def test_check_passes_and_guide_is_current(self):
        self.assertIn("OK", self.pb("check"))

    @unittest.skipUnless(SIBLING.is_file(), "production-playbook is not next to this repo")
    def test_engine_matches_production_playbook(self):
        self.assertEqual((REPO / "pb.py").read_bytes(), SIBLING.read_bytes(), "copy pb.py between the playbook repos")

    def test_every_stage_card_has_all_sections(self):
        for stage in [str(i) for i in range(10)]:
            card = self.pb("card", stage)
            for heading in ("## 要做", "## 用什麼工具", "## 要注意", "## 讓品質更好、更獨特", "## 過關條件 → 下一步"):
                self.assertIn(heading, card, f"stage {stage} misses {heading}")

    def test_type_specific_steps(self):
        self.assertIn("6.1 結構化資料", self.pb("card", "6", "--type", "行銷網站"))
        self.assertNotIn("6.1 結構化資料", self.pb("card", "6", "--type", "應用介面"))

    def test_flow_uses_its_own_state_folder_and_name(self):
        self.pb("start", "demo", "--type", "行銷網站")
        self.assertTrue((self.project / ".website" / "active.json").is_file())
        self.assertIn("進行中的作品（web-playbook）", self.pb("hook", "session"))
        self.assertIn("G0.1", self.pb("advance", ok=False))
        self.pb("check-off", "G0.1", "G0.2")
        self.assertIn("1 內容與架構", self.pb("advance"))
        self.pb("done")
        self.assertEqual(self.pb("hook", "prompt"), "")

    def test_similar_finds_the_matching_entry(self):
        self.assertIn("S0-01", self.pb("similar", "公開頁面和後台分開放").splitlines()[0])


    def _first_tool(self, status):
        import csv
        with open(self.home / "data" / "tools.csv", encoding="utf-8") as f:
            return next(t for t in csv.DictReader(f) if t["狀態"] == status)

    def test_tool_runs_drive_review(self):
        t = self._first_tool("待試")
        self.pb("run-log", "--entries", t["id"], "--result", "有效")
        self.pb("run-log", "--entries", t["id"], "--result", "有效")
        self.assertIn(t["id"], self.pb("review"))

    def test_open_items_need_test_method_and_recheck(self):
        import csv
        path = self.home / "data" / "tools.csv"
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        tid = next(r["id"] for r in rows if r["狀態"] == "待試")
        for r in rows:
            if r["id"] == tid:
                r["測試方法"] = ""
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), quoting=csv.QUOTE_ALL, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        self.assertIn(f"{tid}: 待試 needs 測試方法", self.pb("check", ok=False))


    def test_trials_caps_each_stage_and_drops_logged_items(self):
        import json, re
        stype = next(iter(json.loads((self.home / "data" / "stages.json").read_text(encoding="utf-8"))["asset_types"]))
        self.pb("start", "trial-demo", "--type", stype)
        out = self.pb("trials")
        for block in out.split("\n## ")[1:]:
            self.assertLessEqual(block.count("- [ ] **"), 3, block)
        first = re.search(r"- \[ \] \*\*([A-Z]+-\d+)\*\*", out)
        if first:
            self.pb("run-log", "--entries", first[1], "--result", "有效", "--name", "trial-demo")
            self.assertNotIn(f"**{first[1]}**", self.pb("trials"))
        if out.count("- [ ] **") > 1:
            self.assertIn("排定要測", self.pb("done", "trial-demo"))


    def _golden(self):
        import json
        return json.loads((REPO / "tests" / "golden_briefs.json").read_text(encoding="utf-8"))

    def test_golden_briefs_pick_the_right_items(self):
        for c in self._golden()["cases"]:
            out = self.pb("plan", c["need"], *(["--type", c["type"]] if c.get("type") else []))
            first = out.split("## 方案 2")[0]
            for i in c["must"]:
                self.assertIn(i + " ", first, f"「{c['need']}」的第一個方案少了 {i}")
            self.assertNotIn("〔避開", out)
            self.assertNotIn("〔未採用", out)

    def test_golden_briefs_three_steps(self):
        """need → facets (step 1) → recipe (step 2) → ids (step 3, checked above)."""
        for c in self._golden()["cases"]:
            if c.get("facets"):
                sug = self.pb("facets", "--suggest", c["need"])
                for f in c["facets"]:
                    self.assertIn(f, sug, f"「{c['need']}」推測的分面少了 {f}")
            if c.get("recipe"):
                out = self.pb("plan", c["need"], *(["--type", c["type"]] if c.get("type") else []))
                self.assertIn(f"## 方案 1：{c['recipe']} ", out, f"「{c['need']}」的第一個方案不是 {c['recipe']}")

    def test_tags_are_callable_and_latin_synonyms_match_whole_words(self):
        out = self.pb("facets", "--audit")
        rate = int(out.split("可調用率")[1].split("：")[1].split("%")[0])
        self.assertGreaterEqual(rate, 95, out[:400])
        self.assertIn("缺工作項目：0", out)
        self.assertIn("標籤自相衝突：0", out)
        self.assertNotIn("平台=IG", self.pb("facets", "--suggest", "redesign the company site"))
        self.assertIn("平台=IG", self.pb("facets", "--suggest", "發 IG 貼文"))

    def test_web_spec_from_page_type_style_and_named_dimension(self):
        out = self.pb("spec", "--from", "定價頁改版，要新粗獷風，要通過無障礙")
        self.assertIn("推測：媒材 網站；場景 定價頁；風格 新粗獷", out)
        self.assertIn("| 陰影模糊px | 0 | 風格：新粗獷 |", out)
        self.assertIn("| 方案數 | 2–3 | 場景：定價頁 |", out)
        self.assertIn("焦點可見（指定（整個維度））", out)
        self.assertIn("風格=玻璃擬態", self.pb("facets", "--suggest", "做一個 glassmorphism 的卡片"))

    def test_shared_tags_are_identical_across_books(self):
        others = [REPO.parent / f"{b}-playbook" / "data" / "shared.json" for b in ("production", "marketing", "web", "engineering")]
        for o in others:
            if o.is_file():
                self.assertEqual((REPO / "data" / "shared.json").read_bytes(), o.read_bytes(), f"copy data/shared.json to {o.parent.parent.name}")
        self.assertIn("風格=新粗獷", self.pb("facets", "--suggest", "新粗獷風的活動"))

    def test_rules_file_leaves_items_out(self):
        c = self._golden()["cases"][0]
        rules = self.tmp / "rules.txt"
        rules.write_text("# 樣本規則\nid=" + c["must"][0] + "\n", encoding="utf-8")
        out = self.pb("plan", c["need"], "--rules", str(rules))
        self.assertIn("排除：" + c["must"][0], out)

    def test_saved_plan_shows_in_brief_and_done(self):
        g = self._golden()
        self.pb("start", "demo", "--type", g["start_type"])
        self.assertIn("已把方案 1", self.pb("plan", g["save_need"], "--save"))
        self.assertIn("方案項目：", self.pb("card", g["brief_stage"], "--brief"))
        self.assertIn("方案裡用過、還沒記結果的項目", self.pb("done"))

    def test_bench_lists_desk_items_and_logs_them(self):
        out = self.pb("bench", "--batch", "3")
        self.assertIn("桌上試驗", out)
        first = out.split("**")[1]
        self.pb("run-log", "--bench", "--entries", first, "--result", "有效")
        self.assertNotIn("**" + first + "**", self.pb("bench", "--batch", "500"))


    def test_facets_suggest_expand_and_tone(self):
        self.assertIn("平台=IG Reels", self.pb("facets", "--suggest", "45 秒 IG Reels，質感 premium，要留名單"))
        self.assertIn("調性=安靜高級", self.pb("facets", "--suggest", "要有質感 premium 一點"))
        out = self.pb("plan", "海外投資說明", "--facets", "目的=信任建立；產業=金融保險")
        line = next(l for l in out.splitlines() if l.startswith("推測調性"))
        self.assertIn("權威專業", line)
        self.assertNotIn("可愛", line)
        self.assertIn("提醒：產業=金融保險 建議避開「可愛」", self.pb("plan", "海外投資說明", "--facets", "產業=金融保險；調性=可愛"))

    def test_unknown_facet_value_fails_check(self):
        import csv as _csv
        p = self.home / "data" / "entries.csv"
        rows = list(_csv.DictReader(open(p, encoding="utf-8")))
        rows[0]["情境"] = "目的=不存在的值"
        w = _csv.DictWriter(open(p, "w", encoding="utf-8", newline=""), fieldnames=list(rows[0]), quoting=_csv.QUOTE_ALL, lineterminator="\n")
        w.writeheader(); w.writerows(rows)
        self.assertIn("不在 facets.json", self.pb("check", ok=False))

    def test_web_spec_card_shares_page_values_and_warns_preset_conflicts(self):
        import json
        card = {"頁面": "t", "調性": "安靜高級", "全頁": {"頁面模式": "說服"},
                "區塊": [{"編號": 1, "名稱": "首屏", "區塊類型": "首屏", "版型網格": "不對稱分欄"},
                         {"編號": 2, "名稱": "預約", "區塊類型": "表單", "影像處理": ["影片背景"]}]}
        p = self.tmp / "web.json"; p.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
        out = self.pb("spec", str(p))
        for part in ("## 一、設計提示詞", "## 二、Token 與實作規格", "## 審查對照表", "- 全部區塊共用"):
            self.assertIn(part, out)
        self.assertIn("影像處理=影片背景（指定）和 效能=LCP ≤ 2.5 秒（預設）衝突", out)
        self.assertIn("grid-template-columns: 5fr 7fr", out)
        self.assertIn("不在語彙裡", self.pb("spec", str(p).replace("web.json", "bad.json"), ok=False) if
                      (self.tmp / "bad.json").write_text(json.dumps({**card, "區塊": [{"編號": 1, "版型網格": "九宮格"}]},
                                                                     ensure_ascii=False), encoding="utf-8") else "")
        self.assertIn('"區塊"', self.pb("spec", "--template"))


if __name__ == "__main__":
    unittest.main()
