"""Process-wide wiring shared by the terminal chat, the web chat and the evals.

Importing this module loads the configuration (it may prompt for the API key)
and creates the one ``PipelineRegistry`` of the process. One coordinator can
serve several sessions as long as each uses its own thread id prefix.
"""

import os
from pathlib import Path

from agents.pipeline import PipelineRegistry
from config import load_config

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
CONVERSATIONS_DIR = PROJECT_DIR / "conversations"
LOGS_DIR = PROJECT_DIR / "logs"

config = load_config()
OPENROUTER_API_KEY = config.openrouter_api_key

# None of the agents needs vision, so the TEXT_* config is the shared base
# that each agent file's model directives override.
BASE_CONFIG = config.text
DEFAULT_ARCHITECTURE = os.environ.get("BANK_ARCH", "router")
REGISTRY = PipelineRegistry(BASE_CONFIG, OPENROUTER_API_KEY)
