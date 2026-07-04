from __future__ import annotations
from pathlib import Path

KEYWORDS = ("source", "connector", "loader", "client", "fetcher", "registry", "report", "dashboard", "prediction", "evaluation")
SCAN_ROOTS = ("app", "orchestrator", "scripts", "templates", "docs")

def scan_repo_files(repo_root: Path) -> dict:
    files: list[str] = []
    for root in SCAN_ROOTS:
        base = repo_root / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            rel = path.relative_to(repo_root).as_posix()
            if any(keyword in rel.lower() for keyword in KEYWORDS):
                files.append(rel)
    files = sorted(dict.fromkeys(files))
    return {
        "scanned_roots": list(SCAN_ROOTS),
        "matched_file_count": len(files),
        "matched_files": files[:250],
        "truncated": len(files) > 250,
    }

def evidence_exists(repo_root: Path, candidates: list[str]) -> list[str]:
    found: list[str] = []
    for rel in candidates:
        if (repo_root / rel).exists():
            found.append(rel)
    return found
