"""Execute a project notebook using this interpreter and save stable outputs."""
from pathlib import Path
import argparse
import sys
import os
from tempfile import TemporaryDirectory

import nbformat
from jupyter_client import AsyncKernelManager
from nbclient import NotebookClient


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebook", nargs="?", type=Path, default=root / "notebooks/01_preprocessing.ipynb")
    args = parser.parse_args()
    path = args.notebook.resolve()
    notebook = nbformat.read(path, as_version=4)
    manager = AsyncKernelManager(kernel_name="python3")
    manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
    with TemporaryDirectory(prefix="evcharge-ipython-") as profile:
        NotebookClient(notebook, km=manager, timeout=300, startup_timeout=30, record_timing=False,
                       resources={"metadata": {"path": str(path.parent)}}).execute(
                           cleanup_kc=True, env={**os.environ, "IPYTHONDIR": profile})
    for cell in notebook.cells:
        cell.metadata = {}
    notebook.metadata = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}}
    nbformat.validate(notebook)
    nbformat.write(notebook, path)
    print(f"{path.name} executed and validated successfully; compact outputs saved.")


if __name__ == "__main__":
    main()
