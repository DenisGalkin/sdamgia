from app.main import parse_answer, parse_variant


def test_parse_variant_preserves_number_and_task_id():
    html = """
    <div class="prob_list">
      <div class="prob_num">7</div>
      <div class="prob_view"><span class="prob_nums">
        Тип 7 № <a href="/problem?id=12345">12345</a>
      </span></div>
    </div>
    <div class="prob_list">
      <div class="prob_num">8</div>
      <span class="prob_nums"><a href="https://rus-ege.sdamgia.ru/problem?id=67890">67890</a></span>
    </div>
    """
    assert parse_variant(html) == [
        {"number": "7", "task_id": "12345", "url": "https://rus-ege.sdamgia.ru/problem?id=12345"},
        {"number": "8", "task_id": "67890", "url": "https://rus-ege.sdamgia.ru/problem?id=67890"},
    ]


def test_parse_variant_handles_sdamgia_legacy_unclosed_markup():
    html = """
    <div class="prob_list"><div class="prob_num">1</div>
      <div><span class="prob_nums"><a href="/problem?id=101">101</a></span>
    <div class="prob_list"><div class="prob_num">2</div>
      <div><span class="prob_nums"><a href="/problem?id=202">202</a></span>
    <div class="prob_list"><div class="prob_num">3</div>
      <div><span class="prob_nums"><a href="/problem?id=303">303</a></span>
    """
    assert [(item["number"], item["task_id"]) for item in parse_variant(html)] == [
        ("1", "101"),
        ("2", "202"),
        ("3", "303"),
    ]


def test_parse_answer_prefers_canonical_answer_block():
    html = """
      <div class="prob_maindiv">
      <div><b>Ответ: wrong handbook example</b></div>
      <div class="solution"><span>Ответ: wrong solution text</span></div>
      <div class="answer" style="display:none"><span>Ответ: 315&nbsp;</span></div>
    </div>
    """
    assert parse_answer(html) == "315"


def test_parse_answer_supports_solution_fallback():
    html = '<div class="prob_maindiv"><div class="solution"><span>Ответ: 0.25</span></div></div>'
    assert parse_answer(html) == "0.25"
