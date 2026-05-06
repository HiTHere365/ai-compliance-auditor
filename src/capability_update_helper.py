"""
Capability document management tool.

Analyzes coverage gaps, detects overlap between existing and new documents,
and recommends an update strategy before you add or replace capability docs.
"""

import os
from pathlib import Path
from typing import List, Dict

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from scan_groups import CAPABILITY_DB


class CapabilityManager:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-mpnet-base-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        try:
            self.db = Chroma(
                persist_directory=CAPABILITY_DB["db_dir"],
                embedding_function=self.embeddings,
                collection_name=CAPABILITY_DB["collection"],
            )
            print("Capability database loaded.")
        except Exception as e:
            print(f"Could not load capability database: {e}")
            self.db = None

    def find_overlap(self, query: str, threshold: float = 0.75) -> List[Dict]:
        """Find existing docs that might overlap with a new capability document."""
        if not self.db:
            return []
        results = self.db.similarity_search_with_score(query, k=10)
        return [
            {
                "content": doc.page_content[:200] + "...",
                "source": doc.metadata.get("source", "Unknown"),
                "score": score,
            }
            for doc, score in results
            if score < threshold
        ]

    def analyze_coverage(self, capability_area: str) -> Dict:
        """Analyze how well a capability area is currently documented."""
        if not self.db:
            return {}

        results = self.db.similarity_search_with_score(capability_area, k=20)
        coverage = {}

        for doc, score in results:
            source = doc.metadata.get("source", "Unknown")
            if source not in coverage:
                coverage[source] = {"chunks": [], "best_score": float("inf"), "count": 0}
            coverage[source]["chunks"].append({"content": doc.page_content[:150] + "...", "score": score})
            coverage[source]["best_score"] = min(coverage[source]["best_score"], score)
            coverage[source]["count"] += 1

        sorted_coverage = dict(sorted(coverage.items(), key=lambda x: x[1]["best_score"])[:10])
        return {
            "capability": capability_area,
            "total_docs": len(coverage),
            "documents": sorted_coverage,
        }

    def suggest_strategy(self, capability_area: str, new_doc_description: str) -> Dict:
        """Recommend ADD_NEW, ENHANCE_EXISTING, or CONSOLIDATE for a new document."""
        coverage = self.analyze_coverage(capability_area)
        overlaps = self.find_overlap(new_doc_description)

        strategy = {
            "capability_area": capability_area,
            "current_doc_count": coverage.get("total_docs", 0),
            "overlap_count": len(overlaps),
            "recommendation": None,
            "action_plan": [],
            "overlapping_files": [doc["source"] for doc in overlaps],
        }

        if len(overlaps) == 0:
            strategy["recommendation"] = "ADD_NEW"
            strategy["action_plan"] = [
                "No overlap detected with existing documentation.",
                "Safe to add to the appropriate capability_docs/ subdirectory.",
            ]
        elif len(overlaps) <= 2:
            strategy["recommendation"] = "ENHANCE_EXISTING"
            strategy["action_plan"] = [
                "Limited overlap found.",
                "If the new document is more complete, replace the overlapping file.",
                "If complementary, add alongside the existing document.",
            ]
        else:
            strategy["recommendation"] = "CONSOLIDATE"
            strategy["action_plan"] = [
                f"Found {len(overlaps)} potentially overlapping documents.",
                "New document may supersede multiple existing files.",
                "Review overlapping documents and remove redundant ones after adding the new file.",
            ]

        return strategy

    def interactive(self):
        """Interactive capability management session."""
        print("\n" + "=" * 60)
        print("CAPABILITY UPDATE ASSISTANT")
        print("=" * 60)

        while True:
            print("\nOptions:")
            print("  1. Analyze capability coverage")
            print("  2. Plan new document addition")
            print("  3. Find overlapping documents")
            print("  4. Exit")

            choice = input("\nChoice (1-4): ").strip()

            if choice == "1":
                area = input("Capability area: ").strip()
                result = self.analyze_coverage(area)
                print(f"\nCoverage: {area}")
                print(f"Relevant documents found: {result.get('total_docs', 0)}")
                for src, info in list(result.get("documents", {}).items())[:5]:
                    print(f"  {os.path.basename(src)} ({info['count']} relevant chunks)")

            elif choice == "2":
                area = input("Capability area the new document covers: ").strip()
                desc = input("Brief description of the new document: ").strip()
                strategy = self.suggest_strategy(area, desc)
                print(f"\nRecommendation: {strategy['recommendation']}")
                for action in strategy["action_plan"]:
                    print(f"  - {action}")
                if strategy["overlapping_files"]:
                    print("Overlapping files:")
                    for f in strategy["overlapping_files"][:5]:
                        print(f"  - {os.path.basename(f)}")

            elif choice == "3":
                query = input("Describe the document/capability: ").strip()
                overlaps = self.find_overlap(query)
                if overlaps:
                    print(f"\nFound {len(overlaps)} potentially overlapping documents:")
                    for i, doc in enumerate(overlaps[:10], 1):
                        print(f"  {i}. {os.path.basename(doc['source'])} (score: {doc['score']:.3f})")
                        print(f"     {doc['content']}")
                else:
                    print("No overlapping documents found.")

            elif choice == "4":
                break
            else:
                print("Invalid choice.")


def main():
    if not os.path.exists(CAPABILITY_DB["db_dir"]):
        print("Capability database not found. Run setup_databases.py first.")
        return
    manager = CapabilityManager()
    manager.interactive()


if __name__ == "__main__":
    main()
