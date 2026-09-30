"""Regression tests for the bounded cash-flow detail page."""

import pytest

from repositories.cash_flow_repo import PAGE_SIZE, paginate_movements


def _movements(count):
    return [
        {"source_id": i, "date": f"2026-10-{(i % 28) + 1:02d}", "doc_number": f"M-{i}"}
        for i in range(1, count + 1)
    ]


@pytest.mark.parametrize("count,expected_pages,expected_last", [
    (0, 1, 0), (1, 1, 1), (30, 1, 30), (31, 2, 1),
    (60, 2, 30), (61, 3, 1),
])
def test_cash_flow_detail_page_boundaries(count, expected_pages, expected_last):
    rows = _movements(count)
    result = paginate_movements(rows, page=expected_pages)
    assert result["page_size"] == PAGE_SIZE == 30
    assert result["total"] == count
    assert result["total_pages"] == expected_pages
    assert len(result["items"]) == (expected_last if count else 0)


def test_cash_flow_detail_pages_are_bounded_and_contiguous():
    rows = _movements(61)
    first = paginate_movements(rows, page=1)
    second = paginate_movements(rows, page=2)
    last = paginate_movements(rows, page=3)

    assert len(first["items"]) == 30
    assert len(second["items"]) == 30
    assert len(last["items"]) == 1
    assert first["items"][-1]["source_id"] == 30
    assert second["items"][0]["source_id"] == 31
    assert second["items"][-1]["source_id"] == 60
    assert last["items"][0]["source_id"] == 61
    assert not set(r["source_id"] for r in first["items"]) & set(r["source_id"] for r in second["items"])


def test_cash_flow_detail_page_clamps_invalid_and_out_of_range_values():
    rows = _movements(31)
    assert paginate_movements(rows, page=0)["page"] == 1
    assert paginate_movements(rows, page="invalid")["page"] == 1
    result = paginate_movements(rows, page=999)
    assert result["page"] == 2
    assert result["items"][0]["source_id"] == 31
