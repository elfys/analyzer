from pathlib import Path


def get_indexed_filename(filename, extensions):
    index = max((sum((1 for f in Path(".").glob(f"{filename}*.{ext}"))) for ext in extensions)) + 1
    if index > 1:
        filename = f"{filename}-{index}"
    return filename
