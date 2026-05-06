"""
Framework configuration and scan group definitions.

All framework metadata lives here. Adding a new framework means adding one
entry to FRAMEWORKS and optionally adding it to a SCAN_GROUPS list.
"""

FRAMEWORKS = {
    "nist_genai": {
        "name": "NIST GenAI 600-1",
        "db_dir": "./framework_dbs/nist_genai_db",
        "collection": "nist_genai_requirements",
        "source_doc": "./framework_docs/nist_genai_600_1.pdf",
        "chunk_size": 800,
        "chunk_overlap": 150,
        "group": "security",
    },
    "owasp": {
        "name": "OWASP Top 10",
        "db_dir": "./framework_dbs/owasp_db",
        "collection": "owasp_requirements",
        "source_doc": "./framework_docs/owasp_top10.pdf",
        "chunk_size": 600,
        "chunk_overlap": 100,
        "group": "security",
    },
    "mit_ai_risk": {
        "name": "MIT AI Risk Repository",
        "db_dir": "./framework_dbs/mit_ai_risk_db",
        "collection": "mit_ai_risk_requirements",
        "source_doc": "./framework_docs/mit_ai_risk_repository.pdf",
        "chunk_size": 900,
        "chunk_overlap": 150,
        "group": "security",
    },
    "mit_secure_by_design": {
        "name": "MIT Secure-by-Design AI Framework",
        "db_dir": "./framework_dbs/mit_secure_by_design_db",
        "collection": "mit_secure_by_design_requirements",
        "source_doc": "./framework_docs/mit_secure_by_design.pdf",
        "chunk_size": 800,
        "chunk_overlap": 150,
        "group": "maturity",
    },
    "mitre_ai_maturity": {
        "name": "MITRE AI Maturity Model",
        "db_dir": "./framework_dbs/mitre_ai_maturity_db",
        "collection": "mitre_ai_maturity_requirements",
        "source_doc": "./framework_docs/mitre_ai_maturity_model.pdf",
        "chunk_size": 800,
        "chunk_overlap": 150,
        "group": "maturity",
    },
}

SCAN_GROUPS = {
    "security": [k for k, v in FRAMEWORKS.items() if v["group"] == "security"],
    "maturity": [k for k, v in FRAMEWORKS.items() if v["group"] == "maturity"],
    "full": list(FRAMEWORKS.keys()),
}

CAPABILITY_DB = {
    "db_dir": "./capability_db",
    "collection": "capabilities",
    "docs_dir": "./capability_docs",
    "chunk_size": 1500,
    "chunk_overlap": 300,
}

SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "text",
    ".md": "markdown",
}
