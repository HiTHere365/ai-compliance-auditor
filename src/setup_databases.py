"""
Database setup for ai-compliance-auditor.

Creates vector databases for capability documents and all compliance frameworks.
Run this once before using the query tool or compliance assistant.
"""

import os
import re
import logging
from pathlib import Path
from typing import List

import fitz
from langchain_community.document_loaders import (
    Docx2txtLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from scan_groups import FRAMEWORKS, CAPABILITY_DB

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Control identifiers tagged onto framework chunks, e.g. "LLM01:2025" (OWASP)
# or "GV-1.2" (NIST AI 600-1 / AI RMF style).
CONTROL_ID_PATTERN = re.compile(r'\b(?:LLM\d{2}(?::\d{4})?|[A-Z]{1,3}-\d+\.\d+)\b')


def _clean_spaced_text(text: str) -> str:
    """Repair common PDF text-extraction artifacts.

    Strips control characters, removes single-letter bullet glyphs left over
    from symbol fonts, and collapses character-spaced runs ("O W A S P") back
    into words. Text without these artifacts passes through unchanged.
    """
    # Strip PDF control characters (everything except tab, newline, carriage return)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    # Remove PDF bullet glyph artifacts (OWASP uses L, g, Q, and others as bullet chars):
    #   "[non-alpha][letter] text" at line start  -> "text"
    #   "word[UPPERCASE]\n"                       -> "word\n"
    text = re.sub(r'(?m)^[^a-zA-Z0-9\s][A-Za-z] ', '', text)
    text = re.sub(r'(?<=[a-z])[A-Z]\n', '\n', text)
    # Fix character-level spacing artifact: "O W A S P" -> "OWASP"
    # Detects runs separated by double-spaces as word boundaries
    result = []
    for line in text.split('\n'):
        groups = re.split(r' {2,}', line)
        fixed = []
        for group in groups:
            chars = [c for c in group.split(' ') if c.strip()]
            if chars and all(len(c) == 1 for c in chars):
                fixed.append(''.join(chars))
            else:
                fixed.append(group)
        result.append(' '.join(fixed))
    return '\n'.join(result)


def _load_pdf(filepath: str) -> List[Document]:
    """Extract one Document per non-empty page using PyMuPDF.

    Spans set in Type3 fonts are dropped because PDF producers commonly use
    them for bullet and decoration glyphs that extract as stray letters. If a
    page contains no text outside Type3 spans (some PDFs are typeset entirely
    in Type3 fonts), the page is kept unfiltered instead of being discarded.
    """
    doc = fitz.open(filepath)
    documents = []
    for page_num, page in enumerate(doc):
        filtered_lines = []
        all_lines = []
        for block in page.get_text("dict")["blocks"]:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                spans = line["spans"]
                all_parts = [span["text"] for span in spans]
                kept_parts = [
                    span["text"]
                    for span in spans
                    if "Type3" not in span.get("font", "")
                ]
                if all_parts:
                    all_lines.append("".join(all_parts))
                if kept_parts:
                    filtered_lines.append("".join(kept_parts))
        text = "\n".join(filtered_lines)
        if not text.strip():
            text = "\n".join(all_lines)
        if text.strip():
            documents.append(Document(
                page_content=text,
                metadata={"source": filepath, "page": page_num},
            ))
    return documents


def load_document(filepath: str) -> List[Document]:
    """Load a single file based on its extension and normalize its text.

    Shared by the initial build and the incremental updater so both index
    identical text for the same file.
    """
    ext = Path(filepath).suffix.lower()
    try:
        if ext == ".pdf":
            docs = _load_pdf(filepath)
        else:
            if ext == ".docx":
                loader = Docx2txtLoader(filepath)
            elif ext == ".txt":
                loader = TextLoader(filepath, encoding="utf-8")
            elif ext == ".md":
                loader = UnstructuredMarkdownLoader(filepath)
            else:
                logger.warning(f"Unsupported file type: {filepath}")
                return []
            docs = loader.load()
        for doc in docs:
            doc.page_content = _clean_spaced_text(doc.page_content)
        return docs
    except Exception as e:
        logger.error(f"Failed to load {filepath}: {e}")
        return []


class DatabaseSetup:
    def __init__(self, embedding_model: str = "all-mpnet-base-v2"):
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info("Embedding model ready")

    def load_file(self, filepath: str) -> List[Document]:
        """Load a single file based on its extension."""
        return load_document(filepath)

    def load_capability_docs(self) -> List[Document]:
        """Load all capability documents from all supported subdirectories."""
        docs_path = Path(CAPABILITY_DB["docs_dir"])
        documents = []

        subdir_map = {
            "pdf_files": ".pdf",
            "docx_files": ".docx",
            "txt_files": ".txt",
            "md_files": ".md",
        }

        for subdir, ext in subdir_map.items():
            subdir_path = docs_path / subdir
            if not subdir_path.exists():
                continue
            files = list(subdir_path.glob(f"*{ext}"))
            if not files:
                continue
            for f in files:
                docs = self.load_file(str(f))
                for doc in docs:
                    doc.metadata.update({"document_type": "capability", "file_path": str(f)})
                documents.extend(docs)
            logger.info(f"Loaded {len(files)} {ext} files from {subdir}/")

        logger.info(f"Total capability documents loaded: {len(documents)}")
        return documents

    def build_capability_db(self):
        """Build the capability vector database."""
        logger.info("Building capability database...")
        documents = self.load_capability_docs()

        if not documents:
            logger.error("No capability documents found. Check capability_docs/ subdirectories.")
            return None

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CAPABILITY_DB["chunk_size"],
            chunk_overlap=CAPABILITY_DB["chunk_overlap"],
            separators=["\n## ", "\n### ", "\n\n", "\n", " "],
        )
        chunks = splitter.split_documents(documents)
        logger.info(f"Created {len(chunks)} capability chunks")

        db = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=CAPABILITY_DB["db_dir"],
            collection_name=CAPABILITY_DB["collection"],
        )
        logger.info(f"Capability database built at {CAPABILITY_DB['db_dir']}")
        return db

    def build_framework_db(self, framework_key: str):
        """Build the vector database for a single compliance framework."""
        config = FRAMEWORKS[framework_key]
        source = config["source_doc"]

        if not os.path.exists(source):
            logger.warning(f"Framework document not found, skipping: {source}")
            return None

        logger.info(f"Building {config['name']} database...")
        documents = self.load_file(source)

        if not documents:
            logger.error(f"Could not load {source}")
            return None

        for doc in documents:
            doc.metadata.update({
                "framework": framework_key,
                "framework_name": config["name"],
                "group": config["group"],
            })

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=config["chunk_size"],
            chunk_overlap=config["chunk_overlap"],
            separators=["\n### ", "\n## ", "\n\n", "\n", " "],
        )
        chunks = splitter.split_documents(documents)

        for chunk in chunks:
            match = CONTROL_ID_PATTERN.search(chunk.page_content)
            if match:
                chunk.metadata["control_id"] = match.group()

        db = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=config["db_dir"],
            collection_name=config["collection"],
        )
        logger.info(f"{config['name']} database built: {len(chunks)} chunks")
        return db

    def build_all(self, frameworks: List[str] = None):
        """Build capability DB and all specified framework DBs."""
        self.build_capability_db()
        targets = frameworks or list(FRAMEWORKS.keys())
        for key in targets:
            self.build_framework_db(key)
        logger.info("All databases built.")


def main():
    setup = DatabaseSetup()

    print("Select what to build:")
    print("  1. Capability database only")
    print("  2. All framework databases")
    print("  3. Everything (capability + all frameworks)")
    print("  4. Single framework")

    choice = input("\nChoice (1-4): ").strip()

    if choice == "1":
        setup.build_capability_db()
    elif choice == "2":
        setup.build_all(list(FRAMEWORKS.keys()))
    elif choice == "3":
        setup.build_all()
    elif choice == "4":
        print("\nAvailable frameworks:")
        for i, (k, v) in enumerate(FRAMEWORKS.items(), 1):
            print(f"  {i}. {v['name']} [{k}]")
        key = input("Enter framework key: ").strip()
        if key in FRAMEWORKS:
            setup.build_framework_db(key)
        else:
            print(f"Unknown framework: {key}")
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    main()
