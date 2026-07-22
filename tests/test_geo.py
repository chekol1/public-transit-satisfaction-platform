from transit_satisfaction.geo.geo_tagger import GeoTagger


def test_tag_finds_known_municipality():
    tagger = GeoTagger(municipalities=["Tel Aviv", "Haifa"])
    assert tagger.tag("Bus delayed again in Tel Aviv this morning") == "Tel Aviv"


def test_tag_is_case_insensitive():
    tagger = GeoTagger(municipalities=["Tel Aviv"])
    assert tagger.tag("stuck on a bus in tel aviv") == "Tel Aviv"


def test_tag_returns_none_when_no_match():
    tagger = GeoTagger(municipalities=["Tel Aviv"])
    assert tagger.tag("great ride today") is None
