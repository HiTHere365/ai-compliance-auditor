"""
Framework document version checker.

Sends a one-byte ranged GET to each framework document's source URL (some
publishers, NIST among them, reject HEAD requests) and compares the
Last-Modified and ETag headers against a local cache. Does not download
anything unless --update is passed.

OWASP, MIT Secure-by-Design and MITRE AI Maturity Model have no direct
download URL and are listed for manual review.

Usage:
    python src/doc_version_checker.py
    python src/doc_version_checker.py --update
"""

import argparse
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

CACHE_FILE = "./doc_version_cache.json"

VERSIONED_DOCS = {
    "nist_genai": {
        "name": "NIST AI 600-1",
        "url": "https://doi.org/10.6028/NIST.AI.600-1",
        "local": "./framework_docs/nist_genai_600_1.pdf",
    },
    "mit_ai_risk": {
        "name": "MIT AI Risk Repository (arXiv paper, latest version)",
        "url": "https://arxiv.org/pdf/2408.12622",
        "local": "./framework_docs/mit_ai_risk_repository.pdf",
    },
}

MANUAL_DOCS = {
    "owasp": {
        "name": "OWASP Top 10 for LLM Applications",
        "note": "The PDF is behind a download form at https://genai.owasp.org/llm-top-10/ and cannot be fetched directly.",
        "local": "./framework_docs/owasp_top10.pdf",
    },
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


def probe_url(url: str) -> dict:
    """Fetch only the response headers by requesting the first byte.

    A HEAD request would be the obvious choice, but nvlpubs.nist.gov answers
    HEAD with 404 while serving the PDF on GET. A ranged GET works everywhere
    and transfers one byte. Content-Range carries the full size when the
    server honours the range; Content-Length is the fallback.
    """
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "ai-compliance-auditor/1.0 (document version check)")
    req.add_header("Range", "bytes=0-0")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            content_range = resp.headers.get("Content-Range", "")
            total = content_range.rsplit("/", 1)[-1] if "/" in content_range else None
            return {
                "status": resp.status,
                "final_url": resp.geturl(),
                "last_modified": resp.headers.get("Last-Modified"),
                "etag": resp.headers.get("ETag"),
                "content_length": total or resp.headers.get("Content-Length"),
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

    headers = probe_url(url)

    if "error" in headers:
        print(f"  Could not reach URL (HTTP {headers.get('status')}): {headers['error']}")
        return cached
    if headers.get("final_url") and headers["final_url"] != url:
        print(f"  Resolves to: {headers['final_url']}")

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
        "last_checked": datetime.now(timezone.utc).isoformat() + "Z",
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
        dt = datetime.fromtimestamp(mtime, timezone.utc).strftime("%Y-%m-%d")
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
    print(f"Checked: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
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
