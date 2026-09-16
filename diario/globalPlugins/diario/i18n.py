# -*- coding: UTF-8 -*-

"""Tradução selecionável e preferências próprias do Diário."""

from __future__ import annotations

import json
import os
import tempfile
import ctypes

from .translations import TRANSLATIONS


DEFAULT_LANGUAGE = "pt_BR"
DEFAULT_SPELL_LANGUAGE = "interface"
DEFAULT_SPELL_SOUND_ENABLED = True
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
_spellLanguage = DEFAULT_SPELL_LANGUAGE
_spellSoundEnabled = DEFAULT_SPELL_SOUND_ENABLED
_directory = None


def getSystemLanguage() -> str:
	"""Obtém a marca BCP 47 do idioma regional configurado no Windows."""

	try:
		kernel32 = ctypes.windll.kernel32
		function = kernel32.GetUserDefaultLocaleName
		function.argtypes = (ctypes.c_wchar_p, ctypes.c_int)
		function.restype = ctypes.c_int
		buffer = ctypes.create_unicode_buffer(85)
		if function(buffer, len(buffer)) > 0 and buffer.value:
			return buffer.value.replace("_", "-")
	except (AttributeError, OSError, TypeError, ValueError):
		pass
	return "en-US"


def initialize(directory: str) -> None:
	"""Carrega a preferência sem tocar no conteúdo criptografado do Diário."""

	global _directory, _language, _spellLanguage, _spellSoundEnabled
	_directory = os.path.abspath(directory)
	_language = DEFAULT_LANGUAGE
	_spellLanguage = DEFAULT_SPELL_LANGUAGE
	_spellSoundEnabled = DEFAULT_SPELL_SOUND_ENABLED
	path = os.path.join(_directory, PREFERENCES_FILE_NAME)
	try:
		with open(path, "r", encoding="utf-8") as stream:
			value = json.load(stream)
			candidate = value.get("language") if isinstance(value, dict) else None
			if candidate in SUPPORTED_LANGUAGE_CODES:
				_language = candidate
			spellCandidate = value.get("spellLanguage") if isinstance(value, dict) else None
			if spellCandidate in ("system", "interface", *SUPPORTED_LANGUAGE_CODES):
				_spellLanguage = spellCandidate
			soundCandidate = value.get("spellSoundEnabled") if isinstance(value, dict) else None
			if isinstance(soundCandidate, bool):
				_spellSoundEnabled = soundCandidate
	except (OSError, ValueError, TypeError):
		# Uma preferência ausente ou danificada nunca pode impedir a abertura do Diário.
		pass


def getLanguage() -> str:
	return _language


def getSpellLanguagePreference() -> str:
	return _spellLanguage


def getSpellCheckerLanguage() -> str:
	"""Resolve a preferência para uma marca de idioma aceita pelo Windows."""

	if _spellLanguage == "system":
		return getSystemLanguage()
	if _spellLanguage == "interface":
		return _language
	return _spellLanguage


def isSpellSoundEnabled() -> bool:
	return _spellSoundEnabled


def setLanguage(language: str) -> None:
	"""Grava a escolha de modo atômico e a aplica às próximas janelas."""

	setPreferences(language, _spellLanguage, _spellSoundEnabled)


def setPreferences(language: str, spellLanguage: str, spellSoundEnabled: bool) -> None:
	"""Grava todas as preferências de forma atômica."""

	global _language, _spellLanguage, _spellSoundEnabled
	if language not in SUPPORTED_LANGUAGE_CODES:
		raise ValueError("Idioma do Diário não reconhecido.")
	if spellLanguage not in ("system", "interface", *SUPPORTED_LANGUAGE_CODES):
		raise ValueError("Idioma do corretor não reconhecido.")
	if not isinstance(spellSoundEnabled, bool):
		raise ValueError("A preferência de som do corretor precisa ser booleana.")
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
			json.dump(
				{
					"language": language,
					"spellLanguage": spellLanguage,
					"spellSoundEnabled": spellSoundEnabled,
				},
				stream,
				ensure_ascii=False,
				indent=2,
			)
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
	_spellLanguage = spellLanguage
	_spellSoundEnabled = spellSoundEnabled


def translate(message: str) -> str:
	if _language == DEFAULT_LANGUAGE:
		return message
	return TRANSLATIONS.get(_language, {}).get(message, message)
