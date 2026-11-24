"""Patch an exported AgentArts JSONL without changing the graph or original file.

Usage: uv run python tools/patch_triage_workflow.py INPUT.jsonl OUTPUT.jsonl
"""

import argparse
import ast
import json
from pathlib import Path


def patch_code(code: str, helper: str) -> str:
    old = "need = [field for field in REQUIRED_FIELDS if field in missing]"
    if old not in code:
        raise ValueError("Unsupported Parse-Request version; no output was written")
    code = code.replace(
        old, 'need = [field for field in REQUIRED_FIELDS + ["medication"] if field in missing]'
    )
    code = code.replace(
        'fields = need + (["medication"] if "medication" in missing else [])', "fields = need"
    )
    needle = "        missing = [field for field in FIELDS if not _values(normalized.get(field))]"
    if needle not in code:
        raise ValueError("Missing field classifier; no output was written")
    code = code.replace(
        needle,
        "        normalized = dict(normalized)\n"
        '        if isinstance(normalized.get("duration"), str):\n'
        '            normalized["duration"] = canonical_duration(normalized["duration"])\n'
        + needle,
    )
    code = code.replace("\ndef main(args:", "\n" + helper + "\n\ndef main(args:")
    code = code.replace("2026-11-21.mainflow-io.3", "2026-11-24.mainflow-io.4")
    return "from __future__ import annotations\nimport re\nimport unicodedata\n" + code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.destination.resolve():
        parser.error("The destination must differ from the original export")
    helper_path = Path(__file__).resolve().parents[1] / "app/episode/clarification.py"
    helper_source = helper_path.read_text(encoding="utf-8")
    tree = ast.parse(helper_source)
    helper = next(
        ast.get_source_segment(helper_source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "canonical_duration"
    )
    if not helper:
        raise ValueError("Duration helper not found")
    records = [
        json.loads(line)
        for line in args.source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    patched = 0
    for record in records:
        for node in record.get("dsl", {}).get("nodes", []):
            config = node.get("configs", {})
            code = config.get("code", "")
            if "def parse_request(args):" in code:
                updated = patch_code(code, helper)
                compile(updated, "workflow-node", "exec")
                config["code"] = updated
                patched += 1
    if not patched:
        raise ValueError("No matching Triage code nodes; no output was written")
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )
    print(f"Patched {patched} native code nodes; graph and original export preserved")


if __name__ == "__main__":
    main()
