"""Kill the process at a random point, 20 times, and count clean resumes."""
import random
import subprocess
import sys
from pathlib import Path

from rich.console import Console

from graph.app import build_app, context_for

console = Console()
NODES = ["extract", "decide", "investigate", "approval_gate"]


def main(n: int = 20):
    survived = 0
    for i in range(n):
        node = random.choice(NODES)
        thread = f"kill:{i}"

        # child process dies inside `node` (os._exit, as on Day 9)
        subprocess.run([sys.executable, "chaos_drill.py", "--phase", "crash",
                        "--node", node, "--thread", thread],
                       capture_output=True)

        # parent resumes it
        app = build_app(checkpointer_kind="sqlite", store_kind="memory")
        cfg = {"configurable": {"thread_id": thread}}
        try:
            app.invoke(None, context=context_for("acme-corp"), config=cfg)
            survived += 1
        except Exception as e:
            console.print(f"[red]{i}: killed in {node} -> {type(e).__name__}: {e}")

    console.print(f"\n[bold]{survived}/{n} threads resumed cleanly[/bold]")
    console.print("[dim]anything below 20/20 is a bug, not bad luck - "
                  "find it before tagging[/dim]")


if __name__ == "__main__":
    main()