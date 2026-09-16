"""Gera o pacote instalável do Diário para NVDA."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.ini"
VERSION = "1.4.1"
OUTPUT_DIRECTORY = ROOT / "dist"
OUTPUT_FILE = OUTPUT_DIRECTORY / f"diario-{VERSION}.nvda-addon"
PACKAGE_ITEMS = (
    "manifest.ini",
    "LICENSE.txt",
    "globalPlugins",
    "locale",
    "doc",
)


def add_item(archive: ZipFile, item: Path) -> None:
    """Inclui um arquivo ou uma árvore de diretórios no pacote."""
    if item.is_file():
        archive.write(item, item.relative_to(ROOT).as_posix())
        return

    for path in sorted(item.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix.lower() == ".pyc":
            continue
        archive.write(path, path.relative_to(ROOT).as_posix())


def main() -> None:
    """Valida a estrutura básica e cria o arquivo .nvda-addon."""
    if not MANIFEST.is_file():
        raise FileNotFoundError("manifest.ini não encontrado na raiz do fonte.")

    OUTPUT_DIRECTORY.mkdir(exist_ok=True)
    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()

    with ZipFile(OUTPUT_FILE, "w", compression=ZIP_DEFLATED) as archive:
        for relative_name in PACKAGE_ITEMS:
            item = ROOT / relative_name
            if not item.exists():
                raise FileNotFoundError(f"Item obrigatório não encontrado: {relative_name}")
            add_item(archive, item)

    print(f"Pacote criado: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
