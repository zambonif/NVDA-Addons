# -*- coding: UTF-8 -*-

"""Persistência local e independente da interface do Diário."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import os
import shutil
import tempfile
from typing import Iterable
from uuid import uuid4


SCHEMA_VERSION = 1
DATA_FILE_NAME = "entradas.json"
BACKUP_FILE_NAME = "entradas.backup.json"


class DiaryStorageError(RuntimeError):
	"""Erro ao ler, validar ou gravar as entradas."""


@dataclass(frozen=True)
class Entry:
	"""Uma entrada do diário."""

	id: str
	title: str
	body: str
	entryDate: date
	createdAt: datetime
	updatedAt: datetime | None = None

	@classmethod
	def create(cls, title: str, body: str, entryDate: date) -> "Entry":
		return cls(
			id=uuid4().hex,
			title=title,
			body=body,
			entryDate=entryDate,
			createdAt=datetime.now().astimezone().replace(microsecond=0),
		)

	def edited(self, title: str, body: str, entryDate: date) -> "Entry":
		return Entry(
			id=self.id,
			title=title,
			body=body,
			entryDate=entryDate,
			createdAt=self.createdAt,
			updatedAt=datetime.now().astimezone().replace(microsecond=0),
		)

	def toDict(self) -> dict:
		return {
			"id": self.id,
			"title": self.title,
			"body": self.body,
			"entryDate": self.entryDate.isoformat(),
			"createdAt": self.createdAt.isoformat(timespec="seconds"),
			"updatedAt": self.updatedAt.isoformat(timespec="seconds") if self.updatedAt else None,
		}

	@classmethod
	def fromDict(cls, value: dict) -> "Entry":
		if not isinstance(value, dict):
			raise ValueError("A entrada não é um objeto.")

		entryId = value.get("id")
		title = value.get("title")
		body = value.get("body")
		if not isinstance(entryId, str) or not entryId:
			raise ValueError("A entrada não possui um identificador válido.")
		if not isinstance(title, str):
			raise ValueError("O título da entrada não é um texto.")
		if not isinstance(body, str):
			raise ValueError("O conteúdo da entrada não é um texto.")

		entryDate = date.fromisoformat(value["entryDate"])
		createdAt = datetime.fromisoformat(value["createdAt"])
		updatedValue = value.get("updatedAt")
		updatedAt = datetime.fromisoformat(updatedValue) if updatedValue else None
		return cls(
			id=entryId,
			title=title,
			body=body,
			entryDate=entryDate,
			createdAt=createdAt,
			updatedAt=updatedAt,
		)


@dataclass(frozen=True)
class LoadResult:
	entries: list[Entry]
	recoveredFromBackup: bool = False


class DiaryStorage:
	"""Lê e grava o arquivo JSON do Diário com substituição atômica e cópia de segurança."""

	def __init__(self, directory: str):
		self.directory = os.path.abspath(directory)
		self.filePath = os.path.join(self.directory, DATA_FILE_NAME)
		self.backupPath = os.path.join(self.directory, BACKUP_FILE_NAME)
		self._primaryWasInvalid = False

	def load(self) -> LoadResult:
		self._primaryWasInvalid = False
		if not os.path.exists(self.filePath):
			if os.path.exists(self.backupPath):
				try:
					return LoadResult(entries=self._readFile(self.backupPath), recoveredFromBackup=True)
				except Exception as backupError:
					raise DiaryStorageError(
						"A cópia de segurança das entradas não pôde ser lida."
					) from backupError
			return LoadResult(entries=[])

		try:
			return LoadResult(entries=self._readFile(self.filePath))
		except Exception as primaryError:
			self._primaryWasInvalid = True
			if os.path.exists(self.backupPath):
				try:
					return LoadResult(entries=self._readFile(self.backupPath), recoveredFromBackup=True)
				except Exception as backupError:
					raise DiaryStorageError(
						"O arquivo de entradas e sua cópia de segurança não puderam ser lidos."
					) from backupError
			raise DiaryStorageError("O arquivo de entradas não pôde ser lido.") from primaryError

	def save(self, entries: Iterable[Entry]) -> None:
		os.makedirs(self.directory, exist_ok=True)
		payload = {
			"schemaVersion": SCHEMA_VERSION,
			"entries": [entry.toDict() for entry in entries],
		}

		temporaryPath = self._writeTemporaryJson(payload, prefix="entradas-")
		try:
			if os.path.exists(self.filePath):
				if self._primaryWasInvalid:
					self._preserveInvalidPrimary()
				else:
					self._updateBackup()
			os.replace(temporaryPath, self.filePath)
			self._primaryWasInvalid = False
		except Exception as error:
			try:
				if os.path.exists(temporaryPath):
					os.unlink(temporaryPath)
			except OSError:
				pass
			raise DiaryStorageError("Não foi possível gravar as entradas do Diário.") from error

	def _readFile(self, path: str) -> list[Entry]:
		with open(path, "r", encoding="utf-8") as stream:
			payload = json.load(stream)
		if not isinstance(payload, dict):
			raise ValueError("A raiz do arquivo não é um objeto.")
		if payload.get("schemaVersion") != SCHEMA_VERSION:
			raise ValueError("Versão do arquivo de dados não reconhecida.")
		values = payload.get("entries")
		if not isinstance(values, list):
			raise ValueError("A lista de entradas é inválida.")
		entries = [Entry.fromDict(value) for value in values]
		if len({entry.id for entry in entries}) != len(entries):
			raise ValueError("Há identificadores de entrada repetidos.")
		return entries

	def _writeTemporaryJson(self, payload: dict, prefix: str) -> str:
		descriptor, path = tempfile.mkstemp(
			prefix=prefix,
			suffix=".tmp",
			dir=self.directory,
			text=True,
		)
		try:
			with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
				json.dump(payload, stream, ensure_ascii=False, indent=2)
				stream.write("\n")
				stream.flush()
				os.fsync(stream.fileno())
		except Exception:
			try:
				os.unlink(path)
			except OSError:
				pass
			raise
		return path

	def _updateBackup(self) -> None:
		descriptor, temporaryBackup = tempfile.mkstemp(
			prefix="backup-",
			suffix=".tmp",
			dir=self.directory,
		)
		os.close(descriptor)
		try:
			shutil.copy2(self.filePath, temporaryBackup)
			os.replace(temporaryBackup, self.backupPath)
		finally:
			if os.path.exists(temporaryBackup):
				os.unlink(temporaryBackup)

	def _preserveInvalidPrimary(self) -> None:
		timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
		candidate = os.path.join(self.directory, f"entradas-corrompidas-{timestamp}.json")
		counter = 2
		while os.path.exists(candidate):
			candidate = os.path.join(
				self.directory,
				f"entradas-corrompidas-{timestamp}-{counter}.json",
			)
			counter += 1
		shutil.copy2(self.filePath, candidate)
