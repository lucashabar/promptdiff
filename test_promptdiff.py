"""promptdiff —— 自检测试。

按语义块比对两版提示词，区分措辞调整、约束增删与结构变动。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import promptdiff  # noqa: E402


class TestPromptDiff(unittest.TestCase):
    def test_constraint_change_is_flagged(self):
        old = "# 角色\n你是助手。\n\n# 约束\n不要编造。\n"
        new = "# 角色\n你是助手。\n\n# 约束\n不要编造。\n必须给出依据。\n"
        r = promptdiff.diff_prompts(old, new)
        self.assertTrue(r["constraint_changes"])

    def test_wording_change_is_not_flagged_as_constraint(self):
        old = "你是助手。\n"
        new = "你是一位助手。\n"
        r = promptdiff.diff_prompts(old, new)
        self.assertEqual(r["summary"]["constraint"], 0)

    def test_no_difference(self):
        text = "你是助手。\n请回答。\n"
        r = promptdiff.diff_prompts(text, text)
        self.assertEqual(r["summary"]["total"], 0)

    def test_deletion_detected(self):
        old = "# 约束\n不要编造。\n"
        new = "# 约束\n"
        r = promptdiff.diff_prompts(old, new)
        self.assertEqual(r["summary"]["total"], 1)
        self.assertEqual(r["changes"][0]["type"], "deleted")

    def test_does_not_merge_automatically(self):
        """防呆：只报告，不自动合并两版。"""
        old = "你是助手。\n"
        new = "你是客服。\n"
        r = promptdiff.diff_prompts(old, new)
        self.assertNotIn("merged", r)
        self.assertEqual(len(r["changes"]), 1)
