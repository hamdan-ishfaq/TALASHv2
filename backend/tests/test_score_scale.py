"""Tests for research score 0–10 vs legacy 0–100 storage."""
from app.utils.scores import research_strength_for_persist, research_strength_on_ten


def test_research_on_ten_from_legacy_hundred():
    assert research_strength_on_ten(65.0) == 6.5
    assert research_strength_on_ten(100.0) == 10.0


def test_research_on_ten_already_ten_scale():
    assert research_strength_on_ten(6.2) == 6.2
    assert research_strength_on_ten(10.0) == 10.0


def test_persist_scales_down():
    assert research_strength_for_persist(82.0) == 8.2
    assert research_strength_for_persist(100.0) == 10.0
