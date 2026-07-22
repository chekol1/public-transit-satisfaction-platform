from transit_satisfaction.geo.geo_tagger import GeoTagger


def test_tag_matches_bart_station_first():
    tagger = GeoTagger(bart_stations=["Embarcadero"], muni_stops=["Embarcadero & Mission"])
    match = tagger.tag("Stuck at Embarcadero station for 20 minutes")
    assert match.name == "Embarcadero"
    assert match.source == "bart"


def test_tag_falls_back_to_muni_stop():
    tagger = GeoTagger(bart_stations=["Powell St"], muni_stops=["19th Avenue & Holloway St"])
    match = tagger.tag("Bus skipped 19th Avenue & Holloway St again")
    assert match.name == "19th Avenue & Holloway St"
    assert match.source == "muni"


def test_tag_is_case_insensitive():
    tagger = GeoTagger(bart_stations=["Embarcadero"], muni_stops=[])
    match = tagger.tag("stuck at embarcadero this morning")
    assert match.name == "Embarcadero"
    assert match.source == "bart"


def test_tag_falls_back_to_generic_city_mention():
    tagger = GeoTagger(bart_stations=[], muni_stops=[])
    match = tagger.tag("Public transit in San Francisco is a mess today")
    assert match.name == "San Francisco"
    assert match.source == "text"


def test_tag_falls_back_to_user_location_when_text_has_no_match():
    tagger = GeoTagger(bart_stations=[], muni_stops=[])
    match = tagger.tag("The bus was late again", user_location="San Francisco, CA")
    assert match.name == "San Francisco"
    assert match.source == "user_location"


def test_tag_returns_none_when_no_match():
    tagger = GeoTagger(bart_stations=["Embarcadero"], muni_stops=[])
    match = tagger.tag("great ride today", user_location="Chicago, IL")
    assert match is None
