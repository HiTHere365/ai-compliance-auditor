"""
Framework document version checker.

Uses HTTP HEAD requests to check whether newer versions of framework documents
are available at their source URLs. Compares Last-Modified and ETag headers
against a local cache. Does not download anything unless --update is passed.

MIT Secure-by-Design and MITRE AI Maturity Model have no versioned public URLs
and are flagged for manual review.

Usage:
    python src/doc_version_checker.py
    python src/doc_version_checker.py --update
"""

import argparse
import json
import os
import urllib.request
import urllib.error
from datetime import datetime

CACHE_FILE = "./doc_version_cache.json"

VERSIONED_DOCS = {
    "nist_genai": {
        "name": "NIST AI 600-1",
        "url": "https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.600-1.pdf",
        "local": "./framework_docs/nist_genai_600_1.pdf",
    },
    "mit_ai_risk": {
        "name": "MIT AI Risk Repository",
        "url": "https://airisk.mit.edu/sites/default/files/2024-02/AI_Risk_Repository_V1_30-01-24.pdf",
        "local": "./framework_docs/mit_ai_risk_repository.pdf",
    },
    "owasp": {
        "name": "OWASP Top 10 for LLM Applications",
        "url": "https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-2025-v1_0.pdf",
        "local": "./framework_docs/owasp_top10.pdf",
    },
}

MANUAL_DOCS = {
    "mit_secure_by_design": {
        "name": "MIT Secure-by-Design AI Framework",
        "note": "Article-based framework. Check https://sloanreview.mit.edu for updates.",
        "local": "./framework_docs/mit_secure_by_design.md",
    },
    "mitre_ai_maturity": {
        "name": "MITRE AI Maturity Model",
        "note": "Check https://www.mitre.org for updated versions.",
        "local": "./framework_docs/mitre_ai_maturity_model.pdf",
    },
}


def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def head_request(url: str) -> dict:
    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", "ai-compliance-auditor/1.0 (document version check)")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {
                "status": resp.status,
                "last_modified": resp.headers.get("Last-Modified"),
                "etag": resp.headers.get("ETag"),
                "content_length": resp.headers.get("Content-Length"),
            }
    except urllib.error.HTTPError as e:
        return {"status": e.code, "error": str(e)}
    except Exception as e:
        return {"status": None, "error": str(e)}


def download_doc(url: str, dest: str):
    print(f"  Downloading to {dest}...")
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "ai-compliance-auditor/1.0 (document update)")
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(dest, "wb") as f:
            f.write(resp.read())
    print(f"  Saved.")


def check_versioned(key: str, doc: dict, cache: dict, do_update: bool) -> dict:
    name = doc["name"]
    url = doc["url"]
    local = doc["local"]
    cached = cache.get(key, {})

    print(f"\n{name}")
    print(f"  URL: {url}")

    headers = head_request(url)

    if "error" in headers:
        print(f"  Could not reach URL: {headers['error']}")
        return cached

    last_modified = headers.get("last_modified")
    etag = headers.get("etag")
    content_length = headers.get("content_length")

    cached_lm = cached.get("last_modified")
    cached_etag = cached.get("etag")
    local_exists = os.path.exists(local)

    update_available = False

    if etag and cached_etag and etag != cached_etag:
        print(f"  Update available (ETag changed: {cached_etag} -> {etag})")
        update_available = True
    elif last_modified and cached_lm and last_modified != cached_lm:
        print(f"  Update available (Last-Modified: {cached_lm} -> {last_modified})")
        update_available = True
    elif not local_exists:
        print(f"  Local file missing.")
        update_available = True
    elif not cached_lm and not cached_etag:
        print(f"  No cached version headers. Run again after first download to track changes.")
    else:
        print(f"  Up to date.")

    if last_modified:
        print(f"  Last-Modified: {last_modified}")
    if content_length:
        size_mb = int(content_length) / (1024 * 1024)
        print(f"  Remote size: {size_mb:.1f} MB")

    if update_available and do_update:
        download_doc(url, local)

    return {
        "last_modified": last_modified,
        "etag": etag,
        "content_length": content_length,
        "last_checked": datetime.utcnow().isoformat() + "Z",
    }


def check_manual(key: str, doc: dict):
    name = doc["name"]
    note = doc["note"]
    local = doc["local"]
    local_exists = os.path.exists(local)

    print(f"\n{name}")
    print(f"  Manual check required: {note}")
    if local_exists:
        mtime = os.path.getmtime(local)
        dt = datetime.utcfromtimestamp(mtime).strftime("%Y-%m-%d")
        print(f"  Local file last modified: {dt}")
    else:
        print(f"  Local file not found: {local}")


def main():
    parser = argparse.ArgumentParser(description="Check framework document versions")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Download updated documents when a newer version is detected",
    )
    args = parser.parse_args()

    cache = load_cache()

    print("=" * 60)
    print("FRAMEWORK DOCUMENT VERSION CHECK")
    print(f"Checked: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    print("\n-- Versioned documents (URL-checked) --")
    updated_cache = dict(cache)
    for key, doc in VERSIONED_DOCS.items():
        result = check_versioned(key, doc, cache, args.update)
        if result:
            updated_cache[key] = result

    print("\n-- Manual review required --")
    for key, doc in MANUAL_DOCS.items():
        check_manual(key, doc)

    save_cache(updated_cache)
    print(f"\nCache saved to {CACHE_FILE}")

    if args.update:
        print("\nNote: If databases were rebuilt, run setup_databases.py to re-index updated documents.")


if __name__ == "__main__":
    main()
