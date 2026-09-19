import os

from dotenv import load_dotenv
from langfuse import get_client, observe, propagate_attributes
from openinference.instrumentation.claude_agent_sdk import ClaudeAgentSDKInstrumentor

__all__ = ["langfuse", "observe", "propagate_attributes"]

load_dotenv()

langfuse = get_client()
if os.getenv("LANGFUSE_PUBLIC_KEY"):
    ClaudeAgentSDKInstrumentor().instrument() # Auto-captures every tool call and model completion as an OTEL span.
    if not langfuse.auth_check():
        print("Langfuse credentials set but auth_check failed — traces may not export")
