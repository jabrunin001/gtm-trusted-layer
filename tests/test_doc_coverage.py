import subprocess, sys
from gtm.config import REPO_ROOT

def test_doc_coverage_passes():
    r = subprocess.run([sys.executable, "scripts/check_doc_coverage.py"], cwd=REPO_ROOT)
    assert r.returncode == 0
