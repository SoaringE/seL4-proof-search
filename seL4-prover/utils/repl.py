# This file is used to wrap the Isa_REPL to start and end the REPL

import os
import subprocess
import time
from typing import Dict, List, Tuple

from py4j.java_gateway import GatewayParameters, JavaGateway

import utils.config as config
from utils.isar_utils import delete_comments, delete_texts, replaced_by_sorry
from utils.parser import parse_java_object, parse_tactic


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
                    print(f"repl execution error: {e}")
                    return False, str(e) 
            return wrapper
        return attr

class IsaRepl:
    """
    IsaRepl wraps the Isa_REPL to start and end the REPL, and to initialize the REPL with a theory file.
    """
    def __init__(self, port=25333, create_port=True):
        self.port: int = port
        self.create_port: bool = create_port
        self.isa_repl: JavaGateway.JavaObject = None # type: ignore
        self.process: subprocess.Popen | None = None
        self._log_file = None
        return
    
    # support context manager
    def __enter__(self):
        """enter with block"""
        self.start()
        return self  # return self, for use in with block

    def _wait_for_completion(self, timeout):
        end_time = time.time() + timeout
        while getattr(self, '_pending_operations', 0) > 0:
            if time.time() > end_time:
                raise TimeoutError("waiting for operations to complete timeout")
            time.sleep(0.1)
            
    def __exit__(self, exc_type, exc_val, exc_tb):
        """exit with block"""
        if hasattr(self, '_pending_operations'):
            # wait for all pending operations to complete or timeout
            self._wait_for_completion(timeout=3000)  # set a reasonable timeout
        self.close()
        return False  # return False, to propagate exception

    def run_jar_file(self):
        if not os.path.exists("logs/isa_repl"):
            os.makedirs("logs/isa_repl", exist_ok=True)
        log_path = f"logs/isa_repl/isa_repl_port_{self.port}.log"
        self._log_file = open(log_path, "w")
        jar_path = config.ISA_REPL_PATH
        env = os.environ.copy()
        env["ISABELLE_HOME"] = os.path.expanduser("~/verification/isabelle/")

        process = subprocess.Popen([
            "java", "-jar", jar_path, str(self.port)
        ],
        stdout=self._log_file,
        stderr=self._log_file,
        env=env,
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
        
    def start(self):
        if self.create_port:
            self.run_jar_file()
        gateway = JavaGateway(gateway_parameters=GatewayParameters(port=self.port, auto_convert=True))
        self.isa_repl = gateway.entry_point
        if self.isa_repl is None:
            raise ConnectionError("Failed to connect to Java Gateway")
        
    def close(self):
        if self.create_port and self.process is not None:
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
        return

    def initialize(
        self,
        theory_file: str,
        working_dir: str = ".tmp",
        session: str = "HOL",
        session_dirs: list[str] = [],
    ):
        self.theory_file = theory_file
        self.working_dir = working_dir
        self.session = session
        self.session_dirs = session_dirs
        res = self.isa_repl._initializeRepl(
            self.theory_file, self.working_dir, self.session, self.session_dirs
        )
        ok, msg = parse_java_object(res)
        if not ok:
            raise ValueError(f"Error when initializing the REPL. Get msg: {msg}")
        return ok, msg
    
    def reset(self):
        self.isa_repl._resetRepl(self.theory_file)

    def step(self, tactic):
        res = self.isa_repl._step(tactic)
        ok, msg = parse_java_object(res)
        return ok, msg
    
    def execute_steps(self, steps: list[str]):
        success, message = True, "No proof found"  
        for step in steps:
            success, message = self.step(step)
            if not success:
                print(message)
                break
        return success, message
    
    def step_to_target(self, path: str, target: str, exclude_list: list[str]=[]):
        with open(path, "r") as f:
            content = f.read()
        if target is None or target not in content:
            raise ValueError(f"cannot find target: {target}")
        if target != "":
            content = content.split(target, 1)[0] + "\n" + target
        ok, steps = self.parse(content)
        if not ok:
            raise ValueError(f"Error when parsing file {path}")
        steps = [step for step in steps if step.strip()]
        steps = delete_texts(delete_comments(steps))
        if path not in exclude_list:
            steps = replaced_by_sorry(steps)
        success, message = self.execute_steps(steps)
        if not success:
            raise ValueError(f"Error when executing the file {path}")
        return success, message
            
    def hammer(self):
        res = self.isa_repl._prove_by_hammer()
        return parse_java_object(res)
    
    def try_close(self):
        res = self.isa_repl._try_close()
        return parse_java_object(res)
    
    def check_by_nitpick(self):
        res = self.isa_repl._check_by_nitpick()
        return parse_java_object(res)
    
    def check_by_quickcheck(self):
        res = self.isa_repl._check_by_quickcheck()
        return parse_java_object(res)
    
    def auto_prove(self, max_steps: int=128):
        """ Adaptively apply a tactic to the current goal.
            It will always succeed, even if the tactic fails.
        
        Args:
            tactic (str): The tactic to apply.
            max_steps (int): The maximum number of steps to apply.

        Returns:
            str: The tactic applied.
            str: The message from the tactic.
        """
        steps = []
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
                        # print(f"Tactic `try_close` get a tactic \n`{tactic}`,\n the remaining goal is \n`{msg}`")
                        pass
                else:
                    print(f"Tactic `try_close` get a tactic \n`{tactic}`,\n but failed to close the goal, get message \n`{msg}`")
                    break
            else:
                self.relearn_isar() # NOTE: this is a hack to avoid the retrieval cheating
                success, msg = self.hammer()
                if success:
                    tactic = parse_tactic(msg.split("<\\SEP>")[0])
                    ok, msg = self.step(tactic)
                    if ok:
                        steps.append(tactic)
                        if self.proof_finished() and msg == "":
                            return steps, msg
                        else:
                            # print(f"Tactic `hammer` get a tactic \n`{tactic}`,\n the remaining goal is \n`{msg}`")
                            pass
                    else:
                        print(f"Tactic `hammer` get a tactic \n`{tactic}`,\n but failed to close the goal, get message \n`{msg}`")
                        break
                else:
                    # print(f"Tactic `hammer` get a tactic \n`{tactic}`,\n but failed to close the goal, get message \n`{msg}`")
                    break
        return [], msg

    def relearn_isar(self):
        """Same as sledgehammer relearn_isar command.
        
        Returns:
            Tuple[bool, str]: The result of the relearn operation..
        """
        res = self.isa_repl._mash_state_relearn()
        ok, msg = parse_java_object(res)
        return ok, msg

    def parse(self, thy:str) -> Tuple[bool, List[str]]:
        """Parse a theorem to steps.

        Args:
            thy (str): The theorem to parse.

        Returns:
            str: The steps of the theorem in the format of "<\\SEP>".
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
        
    def extract_vars(self) -> Tuple[bool, List[str]]:
        """Extract the variables from the current proof state.
        """
        res = self.isa_repl._extract_vars()
        ok, res = parse_java_object(res)
        var_lst = res.split("<\\SEP>")
        return ok, var_lst
    
    def extract_assms(self) -> Tuple[bool, Dict[str, str]]:
        """Extract the assumptions from the current proof state.
        """
        res = self.isa_repl._extract_assms()
        ok, res = parse_java_object(res)
        assms = res.split("<\\SEP>")
        return ok, assms
        
    def extract_goal(self) -> Tuple[bool, str]:
        """Extract the goal from the current proof state.
        """
        res = self.isa_repl._extract_goal()
        ok, res = parse_java_object(res)
        return ok, res
    
    def proof_finished(self) -> Tuple[bool, str]:
        """Check if the proof is finished.
        """
        res = self.isa_repl._proof_finished()
        ok, res = parse_java_object(res)
        return ok, res
    
    def extract_theorem(self) -> Tuple[bool, List[str], Dict[str, str], str]:
        """Extract the theorem from the current proof state.
        """
        ok1, vars = self.extract_vars()
        ok2, assms = self.extract_assms()
        ok3, goal = self.extract_goal()
        if not (ok1 and ok2 and ok3):
            return False, [], [], ""
        else:
            return True, vars, assms, goal
        
    def clone_tls(self, tls_name: str) -> Tuple[bool, str]:
        """Clone the current top level state.

        Args:
            tls_name (str): The name of the top level state to clone.

        Returns:
            Tuple[bool, str]: The result of the clone operation.
        """
        res = self.isa_repl._clone_tls(tls_name)
        return parse_java_object(res)
    
    def focus_tls(self, tls_name: str) -> Tuple[bool, str]:
        """Focus on a top level state.

        Args:
            tls_name (str): The name of the top level state to focus on.

        Returns:
            Tuple[bool, str]: The result of the focus operation.
        """
        res = self.isa_repl._focus_tls(tls_name)
        return parse_java_object(res)
    
    def remove_tls(self, tls_name: str) -> Tuple[bool, str]:
        """Remove the top level state.
        """
        res = self.isa_repl._remove_tls(tls_name)
        return parse_java_object(res)
    
    def find_theorems(self, patterns: list[str]) -> Tuple[bool, str]:
        return parse_java_object(self.isa_repl._find_theorems(patterns))
    
