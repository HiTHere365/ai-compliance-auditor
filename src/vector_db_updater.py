"""
Incremental vector database updater.

Tracks file hashes to detect changes and updates only what changed,
avoiding full rebuilds on every new document.
"""

import os
import re
import shutil
import hashlib
import json
import logging
from pathlib import Path
from typing import List, Dict

from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from scan_groups import FRAMEWORKS, CAPABILITY_DB

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MANIFEST_PATH = "./db_manifest.json"


class VectorDBUpdater:
    def __init__(self, embedding_model: str = "all-mpnet-base-v2"):
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> Dict:
        if os.path.exists(MANIFEST_PATH):
            try:
                with open(MANIFEST_PATH) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"capability": {}, "frameworks": {}}

    def _save_manifest(self):
        with open(MANIFEST_PATH, "w") as f:
            json.dump(self.manifest, f, indent=2)

    def _file_hash(self, filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        return h.hexdigest()

    def _load_file(self, filepath: str) -> List[Document]:
        ext = Path(filepath).suffix.lower()
        try:
            if ext == ".pdf":
                loader = PyPDFLoader(filepath)
            elif ext == ".docx":
                loader = Docx2txtLoader(filepath)
            elif ext == ".txt":
                loader = TextLoader(filepath, encoding="utf-8")
            elif ext == ".md":
                loader = UnstructuredMarkdownLoader(filepath)
            else:
                return []
            return loader.load()
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            return []

    def _scan_capability_files(self) -> Dict[str, str]:
        files = {}
        docs_path = Path(CAPABILITY_DB["docs_dir"])
        ext_map = {
            "pdf_files": ".pdf",
            "docx_files": ".docx",
            "txt_files": ".txt",
            "md_files": ".md",
        }
        for subdir, ext in ext_map.items():
            subdir_path = docs_path / subdir
            if not subdir_path.exists():
                continue
            for f in subdir_path.glob(f"*{ext}"):
                files[str(f)] = self._file_hash(str(f))
        return files

    def _detect_changes(self, current: Dict[str, str], stored: Dict[str, str]) -> Dict:
        added = set(current) - set(stored)
        removed = set(stored) - set(current)
        modified = {p for p in set(current) & set(stored) if current[p] != stored[p]}
        return {"added": added, "modified": modified, "removed": removed}

    def update_capability_db(self):
        """Incremental update of the capability database."""
        logger.info("Scanning capability documents for changes...")
        current = self._scan_capability_files()
        stored = self.manifest.get("capability", {})
        changes = self._detect_changes(current, stored)

        if not any([changes["added"], changes["modified"], changes["removed"]]):
            logger.info("No changes detected in capability documents.")
            return

        logger.info(
            f"Changes: {len(changes['added'])} added, "
            f"{len(changes['modified'])} modified, "
            f"{len(changes['removed'])} removed"
        )

        try:
            db = Chroma(
                persist_directory=CAPABILITY_DB["db_dir"],
                embedding_function=self.embeddings,
                collection_name=CAPABILITY_DB["collection"],
            )
        except Exception:
            logger.info("No existing capability DB found, running full build.")
            self._full_rebuild_capability()
            return

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CAPABILITY_DB["chunk_size"],
            chunk_overlap=CAPABILITY_DB["chunk_overlap"],
            separators=["\n## ", "\n### ", "\n\n", "\n", " "],
        )

        for filepath in changes["removed"]:
            try:
                db._collection.delete(where={"file_path": filepath})
                logger.info(f"Removed: {filepath}")
            except Exception as e:
                logger.warning(f"Could not remove {filepath}: {e}")

        for filepath in changes["added"] | changes["modified"]:
            if filepath in changes["modified"]:
                try:
                    db._collection.delete(where={"file_path": filepath})
                except Exception:
                    pass
            docs = self._load_file(filepath)
            for doc in docs:
                doc.metadata.update({"document_type": "capability", "file_path": filepath})
            chunks = splitter.split_documents(docs)
            if chunks:
                db.add_documents(chunks)
                logger.info(f"Indexed: {filepath} ({len(chunks)} chunks)")

        self.manifest["capability"] = current
        self._save_manifest()
        logger.info("Capability database update complete.")

    def _full_rebuild_capability(self):
        """Full rebuild of the capability database."""
        if os.path.exists(CAPABILITY_DB["db_dir"]):
            shutil.rmtree(CAPABILITY_DB["db_dir"])

        current = self._scan_capability_files()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CAPABILITY_DB["chunk_size"],
            chunk_overlap=CAPABILITY_DB["chunk_overlap"],
            separators=["\n## ", "\n### ", "\n\n", "\n", " "],
        )
        all_chunks = []
        for filepath in current:
            docs = self._load_file(filepath)
            for doc in docs:
                doc.metadata.update({"document_type": "capability", "file_path": filepath})
            all_chunks.extend(splitter.split_documents(docs))

        if all_chunks:
            Chroma.from_documents(
                documents=all_chunks,
                embedding=self.embeddings,
                persist_directory=CAPABILITY_DB["db_dir"],
                collection_name=CAPABILITY_DB["collection"],
            )
            self.manifest["capability"] = current
            self._save_manifest()
            logger.info(f"Full rebuild complete: {len(all_chunks)} chunks.")
        else:
            logger.error("No documents found.")

    def update_framework_db(self, framework_key: str):
        """Update a framework DB if its source document has changed."""
        config = FRAMEWORKS[framework_key]
        source = config["source_doc"]

        if not os.path.exists(source):
            logger.warning(f"Framework document not found: {source}")
            return

        current_hash = self._file_hash(source)
        stored_hash = self.manifest.get("frameworks", {}).get(framework_key)

        if current_hash == stored_hash:
            logger.info(f"{config['name']}: no changes.")
            return

        logger.info(f"{config['name']}: rebuilding...")
        if os.path.exists(config["db_dir"]):
            shutil.rmtree(config["db_dir"])

        docs = self._load_file(source)
        for doc in docs:
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
        chunks = splitter.split_documents(docs)

        for chunk in chunks:
            match = re.search(r'\b[A-Z]{1,3}-\d+\.\d+\b', chunk.page_content)
            if match:
                chunk.metadata["control_id"] = match.group()

        Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=config["db_dir"],
            collection_name=config["collection"],
        )

        self.manifest.setdefault("frameworks", {})[framework_key] = current_hash
        self._save_manifest()
        logger.info(f"{config['name']} updated: {len(chunks)} chunks.")

    def status(self):
        """Print current database status."""
        print("\nDatabase Status")
        print("=" * 40)
        cap_exists = os.path.exists(CAPABILITY_DB["db_dir"])
        print(f"Capability DB:  {'exists' if cap_exists else 'missing'}")
        tracked = self.manifest.get("capability", {})
        print(f"Tracked files:  {len(tracked)}")
        print()
        for key, config in FRAMEWORKS.items():
            exists = os.path.exists(config["db_dir"])
            tracked = key in self.manifest.get("frameworks", {})
            print(f"{config['name']}: {'exists' if exists else 'missing'} / {'tracked' if tracked else 'not tracked'}")


def main():
    updater = VectorDBUpdater()

    print("Vector Database Updater")
    print("=" * 40)
    print("  1. Status check")
    print("  2. Update capability database (incremental)")
    print("  3. Full rebuild capability database")
    print("  4. Update all framework databases")
    print("  5. Update single framework database")
    print("  6. Exit")

    while True:
        choice = input("\nChoice (1-6): ").strip()

        if choice == "1":
            updater.status()
        elif choice == "2":
            updater.update_capability_db()
        elif choice == "3":
            updater._full_rebuild_capability()
        elif choice == "4":
            for key in FRAMEWORKS:
                updater.update_framework_db(key)
        elif choice == "5":
            for k, v in FRAMEWORKS.items():
                print(f"  {k}: {v['name']}")
            key = input("Framework key: ").strip()
            if key in FRAMEWORKS:
                updater.update_framework_db(key)
            else:
                print(f"Unknown framework: {key}")
        elif choice == "6":
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
