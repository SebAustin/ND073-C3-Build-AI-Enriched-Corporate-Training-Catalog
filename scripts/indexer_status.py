"""Wait for the indexers to finish and print their last result. Usage: python scripts/indexer_status.py [--wait]"""
import sys
import time

import search_client as sc


def status(name: str) -> dict:
    s = sc.request("GET", f"indexers/{name}/status")
    last = s.get("lastResult") or {}
    return {"indexer": name, "status": last.get("status", "none"), "processed": last.get("itemsProcessed"),
            "failed": last.get("itemsFailed"), "errors": [e.get("errorMessage", "")[:200] for e in last.get("errors", [])[:3]],
            "warnings": len(last.get("warnings", []))}


if __name__ == "__main__":
    names = [sc.COURSES["indexer"], sc.LIBRARY["indexer"]]
    for _ in range(60 if "--wait" in sys.argv else 1):
        results = [status(n) for n in names]
        if all(r["status"] not in ("inProgress", "none") for r in results):
            break
        time.sleep(10)
    for r in results:
        print(r)
