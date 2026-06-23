import json
import subprocess
import sys
from pathlib import Path
from gtm.config import REPO_ROOT


def _dbt_exe() -> str:
    return str(Path(sys.executable).parent / "dbt")


def dbt(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_dbt_exe(), *args, "--profiles-dir", "."],
        cwd=REPO_ROOT, check=True,
    )


def build(inject_break: bool = False, target: str = "local") -> None:
    dbt(["build", "--vars", json.dumps({"inject_break": inject_break}), "--target", target])
