"""
Interactive compliance query tool.

Search capability docs against one framework, a scan group (security or maturity),
or a full audit across all frameworks.
"""

import os
from typing import List, Dict, Any

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from scan_groups import FRAMEWORKS, SCAN_GROUPS, CAPABILITY_DB


class ComplianceQueryTool:
    def __init__(self, scan_mode: str = "full"):
        """
        scan_mode -- "security", "maturity", "full", or a single framework key
        """
        print("Loading embedding model...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-mpnet-base-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        self.scan_mode = scan_mode
        self.framework_keys = self._resolve_scan_mode(scan_mode)
        self.framework_dbs = self._load_framework_dbs()
        self.capability_db = self._load_capability_db()

    def _resolve_scan_mode(self, mode: str) -> List[str]:
        if mode in SCAN_GROUPS:
            return SCAN_GROUPS[mode]
        if mode in FRAMEWORKS:
            return [mode]
        raise ValueError(f"Unknown scan mode: {mode}. Use 'security', 'maturity', 'full', or a framework key.")

    def _load_framework_dbs(self) -> Dict[str, Chroma]:
        dbs = {}
        for key in self.framework_keys:
            config = FRAMEWORKS[key]
            if not os.path.exists(config["db_dir"]):
                print(f"  Warning: {config['name']} database not found, skipping.")
                continue
            dbs[key] = Chroma(
                persist_directory=config["db_dir"],
                embedding_function=self.embeddings,
                collection_name=config["collection"],
            )
            print(f"  Loaded: {config['name']}")
        return dbs

    def _load_capability_db(self) -> Chroma | None:
        if not os.path.exists(CAPABILITY_DB["db_dir"]):
            print("  Warning: capability database not found.")
            return None
        db = Chroma(
            persist_directory=CAPABILITY_DB["db_dir"],
            embedding_function=self.embeddings,
            collection_name=CAPABILITY_DB["collection"],
        )
        print("  Loaded: capability documents")
        return db

    def search_capabilities(self, query: str, k: int = 5) -> List[Dict]:
        if not self.capability_db:
            return []
        results = self.capability_db.similarity_search_with_score(query, k=k)
        return [
            {
                "content": doc.page_content,
                "source": doc.metadata.get("source", "Unknown"),
                "score": score,
            }
            for doc, score in results
        ]

    def search_framework(self, framework_key: str, query: str, k: int = 3) -> List[Dict]:
        if framework_key not in self.framework_dbs:
            return []
        results = self.framework_dbs[framework_key].similarity_search_with_score(query, k=k)
        return [
            {
                "content": doc.page_content,
                "control_id": doc.metadata.get("control_id", "N/A"),
                "framework": FRAMEWORKS[framework_key]["name"],
                "score": score,
            }
            for doc, score in results
        ]

    def compliance_check(self, query: str):
        """Run a compliance check across all loaded frameworks."""
        print(f"\nCompliance Check: '{query}'")
        print("=" * 60)

        print("\nCapability Evidence:")
        cap_results = self.search_capabilities(query)
        if cap_results:
            for i, r in enumerate(cap_results, 1):
                src = os.path.basename(r["source"]) if r["source"] else "Unknown"
                print(f"\n  {i}. {src} (score: {r['score']:.3f})")
                print(f"     {r['content'][:200]}...")
        else:
            print("  No capability evidence found.")

        for key, db in self.framework_dbs.items():
            name = FRAMEWORKS[key]["name"]
            print(f"\n{name} Requirements:")
            results = self.search_framework(key, query)
            if results:
                for i, r in enumerate(results, 1):
                    print(f"\n  {i}. Control ID: {r['control_id']} (score: {r['score']:.3f})")
                    print(f"     {r['content'][:200]}...")
            else:
                print("  No matching requirements found.")

    def interactive_mode(self):
        """Start interactive compliance checking."""
        print("\n" + "=" * 60)
        print(f"COMPLIANCE AUDITOR -- Scan Mode: {self.scan_mode.upper()}")
        print("Active frameworks:", ", ".join(
            FRAMEWORKS[k]["name"] for k in self.framework_keys if k in self.framework_dbs
        ))
        print("=" * 60)
        print("Commands:")
        print("  <query>              -- search all active frameworks + capability docs")
        print("  cap:<query>          -- search capability docs only")
        print("  fw:<key>:<query>     -- search a single framework (e.g. fw:owasp:injection)")
        print("  quit                 -- exit")
        print("=" * 60)

        while True:
            query = input("\nQuery: ").strip()

            if query.lower() == "quit":
                break

            elif query.startswith("cap:"):
                q = query[4:].strip()
                results = self.search_capabilities(q)
                for i, r in enumerate(results, 1):
                    src = os.path.basename(r["source"]) if r["source"] else "Unknown"
                    print(f"\n  {i}. {src} (score: {r['score']:.3f})")
                    print(f"     {r['content'][:200]}...")

            elif query.startswith("fw:"):
                parts = query[3:].split(":", 1)
                if len(parts) == 2:
                    key, q = parts[0].strip(), parts[1].strip()
                    results = self.search_framework(key, q)
                    for i, r in enumerate(results, 1):
                        print(f"\n  {i}. Control: {r['control_id']} (score: {r['score']:.3f})")
                        print(f"     {r['content'][:200]}...")
                else:
                    print("Usage: fw:<framework_key>:<query>")

            else:
                self.compliance_check(query)


def select_scan_mode() -> str:
    print("\nSelect scan mode:")
    print("  1. Security Compliance  (OWASP, NIST GenAI 600-1, MIT AI Risk)")
    print("  2. AI Maturity          (MIT Secure-by-Design, MITRE AI Maturity)")
    print("  3. Full Audit           (all frameworks)")
    print("  4. Single framework")

    choice = input("\nChoice (1-4): ").strip()

    if choice == "1":
        return "security"
    elif choice == "2":
        return "maturity"
    elif choice == "3":
        return "full"
    elif choice == "4":
        print("\nAvailable frameworks:")
        for k, v in FRAMEWORKS.items():
            print(f"  {k}: {v['name']}")
        return input("Framework key: ").strip()
    else:
        print("Invalid choice, defaulting to full audit.")
        return "full"


def main():
    if not os.path.exists(CAPABILITY_DB["db_dir"]):
        print("Capability database not found. Run setup_databases.py first.")
        return

    mode = select_scan_mode()

    try:
        tool = ComplianceQueryTool(scan_mode=mode)
        tool.interactive_mode()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except ValueError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
