from wiki.markdown import SafeMarkdownRenderer


def test_raw_html_is_not_executed():
    html = SafeMarkdownRenderer().render("# Safe\n<script>alert(1)</script>")

    assert "<script" not in html
    assert "alert(1)" in html


def test_unsafe_link_protocols_are_removed():
    html = SafeMarkdownRenderer().render("[bad](javascript:alert(1)) [data](data:text/html,boom)")

    assert "javascript:" not in html
    assert "data:text" not in html
