"""Interactive .env setup: asks for each value with hidden input and writes .env.

Usage (from the repo root):  python3 scripts/configure_env.py
Press Enter to keep the current value (or leave it blank). Nothing is printed back.
"""
from __future__ import annotations
import getpass
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV, EXAMPLE = ROOT / ".env", ROOT / ".env.example"

PROMPTS = [
    ("MONGODB_URI", "MongoDB connection string (Atlas > Cluster0 > Connect > Drivers > Python, password filled in)", True),
    ("LANGSMITH_API_KEY", "LangSmith API key (Enter to skip)", True),
    ("VOYAGE_API_KEY", "Voyage AI API key (optional, Enter to skip)", True),
    ("ELEVENLABS_API_KEY", "ElevenLabs API key (optional, Enter to skip)", True),
]


def read_env(path: pathlib.Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text().splitlines() if path.exists() else []
    values = {}
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            values[k.strip()] = v
    return lines, values


def main() -> None:
    lines, values = read_env(ENV if ENV.exists() else EXAMPLE)
    for key, label, secret in PROMPTS:
        have = " [set, Enter keeps it]" if values.get(key) else ""
        ask = getpass.getpass if secret else input
        new = ask(f"{label}{have}: ").strip()
        if new:
            values[key] = new
    if values.get("LANGSMITH_API_KEY"):
        values["LANGSMITH_TRACING"] = "true"

    out, seen = [], set()
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            k = line.split("=", 1)[0].strip()
            out.append(f"{k}={values.get(k, '')}")
            seen.add(k)
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in values.items() if k not in seen]
    ENV.write_text("\n".join(out) + "\n")
    ENV.chmod(0o600)

    uri = values.get("MONGODB_URI", "")
    print(f"Wrote {ENV} (only you can read it; it is gitignored).")
    print("MONGODB_URI:", "set" if uri.startswith("mongodb") else "MISSING or not a mongodb:// string")
    if "<db_password>" in uri or "<password>" in uri:
        print("WARNING: replace <db_password> in the connection string with your real database password.")
    print("LangSmith:", "set, tracing on" if values.get("LANGSMITH_API_KEY") else "skipped")


if __name__ == "__main__":
    main()
