from __future__ import annotations

from docs_reader.evaluate import (
    cer,
    score_ocr,
    score_record,
    values_match,
    wer,
)


def test_values_match_numbers_and_commas():
    assert values_match(99000, "99,000")
    assert values_match(90.0, "90")
    assert values_match(5.0, 5)
    assert not values_match(90.0, 900.0)


def test_values_match_strings_case_insensitive():
    assert values_match("USD", "usd ")
    assert not values_match("USD", "KRW")


def test_values_match_list_order_insensitive():
    a = [{"d": "A", "q": 1}, {"d": "B", "q": 2}]
    b = [{"d": "B", "q": 2}, {"d": "A", "q": 1}]
    assert values_match(a, b)
    assert not values_match(a, [{"d": "A", "q": 1}])


def test_score_record_statuses():
    gold = {"a": "x", "b": None, "c": 1, "d": "keep"}
    pred = {"a": "x", "b": "hallo", "c": 2, "d": None}
    rs = score_record(pred, gold, keys=["a", "b", "c", "d"])
    st = {o.field: o.status for o in rs.outcomes}
    assert st == {"a": "correct", "b": "hallucinated", "c": "wrong", "d": "missing"}


def test_score_record_metrics_perfect():
    gold = {"a": 1, "b": "x", "c": None}
    rs = score_record(dict(gold), gold, keys=["a", "b", "c"])
    m = rs.metrics()
    assert m["field_accuracy"] == 1.0
    assert m["precision"] == 1.0 and m["recall"] == 1.0 and m["f1"] == 1.0
    assert m["hallucinations"] == 0


def test_score_record_prf():
    gold = {"a": "x", "b": "y", "c": None, "d": "z"}
    pred = {"a": "x", "b": "WRONG", "c": "halluc", "d": None}
    m = score_record(pred, gold, keys=list(gold)).metrics()
    # TP=1(a), FN=wrong(b)+missing(d)=2, FP=wrong(b)+halluc(c)=2
    assert abs(m["precision"] - 1 / 3) < 1e-9
    assert abs(m["recall"] - 1 / 3) < 1e-9
    assert m["hallucinations"] == 1


def test_cer_wer():
    assert cer("hello", "hello") == 0.0
    assert wer("a b c", "a b c") == 0.0
    assert cer("helo", "hello") > 0.0
    # spacing-only differences vanish under CER (spaces removed)
    assert cer("공급자:(주)아크메", "공급자: (주)아크메") == 0.0


def test_score_ocr_shape():
    s = score_ocr("세금계산서", "세금계산서")
    assert s["char_accuracy"] == 1.0 and s["cer"] == 0.0
