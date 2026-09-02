"""Gera o instalador .nvda-addon sem exigir SCons."""

from pathlib import Path
import zipfile


PROJECT_DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = PROJECT_DIRECTORY / "dist"
VERSION = "1.1.0"
OUTPUT_FILE = OUTPUT_DIRECTORY / f"diario-{VERSION}.nvda-addon"
INCLUDED_ROOTS = ("manifest.ini", "globalPlugins", "doc", "locale", "LICENSE.txt")


def shouldInclude(path: Path) -> bool:
	if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
		return False
	if "locale" in path.parts and path.suffix.lower() == ".md":
		return False
	return True


def main() -> None:
	OUTPUT_DIRECTORY.mkdir(exist_ok=True)
	with zipfile.ZipFile(OUTPUT_FILE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
		for rootName in INCLUDED_ROOTS:
			root = PROJECT_DIRECTORY / rootName
			if not root.exists():
				continue
			paths = [root] if root.is_file() else sorted(root.rglob("*"))
			for path in paths:
				if path.is_file() and shouldInclude(path):
					archive.write(path, path.relative_to(PROJECT_DIRECTORY).as_posix())
	print(OUTPUT_FILE)


if __name__ == "__main__":
	main()
