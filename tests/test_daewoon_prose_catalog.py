from domains.daewoon.prose_catalog import age_band, iter_keys, prompt_facts


def test_catalog_covers_37800_closed_keys():
    keys = list(iter_keys())
    assert len(keys) == 37800
    assert len(set(keys)) == 37800


def test_age_bands_follow_decade_end():
    assert age_band(8) == "school"
    assert age_band(9) == "school"
    assert age_band(10) == "span"
    assert age_band(18) == "span"
    assert age_band(19) == "adult"


def test_pair_front_mentions_next_decade_without_naming_terms():
    facts = prompt_facts("목|신강|none|甲子|school")
    assert facts["paired"] is True
    assert facts["next_ganji"] == "乙丑"
    solo = prompt_facts("목|신강|none|乙丑|school")
    assert solo["paired"] is False
