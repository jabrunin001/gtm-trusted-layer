import subprocess, sys
from pathlib import Path
import pytest
from gtm.config import REPO_ROOT


def _dbt_build_clean():
    exe = Path(sys.executable).parent / "dbt"
    subprocess.run(
        [str(exe), "build", "--vars", '{"inject_break": false}', "--profiles-dir", "."],
        cwd=REPO_ROOT,
        check=True,
    )


@pytest.fixture(scope="session", autouse=True)
def _clean_db_session():
    _dbt_build_clean()
    yield
    _dbt_build_clean()
