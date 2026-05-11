# This file is used to wrap the Isa_REPL to start and end the REPL

import hashlib
import logging
import os
import shutil
import subprocess
import time
import traceback
import weakref
from collections.abc import Iterable, Mapping, MutableMapping
from copy import deepcopy
from io import TextIOWrapper
from pathlib import Path
from typing import Literal, Self, TypeAlias

from py4j.java_gateway import GatewayParameters, JavaGateway, JavaObject
from pydantic import BaseModel, Field, model_validator

from config import ISA_REPL_PATH
from utils.isar_utils import (
    NormalizedStep,
    delete_comments,
    delete_texts,
    replaced_by_sorry,
)
from utils.parser import parse_hammer_facts, parse_java_object, parse_tactic

# pyright: reportCallIssue=false, reportOptionalMemberAccess=information, reportOptionalCall=information

logger = logging.getLogger(__name__)


def get_java_path(java_home: str | None = None) -> Path:
    """
    Get the path to the Java executable.

    Args:
        java_home (str | None): Optional JAVA_HOME. If not provided, the function will attempt to find Java in the system PATH.

    Returns:
        Path: The path to the Java executable.
    """
    # If java_home is not provided, check the JAVA_HOME environment variable
    if java_home is None:
        java_home = os.environ.get("JAVA_HOME")
    if java_home is not None:
        java_path = Path(java_home) / "bin" / "java"
        # Check if the Java executable exists.
        if not java_path.is_file():
            raise FileNotFoundError(
                f"Java executable not found in provided JAVA_HOME: {java_home}"
            )
        return java_path
    else:
        # Attempt to find Java in the system PATH.
        java_path_str = shutil.which("java")
        if java_path_str is None:
            raise FileNotFoundError("Java executable not found in system PATH.")
        return Path(java_path_str)

def update_env(envs: MutableMapping[str, str], updates: Mapping[str, str | None]):
    """Update the environment variables with the given updates. If a value in updates is None, remove that variable from envs."""
    for key, value in updates.items():
        if value is not None:
            envs[key] = value
        elif key in envs:
            del envs[key]


ToplevelType: TypeAlias = Literal["state", "prove", "chain", "other"]
ToplevelType.__doc__ = """
The type of the toplevel state. In Isabelle, the actual types of toplevel states are more complex than these. We only consider these four types for simplicity:
- state: the message is in the form of "proof (state)"
- prove: the message is in the form of "proof (prove)"
- chain: the message is in the form of "proof (chain)"
- other: other states that are not in the above three types like "theory", "skipped_proof", etc.
"""


def msg2TlsType(msg: str) -> ToplevelType:
    if msg.startswith("proof (state)"):
        return "state"
    elif msg.startswith("proof (chain)"):
        return "chain"
    elif msg.startswith("proof (prove)"):
        return "prove"
    else:
        return "other"


class ToplevelState(BaseModel):
    """
    ToplevelState is a class to abstract Isabelle toplevel state.
    The checksum is computed as sha256 of the prefix.
    """

    name: str
    prefix: list[NormalizedStep] = Field(
        default=[],
        description="Pieces of code from beginning of the theory file to this toplevel state. Since it is critical to skip the time-consuming PROOFs of the lemmas before the target in the same theory file, we may replace them with sorry tactics. So we use a list of normalized steps to represent the prefix instead of raw string.",
    )
    checksum: bytes | None = Field(
        default=None,
        description="SHA256 checksum of the prefix (32 bytes).",
    )
    msg: str = ""

    @staticmethod
    def compute_checksum(prefix: Iterable[NormalizedStep]) -> bytes:
        """Compute SHA256 checksum of the prefix."""
        return hashlib.sha256(" ".join(prefix).encode("utf-8")).digest()

    @model_validator(mode="after")
    def compute_checksum_if_empty(self):
        """Compute checksum from prefix if checksum is empty and prefix is provided."""
        if self.checksum is None and self.prefix:
            self.checksum = self.compute_checksum(self.prefix)
        return self

    def get_type(self) -> ToplevelType:
        return msg2TlsType(self.msg)


class SafeIsaRepl:
    def __init__(self, real_isa):
        self._real_isa = real_isa

    def __getattr__(self, name):
        # original
        attr = getattr(self._real_isa, name)
        if callable(attr):

            def wrapper(*args, **kwargs):
                try:
                    return attr(*args, **kwargs)
                except Exception as e:
                    # Preserve full traceback in the logs; callers see the
                    # exception type and message in the returned tuple.
                    logger.exception(
                        "SafeIsaRepl: %s(*%r, **%r) raised %s",
                        name,
                        args,
                        kwargs,
                        type(e).__name__,
                    )
                    tb = traceback.format_exc()
                    return False, f"{type(e).__name__}: {e}\n{tb}"

            return wrapper
        return attr


def _shutdown_gateway(gateway: JavaGateway | None):
    if gateway is not None:
        gateway.shutdown()


class IsaRepl:
    def __init__(self, port: int=25333, do_connect: bool = False, envs: Mapping[str, str | None] = {}):
        """
        IsaRepl is a python wrapper for the Isa_REPL Java backend. It provides methods to interact with the REPL, such as initializing with a theory file, stepping through proof states, and extracting information from the current state.

        Usage:
        Type 1: Use as a context manager to automatically manage the lifecycle of the Java process:
        ```python
        with IsaRepl(port=25333) as repl:
            repl.initialize("path/to/theory.thy")
            repl.step_to_target("target line in the theory")
            success, msg = repl.step("by auto")
            ...
        ```

        Type 2: Reuse an existing Java process:
        ```python
        repl = IsaRepl(port=25333, do_connect=True)
        repl.initialize("path/to/theory.thy")
        ...
        ```
        NOTE: 
        1. you can still use the `with` syntax if a process is already running, but the process will always be cleaned when exiting the `with` block.
        2. if `do_connect` is not set to True on instantiation, the connection to the Java backend will be deferred until the first call to `connect()` or entering the context manager.


        Args:
            port (int): The port number to use for the REPL.
            do_connect (bool): Whether to immediately connect to a running Java backend via the gateway. It will be ignored when using the `with` syntax.
            envs (dict[str, str | None]): Environment variables to pass to the backend REPL process when launched in __enter__.
        """
        self.theory_file: Path
        self.working_dir: str = ""
        self.session: str = ""
        self.session_dirs: list[str] = []

        self.port: int = port
        self._envs_update: Mapping[str, str | None] = envs
        self.envs: dict[str, str] | None = None

        self.process: subprocess.Popen | None = None
        self._log_file: TextIOWrapper | None = None

        self.gateway: JavaGateway | None = None
        self.isa_repl: JavaObject | None = None # type: ignore
        self._finalizer: weakref.finalize | None = None
        if do_connect:
            self.connect()

        self.tls_cache: dict[str, ToplevelState] = {}
        self.current_tls: str | None  # Current toplevel state name. If None, current state is not cached or we haven't checked whether it equals a previously cached state.
        self.current_prefix: list[NormalizedStep] = []
        self.current_msg: str = "" # Current state message (proof state)
        self._init_tls_cache()

    def _init_tls_cache(self):
        self.tls_cache.clear()
        self.current_tls = None
        self.current_prefix.clear()
        self.current_msg = ""

    def connect(self) -> JavaObject:
        """Connect to the Java gateway and obtain the REPL entry point object."""
        if self.isa_repl is not None:
            logger.warning("Already connected to Java Gateway on port %d", self.port)
            return self.isa_repl
        try:
            self.gateway = JavaGateway(
                gateway_parameters=GatewayParameters(port=self.port, auto_convert=True)
            )
            self.isa_repl = self.gateway.entry_point
        except Exception as e:
            logger.error("Failed to connect to Java Gateway: %s", e)
            raise ConnectionError("Failed to connect to Java Gateway")
        if self._finalizer is None:
            self._finalizer = weakref.finalize(self, _shutdown_gateway, self.gateway)
        self._init_tls_cache()
        
        return self.isa_repl

    # support context manager
    def __enter__(self) -> Self:
        """enter with block — launch the Java backend and connect to the gateway"""
        self.envs = os.environ.copy()
        update_env(self.envs, self._envs_update)

        if self.process is not None:
            logger.info("Reusing existing IsaRepl process (pid=%d)", self.process.pid)
        else:
            self.run_jar()

        if self.isa_repl is None:
            self.connect()
        self._init_tls_cache()
        return self

    def _wait_for_completion(self, timeout):
        end_time = time.time() + timeout
        while getattr(self, "_pending_operations", 0) > 0:
            if time.time() > end_time:
                raise TimeoutError("waiting for operations to complete timeout")
            time.sleep(0.1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """exit with block — kill the Java process, keep the gateway"""
        if hasattr(self, "_pending_operations"):
            self._wait_for_completion(timeout=3000)
        self.gateway = None
        self.isa_repl = None
        self.close_jar()
        return False

    def get_port(self) -> int:
        return self.port

    def run_jar(self):
        if not os.path.exists("logs/isa_repl"):
            os.makedirs("logs/isa_repl", exist_ok=True)
        log_path = f"logs/isa_repl/isa_repl_port_{self.port}.log"
        self._log_file = open(log_path, "w")
        jar_path = ISA_REPL_PATH
        process = subprocess.Popen(
            [
                str(get_java_path(self.envs.get("JAVA_HOME"))),  # pyright: ignore[reportOptionalMemberAccess]
                "-jar",
                jar_path,
                str(self.port),
            ],
            stdout=self._log_file,
            stderr=self._log_file,
            env=self.envs,
        )
        # Give the server some time to start
        time.sleep(1)
        if process.poll() is not None:
            self._log_file.flush()
            try:
                with open(log_path, "r", errors="replace") as f:
                    log_tail = f.read()[-500:].strip()
            except OSError:
                log_tail = ""
            raise RuntimeError(
                f"Failed to start IsaRepl on port {self.port}. {log_tail}"
            )
        self.process = process

    def close_jar(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            self.process = None
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None
        self.gateway = None
        self.isa_repl = None
        self._init_tls_cache()



    def initialize(
        self,
        theory_file: str,
        working_dir: str = ".tmp",
        session: str = "HOL",
        session_dirs: list[str] = [],
    ):
        """
        Initialize the IsaRepl with a theory file.

        Args:
            theory_file (str): Path to the Isabelle theory file to load.
            working_dir (str): Working directory for Isabelle build process. Defaults to ".tmp".
            session (str): Isabelle session name. Defaults to "HOL".
            session_dirs (list[str]): Additional directories for session roots. Defaults to [].

        Returns:
            tuple[bool, str]: Success status and message.
                On success, returns (True, "initialize successfully").
                On failure, raises ValueError with error message.
        """
        self.theory_file = Path(theory_file)
        self.working_dir = working_dir
        self.session = session
        self.session_dirs = session_dirs
        res = self.isa_repl._initializeRepl(
            str(self.theory_file), self.working_dir, self.session, self.session_dirs
        )
        ok, msg = parse_java_object(res)
        if not ok:
            raise ValueError(f"Error when initializing the REPL. Get msg: {msg}")
        self._init_tls_cache()
        return ok, msg

    # def reset(self):
    #     self.isa_repl._resetRepl(str(self.theory_file))

    def get_msg(self) -> str:
        """Get the current message."""
        return self.current_msg

    def step(self, step: str) -> tuple[bool, str]:
        """
        Run a piece of Isabelle code that may include one or multiple transitions of toplevel states.

        Args:
            step (str): Isabelle code to execute like "by arith", "have ... \\n by auto"
        Returns:
            tuple[bool, str]: Success status and message.
        """
        res = self.isa_repl._step(step)
        ok, msg = parse_java_object(res)
        if ok:
            self.current_tls = None  # After step, we don't know whether current tls equals a cached state unless we check it.
            self.current_prefix.extend(self.parse(step)[1])
            self.current_msg = msg  # Cache the current state message
        return ok, msg

    def execute_steps(self, steps: list[NormalizedStep]) -> tuple[bool, str]:
        """
        Run a list of normalized steps. Stop at the last successful step.

        Args:
            steps (list[NormalizedStep]): List of normalized steps to execute.
                Each step is a normalized step that only contains one transition of toplevel states.
        Returns:
            tuple[bool, str]: Success status and message.
        """
        success, message = True, "No proof found"
        for step in steps:
            # success, message = self.step(step)
            res = self.isa_repl._step(step)
            ok, msg = parse_java_object(res)
            if not ok:
                break
            self.current_tls = None  # After step, we don't know whether current tls equals a cached state unless we check it.
            self.current_prefix.append(step)
            self.current_msg = msg  # Cache the current state message
            message = msg
        return success, message

    def step_to_target(
        self, target: str, exclude_list: list[str] = [], use_cache: bool = True
    ):
        """
        Execute proof steps from the beginning of the initialized theory file to just after the first occurrence of the given target line/content.

        Args:
            target (str): Target line/content to execute up to.
            exclude_list (list[str]): List of file paths to exclude from sorry replacement.
            use_cache (bool): If True, check if the prefix exists in tls_cache and use cached state.

        Returns:
            tuple[bool, str]: Success status and message.
                Returns (True, message) if execution succeeds.
                Raises ValueError if target not found, parsing fails, or execution fails.
        """
        content = self.theory_file.read_text()
        if not target or target not in content:
            raise ValueError(f"cannot find target: {target}")
        target = target.lstrip()
        content: str = content.split(target, maxsplit=1)[0] + target
        ok, steps = self.parse(content)

        if not ok:
            raise ValueError(f"Error when parsing file {self.theory_file}")
        steps = delete_texts(delete_comments(steps))

        if str(self.theory_file) not in exclude_list:
            steps = replaced_by_sorry(steps)

        # Check if we can use existing cached state
        if use_cache:
            target_checksum = ToplevelState.compute_checksum(steps)
            found: ToplevelState | None = next(
                (
                    tls
                    for tls in self.tls_cache.values()
                    if tls.checksum == target_checksum
                ),
                None,
            )
            if found is not None:
                assert found.name is not None, (
                    "Cached ToplevelState name cannot be None!"
                )
                return self.focus_tls(found.name)

        self.current_prefix = []
        success, message = self.execute_steps(steps)
        if not success:
            raise ValueError(f"Error when executing the file {self.theory_file}")
        return success, message

    def hammer(self):
        res = self.isa_repl._prove_by_hammer()
        return parse_java_object(res)

    def hammer_facts(self):
        res = self.isa_repl._extract_hammer_facts()
        # True<\SEP>Selected 126 mepo facts: semiring_norm(86)
        return parse_hammer_facts(res)

    def try_close(self):
        res = self.isa_repl._try_close()
        return parse_java_object(res)

    def check_by_nitpick(self):
        res = self.isa_repl._check_by_nitpick()
        return parse_java_object(res)

    def check_by_quickcheck(self):
        res = self.isa_repl._check_by_quickcheck()
        return parse_java_object(res)

    def auto_prove(self, max_steps: int = 128):
        """Adaptively apply a tactic to the current goal.
            It will always succeed, even if the tactic fails.

        Args:
            max_steps (int): The maximum number of steps to apply.

        Returns:
            str: The tactic applied.
            str: The message from the tactic.
        """
        steps = []
        msg = "No proof found"
        for _ in range(max_steps):
            success, msg = self.try_close()
            if success:
                tactic = parse_tactic(msg.split("<\\SEP>")[0])
                ok, msg = self.step(tactic)
                if ok:
                    steps.append(tactic)
                    if self.proof_finished() and msg == "":
                        return steps, msg
                    else:
                        pass
                else:
                    print(
                        f"Tactic `try_close` get a tactic \n`{tactic}`,\n but failed to close the goal, get message \n`{msg}`"
                    )
                    break
            else:
                self.relearn_isar()  # NOTE: this is a hack to avoid the retrieval cheating
                success, msg = self.hammer()
                if success:
                    tactic = parse_tactic(msg.split("<\\SEP>")[0])
                    ok, msg = self.step(tactic)
                    if ok:
                        steps.append(tactic)
                        if self.proof_finished() and msg == "":
                            return steps, msg
                        else:
                            pass
                    else:
                        print(
                            f"Tactic `hammer` get a tactic \n`{tactic}`,\n but failed to close the goal, get message \n`{msg}`"
                        )
                        break
                else:
                    # print(f"Tactic `hammer` get a tactic \n`{tactic}`,\n but failed to close the goal, get message \n`{msg}`")
                    break
        return [], msg

    def relearn_isar(self):
        """Same as sledgehammer relearn_isar command.

        Returns:
            tuple[bool, str]: The result of the relearn operation..
        """
        res = self.isa_repl._mash_state_relearn()
        ok, msg = parse_java_object(res)
        return ok, msg

    def parse(self, thy: str) -> tuple[bool, list[NormalizedStep]]:
        """
        Parse a theorem to `NormalizedStep`s. Each normalized step is a string with no leading or trailing whitespace that represents a transition of ToplevelState.

        Args:
            thy (str): The theorem to parse.

        Returns:
            tuple[bool, list[NormalizedStep]]: Success status and steps.
        """
        res = self.isa_repl._parse_to_steps(thy)
        ok, msg = parse_java_object(res)
        if ok:
            return ok, msg.split("<\\SEP>")
        else:
            return ok, []

    def translate_to_smt(self):
        res = self.isa_repl._translate_to_smt()
        return parse_java_object(res)

    def extract_vars(self) -> tuple[bool, list[str]]:
        """Extract the variables from the current proof state."""
        res = self.isa_repl._extract_vars()
        ok, res = parse_java_object(res)
        var_lst = res.split("<\\SEP>")
        return ok, var_lst

    def extract_assms(self) -> tuple[bool, list[str]]:
        """Extract the assumptions from the current proof state."""
        res = self.isa_repl._extract_assms()
        ok, res = parse_java_object(res)
        assms = res.split("<\\SEP>")
        return ok, assms

    def extract_goal(self) -> tuple[bool, str]:
        """Extract the goal from the current proof state."""
        res = self.isa_repl._extract_goal()
        ok, res = parse_java_object(res)
        return ok, res

    def proof_finished(self) -> tuple[bool, str]:
        """Check if the proof is finished."""
        res = self.isa_repl._proof_finished()
        ok, res = parse_java_object(res)
        return ok, res

    def extract_theorem(self) -> tuple[bool, list[str], list[str], str]:
        """Extract the theorem from the current proof state."""
        ok1, vars = self.extract_vars()
        ok2, assms = self.extract_assms()
        ok3, goal = self.extract_goal()
        if not (ok1 and ok2 and ok3):
            return False, [], [], ""
        else:
            return True, vars, assms, goal

    def clone_tls(
        self, tls_name: str
    ) -> tuple[Literal[True], ToplevelState] | tuple[Literal[False], str]:
        """
        Create a new top level state in the cache with the name `tls_name`. If the `tls_name` already exists in the cache, overwrite it.

        Args:
            tls_name (str): The name of the new top level state.

        Returns:
            tuple[Literal[True], ToplevelState] | tuple[Literal[False], str]:
                If success, return a flag `True` and the new top level state.
                If fail, return a flag `False` and the error message.
        """
        res = self.isa_repl._clone_tls(tls_name)
        success, msg = parse_java_object(res)
        if success:
            if tls_name in self.tls_cache:
                print(f"Warning: overwrite existing tls: {tls_name}.")
            self.current_tls = tls_name
            self.tls_cache[tls_name] = ToplevelState(
                name=tls_name,
                prefix=deepcopy(self.current_prefix),
                msg=self.current_msg,
            )
            return success, self.tls_cache[tls_name]
        else:
            return False, msg

    def focus_tls(self, tls_name: str) -> tuple[bool, str]:
        """Focus on a top level state.

        Args:
            tls_name (str): The name of the top level state to focus on.

        Returns:
            tuple[bool, str]: The result of the focus operation.
        """
        if tls_name not in self.tls_cache:
            return False, f'tls "{tls_name}" not cached!'
        res = self.isa_repl._focus_tls(tls_name)
        success, msg = parse_java_object(res)
        if success:
            self.current_tls = tls_name
            self.current_prefix, self.current_msg = (
                deepcopy(self.tls_cache[tls_name].prefix),
                self.tls_cache[tls_name].msg,
            )
        return success, msg

    def remove_tls(self, tls_name: str) -> tuple[bool, str]:
        """Remove the top level state."""
        res = self.isa_repl._remove_tls(tls_name)
        success, msg = parse_java_object(res)
        if success:
            del self.tls_cache[tls_name]
            if self.current_tls == tls_name:
                self.current_tls = None
        return success, msg

    def get_tls(self, tls_name: str) -> ToplevelState:
        """Get the top level state with the name `tls_name`."""
        if tls_name not in self.tls_cache:
            raise KeyError(f'tls "{tls_name}" not cached!')
        return self.tls_cache[tls_name]

    def tls2type(self, tls_name: str | None = None) -> ToplevelType:
        """
        Get the type of the top level state with the name `tls_name`. If `tls_name` is None or not provided, return the type of the current top level state.

        """
        if tls_name is None:
            return msg2TlsType(self.current_msg)
        return self.get_tls(tls_name).get_type()
