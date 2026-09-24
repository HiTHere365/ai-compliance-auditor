# AI Compliance Auditor

A multi-framework AI compliance auditing tool. Ingests your capability documentation and compliance framework documents into separate local vector databases, then lets you query gaps between what you have and what the frameworks require.

Supports individual framework scans, grouped scans by category, or a full audit across all loaded frameworks.

## Frameworks

**Security Compliance**
- OWASP Top 10 for LLM Applications
- NIST AI 600-1 (Generative AI Profile)
- MIT AI Risk Repository

**AI Maturity**
- MIT Secure-by-Design AI Framework
- MITRE AI Maturity Model

## How It Works

1. Your capability documents (PDF, DOCX, TXT, MD) are chunked and embedded into a local vector database using a local embedding model (no API required)
2. Each compliance framework document is embedded into its own separate database with framework-specific chunking
3. At query time, both databases are searched and results are compared to surface gaps
4. The optional LLM assistant (Ollama) generates a structured gap analysis and recommendations

PDF text is extracted with PyMuPDF and passed through a small repair step that removes control characters, drops stray bullet glyphs from symbol fonts, and collapses character-spaced runs such as `O W A S P` back into words. Framework chunks are tagged with the control identifier they mention (for example `LLM01:2025` or `GV-1.2`) so query results can cite it.

## Setup

All commands below are run from the repository root; the scripts use paths relative to it.

### 1. Install dependencies

Python 3.10 or newer.

```
pip install -r requirements.txt
```

The first database build downloads the `all-mpnet-base-v2` embedding model (about 420 MB) from Hugging Face. After that, the core tools run offline.

### 2. Download the framework documents

The framework PDFs are copyrighted and are not included in this repository (`.gitignore` excludes `framework_docs/*.pdf`). Download each one yourself and save it under `framework_docs/` with the exact file name below, because `src/scan_groups.py` looks for these names.

| Save as | Document | Source |
|---|---|---|
| `framework_docs/nist_genai_600_1.pdf` | NIST AI 600-1, Artificial Intelligence Risk Management Framework: Generative AI Profile | https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.600-1.pdf |
| `framework_docs/owasp_top10.pdf` | OWASP Top 10 for LLM Applications | https://owasp.org/www-project-top-10-for-large-language-model-applications/ (PDF under Assets) |
| `framework_docs/mit_ai_risk_repository.pdf` | MIT AI Risk Repository | https://airisk.mit.edu/ (download the repository PDF) |
| `framework_docs/mitre_ai_maturity_model.pdf` | MITRE AI Maturity Model and Organizational Assessment Tool Guide | https://www.mitre.org/ (search publications; no stable direct link) |
| `framework_docs/mit_secure_by_design.md` | MIT Secure-by-Design AI Framework | Included in this repository as a structured summary of the MIT Sloan Management Review article "Is Your AI System Secure by Design? 10 Questions to Ask" |

`python src/doc_version_checker.py --update` fetches the NIST, OWASP, and MIT AI Risk PDFs from the URLs recorded in that script when they are missing or have changed upstream. The MITRE guide has to be downloaded by hand.

A framework whose file is missing is skipped with a warning at build time; the remaining frameworks still build and can be queried.

### 3. Add capability documents

Place your capability documents in the subdirectory that matches their format:

```
capability_docs/
  pdf_files/       PDF documents
  docx_files/      Word documents
  txt_files/       Plain text files
  md_files/        Markdown files
```

Real capability documents in these folders are ignored by git. PDF and TXT files load with no additional downloads. Markdown files are parsed by the `unstructured` library, which fetches a small English spaCy model the first time it runs (this also applies when building the MIT Secure-by-Design database).

### 4. Build the databases

```
python src/setup_databases.py
```

Choose what to build from the menu: the capability database only, all framework databases, everything, or a single framework.

## Quick start with the example document

The repository ships one fictional capability document, `capability_docs/txt_files/example_meridian_support_assistant.txt`, describing an invented customer-service chatbot called the Meridian Support Assistant. It covers model access, tool use, data retention, human escalation, and change management, and it says nothing about adversarial testing or logging, so an audit against the frameworks turns up real gaps.

1. Install dependencies and download at least one framework document (steps 1 and 2 above). The OWASP and NIST PDFs are the most useful for this walkthrough.
2. Build everything:

   ```
   python src/setup_databases.py
   ```

   Choose option 3.
3. Start the query tool and pick the Security Compliance scan:

   ```
   python src/query_tool.py
   ```

4. Try these queries and compare the capability evidence against the framework requirements returned for each:

   - `red teaming and adversarial testing` (no supporting evidence in the sample document)
   - `logging monitoring and audit trails` (no supporting evidence in the sample document)
   - `data retention and deletion` (covered by section 4 of the sample)
   - `human escalation and oversight` (covered by section 5 of the sample)

   `cap:<query>` searches only the capability documents and works even when no framework database has been built.

### Example output

Query: `red teaming and adversarial testing` (Security Compliance scan). Capability hits all come from the shipped example; the framework sections show related controls that the sample does not cover.

```
Capability Evidence:
Lower distance = closer match.

  1. example_meridian_support_assistant.txt (distance: 1.722)
     Meridian Support Assistant: System Capability Overview

This is a fictional sample document. Meridian Systems, its products, and the
figures below are invented for demonstration purposes only.

## 1. ...

  2. example_meridian_support_assistant.txt (distance: 1.735)
     ## 3. Tool Use

The assistant can invoke the following internal tools during a conversation:

- lookup_account: reads account status, plan, and last three invoices for the
 authenticated customer only...

NIST GenAI 600-1 Requirements:
Lower distance = closer match.

  1. Control ID: N/A (distance: 0.863)
     standards such as informed consent and compensation. Organizations should follow applicable human
subjects research requirements, and best practices such as informed consent and subject compensation,...

  2. Control ID: N/A (distance: 0.885)
     Various types of AI red-teaming may be appropriate, depending on the use case:
•
General Public: Performed by general users (not necessarily AI or technical experts) who are
expected to use the mode...
```

Replace the example with your own documents when you are ready; nothing in the code refers to it by name.

## Running

Interactive query tool (no LLM required):

```
python src/query_tool.py
```

LLM-powered gap analysis (requires a local Ollama server with the `llama3` model pulled, or edit the model name in `src/compliance_assistant.py`):

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

Check whether newer framework documents are available at source URLs:

```
python src/doc_version_checker.py
```

Download updates when newer versions are detected:

```
python src/doc_version_checker.py --update
```

## Scan Modes

| Mode | Frameworks |
|---|---|
| security | OWASP Top 10, NIST AI 600-1, MIT AI Risk Repository |
| maturity | MIT Secure-by-Design, MITRE AI Maturity Model |
| full | All frameworks |
| single | Any one framework by key |

## Tests

```
pip install pytest
pytest -q tests
```

The suite covers the PDF text repair (`_clean_spaced_text`), the PyMuPDF page loader (`_load_pdf`, including the Type3 font handling), the shared `load_document` entry point, capability document discovery, and the control identifier pattern. The tests generate their own small PDF with PyMuPDF, so they need neither the framework documents nor the embedding model. Most of the wall time is importing the LangChain modules used by `setup_databases.py`.

`.github/workflows/ci.yml` runs the same command on Python 3.11 with a reduced dependency set (pytest, PyMuPDF, and the LangChain packages the tested module imports) rather than the full `requirements.txt`, so CI does not have to install PyTorch.

## Requirements

Python 3.10+. All embedding runs locally using `all-mpnet-base-v2`. PDF text extraction uses PyMuPDF. No external API keys required for core functionality. Ollama is optional and only used by the LLM assistant.

## License

Apache License 2.0. See [LICENSE](LICENSE).

Copyright (c) 2026 William Rogers.
