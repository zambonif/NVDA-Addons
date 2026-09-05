# -*- coding: UTF-8 -*-

"""Tradução selecionável e preferências próprias do Diário."""

from __future__ import annotations

import json
import os
import tempfile

from .translations import TRANSLATIONS


DEFAULT_LANGUAGE = "pt_BR"
PREFERENCES_FILE_NAME = "preferencias.json"
SUPPORTED_LANGUAGES = (
	("pt_BR", "Português (Brasil)"),
	("es", "Español"),
	("it", "Italiano"),
	("fr", "Français"),
	("en", "English"),
)
SUPPORTED_LANGUAGE_CODES = tuple(code for code, name in SUPPORTED_LANGUAGES)

_language = DEFAULT_LANGUAGE
_directory = None


def initialize(directory: str) -> None:
	"""Carrega a preferência sem tocar no conteúdo criptografado do Diário."""

	global _directory, _language
	_directory = os.path.abspath(directory)
	_language = DEFAULT_LANGUAGE
	path = os.path.join(_directory, PREFERENCES_FILE_NAME)
	try:
		with open(path, "r", encoding="utf-8") as stream:
			value = json.load(stream)
		candidate = value.get("language") if isinstance(value, dict) else None
		if candidate in SUPPORTED_LANGUAGE_CODES:
			_language = candidate
	except (OSError, ValueError, TypeError):
		# Uma preferência ausente ou danificada nunca pode impedir a abertura do Diário.
		pass


def getLanguage() -> str:
	return _language


def setLanguage(language: str) -> None:
	"""Grava a escolha de modo atômico e a aplica às próximas janelas."""

	global _language
	if language not in SUPPORTED_LANGUAGE_CODES:
		raise ValueError("Idioma do Diário não reconhecido.")
	if _directory is None:
		raise RuntimeError("As preferências do Diário ainda não foram inicializadas.")

	os.makedirs(_directory, exist_ok=True)
	descriptor, temporaryPath = tempfile.mkstemp(
		prefix="preferencias-",
		suffix=".tmp",
		dir=_directory,
		text=True,
	)
	try:
		with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
			json.dump({"language": language}, stream, ensure_ascii=False, indent=2)
			stream.write("\n")
			stream.flush()
			os.fsync(stream.fileno())
		os.replace(temporaryPath, os.path.join(_directory, PREFERENCES_FILE_NAME))
	except Exception:
		try:
			if os.path.exists(temporaryPath):
				os.unlink(temporaryPath)
		except OSError:
			pass
		raise
	_language = language


def translate(message: str) -> str:
	if _language == DEFAULT_LANGUAGE:
		return message
	return TRANSLATIONS.get(_language, {}).get(message, message)

