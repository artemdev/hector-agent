import argparse
import asyncio
import json
import logging
import signal
import sys
from pathlib import Path

from rich.logging import RichHandler

from src.autofix import fix_issue
from src.progress import console


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="python -m src", description="Fix a Sentry issue and open a PR.")
    parser.add_argument("event", type=Path, help="the Sentry webhook payload, as a JSON file")
    parser.add_argument("--ref", help="branch or tag to fix (default: the repo's default branch)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s: %(message)s",
        handlers=[
            RichHandler(console=console, omit_repeated_times=False)
        ],  # log lines print above the live view
    )
    logging.getLogger("claude_agent_sdk").setLevel(logging.WARNING)

    signal.signal(signal.SIGTERM, signal.default_int_handler)

    try:
        asyncio.run(fix_issue(json.loads(args.event.read_text()), args.ref))
    except KeyboardInterrupt:
        sys.exit(130)
