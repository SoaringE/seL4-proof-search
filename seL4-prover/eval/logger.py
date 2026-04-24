import logging
import os

def get_proof_logger(log_dir: str = "logs", proof_name: str = "proof") -> logging.Logger:
    tree_search_log_dir = os.path.join(log_dir, "tree_search")
    os.makedirs(tree_search_log_dir, exist_ok=True)
    logger = logging.getLogger(f"{proof_name}")
    logger.setLevel(logging.INFO)
    log_path = os.path.join(tree_search_log_dir, f"{proof_name}.log")
    # avoid duplicate handler
    if not logger.handlers:
        handler = logging.FileHandler(log_path, mode='w')
        # formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
