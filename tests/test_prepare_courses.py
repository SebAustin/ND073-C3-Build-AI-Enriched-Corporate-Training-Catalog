import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepare_courses as pc  # noqa: E402

ROW = {
    "PartitionKey": "company-moodle", "RowKey": "abc", "source": "Company Moodle",
    "title": " Secure APIs ", "description": "Learn things", "instructor": "Eileen Diaz",
    "level": "Intermediate ", "role": "developer", "product": "azure",
    "duration": "45", "rating_count": "12", "rating_average": "4.8", "url": "https://x",
}


def test_clean_row_types_and_normalises_fields():
    entity = pc.clean_row(ROW)

    assert entity["level"] == "intermediate"
    assert entity["title"] == "Secure APIs"
    assert entity["type"] == "Internal"
    assert entity["duration"] == 45.0  # Moodle durations are already hours
    assert entity["duration_text"] == "45"
    assert entity["rating_count"] == 12 and isinstance(entity["rating_count"], int)
    assert entity["rating_average"] == pytest.approx(4.8)


def test_clean_row_does_not_mutate_input():
    original = dict(ROW)
    pc.clean_row(ROW)
    assert ROW == original


def test_clean_row_omits_empty_instructor():
    entity = pc.clean_row({**ROW, "PartitionKey": "ms-learn", "instructor": ""})
    assert "instructor" not in entity
    assert entity["type"] == "Module"


def test_clean_row_rejects_unknown_partition():
    with pytest.raises(pc.CourseDataError, match="Unknown source"):
        pc.clean_row({**ROW, "PartitionKey": "coursera"})


def test_clean_row_rejects_non_numeric_duration():
    with pytest.raises(pc.CourseDataError, match="duration"):
        pc.clean_row({**ROW, "duration": "two hours"})


def test_ms_learn_minutes_become_hours():
    entity = pc.clean_row({**ROW, "PartitionKey": "ms-learn", "duration": "90"})
    assert entity["duration"] == 1.5


def test_udacity_months_become_hours_and_ratings_are_unswapped():
    entity = pc.clean_row({**ROW, "PartitionKey": "ud-learn", "duration": "3 Months ",
                           "rating_count": "4.6 ", "rating_average": "700"})
    assert entity["duration"] == 120.0
    assert entity["duration_text"] == "3 Months"
    assert entity["rating_count"] == 700
    assert entity["rating_average"] == pytest.approx(4.6)


def test_unrated_course_has_no_rating_fields():
    entity = pc.clean_row({**ROW, "PartitionKey": "ud-learn", "duration": "1 month",
                           "rating_count": " ", "rating_average": " "})
    assert "rating_count" not in entity and "rating_average" not in entity


def test_udacity_duration_without_months_is_rejected():
    with pytest.raises(pc.CourseDataError, match="months"):
        pc.clean_row({**ROW, "PartitionKey": "ud-learn", "duration": "12 weeks"})


def test_real_dataset_cleans_to_three_levels(tmp_path):
    source = Path(__file__).resolve().parents[1] / "starter" / "Data" / "courses.csv"
    entities = pc.read_courses(str(source))

    assert len(entities) == 995
    assert {e["level"] for e in entities} == {"beginner", "intermediate", "advanced"}
    assert {e["type"] for e in entities} == {"Module", "Nanodegree", "Internal"}
    assert all(0 < e.get("rating_average", 1) <= 5 for e in entities)
    assert pc.write_csv(entities, str(tmp_path / "out.csv")) == 995


def test_zero_count_course_is_unrated():
    entity = pc.clean_row({**ROW, "rating_count": "0", "rating_average": "0.0"})
    assert entity["rating_count"] == 0
    assert "rating_average" not in entity
