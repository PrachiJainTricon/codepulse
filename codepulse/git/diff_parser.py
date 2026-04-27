# C:\Users\prachi.jain\tricon-git\codepulse\codepulse\git\diff_parser.py

import subprocess
import json
from typing import List, Dict, Literal

ChangedType = Literal["added", "modified", "deleted"]

ChangedSymbol = Dict[str, str]


def parse_diff(commit: str = "HEAD~1") -> List[ChangedSymbol]:
    """
    Run `git diff` in this repo and return list[ChangedSymbol].
    """
    result = subprocess.run(
        ["git", "diff", commit],
        text=True,
        capture_output=True,
        check=True
    )
    raw_diff = result.stdout
    return _parse_diff_text(raw_diff)


def _parse_diff_text(diff_text: str) -> List[ChangedSymbol]:
    """
    Very simple parser: only file names, mock symbol/kind.
    """
    lines = diff_text.splitlines()
    changed = []

    for line in lines:
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                from_path = parts[2].removeprefix("a/")
                to_path = parts[3].removeprefix("b/")

                if from_path == to_path:
                    change_type = "modified"
                elif from_path == "/dev/null":
                    change_type = "added"
                elif to_path == "/dev/null":
                    change_type = "deleted"
                else:
                    change_type = "modified"

                changed.append({
                    "file": from_path if from_path != "/dev/null" else to_path,
                    "symbol": "dummy_func",
                    "kind": "function",
                    "changeType": change_type
                })

    return changed


def mock_changed_symbols() -> List[ChangedSymbol]:
    """Hardcoded mock in the same schema."""
    return [
        {
            "file": "codepulse/parsers/python_parser.py",
            "symbol": "PythonParser.parse",
            "kind": "function",
            "changeType": "modified"
        },
        {
            "file": "tests/test_parsers.py",
            "symbol": "test_python_parser",
            "kind": "function",
            "changeType": "added"
        }
    ]