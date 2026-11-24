import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"

EVIDENCE_FILES = ["order_history.json", "docs.json", "roles.json", "changes.json"]
ALLOWED_OUTCOMES = {"finding", "clarify", "undetermined", "controlled_stop", "refuse"}


def load(name):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def all_record_ids():
    ids = []
    for name in EVIDENCE_FILES:
        for record in load(name):
            ids.append(record["id"])
    return ids


def test_record_ids_are_unique():
    ids = all_record_ids()
    assert len(ids) == len(set(ids))


def test_required_evidence_exists_in_data():
    ids = set(all_record_ids())
    for case in load("cases.json"):
        for evidence_id in case["required_evidence"]:
            assert evidence_id in ids, f"{case['case_id']}: {evidence_id} not found"


def test_expected_outcomes_are_valid():
    for case in load("cases.json"):
        assert case["expected_outcome"] in ALLOWED_OUTCOMES, case["case_id"]
