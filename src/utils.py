
import sys
from itertools import cycle
import asyncio

async def show_spinner():
    frames = cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])
    try:
        for frame in frames:
            sys.stdout.write("\r\033[K" + frame + " working")
            sys.stdout.flush()
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        sys.stdout.write("\r\033[K")  # clear the line when done
        sys.stdout.flush()
        raise
