"""货币战争挪人与奖励滑动的纯逻辑：不接触窗口、鼠标或 OCR 引擎。"""
import math

import pytest

from tests.test_tasks.test_currency_wars_settlement import load_currency_wars


def test_reward_path_keeps_every_icon_center_and_skips_dense_fill():
    module = load_currency_wars()
    centers = module.reward_icon_pixel_centers()
    path = module.build_reward_collect_path(centers)
    assert len(centers) == 18
    assert len(path) == len(centers)
    for center in centers:
        assert min(math.hypot(center[0] - point[0], center[1] - point[1]) for point in path) < 1
    dense = module.build_reward_collect_path(centers, step_px=50)
    assert len(dense) > len(path)
    assert module.build_reward_collect_path([]) == []
    with pytest.raises(ValueError):
        module.build_reward_collect_path(centers, step_px=0)


def _movable(module):
    war = module.CurrencyWars()
    war.forward_pos = [(0.1, 0.2, 0.05, 0.05)]
    war.prepare_pos = [(0.3, 0.4, 0.05, 0.05)]
    war.forward_characters = [module.CurrencyWarsCharacter(None, None)]
    module.auto.find_element.return_value = ((1, 2), (3, 4))
    module.auto.click_element_with_pos.return_value = True
    module.auto.mouse_up.return_value = None
    return war


def test_plain_move_does_not_sleep_on_unrelated_title_text(monkeypatch):
    module = load_currency_wars()
    war = _movable(module)
    war.prepare_characters = [module.CurrencyWarsCharacter("乱破", "all")]
    module.auto.get_single_line_text.return_value = "备战"
    sleeps = []
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleeps.append(seconds))
    assert war.move_character(("prepare", 0), ("forward", 0)) is True
    assert sleeps == [
        module.CHARACTER_DRAG_PICKUP_SECONDS,
        module.CHARACTER_DRAG_ARRIVE_SECONDS,
        module.CHARACTER_DRAG_RELEASE_SECONDS,
    ]
    assert module.auto.get_single_line_text.call_count == 1
    assert module.POPUP_AFTER_HANDLE_SECONDS not in sleeps


def test_expected_popup_polls_briefly_then_stops(monkeypatch):
    module = load_currency_wars()
    war = module.CurrencyWars()
    module.auto.get_single_line_text.return_value = "货币战争"
    sleeps = []
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleeps.append(seconds))
    war.check_festival_star_popup(expect_popup=True)
    assert sleeps == [module.POPUP_POLL_SECONDS] * (module.POPUP_APPEAR_POLLS - 1)
    assert module.auto.get_single_line_text.call_count == module.POPUP_APPEAR_POLLS
    module.auto.click_element.assert_not_called()


def test_visible_partner_popup_is_handled_once(monkeypatch):
    module = load_currency_wars()
    war = module.CurrencyWars()
    module.auto.get_single_line_text.side_effect = ["选择伙伴", None]
    sleeps = []
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleeps.append(seconds))
    war.check_festival_star_popup(expect_popup=True)
    assert sleeps.count(module.POPUP_AFTER_HANDLE_SECONDS) == 1
    assert module.POPUP_POLL_SECONDS not in sleeps
    assert module.auto.click_element.call_count == 3
    assert any("选择伙伴" in str(call.args[0]) for call in module.log.info.call_args_list)


def test_star_character_still_waits_for_the_popup_to_appear(monkeypatch):
    module = load_currency_wars()
    war = _movable(module)
    war.prepare_characters = [module.CurrencyWarsCharacter("姬子·启行", "forward")]
    module.auto.get_single_line_text.return_value = None
    sleeps = []
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleeps.append(seconds))
    assert war.move_character(("prepare", 0), ("forward", 0)) is True
    assert module.CHARACTER_POPUP_APPEAR_SECONDS in sleeps
    assert sleeps.count(module.POPUP_POLL_SECONDS) == module.POPUP_APPEAR_POLLS - 1
    assert module.POPUP_AFTER_HANDLE_SECONDS not in sleeps
