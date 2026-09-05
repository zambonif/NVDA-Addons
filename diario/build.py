#!/usr/bin/env python3
"""Monta o complemento do NVDA e, opcionalmente, um ZIP do repositório."""

from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
FIXED_DATE = (2026, 1, 1, 0, 0, 0)

ADDON_ROOT_FILES = ("manifest.ini", "LICENSE.txt")
ADDON_DIRECTORIES = ("globalPlugins", "doc", "locale")
SOURCE_ROOT_FILES = (
	".gitignore",
	"build.py",
	"CHANGELOG.md",
	"LICENSE.txt",
	"manifest.ini",
	"README.md",
	"README.pt-BR.md",
	"README.es.md",
	"README.it.md",
	"README.fr.md",
)
SOURCE_DIRECTORIES = (*ADDON_DIRECTORIES, "tests")


def readVersion() -> str:
	manifest = (ROOT / "manifest.ini").read_text(encoding="utf-8")
	match = re.search(r'^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"\s*$', manifest, re.MULTILINE)
	if not match:
		raise RuntimeError("manifest.ini não contém uma versão válida")
	return match.group(1)


def wantedFile(path: Path) -> bool:
	return (
		path.is_file()
		and "__pycache__" not in path.parts
		and path.suffix not in (".pyc", ".pyo")
	)


def filesFrom(rootFiles, directories):
	for name in rootFiles:
		path = ROOT / name
		if not path.is_file():
			raise FileNotFoundError(path)
		yield path
	for name in directories:
		directory = ROOT / name
		if not directory.is_dir():
			raise FileNotFoundError(directory)
		for path in sorted(directory.rglob("*")):
			if wantedFile(path):
				yield path


def writeFile(archive: zipfile.ZipFile, source: Path, archiveName: str) -> None:
	info = zipfile.ZipInfo(archiveName, FIXED_DATE)
	info.compress_type = zipfile.ZIP_DEFLATED
	info.create_system = 3
	info.external_attr = 0o100644 << 16
	archive.writestr(info, source.read_bytes())


def buildAddon(version: str) -> Path:
	output = DIST / f"diario-{version}.nvda-addon"
	with zipfile.ZipFile(output, "w") as archive:
		for path in filesFrom(ADDON_ROOT_FILES, ADDON_DIRECTORIES):
			writeFile(archive, path, path.relative_to(ROOT).as_posix())
	return output


def buildSource(version: str) -> Path:
	output = DIST / f"diario-{version}-source.zip"
	prefix = f"diario-{version}-source"
	with zipfile.ZipFile(output, "w") as archive:
		for path in filesFrom(SOURCE_ROOT_FILES, SOURCE_DIRECTORIES):
			archiveName = f"{prefix}/{path.relative_to(ROOT).as_posix()}"
			writeFile(archive, path, archiveName)
	return output


def writeChecksums(outputs: list[Path]) -> Path:
	path = DIST / "SHA256SUMS.txt"
	lines = []
	for output in outputs:
		digest = hashlib.sha256(output.read_bytes()).hexdigest()
		lines.append(f"{digest}  {output.name}\n")
	path.write_text("".join(lines), encoding="ascii", newline="\n")
	return path


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--source",
		action="store_true",
		help="também cria um ZIP pronto para iniciar ou atualizar o repositório Git",
	)
	arguments = parser.parse_args()

	version = readVersion()
	DIST.mkdir(exist_ok=True)
	outputs = [buildAddon(version)]
	if arguments.source:
		outputs.append(buildSource(version))
	checksums = writeChecksums(outputs)
	for output in (*outputs, checksums):
		print(output.relative_to(ROOT))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
