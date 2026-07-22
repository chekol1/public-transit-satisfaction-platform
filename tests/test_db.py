import mongomock
from transit_satisfaction.db.repository import SatisfactionRecord, SatisfactionRepository


def _repo() -> SatisfactionRepository:
    return SatisfactionRepository(client=mongomock.MongoClient())


def test_add_and_find_all():
    with _repo() as repo:
        record_id = repo.add(
            SatisfactionRecord(text="great ride", satisfaction_score=0.9, label="satisfied")
        )
        assert record_id

        results = list(repo.find_all())
        assert len(results) == 1
        assert results[0]["text"] == "great ride"


def test_add_many_and_find_by_municipality():
    with _repo() as repo:
        repo.add_many(
            [
                SatisfactionRecord(
                    text="a", satisfaction_score=0.8, label="satisfied", municipality="Tel Aviv"
                ),
                SatisfactionRecord(
                    text="b", satisfaction_score=0.2, label="unsatisfied", municipality="Haifa"
                ),
            ]
        )

        tel_aviv_results = list(repo.find_by_municipality("Tel Aviv"))
        assert len(tel_aviv_results) == 1
        assert tel_aviv_results[0]["text"] == "a"


def test_find_all_respects_limit():
    with _repo() as repo:
        repo.add_many(
            [
                SatisfactionRecord(text=f"tweet {i}", satisfaction_score=0.5, label="satisfied")
                for i in range(5)
            ]
        )
        assert len(list(repo.find_all(limit=2))) == 2
