# AI Compliance Auditor

A multi-framework AI compliance auditing tool. Ingests your capability documentation and compliance framework PDFs into separate vector databases, then lets you query gaps between what you have and what the frameworks require.

Supports individual framework scans, grouped scans by category, or a full audit across all loaded frameworks.

## Frameworks

**Security Compliance**
- OWASP Top 10
- NIST AI 600-1 (Generative AI)
- MIT AI Risk Repository

**AI Maturity**
- MIT Secure-by-Design AI Framework
- MITRE AI Maturity Model

## How It Works

1. Your capability documents (PDFs, DOCX, TXT, MD) are chunked and embedded into a local vector database using a local embedding model (no API required)
2. Each compliance framework document is embedded into its own separate database with framework-specific chunking
3. At query time, both databases are searched and results are compared to surface gaps
4. The optional LLM assistant (Ollama) generates a structured gap analysis and recommendations

## Setup

Install dependencies:

```
pip install -r requirements.txt
```

Place your capability documents in the appropriate subdirectory:

```
capability_docs/
  pdf_files/       PDF documents
  docx_files/      Word documents
  txt_files/       Plain text files
  md_files/        Markdown files
```

Place framework PDFs in `framework_docs/`:

```
framework_docs/
  nist_genai_600_1.pdf
  owasp_top10.pdf
  mit_ai_risk_repository.pdf
  mit_secure_by_design.pdf
  mitre_ai_maturity_model.pdf
```

Build the databases:

```
python src/setup_databases.py
```

## Running

Interactive query tool (no LLM required):

```
python src/query_tool.py
```

LLM-powered gap analysis (requires Ollama):

```
python src/compliance_assistant.py
```

Incremental database updates when documents change:

```
python src/vector_db_updater.py
```

Capability document management and overlap detection:

```
python src/capability_update_helper.py
```

## Scan Modes

| Mode | Frameworks |
|---|---|
| security | OWASP Top 10, NIST AI 600-1, MIT AI Risk Repository |
| maturity | MIT Secure-by-Design, MITRE AI Maturity Model |
| full | All frameworks |
| single | Any one framework by key |

## Requirements

Python 3.10+. All embedding runs locally using `all-mpnet-base-v2`. No external API keys required for core functionality. Ollama is optional for the LLM assistant.

## License

GNU Affero General Public License v3.0 (AGPL v3)

For commercial licensing or research collaboration: volts-beret0t@icloud.com
