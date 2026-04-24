import os
import re
from collections.abc import Iterable, MutableSequence
from pathlib import Path, PurePath
from typing import OrderedDict, TypeVar

import psutil
from rustworkx import PyDiGraph as DiGraph


def expand_vars(p: PurePath) -> Path:
    """
    Expand environment variables in the given path.
    """
    return Path(os.path.expandvars(str(p)))


def locate_file(
    f: str,
    dirs: Iterable[PurePath],
) -> list[Path]:
    """
    Given a file name and a list of directories, return the list of paths found in the directories.
    """
    return [p for p in [Path(d) / f for d in dirs] if expand_vars(p).exists()]


def remove_quotes(s: str) -> str:
    """Remove surrounding quotes from a string."""
    # There shouldn't be any spaces around s
    assert re.match(r"\s", s) is None and re.match(r"\s", s[-1]) is None
    if s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    elif s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    else:
        return s


N = TypeVar("N")


def build_digraph(edges: Iterable[tuple[N, N]]) -> DiGraph[N]:
    """
    Build a digraph from a list of edges, where each edge is a tuple of nodes (A, B) representing an edge A -> B.
    """
    graph: DiGraph[N] = DiGraph[N]()
    # nodes: list[N] = []
    src_idx: int
    dst_idx: int
    for src, dst in edges:
        if src not in graph.nodes():
            src_idx = graph.add_node(src)
        else:
            src_idx = graph.node_indexes()[graph.nodes().index(src)]
        if dst not in graph.nodes():
            dst_idx = graph.add_node(dst)
        else:
            dst_idx = graph.node_indexes()[graph.nodes().index(dst)]
        graph.add_edge(src_idx, dst_idx, (src, dst))
    return graph


def normalizeIsarPathPattern(p: str) -> str:
    """
    This is specialized for normalizing path patterns (i.e. imports, theories in ROOT files) in Isabelle:
    1. Remove surrounding quotes
    2. Expand environment variables
    3. Remove leading './' and trailing '/'
    """
    p = remove_quotes(p)
    p = os.path.expandvars(p)
    if p.startswith("./"):
        p = p[2:]
    if p.endswith("/"):
        p = p[:-1]
    return p


def resolveAbsPath(p: str) -> str:
    """
    Resolve a given absolute path by:
    1. replacing environment variables
    2. resolving symbolic links
    3. resolve all "." and ".." components
    4. returning the absolute path as a string.

    Args:
        p: The path to resolve. This is expected to be an absolute path already e.g. a path specified by an environment variable.
    Returns:
        The resolved absolute path as a string.
    """
    return str(Path(os.path.expandvars(p)).resolve())


T = TypeVar("T", bound=MutableSequence)


def delByIndices(l: T, indices: Iterable[int]) -> T:
    """
    Delete elements from a list by their indices.
    """
    for i in sorted(indices, reverse=True):
        del l[i]
    return l


def listDedup(lst: list, inplace: bool = True) -> list:
    """
    Remove duplicates from a list while preserving order.

    Args:
        lst: List of elements
        inplace: If True, modify the list in place. If False, return a new list. Default is True.

    Returns:
        List with duplicates removed.
    """
    res = list(OrderedDict.fromkeys(lst))
    if inplace:
        lst[:] = res
        return lst
    return res


def getFreeMemory() -> int:
    """
    Get free memory in MB at present.
    """
    return psutil.virtual_memory().available // (1024 * 1024)
