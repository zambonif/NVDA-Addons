# -*- coding: UTF-8 -*-

"""Exportação e preparação segura de backups criptografados do Diário."""

from __future__ import annotations

from contextlib import contextmanager
import os
import stat
import tempfile
from typing import Iterable, Iterator
import zipfile

from .storage import Entry


VAULT_FILE_NAME = "diario.enc"
VAULT_BACKUP_FILE_NAME = "diario.backup.enc"
ARCHIVE_FILE_NAMES = (VAULT_FILE_NAME, VAULT_BACKUP_FILE_NAME)
MAX_ARCHIVE_MEMBER_SIZE = 128 * 1024 * 1024
COPY_CHUNK_SIZE = 1024 * 1024


class DiaryBackupError(RuntimeError):
	"""O backup não pôde ser exportado, validado ou preparado."""


def exportEncryptedVault(primaryPath: str, backupPath: str, destinationPath: str) -> None:
	"""Cria um ZIP atômico contendo somente as duas cópias criptografadas."""

	sources = (
		(VAULT_FILE_NAME, os.path.abspath(primaryPath)),
		(VAULT_BACKUP_FILE_NAME, os.path.abspath(backupPath)),
	)
	if any(not os.path.isfile(path) for archiveName, path in sources):
		raise DiaryBackupError(
			"Os dois arquivos criptografados do Diário precisam existir antes da exportação."
		)

	destinationPath = os.path.abspath(destinationPath)
	destinationDirectory = os.path.dirname(destinationPath)
	if not os.path.isdir(destinationDirectory):
		raise DiaryBackupError("A pasta escolhida para o backup não existe.")

	descriptor, temporaryPath = tempfile.mkstemp(
		prefix="diario-export-",
		suffix=".tmp",
		dir=destinationDirectory,
	)
	os.close(descriptor)
	try:
		with zipfile.ZipFile(
			temporaryPath,
			"w",
			compression=zipfile.ZIP_DEFLATED,
			compresslevel=6,
			allowZip64=True,
		) as archive:
			for archiveName, sourcePath in sources:
				archive.write(sourcePath, arcname=archiveName)
		with open(temporaryPath, "rb+") as stream:
			os.fsync(stream.fileno())
		os.replace(temporaryPath, destinationPath)
	except Exception as error:
		try:
			if os.path.exists(temporaryPath):
				os.unlink(temporaryPath)
		except OSError:
			pass
		raise DiaryBackupError("Não foi possível criar o arquivo ZIP do backup.") from error


def _validatedMembers(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
	members = archive.infolist()
	if len(members) != len(ARCHIVE_FILE_NAMES):
		raise DiaryBackupError(
			"O backup ZIP precisa conter somente diario.enc e diario.backup.enc."
		)
	byName = {member.filename: member for member in members}
	if len(byName) != len(members) or set(byName) != set(ARCHIVE_FILE_NAMES):
		raise DiaryBackupError(
			"O backup ZIP precisa conter somente diario.enc e diario.backup.enc."
		)
	for member in members:
		mode = member.external_attr >> 16
		if (
			member.is_dir()
			or stat.S_ISLNK(mode)
			or member.flag_bits & 0x1
			or member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
		):
			raise DiaryBackupError("O arquivo selecionado não é um backup ZIP válido do Diário.")
		if member.file_size < 1 or member.file_size > MAX_ARCHIVE_MEMBER_SIZE:
			raise DiaryBackupError(
				"Um dos arquivos criptografados do backup excede o limite de tamanho aceito."
			)
	return byName


def _copyValidatedMember(
	archive: zipfile.ZipFile,
	member: zipfile.ZipInfo,
	destinationPath: str,
) -> None:
	written = 0
	with archive.open(member, "r") as source, open(destinationPath, "xb") as destination:
		while True:
			chunk = source.read(COPY_CHUNK_SIZE)
			if not chunk:
				break
			written += len(chunk)
			if written > MAX_ARCHIVE_MEMBER_SIZE:
				raise DiaryBackupError(
					"Um dos arquivos criptografados do backup excede o limite de tamanho aceito."
				)
			destination.write(chunk)
		destination.flush()
		os.fsync(destination.fileno())
	if written != member.file_size:
		raise DiaryBackupError("O arquivo selecionado não é um backup ZIP válido do Diário.")


@contextmanager
def stagedImportArchive(archivePath: str) -> Iterator[str]:
	"""Valida o ZIP e expõe suas cópias cifradas em uma pasta temporária."""

	try:
		temporary = tempfile.TemporaryDirectory(
			prefix="diario-import-",
			ignore_cleanup_errors=True,
		)
	except OSError as error:
		raise DiaryBackupError("Não foi possível preparar o backup ZIP selecionado.") from error
	try:
		try:
			with zipfile.ZipFile(os.path.abspath(archivePath), "r") as archive:
				members = _validatedMembers(archive)
				for name in ARCHIVE_FILE_NAMES:
					_copyValidatedMember(
						archive,
						members[name],
						os.path.join(temporary.name, name),
					)
		except DiaryBackupError:
			raise
		except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
			raise DiaryBackupError("Não foi possível ler o backup ZIP selecionado.") from error
		yield temporary.name
	finally:
		temporary.cleanup()


def mergeNewEntries(
	currentEntries: Iterable[Entry],
	importedEntries: Iterable[Entry],
) -> tuple[list[Entry], list[Entry]]:
	"""Acrescenta somente IDs ainda inexistentes, preservando os dados atuais."""

	mergedEntries = list(currentEntries)
	knownIds = {entry.id for entry in mergedEntries}
	newEntries = []
	for entry in importedEntries:
		if entry.id in knownIds:
			continue
		knownIds.add(entry.id)
		newEntries.append(entry)
	mergedEntries.extend(newEntries)
	return mergedEntries, newEntries
