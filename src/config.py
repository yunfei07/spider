import os
import sys

# Try to load formatted output if available, otherwise default
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_API_BASE_URL", os.getenv("OPENAI_BASE_URL")) # Support both namings
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-v4")

def check_api_key():
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("Please export OPENAI_API_KEY='sk-...' or create a .env file.")
        sys.exit(1)
