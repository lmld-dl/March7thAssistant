import unittest
from unittest.mock import Mock, patch

from tests.test_tasks.test_currency_wars_settlement import load_currency_wars


class TestCurrencyWarsStart(unittest.TestCase):
    def setUp(self):
        self.module = load_currency_wars()
        self.war = self.module.CurrencyWars()
        self.war.choose_level = Mock(return_value=True)
        self.module.cfg.currencywars_type = 'normal'
        self.module.auto.click_element.return_value = False
        self.module.auto.find_element.side_effect = self.find_element
        self.module.auto.click_element_with_pos.side_effect = self.click
        self.frame = 0
        self.state = 'ready'
        self.ignored_clicks = 0
        self.clicks = 0
        self.loading_frames = 0
        self.missing_button_frames = set()
        self.entry_marker = 'text'
        sleep = patch.object(self.module.time, 'sleep', side_effect=self.advance_frame)
        sleep.start()
        self.addCleanup(sleep.stop)

    def find_element(self, target, kind, *args, **kwargs):
        if target == '开始对局' and self.state == 'ready' and self.frame not in self.missing_button_frames:
            return (1500 + self.frame, 950, 200, 50)
        if self.state == 'started':
            if self.entry_marker == 'text' and isinstance(target, tuple) and '下一步' in target:
                return (800, 900, 200, 50)
            if self.entry_marker == 'image' and kind == 'image':
                return (3, 37, 104, 57)
        return None

    def click(self, position):
        self.assertEqual(self.state, 'ready', 'Must not click during loading or after entry')
        self.assertEqual(position[0], 1500 + self.frame, 'Must not reuse stale coordinates')
        self.clicks += 1
        if self.ignored_clicks:
            self.ignored_clicks -= 1
        else:
            self.state = 'loading' if self.loading_frames else 'started'
        return True

    def advance_frame(self, seconds):
        self.frame += 1
        if self.state == 'loading':
            self.loading_frames -= 1
            if self.loading_frames == 0:
                self.state = 'started'

    def test_ignored_click_is_retried_and_entry_is_verified(self):
        self.ignored_clicks = 1
        self.assertTrue(self.war.start_war())
        self.assertEqual(self.clicks, 2)
        self.assertEqual(self.state, 'started')
        self.war.choose_level.assert_called_once_with(1)

    def test_slow_loading_does_not_cause_duplicate_clicks(self):
        self.loading_frames = 8
        self.assertTrue(self.war.start_war('overclock'))
        self.assertEqual(self.clicks, 1)
        self.assertEqual(self.state, 'started')
        self.module.screen.change_to.assert_any_call('currency_wars_mode_select_overclock')

    def test_transient_button_ocr_miss_is_not_treated_as_entry(self):
        self.missing_button_frames = {0, 1, 2}
        self.assertTrue(self.war.start_war())
        self.assertEqual(self.clicks, 1)
        self.assertGreaterEqual(self.frame, 3)
        self.assertEqual(self.state, 'started')

    def test_main_board_is_also_valid_entry_evidence(self):
        self.entry_marker = 'image'
        self.assertTrue(self.war.start_war())
        self.assertEqual(self.clicks, 1)

    def test_persistent_start_button_stops_after_three_clicks(self):
        self.ignored_clicks = 100
        self.war.loop = Mock(side_effect=AssertionError('Entered battle loop before start was confirmed'))
        with self.assertRaisesRegex(RuntimeError, '未确认进入对局'):
            self.war.start()
        self.assertEqual(self.clicks, 3)
        self.assertEqual(self.frame, 30)
        self.war.loop.assert_not_called()
        self.module.Base.send_notification_with_screenshot.assert_not_called()
        self.module.auto.get_single_line_text.assert_not_called()

    def test_missing_button_and_unknown_screen_time_out_without_clicks(self):
        self.state = 'unknown'
        with self.assertRaises(RuntimeError):
            self.war.start_war()
        self.assertEqual(self.clicks, 0)
        self.assertEqual(self.frame, 30)

    def test_loading_without_entry_evidence_times_out(self):
        self.loading_frames = 100
        with self.assertRaises(RuntimeError):
            self.war.start_war()
        self.assertEqual(self.clicks, 1)

    def test_level_selection_failure_does_not_attempt_start(self):
        self.war.choose_level.return_value = False
        self.assertFalse(self.war.start_war())
        self.assertFalse(any(
            call.args and call.args[0] == "开始对局"
            for call in self.module.auto.find_element.call_args_list
        ))
        self.module.auto.press_key.assert_not_called()
        self.assertEqual(self.clicks, 0)

    def test_world_interaction_enters_before_the_phone_menu(self):
        def find_element(target, kind, *args, **kwargs):
            if target == "货币战争":
                return ((900, 520), (1100, 560))
            return TestCurrencyWarsStart.find_element(self, target, kind, *args, **kwargs)

        self.module.auto.find_element.side_effect = find_element
        self.module.screen.check_screen.side_effect = lambda name: name == "currency_wars_homepage"

        self.assertTrue(self.war.start_war())

        world_calls = [
            call for call in self.module.auto.find_element.call_args_list
            if call.args and call.args[0] == "货币战争"
        ]
        self.assertEqual(len(world_calls), 1)
        origin_x, origin_y, width, height = world_calls[0].kwargs["crop"]
        # 中央交互提示。左侧任务栏和右侧队伍栏不在这块里。
        self.assertGreaterEqual(origin_x, 0.2)
        self.assertLessEqual(origin_x + width, 0.85)
        self.assertGreaterEqual(origin_y, 0.25)
        self.module.auto.press_key.assert_any_call("f")
        self.module.screen.change_to.assert_any_call("currency_wars_mode_select")


if __name__ == '__main__':
    unittest.main()
