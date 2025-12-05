import shutil
import subprocess
from pathlib import Path

def open_editor(file: Path, command: list = None):
    cmd = command or ["code", "--wait"]
    subprocess.run(cmd + [str(file)])