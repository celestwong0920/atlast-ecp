"""
Stress test configuration — models via OpenRouter.
"""
import os

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Models (via OpenRouter)
MODEL_SONNET = "anthropic/claude-sonnet-4-20250514"
MODEL_HAIKU = "anthropic/claude-3-5-haiku-20241022"
MODEL_GPT4O = "openai/gpt-4o"
MODEL_GPT4O_MINI = "openai/gpt-4o-mini"

# ECP Server
ECP_SERVER = "https://api.weba0.com"
LLACHAT_API = "https://api.llachat.com"

# Atlas identity
ATLAS_IDENTITY = os.path.expanduser("~/.ecp/production-agents/atlas.json")

# Stress test params
BATCH_UPLOAD_DELAY = 2  # seconds between batch uploads
MAX_RECORDS_PER_AGENT = 200
