import json
import os
import ray
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple

from utils.repl import IsaRepl

import eval.config as config

class BaseEvaluator(ABC):
    """Base evaluator class for seL4 proof generation and verification evaluation"""
    
    def __init__(self, args: Any) -> None:
        """Initialize the evaluator
        
        Args:
            args: Command line arguments object
        """
        # Basic configuration
        self.server_num: int = args.server_num
        self.start_port: int = args.start_port
        self.check_point: str = args.check_point
        self.test: bool = args.test
        self.test_path: str = args.test_path
        self.timeout: int = args.timeout
        self.use_temp_file: bool = False  # TODO: support temp file
        self.save_path: str = args.save_path
        self.llm_address: str = args.llm_address
        self.use_crafted_steps = args.crafted_steps
        self.use_nitpick = args.nitpick
        self.log_dir: str = args.log_dir
        
        # Data source configuration
        if self.test_path:
            with Path(self.test_path).open("r") as f:
                self._custom_split: Optional[Dict[str, List[Dict[str, Any]]]] = json.load(f)
            self.data_sources = list(self._custom_split.keys())
        elif args.all_lemmas:
            self._custom_split = None
            self.data_sources = ["train", "val", "test", "test_hard"]
        else:
            self._custom_split = None
            self.data_sources = ["val", "test", "test_hard"]
        
        # Create output directories
        os.makedirs("output", exist_ok=True)
        os.makedirs(args.log_dir, exist_ok=True)
        
        # Initialize settings
        self._init_settings()
        
        # Initialize paths
        self._init_paths()
        
        # Initialize data structures
        self._init_data_structures()
        
        # Load dataset
        self._load_dataset()
        
        # Process session and path information
        self._process_session_info()
        
        # Setup environment
        self._setup_environment()
        
        # Initialize exclude list
        self._init_exclude_list()
        
    def _init_settings(self) -> None:
        """Initialize settings"""
        self.session_root = config.SESSION_ROOT
        self.execute_batch_size = config.EXECUTE_BATCH_SIZE

    def _init_paths(self) -> None:
        """Initialize file paths"""
        self.dataset_lemma_split_path = Path("/sel4-project/seL4-prover/datasets/dataset_lemma_split.json")
        
        self.sel4_session_info_path = Path(config.FVEL_EXTRACTION_PATH) / Path(
            "sel4_session_info.json"
        )
        self.sel4_thy_info_path = Path(config.FVEL_EXTRACTION_PATH) / Path(
            "sel4_thy_info.json"
        )

    def _init_data_structures(self) -> None:
        """Initialize data structures"""
        self.lemmas: Dict[str, List[Dict[str, Any]]] = {}
        self.lemma_lists: Dict[str, List[Dict[str, Any]]] = {}
        self.result_lists: Dict[str, List[Dict[str, Any]]] = {}
        self.success_nums: Dict[str, int] = {}
        self.task_started: int = 0
        
        for source in self.data_sources:
            self.lemma_lists[source] = []
            self.result_lists[source] = []
            self.success_nums[source] = 0

    def _load_dataset(self) -> None:
        """Load dataset from JSON file"""
        if self._custom_split is not None:
            dataset_lemma_split = self._custom_split
        else:
            with self.dataset_lemma_split_path.open("r") as f:
                dataset_lemma_split: Dict[str, List[Dict[str, Any]]] = json.load(f)

        for source in self.data_sources:
            self.lemmas[source] = dataset_lemma_split[source]

    def _process_session_info(self) -> None:
        """Process session information, find sessions and paths"""
        self.find_sessions()
        self.find_paths()

    def _setup_environment(self) -> None:
        """Setup environment variables"""
        self.custom_env: Dict[str, str] = os.environ.copy()
        self.custom_env["PATH"] = f"{config.ISABELLE_BIN_PATH}:" + self.custom_env["PATH"]

    def _init_exclude_list(self) -> None:
        """Initialize exclude list for theory files"""
        self.exclude_list: List[str] = [
            f"{self.session_root}spec/take-grant/Example2.thy",
            f"{self.session_root}lib/EVTutorial/EquivValidTutorial.thy",
            f"{self.session_root}lib/test/Apply_Debug_Test.thy",
            f"{self.session_root}lib/test/FastMap_Test.thy",
            f"{self.session_root}lib/test/RangeMap_Test.thy",
            f"{self.session_root}lib/test/FP_Eval_Tests.thy",
            f"{self.session_root}lib/test/CorresK_Test.thy",
        ]

    def find_sessions(self) -> None:
        """Find session information for theory files"""
        with self.sel4_thy_info_path.open("r") as f:
            sel4_thy_info: Dict[str, Dict[str, Any]] = json.load(f)
        
        all_theory_sessions: Dict[str, str] = {}
        for thy, thy_info in sel4_thy_info.items():
            # for theory in session_info["theories"]:
            #     all_theory_sessions[Path(theory).stem] = session
            # for additional_dir in session_info["additional_dir"]:
            #     target_dir = (
            #         Path(SESSION_ROOT)
            #         / Path(session_info["ROOT_dir"])
            #         / Path(session_info["ROOT_relative_dir"])
            #         / Path(additional_dir)
            #     )
            #     for file in target_dir.rglob("*"):
            #         if file.is_file() and file.suffix == ".thy":
            #             if file.stem not in all_theory_sessions:
            #                 all_theory_sessions[file.stem] = session
            all_theory_sessions[Path(thy).stem] = thy_info["session"]

        for key, value in self.lemmas.items():
            for lemma in value:
                lemma["session"] = all_theory_sessions[lemma["theory_name"]]

    def find_paths(self) -> None:
        """Find path information for theory files"""
        with self.sel4_session_info_path.open("r") as f:
            sel4_session_info: Dict[str, Dict[str, Any]] = json.load(f)
        
        all_theory_paths: Dict[str, str] = {}
        for session, session_info in sel4_session_info.items():
            for theory in session_info["theories"]:
                all_theory_paths[Path(theory).stem] = self.session_root + theory[1:]
            for additional_dir in session_info["additional_dir"]:
                target_dir = (
                    Path(self.session_root)
                    / Path(session_info["ROOT_dir"])
                    / Path(session_info["ROOT_relative_dir"])
                    / Path(additional_dir)
                )
                for file in target_dir.rglob("*"):
                    if file.is_file() and file.suffix == ".thy":
                        all_theory_paths[file.stem] = str(file)
        
        for key, value in self.lemmas.items():
            for lemma in value:
                lemma["path"] = all_theory_paths[lemma["theory_name"]]

    def eval(self) -> None:
        """Execute the complete evaluation pipeline"""
        print("Constructing dataset...")
        self.construct_theorems()
        
        print(f"There are {len(self.data_sources)} sources:")
        for source in self.data_sources:
            print(f"\t{source}: {len(self.lemma_lists[source])} lemmas to be evaluated")
        lemma_list, lemma_idx_mapping = self.prepare_dataset()
        
        print("Generating proofs...")
        ### single process
        # for lemma in self.lemma_lists["test"] + self.lemma_lists["test_hard"]:
        #     proof = self.generate_single_proof(lemma, 25555)
        #     lemma["generated_proof"] = proof
        ### multi process
        self.generate_proofs(lemma_list)
        print("Checking proofs...")
        self.check_proofs(lemma_list)
        print("Saving results...")
        self.save_results(lemma_list, lemma_idx_mapping)
        return 
    
    def batch_eval(self) -> None:
        """Execute the complete evaluation pipeline"""
        print("Constructing dataset...")
        self.construct_theorems()
        
        print(f"There are {len(self.data_sources)} sources:")
        for source in self.data_sources:
            print(f"\t{source}: {len(self.lemma_lists[source])} lemmas to be evaluated")
        lemma_list, lemma_idx_mapping = self.prepare_dataset()
        
        num_batches = (len(lemma_list) + 1) // self.execute_batch_size
        for batch_idx in range(num_batches):
            print(f"Processing batch {batch_idx}...")
            batch_start = batch_idx * self.execute_batch_size
            batch_end = min(batch_start + self.execute_batch_size, len(lemma_list))
            batch_lemma_list = lemma_list[batch_start: batch_end]
            print(f"Generating proofs for batch {batch_idx}...")
            self.generate_proofs(batch_lemma_list)
            print(f"Checking proofs for batch {batch_idx}...")
            self.check_proofs(batch_lemma_list)
            print(f"Saving results for batch {batch_idx}...")
            self.save_results(batch_lemma_list, lemma_idx_mapping)
            print(f"Batch {batch_idx} finished")
                
        return 

    def should_be_added(self, lemma: Dict[str, Any], checked_lemmas: Dict[str, Any]) -> bool:
        """Check if lemma should be added to evaluation list
        
        Args:
            lemma: Lemma information dictionary
            checked_lemmas: Dictionary of already checked lemmas
            
        Returns:
            True if lemma should be added, False otherwise
        """
        return (lemma["name"]) not in checked_lemmas

    def construct_theorems(self) -> None:
        """Construct the dataset for evaluation.
        
        The dataset is a list of lemmas, each lemma is a dictionary with the following keys:
        - name: the name of the lemma
        - statement: the statement of the lemma
        - path: the path of the lemma
        - session: the session of the lemma
        """
        self.task_started = 0

        checked_lemmas: Dict[str, Dict[str, Any]] = {}
        for source in self.data_sources:
            checked_lemmas[source] = {}

        checked_data: Dict[str, Any] = {}
        for source in self.data_sources:
            checked_data[source + "_pass"] = 0
        for source in self.data_sources:
            checked_data[source + "_results"] = []

        if self.check_point != "":
            with open(self.check_point, "r") as f:
                checked_data = json.load(f)

            for source in self.data_sources:
                checked_lemmas[source] = {
                    lemma["name"]: lemma for lemma in checked_data[source + "_results"]
                }

        for source in self.data_sources:
            for lemma in self.lemmas[source]:
                if self.should_be_added(lemma, checked_lemmas[source]):
                    self.lemma_lists[source].append(lemma)
                    if lemma["name"] in checked_lemmas[source]:
                        stored_result = checked_lemmas[source][lemma["name"]]
                        if stored_result.get("success", False):
                            checked_data[source + "_pass"] -= 1
                        checked_lemmas[source].pop(lemma["name"])
                else:
                    continue

        for source in self.data_sources:
            self.result_lists[source] = list(checked_lemmas[source].values())
            self.success_nums[source] = checked_data[source + "_pass"]
            
    def prepare_dataset(self) -> Tuple[List[Dict[str, Any]], Dict[Tuple[int, int], int]]:
        """Prepare the dataset for evaluation"""
        lemma_list: List[Dict[str, Any]] = []
        lamma_idx_mapping = {}
        idx = 0
        for (i, source) in enumerate(self.data_sources):
            for (j, lemma) in enumerate(self.lemma_lists[source]):
                lemma_list.append(lemma)
                lamma_idx_mapping[(i, j)] = idx
                idx += 1
        return lemma_list, lamma_idx_mapping
    
    def build_generate_method(self) -> None:
        """Build the proof generation method"""
        @abstractmethod
        def _generate_single_proof(lemma: Dict[str, Any], port: int) -> List[str]:
            """Generate a proof for a single lemma using the specified proof type.
            Note: it should be a ray remote function.

            Args:
                lemma: The lemma information dictionary
                port: The port for the Isabelle REPL
                
            Returns:
                List of proof steps
            """
            raise NotImplementedError("Subclasses must implement this method")
        
        self._generate_single_proof = _generate_single_proof
        
    def build_check_method(self) -> None:
        """Build the proof checking method"""
        @ray.remote
        def _check_single_proof(lemma: Dict[str, Any], port: int, session_root: str = config.SESSION_ROOT) -> Tuple[bool, str]:
            """Check a single proof for a single lemma.
            Note: it should be a ray remote function.

            Args:
                lemma: The lemma information dictionary
                port: The port for the Isabelle REPL
                session_root: The session root directory
                
            Returns:
                Tuple of (success_flag, message)
            """
            with IsaRepl(port=port, create_port=True) as isa_repl:
                if self.use_temp_file:
                    raise NotImplementedError("Temp file is not supported for now")
                    # template = "theory Test\n  imports {logic}.{theory_name}\nbegin\n"
                    # tmpdirname = tempfile.mkdtemp(dir='./.tmp')
                    # filepath = os.path.join(tmpdirname, 'Test.thy')
                    # with open(filepath, 'w') as f:
                    #     f.write(template.format(logic=lemma["session"], theory_name=lemma["theory_name"]))
                    # # print("temp dir:", tmpdirname)
                    # path = filepath
                else:
                    path = lemma["path"]
                
                isa_repl.initialize(path, session_root, lemma["session"], [session_root])
                success: bool = False
                msg: str = ""
                
                try:
                    if self.use_temp_file:
                        # step_success, message = parse_str_output(isa_repl._compile())
                        raise NotImplementedError("Temp file is not supported for now")
                    else:
                        isa_repl.step_to_target(lemma["path"], lemma["statement"], self.exclude_list)
                        # up to now, the theorem is successfully compiled
                        print(f"lemma: {lemma['name']}")
                        print(f"statement: {lemma['statement']}")
                        print(f"generated_proof: {lemma.get('generated_proof', [])}")
                        ok, msg = isa_repl.execute_steps(lemma.get("generated_proof", []))
                        if ok and msg == "":
                            success = True  # if the message is empty, then the proof is successful
                        else:
                            success = False  # if the proof is not successful, then the message is not empty
                        print(f"result: {success} with message: {msg}")
                except Exception as e:
                    success = False
                    msg = str(e)
                    print(f"result: {success} with message: {msg}")
                
                return success, msg

        self._check_single_proof = _check_single_proof
    
    def generate_proofs(self, lemma_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate proofs for all lemmas"""

        results: List[List[str]] = ray.get([
            self._generate_single_proof.remote(lemma, self.dispatch_port(idx)) 
            for (idx, lemma) in enumerate(lemma_list)
        ])
        
        for lemma, result in zip(lemma_list, results):
            lemma.update({"generated_proof": result})
        return lemma_list
    
    def check_proofs(self, lemma_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check proofs for all lemmas"""
        
        results: List[Tuple[bool, str]] = ray.get([
            self._check_single_proof.remote(lemma, self.dispatch_port(idx)) 
            for (idx, lemma) in enumerate(lemma_list)
        ])
        
        for lemma, result in zip(lemma_list, results):
            lemma.update({"success": result[0], "message": result[1]})
        return lemma_list

    def dispatch_port(self, offset: int) -> int:
        """Dispatch port number based on offset
        
        Args:
            offset: Port offset
            
        Returns:
            Port number
        """
        return self.start_port + offset

    def save_results(self, lemma_list: List[Dict[str, Any]], lemma_idx_mapping: Dict[Tuple[int, int], int]) -> None:
        """Save evaluation results"""
        print("Evaluating results:")
        
        for (i, source) in enumerate(self.data_sources):
            for (j, lemma) in enumerate(self.lemma_lists[source]):
                lemma_idx = lemma_idx_mapping[(i, j)]
                if lemma_list[lemma_idx]["success"]:
                    self.success_nums[source] += 1
            
            print(
                f"\t{source}: {self.success_nums[source]} out of {len(self.lemma_lists[source])} success"
            )

        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        with open(self.save_path, "w") as f:
            json.dump(self.lemma_lists, f, indent=2)
        print(f"Results saved to {self.save_path}")