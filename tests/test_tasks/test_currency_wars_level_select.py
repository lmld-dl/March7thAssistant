import pytest

pytest.skip('货币战争 S2 用职级确认取代旧的 level_1 徽标循环；1440p 选关不再走 0.95 阈值', allow_module_level=True)

"""货币战争关卡选择：难度 1 徽标的匹配阈值。

实机取证（2560×1440）：整帧缩到 1920 基准图后，正确徽标 level_1.png 的相似度
只有 0.9351。旧阈值 0.95 会把「敌人难度已经是 1」判成没选中，于是继续点已经
消失的下调箭头，循环 100 次（约 2 分钟）后误报「选择敌人难度为1的关卡失败」。
"""
import unittest
import unittest.mock

from tests.test_tasks.test_currency_wars_settlement import load_currency_wars

# 实机实测值，留出余量后作为阈值上限。
REAL_DEVICE_LEVEL_1_SCORE = 0.9351
# 其他难度数字的实测上限（难度 61 时约 0.52），阈值需明显高于它。
WRONG_DIFFICULTY_SCORE = 0.52
# 与 module/screen/screen.py 的界面阈值一致，避免比界面识别更严。
SCREEN_MATCH_THRESHOLD = 0.88


class TestCurrencyWarsLevelSelect(unittest.TestCase):
    def setUp(self):
        self.module = load_currency_wars()
        self.war = self.module.CurrencyWars()
        self.module.cfg.currencywars_rank_difficulty = 'lowest'
        self.module.auto.reset_mock()
        self.image_calls = []
        self.sleep = unittest.mock.patch.object(self.module.time, 'sleep')
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def test_threshold_accepts_real_device_score(self):
        threshold = self.module.CURRENCY_WARS_LEVEL_1_THRESHOLD
        self.assertLessEqual(threshold, REAL_DEVICE_LEVEL_1_SCORE - 0.02)
        self.assertGreater(threshold, WRONG_DIFFICULTY_SCORE + 0.2)
        self.assertGreaterEqual(threshold, SCREEN_MATCH_THRESHOLD)

    def _find_element(self, target, kind, *args, **kwargs):
        if kind == 'crop':
            return ((1248, 1106), (1308, 1147))
        self.image_calls.append((args, kwargs))
        return None

    def test_choose_level_passes_measured_threshold(self):
        def find_element(target, kind, *args, **kwargs):
            if kind == 'crop':
                return ((1248, 1106), (1308, 1147))
            self.image_calls.append((args, kwargs))
            return ((845, 940), (922, 1004))

        self.module.auto.find_element.side_effect = find_element
        self.assertTrue(self.war.choose_level(1))
        self.assertEqual(len(self.image_calls), 1)
        args, _ = self.image_calls[0]
        self.assertEqual(args[0], self.module.CURRENCY_WARS_LEVEL_1_THRESHOLD)
        self.module.auto.click_element_with_pos.assert_not_called()

    def test_choose_level_clicks_down_until_difficulty_one(self):
        remaining = 3
        clicks = []

        def find_element(target, kind, *args, **kwargs):
            nonlocal remaining
            if kind == 'crop':
                return ((1248, 1106), (1308, 1147))
            self.image_calls.append((args, kwargs))
            if remaining == 0:
                return ((845, 940), (922, 1004))
            remaining -= 1
            return None

        self.module.auto.find_element.side_effect = find_element
        self.module.auto.click_element_with_pos.side_effect = lambda pos, cnt=1: clicks.append((pos, cnt))
        self.assertTrue(self.war.choose_level(1))
        self.assertEqual(len(clicks), 3)
        self.assertEqual(len(self.image_calls), 4)

    def test_choose_level_gives_up_after_loop_limit(self):
        self.module.auto.find_element.side_effect = self._find_element
        self.assertFalse(self.war.choose_level(1))
        self.assertEqual(len(self.image_calls), 100)


if __name__ == '__main__':
    unittest.main()
