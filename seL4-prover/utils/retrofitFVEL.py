import json
from pathlib import Path
from sys import argv
from typing import Any, Optional, TypedDict

from pydantic import TypeAdapter
from tqdm import tqdm

from data.FVELv2Data import FVELv2Data
from data.lemma import Lemma, LemmaFVEL
from data.session import (
    Session,
    SessionFVEL,
    new_Session_from_FVEL,
    safely_unquote_session_names,
)
from data.theory import Theory, TheoryFVEL, new_Theory_from_FVEL
from utils.lib import remove_quotes


def retrofitFVELSession(session_fvel: Path, out_dir: Path) -> dict[str, Session]:
    """
    Retrofit sel4_session_info.json to the new format.
    """
    with session_fvel.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    # The example JSON is a mapping of name->SessionFVEL object
    for name, sess_obj in data.items():
        sf = SessionFVEL(**sess_obj)
        data[name] = new_Session_from_FVEL(sf)

    safely_unquote_session_names(data)

    # Serialize back to JSON
    (out_dir / session_fvel.name.replace(".json", "V2.json")).write_bytes(
        TypeAdapter(dict[str, Session]).dump_json(data, indent=2)
    )
    return data


class LemmaDataIdx(TypedDict):
    split: str
    idx: int


def fromFVELTheory(theory_fvel: Path) -> dict[str, Theory]:
    """
    Load sel4_thy_info.json from FVEL format to the new format.
    Returns a dict of theory path to Theory object.
    """
    with theory_fvel.open("r", encoding="utf-8") as f:
        data_fvel = json.load(f)

    return {
        path: new_Theory_from_FVEL(TheoryFVEL(**thy_obj))
        for path, thy_obj in data_fvel.items()
    }


def findLemmaInThyData(
    lf: LemmaFVEL,
    thy_data: dict[str, Theory],
    theory_fvel: Path,
    data_idx: Optional[LemmaDataIdx] = None,
) -> Optional[Lemma]:
    """
    Find the corresponding Lemma object in thy_data for the given LemmaFVEL object.
    If not found, return None.
    """
    thy_name = lf.theory_name
    matching_thys = [p for p, t in thy_data.items() if t.name == thy_name]

    split: str
    idx: Optional[int]
    if data_idx is not None:
        split, idx = data_idx["split"], data_idx["idx"]
    else:
        split, idx = "unknown", None

    if not matching_thys:
        print(
            f"ERROR: Theory {thy_name} not found in {theory_fvel} for lemma {split}[{idx}]: {lf.name}\n"
        )
        return None
    if len(matching_thys) > 1:
        print(
            f"Warning: Multiple theories found in thy_data for lemma {split}[{idx}]: {lf.name}. Using the first one.",
            "The lemma:",
            "```",
            lf.statement,
            "```",
            "Matching theories:",
            "\n".join(matching_thys),
            "\n",
            sep="\n",
        )

    thy_path = matching_thys[0]

    thy = thy_data[thy_path]
    # Find the lemma by name and statement
    matching_lemmas = [
        i
        for i, l in enumerate(thy.cells)
        if isinstance(l, Lemma) and l.name == lf.name and l.statement == lf.statement
    ]

    if not matching_lemmas:
        # There may be more than one thys with the same name but different paths.
        if len(matching_thys) <= 1:
            print(
                f"ERROR: Lemma {lf.name} not found in {thy_path} for statement:",
                "```",
                lf.statement,
                "```\n",
                sep="\n",
            )
            return None
        else:
            # Try other matching theories until we find the lemma
            found = False
            for other_thy_path in matching_thys[1:]:
                matching_lemmas = [
                    i
                    for i, l in enumerate(thy_data[other_thy_path].cells)
                    if isinstance(l, Lemma)
                    and l.name == lf.name
                    and l.statement == lf.statement
                ]
                if matching_lemmas:
                    thy_path = other_thy_path
                    thy = thy_data[thy_path]
                    found = True
                    break
            if not found:
                print(
                    f"ERROR: Lemma {lf.name} not found in any theories matching the name {thy_name} for statement:",
                    "```",
                    lf.statement,
                    "```\n",
                    sep="\n",
                )
                return None
    if len(matching_lemmas) > 1:
        print(
            # f"Warning: Multiple lemmas found in {thy_path} for statement {lf.statement}. Using the first one."
            f"Warning: Multiple lemmas found in {thy_path} for lemma {lf.name} with statement:",
            "```",
            lf.statement,
            "```",
            "Using the first one.\n",
            sep="\n",
        )
    j = matching_lemmas[0]
    assert isinstance(thy_data[thy_path].cells[j], Lemma)
    thy_data[thy_path].cells[j].source = split  # type: ignore
    return thy_data[thy_path].cells[j]  # type: ignore


def retrofit_lemmas(
    thy_data: dict[str, Theory],
    theory_fvel: Path,
    dataset_path: Path,
) -> FVELv2Data:
    """
    Intermediate function to:
    1. load the splitted lemmas from the dataset_path
    2. find the corresponding Lemma object in thy_data for each lemma
    3. return the FVELv2Data object
    Since the theory data is very large, we introduce this function to reuse loaded theory data.

    Args:
        thy_data (dict[str, Theory]): The theory data in new format.
        theory_fvel (Path): Path to the sel4_thy_info.json file. This is only needed for logging.
        dataset_path (Path): Path to the splitted lemmas in FVEL format.

    Returns:
        FVELv2Data: The splitted lemmas in new format.
    """

    with dataset_path.open("r", encoding="utf-8") as f:
        dataset_fvel: dict[str, list[dict[str, Any]]] = json.load(f)

    datasetV2: FVELv2Data = {}
    for split, lem_list in dataset_fvel.items():
        datasetV2[split] = []
        for i, lemma_obj in enumerate(
            tqdm(lem_list, desc=f"Processing lemmas in {split}")
        ):
            lf = LemmaFVEL(**lemma_obj)
            found = findLemmaInThyData(
                lf, thy_data, theory_fvel, {"split": split, "idx": i}
            )
            if found is not None:
                datasetV2[split].append(found)
    return datasetV2


def fromFVELTheoryAndLemmas(
    theory_fvel: Path, lemmas_fvel: Path
) -> tuple[dict[str, Theory], FVELv2Data]:
    """
    Load sel4_thy_info.json and dataset_lemma_split.json from FVEL format to the new format.
    Returns:
        - A mapping of theory path to Theory object.
        - A mapping of split name to a mapping of lemma name to Lemma object.
    """
    thy_data: dict[str, Theory] = fromFVELTheory(theory_fvel)

    splited_lemmas: FVELv2Data = retrofit_lemmas(thy_data, theory_fvel, lemmas_fvel)
    return thy_data, splited_lemmas


def retrofitFVELTheoryAndLemmas(
    theory_fvel: Path, lemmas_fvel: Path, out_dir: Path
) -> None:
    thy_data, splited_lemmas = fromFVELTheoryAndLemmas(theory_fvel, lemmas_fvel)

    # Serialize the theories back to JSON
    (out_dir / theory_fvel.name.replace(".json", "V2.json")).write_bytes(
        TypeAdapter(dict[str, Theory]).dump_json(
            thy_data,
            indent=2,
        )
    )

    # Serialize the lemmas back to JSON
    (out_dir / lemmas_fvel.name.replace(".json", "V2.json")).write_bytes(
        TypeAdapter(dict[str, list[Lemma]]).dump_json(
            splited_lemmas,
            indent=2,
        )
    )


def splitPerThy(thy_fvel: Path, lem_fvel: Path, out_dir: Path):
    """
    For each theory in thy_fvel, create a separate JSON file.
    Args:
        thy_fvel (Path): Path to the sel4_thy_info.json file.
        lem_fvel (Path): Path to the dataset_lemma_split.json file.
        out_dir (Path): Path to the directory to output the split files.
    """
    # Get the retrofitted theory and lemmas
    thy_data, splited_lemmas = fromFVELTheoryAndLemmas(thy_fvel, lem_fvel)

    # For each theory, create a separate JSON file
    for thy in tqdm(thy_data.values(), desc="Dumping per-theory jsons"):
        thy_out_path = (out_dir / thy.path).with_suffix(".json")
        thy_out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(thy_out_path, "w", encoding="utf-8") as f:
            json.dump(thy.model_dump(mode="json"), f, indent=2)


def retrofitFVEL(FVEL_dir: Path, out_dir: Path):
    """
    Retrofit FVEL data in FVEL_dir to the new format in out_dir.

    Args:
        FVEL_dir (Path): Path to the directory containing FVEL data files. It should contain:
            - sel4_session_info.json
            - sel4_thy_info.json
            - dataset_lemma_split.json
        out_dir (Path): Path to the directory to output the retrofit files.
    Returns:
        None.
        Outputs the retrofitted files in out_dir:
            - sel4_session_infoV2.json
            - sel4_thy_infoV2.json
            - dataset_lemma_splitV2.json
    """

    # Create the output directory if it doesn't exist
    out_dir.mkdir(parents=True, exist_ok=True)

    # Process session file
    session_fvel = FVEL_dir / "sel4_session_info.json"
    sessions = retrofitFVELSession(session_fvel, out_dir)

    # Process theory_fvel and lemmas_fvel in memory
    theory_fvel = FVEL_dir / "sel4_thy_info.json"
    lemmas_fvel = FVEL_dir / "dataset_lemma_split.json"
    thy_data, splited_lemmas = fromFVELTheoryAndLemmas(theory_fvel, lemmas_fvel)

    # Safely unquote session names in theories and their cells
    for thy in thy_data.values():
        unquoted = remove_quotes(thy.session)
        if unquoted != thy.session and unquoted in sessions:
            thy.session = unquoted
        for cell in thy.cells:
            cell_unquoted = remove_quotes(cell.session)
            if cell_unquoted != cell.session and cell_unquoted in sessions:
                cell.session = cell_unquoted

    # Safely unquote session names in split lemmas
    for lem_list in splited_lemmas.values():
        for lemma in lem_list:
            unquoted = remove_quotes(lemma.session)
            if unquoted != lemma.session and unquoted in sessions:
                lemma.session = unquoted

    # Serialize the theories back to JSON
    (out_dir / theory_fvel.name.replace(".json", "V2.json")).write_bytes(
        TypeAdapter(dict[str, Theory]).dump_json(thy_data, indent=2)
    )

    # Serialize the lemmas back to JSON
    (out_dir / lemmas_fvel.name.replace(".json", "V2.json")).write_bytes(
        TypeAdapter(dict[str, list[Lemma]]).dump_json(splited_lemmas, indent=2)
    )


if __name__ == "__main__":
    if len(argv) != 3:
        print("Usage: python utils/retrofitFVEL.py <FVEL_dir> <out_dir>")
        exit(1)

    FVEL_dir = Path(argv[1])
    out_dir = Path(argv[2])

    assert FVEL_dir.is_dir(), f"{FVEL_dir} is not a directory."

    retrofitFVEL(FVEL_dir, out_dir)
