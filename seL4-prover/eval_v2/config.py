import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

from utils.lib import resolveAbsPath

__all__ = [
    "SESSION_ROOT",
    "ISABELLE_HOME",
    "ISABELLE_USER_DIR",
    "ISA_REPL_PATH",
    "FVEL_EXTRACTION_PATH",
    "DATASET_LEMMA_SPLIT_PATH",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "L4V_PATH",
]

# Load environment variables from .env file
load_dotenv()

# openai config
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv(
    "OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"
)
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")


# path config
L4V_PATH: str = resolveAbsPath(os.getenv("L4V_PATH", "l4v"))
SESSION_ROOT: str = resolveAbsPath(os.getenv("SESSION_ROOT", L4V_PATH))

ISABELLE_HOME: str
_isa_home = os.getenv("ISABELLE_HOME")
if _isa_home is not None:
    ISABELLE_HOME = resolveAbsPath(_isa_home)
else:
    _found = shutil.which("isabelle")
    if _found is None:
        raise RuntimeError(
            "ISABELLE_HOME environment variable is not set and 'isabelle' executable "
            "was not found in PATH."
        )
    ISABELLE_HOME = resolveAbsPath(str(Path(_found).parent.parent))

ISABELLE_USER_DIR: str = resolveAbsPath(os.getenv("ISABELLE_USER_DIR", ""))


FVEL_EXTRACTION_PATH: str = resolveAbsPath(os.getenv("FVEL_EXTRACTION_PATH", ""))

# Dataset config: defaults to <FVEL_EXTRACTION_PATH>/dataset_lemma_split.json
# unless DATASET_LEMMA_SPLIT_PATH is explicitly set.
_dataset_lemma_split_env = os.getenv("DATASET_LEMMA_SPLIT_PATH", "")
DATASET_LEMMA_SPLIT_PATH: str
if _dataset_lemma_split_env:
    DATASET_LEMMA_SPLIT_PATH = resolveAbsPath(_dataset_lemma_split_env)
elif FVEL_EXTRACTION_PATH:
    DATASET_LEMMA_SPLIT_PATH = str(
        Path(FVEL_EXTRACTION_PATH) / "dataset_lemma_split.json"
    )
else:
    DATASET_LEMMA_SPLIT_PATH = ""

ISA_REPL_PATH: str = resolveAbsPath(os.getenv("ISA_REPL_PATH", ""))


def update_environ():
    if ISA_REPL_PATH == "":
        raise ValueError("ISA_REPL_PATH environment variable is not set")
    os.environ["ISA_REPL_PATH"] = ISA_REPL_PATH
    os.environ["ISABELLE_HOME"] = ISABELLE_HOME


update_environ()
