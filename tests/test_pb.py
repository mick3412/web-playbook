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
        shutil.copytree(REPO, self.home, ignore=shutil.ignore_patterns(".git", "__pycache__", "inbox"))
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


if __name__ == "__main__":
    unittest.main()
