"""Container entrypoint: run the agent on the repo mounted at /work, printing the run as one JSON line.

    /work         the repo; the agent edits it in place (mount its .git read-only)
    /event.json   the Sentry event
    stdout        `{"result": ..., "tool_calls": ...}` when the agent finished, `{"failed": ...}` when it failed

Exit code: 0 when the agent finished, 1 when it failed.
"""
import asyncio
import dataclasses
import json
import logging
import sys
from pathlib import Path

from src.agent.run_agent import AgentFailed, run_agent

WORKDIR = Path("/work")
EVENT_FILE = Path("/event.json")


def main(workdir: Path = WORKDIR, event_file: Path = EVENT_FILE) -> int:
    event = json.loads(event_file.read_text())

    try:
        run = asyncio.run(run_agent(workdir, event))
    except AgentFailed as e:
        print(json.dumps({"failed": str(e)}))
        return 1

    print(json.dumps(dataclasses.asdict(run), default=str))  # default=str: anything JSON can't encode, as text
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(name)s: %(message)s")
    sys.exit(main())
