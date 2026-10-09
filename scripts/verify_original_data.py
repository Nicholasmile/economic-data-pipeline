"""Verify the original dataset checksums without changing any files."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "dataset_hashes_before.json").read_text(encoding="utf-8-sig"))
    failures = []
    for entry in manifest:
        original = entry["Path"].replace("\\", "/")
        relative = original.split("/data/", 1)[1]
        path = ROOT / "data" / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest().upper() != entry["Hash"]:
            failures.append(str(path))
    if failures:
        print("Changed or missing original datasets:\n" + "\n".join(failures))
        return 1
    print(f"Verified: all {len(manifest)} original dataset files are unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
