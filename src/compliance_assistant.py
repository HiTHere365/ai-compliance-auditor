"""
LLM-powered compliance assistant.

Retrieves relevant chunks from capability and framework databases, then uses
a local LLM (Ollama) to assess compliance gaps and produce recommendations.

Requires Ollama running locally: https://ollama.ai
Default model: llama3 -- swap in any Ollama-compatible model.
"""

import os
from typing import List, Dict

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.llms import Ollama

from scan_groups import FRAMEWORKS, SCAN_GROUPS, CAPABILITY_DB


COMPLIANCE_PROMPT = """
You are a compliance analyst. Your task is to assess whether the capability
evidence provided satisfies the framework requirements, identify gaps, and
recommend actions.

Framework Requirements:
{framework_context}

Capability Evidence:
{capability_context}

Question: {question}

Provide:
1. Current compliance status for this area
2. Specific gaps between capabilities and requirements
3. Recommended actions to close the gaps
4. Confidence level (High / Medium / Low) based on available evidence
"""


class ComplianceAssistant:
    def __init__(self, scan_mode: str = "full", llm_model: str = "llama3"):
        """
        scan_mode -- "security", "maturity", "full", or a single framework key
        llm_model -- Ollama model name to use for gap analysis
        """
        print("Loading embedding model...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-mpnet-base-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        self.framework_keys = self._resolve_scan_mode(scan_mode)
        self.framework_dbs = self._load_framework_dbs()
        self.capability_db = self._load_capability_db()

        print(f"Connecting to Ollama ({llm_model})...")
        self.llm = Ollama(model=llm_model)

    def _resolve_scan_mode(self, mode: str) -> List[str]:
        if mode in SCAN_GROUPS:
            return SCAN_GROUPS[mode]
        if mode in FRAMEWORKS:
            return [mode]
        raise ValueError(f"Unknown scan mode: {mode}")

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
        return dbs

    def _load_capability_db(self) -> Chroma | None:
        if not os.path.exists(CAPABILITY_DB["db_dir"]):
            print("  Warning: capability database not found.")
            return None
        return Chroma(
            persist_directory=CAPABILITY_DB["db_dir"],
            embedding_function=self.embeddings,
            collection_name=CAPABILITY_DB["collection"],
        )

    def _retrieve_capability_context(self, query: str, k: int = 5) -> str:
        if not self.capability_db:
            return "No capability evidence available."
        results = self.capability_db.similarity_search(query, k=k)
        return "\n\n".join(
            f"[Source: {doc.metadata.get('source', 'Unknown')}]\n{doc.page_content}"
            for doc in results
        )

    def _retrieve_framework_context(self, framework_key: str, query: str, k: int = 3) -> str:
        if framework_key not in self.framework_dbs:
            return ""
        results = self.framework_dbs[framework_key].similarity_search(query, k=k)
        name = FRAMEWORKS[framework_key]["name"]
        return "\n\n".join(
            f"[{name} | Control: {doc.metadata.get('control_id', 'N/A')}]\n{doc.page_content}"
            for doc in results
        )

    def assess(self, question: str) -> Dict[str, str]:
        """
        Run a compliance assessment for a given question across all loaded frameworks.

        Returns a dict mapping framework key to LLM assessment text.
        """
        capability_context = self._retrieve_capability_context(question)
        assessments = {}

        for key in self.framework_dbs:
            framework_context = self._retrieve_framework_context(key, question)
            if not framework_context:
                continue

            prompt = COMPLIANCE_PROMPT.format(
                framework_context=framework_context,
                capability_context=capability_context,
                question=question,
            )

            name = FRAMEWORKS[key]["name"]
            print(f"\nAssessing against {name}...")
            assessments[key] = self.llm(prompt)

        return assessments

    def interactive_mode(self):
        """Start an interactive compliance assessment session."""
        print("\n" + "=" * 60)
        print("COMPLIANCE ASSISTANT (LLM-powered)")
        print("Active frameworks:", ", ".join(
            FRAMEWORKS[k]["name"] for k in self.framework_keys if k in self.framework_dbs
        ))
        print("=" * 60)
        print("Type a compliance question or area to assess.")
        print("Type 'quit' to exit.")
        print("=" * 60)

        while True:
            question = input("\nQuestion: ").strip()
            if question.lower() == "quit":
                break

            assessments = self.assess(question)
            for key, text in assessments.items():
                print(f"\n{'='*40}")
                print(f"Framework: {FRAMEWORKS[key]['name']}")
                print("=" * 40)
                print(text)


def main():
    if not os.path.exists(CAPABILITY_DB["db_dir"]):
        print("Capability database not found. Run setup_databases.py first.")
        return

    print("Select scan mode:")
    print("  1. Security Compliance")
    print("  2. AI Maturity")
    print("  3. Full Audit")
    choice = input("Choice (1-3): ").strip()
    mode_map = {"1": "security", "2": "maturity", "3": "full"}
    mode = mode_map.get(choice, "full")

    try:
        assistant = ComplianceAssistant(scan_mode=mode)
        assistant.interactive_mode()
    except KeyboardInterrupt:
        print("\nInterrupted.")


if __name__ == "__main__":
    main()
