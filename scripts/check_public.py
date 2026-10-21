"""Project-specific pre-publication scan; reports paths/lines, never matched secret values."""

import re
import subprocess
from pathlib import Path

RULES = {
    "credential_pattern": re.compile(r"(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{24,})"),
    "machine_absolute_path": re.compile(r"/(?:home|Users|mnt/[a-zA-Z])/[A-Za-z0-9_.-]+/"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "private_network_address": re.compile(
        r"https?://(?:10\.[0-9.]+|192\.168\.[0-9.]+|172\.(?:1[6-9]|2[0-9]|3[01])\.[0-9.]+)"
    ),
}


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        check=True,
        capture_output=True,
    )
    paths = sorted(set(p for p in result.stdout.decode().split("\x00") if p))
    problems = []
    for name in paths:
        path = Path(name)
        if not path.is_file():
            continue
        if path.name == ".env" or path.suffix in {".db", ".sqlite", ".key", ".pem"}:
            problems.append(f"{name}: forbidden file type")
            continue
        data = path.read_bytes()
        if b"\x00" in data or path.suffix == ".pdf":
            continue
        for number, line in enumerate(data.decode("utf-8").splitlines(), 1):
            for rule, pattern in RULES.items():
                if pattern.search(line):
                    problems.append(f"{name}:{number}: {rule}")
    print("\n".join(problems) if problems else f"Public-content scan passed ({len(paths)} files).")
    return bool(problems)


if __name__ == "__main__":
    raise SystemExit(main())
