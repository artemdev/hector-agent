import sys
import asyncio
import logging
from src.autofix import main
from src.progress import console
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s: %(message)s",
    handlers=[RichHandler(console=console, omit_repeated_times=False)],  # log lines print above the live view
)

logging.getLogger("claude_agent_sdk").setLevel(logging.WARNING)


try:
    asyncio.run(main())
except KeyboardInterrupt:
    sys.exit(130)
