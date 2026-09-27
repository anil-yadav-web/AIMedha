"""Create a source-only archive, excluding secrets, runtimes, caches and builds."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import os

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {'.git','.venv','.tools','.cache','node_modules','dist','__pycache__','.pytest_cache','artifacts'}

def sources():
    for directory,subdirs,files in os.walk(ROOT):
        subdirs[:] = [name for name in subdirs if name not in EXCLUDE]
        for name in files:
            path = Path(directory) / name
            if path.name.startswith('.env') and path.name != '.env.example':
                continue
            if path.suffix in {'.pyc','.log','.tsbuildinfo'}:
                continue
            yield path,path.relative_to(ROOT)

if __name__ == '__main__':
    output = ROOT / 'artifacts' / 'find-that-notice-source.zip'
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output,'w',compression=ZIP_DEFLATED) as archive:
        for path,rel in sources():
            archive.write(path,Path('find-that-notice') / rel)
    print(output)
