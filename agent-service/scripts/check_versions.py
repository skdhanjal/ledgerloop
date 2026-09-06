"""Fails loudly if the runtime graph drifted from what we locked."""
import importlib.metadata as md
import sys

EXPECTED = {
    "langgraph": "1.2", "langchain": "1.4", "langchain-core": "1.6",
    "langgraph-checkpoint-postgres": "3.1", "pydantic": "2.13",
    "fastapi": "0.141", "sse-starlette": "3.4", "psycopg": "3.3",
    "fastembed": "0.8", "faker": "40.", "langsmith": "0.12",
}
bad = []
for pkg, prefix in EXPECTED.items():
    try:
        got = md.version(pkg)
    except md.PackageNotFoundError:
        bad.append(f"{pkg}: NOT INSTALLED")
        continue
    if not got.startswith(prefix):
        bad.append(f"{pkg}: expected {prefix}.x, got {got}")
    print(f"  {pkg:32} {got}")
if bad:
    print("\nDRIFT DETECTED:")
    [print("  " + b) for b in bad]
    sys.exit(1)
print("\nversion graph OK")
