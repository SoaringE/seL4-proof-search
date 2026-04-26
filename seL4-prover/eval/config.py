import argparse
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from utils.lib import resolveAbsPath

__all__ = [
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "ISABELLE_PATH",
    "ISABELLE_USER_DIR",
    "SESSION_ROOT",
    "ISABELLE_BIN_PATH",
    "FVEL_EXTRACTION_PATH",
    "ISA_REPL_PATH",
    "DATASET_LEMMA_SPLIT_PATH",
    "STEP_LIMIT",
]

# Load environment variables from .env file
load_dotenv()

def parse_args():  
    parser = argparse.ArgumentParser("FVEL Evaluator")
    parser.add_argument("--server_num", type=int, default=9, help="Number of servers to run")
    parser.add_argument("--start_port", type=int, default=25555, help="Start port for servers")
    parser.add_argument("--check_point", type=str, default="", help="Checkpoint to load")
    parser.add_argument("--test", action="store_true", help="Whether to run test")
    parser.add_argument("--test_path", type=str, default="", help="Path to test file")
    parser.add_argument("--identifier", type=str, default="test")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout for each proof check")
    parser.add_argument("--all_lemmas", type=bool, default=False, help="Whether to run all lemmas")
    parser.add_argument("--save_path", type=str, default="", help="Path to save results")
    parser.add_argument("--llm_address", type=str, default="0.0.0.0:8080", help="Address of LLM server")
    parser.add_argument("--crafted_steps", action="store_true", help="Whether to use crafted steps")
    parser.add_argument("--nitpick", action="store_true", help="Whether to use nitpick")
    parser.add_argument("--log_dir", type=str, default="logs/temp", help="Path to save logs")
    return parser.parse_args()


# openai config
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv(
    "OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"
)
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# search config
STEP_LIMIT: int = int(os.getenv("STEP_LIMIT", "500"))
EXECUTE_BATCH_SIZE: int = int(os.getenv("EXECUTE_BATCH_SIZE", "50"))
CRAFTED_STEP_LIMIT: int = 16
PREMISE_LIMIT: int = 3

# path config
ISABELLE_PATH: str = resolveAbsPath(os.getenv("ISABELLE_PATH", ""))
ISABELLE_HOME: str = resolveAbsPath(os.getenv("ISABELLE_HOME", ""))
ISABELLE_USER_DIR: str = resolveAbsPath(os.getenv("ISABELLE_USER_DIR", ""))
SESSION_ROOT: str = resolveAbsPath(os.getenv("SESSION_ROOT", ""))
ISABELLE_BIN_PATH: str = resolveAbsPath(os.getenv("ISABELLE_BIN_PATH", ""))
FVEL_EXTRACTION_PATH: str = resolveAbsPath(os.getenv("FVEL_EXTRACTION_PATH", ""))
ISA_REPL_PATH: str = resolveAbsPath(os.getenv("ISA_REPL_PATH", ""))
L4V_PATH: Path = Path(os.path.expandvars(os.getenv("L4V_PATH", "l4v")))

# Dataset config: defaults to <FVEL_EXTRACTION_PATH>/dataset_lemma_split.json
# unless DATASET_LEMMA_SPLIT_PATH is explicitly set.
_dataset_lemma_split_env = os.getenv("DATASET_LEMMA_SPLIT_PATH", "")
if _dataset_lemma_split_env:
    DATASET_LEMMA_SPLIT_PATH: str = resolveAbsPath(_dataset_lemma_split_env)
elif FVEL_EXTRACTION_PATH:
    DATASET_LEMMA_SPLIT_PATH = str(Path(FVEL_EXTRACTION_PATH) / "dataset_lemma_split.json")
else:
    DATASET_LEMMA_SPLIT_PATH = ""

def update_environ():
    if ISABELLE_PATH == "":
        raise ValueError("ISABELLE_PATH environment variable is not set")
    if ISABELLE_HOME == "":
        raise ValueError("ISABELLE_HOME environment variable is not set")
    if ISA_REPL_PATH == "":
        raise ValueError("ISA_REPL_PATH environment variable is not set")
    os.environ["ISABELLE_PATH"] = ISABELLE_PATH
    os.environ["ISABELLE_HOME"] = ISABELLE_HOME
    os.environ["ISA_REPL_PATH"] = ISA_REPL_PATH
    
update_environ()

# remove HTTP/HTTPS proxy
def clear_proxy_env():
    """Clear proxy environment variables."""
    for var in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
        os.environ.pop(var, None)

clear_proxy_env()

# tree search config
TREE_SEARCH_MAX_ATTEMPTS: int = int(os.getenv("TREE_SEARCH_MAX_ATTEMPTS", "128")) # max attempts to find a proof
TREE_SEARCH_SELECTED_STATES_NUM: int = int(os.getenv("TREE_SEARCH_SELECTED_STATES_NUM", "5")) # at each iteration, select 5 states
TREE_SEARCH_SELECTED_HAMMER_NUM: int = int(os.getenv("TREE_SEARCH_SELECTED_HAMMER_NUM", "128")) # finally, select 128 hammer steps
TREE_SEARCH_WIDTH: int = int(os.getenv("TREE_SEARCH_WIDTH", "128")) # at each iteration, generate 128 steps
TREE_SEARCH_MAX_DEPTH: int = int(os.getenv("TREE_SEARCH_MAX_DEPTH", "128")) # max depth of the tree
