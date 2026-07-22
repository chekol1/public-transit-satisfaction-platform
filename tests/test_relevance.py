from transit_satisfaction.nlp.relevance import is_transit_related


def test_relevant_text_detected():
    assert is_transit_related("The bus was late again this morning") is True


def test_relevant_text_detected_case_insensitive_and_hashtag():
    assert is_transit_related("Loving the new #BART cars") is True


def test_irrelevant_text_rejected():
    assert is_transit_related("I made pasta for dinner tonight") is False


def test_empty_text_is_not_relevant():
    assert is_transit_related("") is False
    assert is_transit_related("   ") is False


def test_substring_inside_unrelated_word_does_not_match():
    # "train" should not match inside an unrelated word like "training"
    assert is_transit_related("I finished my training course today") is False
