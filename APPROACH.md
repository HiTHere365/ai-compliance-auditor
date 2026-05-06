# Design Approach

## The Problem

Compliance work is manual and slow. An analyst wants to know whether their system satisfies a specific NIST or OWASP control, but finding the relevant capability documentation means searching through dozens of PDFs and cross-referencing against framework requirements. The answer is usually buried somewhere, but getting to it takes hours.

The core problem is retrieval: the analyst already has the documents. What's missing is a fast, semantic search layer that can surface relevant capability evidence and relevant framework requirements at the same time.

## Two-Database Architecture

The central design decision is to keep capability documents and framework documents in separate vector databases.

Putting them in the same database would allow queries to match against both types at once, but it would also make it harder to distinguish evidence (what you have) from requirements (what you need). Separating them keeps that distinction explicit: the capability DB is your evidence base, the framework DBs are your requirement sources. A compliance check is always a comparison between the two, not a single search.

Each framework gets its own database rather than a shared framework database. This allows:
- Per-framework chunking strategies tuned to the document structure
- Targeted single-framework scans without loading all frameworks
- Independent updates when a framework document is revised

## Chunking Strategy

Capability documents use larger chunks (1500 characters, 300 overlap). Technical documentation benefits from more context per chunk: a procedure, a policy section, or a system description needs surrounding text to be interpreted correctly.

Framework documents use smaller chunks (600-900 characters, 100-150 overlap depending on the framework). Compliance requirements are typically short, specific, and self-contained. Smaller chunks produce more precise matches and reduce the chance that a retrieved chunk mixes multiple unrelated controls.

## Local Embeddings

`all-mpnet-base-v2` runs entirely on CPU with no external API. For compliance work, keeping documents local is important: capability documentation may include sensitive system details or internal policies that should not be sent to a third-party API. Local embeddings address this by keeping all data on the machine.

The model performs well on technical and policy content, which is the primary document type in both the capability and framework corpora.

## Scan Groups

Frameworks are grouped into two categories that reflect how compliance work is typically scoped:

**Security Compliance**: OWASP Top 10, NIST AI 600-1, MIT AI Risk Repository. These frameworks address what can go wrong and whether the system is protected. Relevant for security audits, risk assessments, and regulatory compliance.

**AI Maturity**: MIT Secure-by-Design, MITRE AI Maturity Model. These frameworks address how well AI capabilities are integrated and governed. Relevant for organizational readiness assessments and capability planning.

The grouping is defined in `scan_groups.py`. Adding a new framework means adding one entry to that file.

## LLM Integration

The query tool performs retrieval only: it surfaces relevant chunks and lets the analyst interpret them. The compliance assistant adds an LLM layer (Ollama, local) that reads the retrieved chunks and produces a structured assessment: compliance status, specific gaps, and recommended actions.

The LLM is not the source of truth. The vault databases are the source of truth. The LLM is an interpreter that formats and reasons over what the retrieval layer found. This keeps the system auditable: every LLM response is grounded in specific retrieved documents, not in the model's training knowledge.

## Incremental Updates

The updater tracks a SHA-256 hash of every indexed file in a manifest. When documents change, only the changed files are re-embedded. This avoids full rebuilds on every update and keeps the turnaround time short when capabilities evolve or framework documents are revised.

## Capability Document Formats

Capability documentation comes in many formats. Supporting PDF, DOCX, TXT, and MD (in addition to PDF-only in earlier versions) removes the preprocessing step of converting everything to PDF before ingestion. The loaders handle format-specific extraction internally; the chunking and embedding pipeline is identical downstream regardless of input format.
