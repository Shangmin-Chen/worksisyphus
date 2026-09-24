"""Unit tests for HTML pre-cleaner and noise removal."""

from __future__ import annotations

from worksisyphus.adapters.outbound.ingestion.pre_cleaner import PreCleaner, clean_html


def test_clean_html_removes_scripts_and_styles() -> None:
    raw = """
    <html>
        <head>
            <style>body { color: red; }</style>
            <script>console.log("tracking pixel");</script>
        </head>
        <body>
            <nav><a href="/">Home</a></nav>
            <h1>Software Engineer</h1>
            <p>We are hiring a backend engineer.</p>
            <footer>Copyright 2026</footer>
        </body>
    </html>
    """
    cleaned = clean_html(raw)
    assert "body { color: red; }" not in cleaned
    assert "tracking pixel" not in cleaned
    assert "Home" not in cleaned
    assert "Copyright 2026" not in cleaned
    assert "Software Engineer" in cleaned
    assert "We are hiring a backend engineer." in cleaned


def test_clean_html_formats_lists_and_paragraphs() -> None:
    raw = """
    <div>
        <p>Requirements:</p>
        <ul>
            <li>Experience with Python &amp; Go.</li>
            <li>Solid knowledge of Kubernetes.</li>
        </ul>
    </div>
    """
    cleaned = clean_html(raw)
    assert "Requirements:" in cleaned
    assert "• Experience with Python & Go." in cleaned
    assert "• Solid knowledge of Kubernetes." in cleaned


def test_clean_html_unescapes_entities_and_unicode_spaces() -> None:
    raw = "Stripe&nbsp;&amp;&nbsp;Co.&nbsp;--&nbsp;&lt;special&gt; &#39;metrics&#39;"
    cleaned = clean_html(raw)
    assert cleaned == "Stripe & Co. -- <special> 'metrics'"


def test_clean_plain_text_passthrough() -> None:
    cleaner = PreCleaner()
    plain = "Just a standard plain text job description without any HTML tags."
    assert cleaner.clean(plain) == plain
