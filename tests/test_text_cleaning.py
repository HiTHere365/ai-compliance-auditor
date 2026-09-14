"""Tests for the PDF text repair helpers in src/setup_databases.py.

Importing setup_databases pulls in the LangChain loader modules but performs
no I/O and builds no databases; the embedding model is only loaded when
DatabaseSetup is instantiated, which these tests never do.
"""

import fitz
import pytest

import setup_databases
from setup_databases import (
    CONTROL_ID_PATTERN,
    DatabaseSetup,
    _clean_spaced_text,
    _load_pdf,
    load_document,
)


class TestCleanSpacedText:
    def test_character_spaced_word_is_collapsed(self):
        assert _clean_spaced_text("S e c u r i t y") == "Security"

    def test_double_space_marks_word_boundary(self):
        assert _clean_spaced_text("O W A S P  T o p  1 0") == "OWASP Top 10"

    def test_normal_text_is_unchanged(self):
        text = "Prompt injection is the top risk for LLM applications."
        assert _clean_spaced_text(text) == text

    def test_normal_text_with_single_letter_words_is_unchanged(self):
        text = "I am a user of the API and I need a key."
        assert _clean_spaced_text(text) == text

    def test_mixed_lines(self):
        text = (
            "LLM01: Prompt Injection\n"
            "P r o m p t  I n j e c t i o n\n"
            "A description of the risk follows."
        )
        expected = (
            "LLM01: Prompt Injection\n"
            "Prompt Injection\n"
            "A description of the risk follows."
        )
        assert _clean_spaced_text(text) == expected

    def test_empty_string(self):
        assert _clean_spaced_text("") == ""

    def test_control_characters_are_stripped(self):
        assert _clean_spaced_text("Risk\x00 Manage\x0cment") == "Risk Management"

    def test_tabs_and_newlines_are_preserved(self):
        assert _clean_spaced_text("alpha\tbeta\ngamma") == "alpha\tbeta\ngamma"

    def test_leading_bullet_glyph_is_removed(self):
        assert _clean_spaced_text("•L Validate all inputs") == "Validate all inputs"

    def test_trailing_glyph_before_newline_is_removed(self):
        assert _clean_spaced_text("sensitive dataL\nnext line") == "sensitive data\nnext line"


def _write_pdf(path, pages):
    """Create a small PDF with one entry per page; empty strings give blank pages."""
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text, fontname="helv", fontsize=11)
    doc.save(str(path))
    doc.close()


class _FakePage:
    def __init__(self, blocks):
        self._blocks = blocks

    def get_text(self, kind):
        assert kind == "dict"
        return {"blocks": self._blocks}


def _span(text, font):
    return {"text": text, "font": font}


def _text_block(*spans):
    return {"lines": [{"spans": list(spans)}]}


class TestLoadPdf:
    def test_reads_text_pages_and_skips_blank_pages(self, tmp_path):
        pdf = tmp_path / "sample.pdf"
        _write_pdf(pdf, ["First page text", "", "Third page text"])

        docs = _load_pdf(str(pdf))

        assert [d.metadata["page"] for d in docs] == [0, 2]
        assert "First page text" in docs[0].page_content
        assert "Third page text" in docs[1].page_content
        assert all(d.metadata["source"] == str(pdf) for d in docs)

    def test_type3_spans_are_dropped_when_other_text_exists(self, monkeypatch):
        page = _FakePage([
            {"image": b""},  # image block without lines is ignored
            _text_block(_span("L", "Type3 (580 0 R)"), _span("Validate inputs", "Calibri")),
            _text_block(_span("g", "Type3 (580 0 R)")),
        ])
        monkeypatch.setattr(setup_databases.fitz, "open", lambda path: [page])

        docs = _load_pdf("fake.pdf")

        assert len(docs) == 1
        assert docs[0].page_content == "Validate inputs"

    def test_page_set_entirely_in_type3_fonts_is_kept(self, monkeypatch):
        page = _FakePage([
            _text_block(_span("OWASP Top 10", "Type3 (580 0 R)")),
            _text_block(_span("for LLM Applications", "Type3 (1024 0 R)")),
        ])
        monkeypatch.setattr(setup_databases.fitz, "open", lambda path: [page])

        docs = _load_pdf("fake.pdf")

        assert len(docs) == 1
        assert docs[0].page_content == "OWASP Top 10\nfor LLM Applications"


class TestLoadDocument:
    def test_txt_file_is_loaded_and_cleaned(self, tmp_path):
        f = tmp_path / "note.txt"
        f.write_text("Overview\nD a t a  R e t e n t i o n\n", encoding="utf-8")

        docs = load_document(str(f))

        assert len(docs) == 1
        assert docs[0].page_content == "Overview\nData Retention\n"

    def test_unsupported_extension_returns_empty_list(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b\n", encoding="utf-8")
        assert load_document(str(f)) == []

    def test_missing_file_returns_empty_list(self, tmp_path):
        assert load_document(str(tmp_path / "missing.pdf")) == []


class TestCapabilityDocDiscovery:
    def test_finds_files_in_expected_subdirectories(self, tmp_path, monkeypatch):
        (tmp_path / "txt_files").mkdir()
        (tmp_path / "txt_files" / "alpha.txt").write_text("alpha body", encoding="utf-8")
        (tmp_path / "txt_files" / "ignored.csv").write_text("x", encoding="utf-8")
        (tmp_path / "md_files").mkdir()  # empty subdirectory is skipped
        monkeypatch.setitem(setup_databases.CAPABILITY_DB, "docs_dir", str(tmp_path))

        # Bypass __init__ so no embedding model is loaded.
        setup = DatabaseSetup.__new__(DatabaseSetup)
        docs = setup.load_capability_docs()

        assert len(docs) == 1
        assert docs[0].page_content == "alpha body"
        assert docs[0].metadata["document_type"] == "capability"
        assert docs[0].metadata["file_path"].endswith("alpha.txt")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("LLM01:2025 Prompt Injection", "LLM01:2025"),
        ("LLM07 System Prompt Leakage", "LLM07"),
        ("Suggested action GV-1.2 applies here", "GV-1.2"),
        ("No identifier in this chunk", None),
    ],
)
def test_control_id_pattern(text, expected):
    match = CONTROL_ID_PATTERN.search(text)
    assert (match.group() if match else None) == expected
