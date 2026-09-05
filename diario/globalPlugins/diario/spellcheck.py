# -*- coding: UTF-8 -*-

"""Corretor ortográfico do Diário baseado na API nativa do Windows.

O módulo não depende de pacotes Python distribuídos com o NVDA. A pequena
ponte COM usa somente ``ctypes`` e fica separada da interface para que qualquer
falha do corretor apenas desative os bipes e as sugestões.
"""

from __future__ import annotations

import ctypes
import os
import tempfile
import unicodedata

try:
	from logHandler import log
except ImportError:  # Permite testar a lógica fora do NVDA.
	import logging

	log = logging.getLogger(__name__)


DICTIONARY_FILE_NAME = "dicionario.txt"
MAX_WORD_LENGTH = 128
MAX_LOCAL_WORDS = 4096
MAX_SUGGESTIONS = 8
MAX_DICTIONARY_BYTES = 1024 * 1024

LANGUAGE_TAGS = {
	"pt_BR": "pt-BR",
	"es": "es-ES",
	"it": "it-IT",
	"fr": "fr-FR",
	"en": "en-US",
}

_JOINERS = frozenset(("'", "-", "\u02bc", "\u2010", "\u2011", "\u2019"))
_WINFUNCTYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)


class SpellCheckerUnavailable(RuntimeError):
	"""Indica que o Windows não oferece um corretor para o idioma pedido."""


class _GUID(ctypes.Structure):
	_fields_ = (
		("data1", ctypes.c_uint32),
		("data2", ctypes.c_uint16),
		("data3", ctypes.c_uint16),
		("data4", ctypes.c_ubyte * 8),
	)


def _guid(data1, data2, data3, *data4):
	return _GUID(data1, data2, data3, (ctypes.c_ubyte * 8)(*data4))


_CLSID_SPELL_CHECKER_FACTORY = _guid(
	0x7AB36653,
	0x1796,
	0x484B,
	0xBD,
	0xFA,
	0xE7,
	0x4F,
	0x1D,
	0xB7,
	0xC1,
	0xDC,
)
_IID_SPELL_CHECKER_FACTORY = _guid(
	0x8E018A9D,
	0x2415,
	0x4677,
	0xBF,
	0x08,
	0x79,
	0x4E,
	0xA6,
	0x1F,
	0x94,
	0xBB,
)

_COINIT_APARTMENTTHREADED = 0x2
_CLSCTX_INPROC_SERVER = 0x1
_RPC_E_CHANGED_MODE = 0x80010106
_S_OK = 0


def languageTag(languageCode: str) -> str:
	"""Converte o idioma próprio do Diário em uma marca reconhecida pelo Windows."""

	return LANGUAGE_TAGS.get(languageCode, LANGUAGE_TAGS["pt_BR"])


def isWordCharacter(character: str) -> bool:
	if not character:
		return False
	if character in _JOINERS:
		return True
	return unicodedata.category(character)[0] in ("L", "M", "N")


def isDictionaryWord(word: str) -> bool:
	if not word or len(word) > MAX_WORD_LENGTH:
		return False
	hasLetter = False
	for character in word:
		if not isWordCharacter(character):
			return False
		if unicodedata.category(character).startswith("L"):
			hasLetter = True
	return hasLetter


def finishesWord(character: str) -> bool:
	if not character or character in ("\b", "\x7f"):
		return False
	if ord(character) < 0x20:
		return character in ("\t", "\r", "\n")
	return not isWordCharacter(character)


def wordRangeEnding(text: str, position: int) -> tuple[int, int] | None:
	"""Localiza a palavra que termina exatamente em ``position``."""

	if position <= 0 or position > len(text) or not isWordCharacter(text[position - 1]):
		return None
	first = position - 1
	while first and isWordCharacter(text[first - 1]):
		first -= 1
	last = position
	while first < last and text[first] in _JOINERS:
		first += 1
	while last > first and text[last - 1] in _JOINERS:
		last -= 1
	return (first, last) if first < last else None


def wordRangeNear(text: str, position: int) -> tuple[int, int] | None:
	"""Localiza a palavra sob a posição ou a palavra anterior mais próxima."""

	if not text:
		return None
	position = max(0, min(position, len(text)))
	if position < len(text) and isWordCharacter(text[position]):
		anchor = position
	else:
		anchor = position
		while anchor and not isWordCharacter(text[anchor - 1]):
			anchor -= 1
		if not anchor:
			return None
		anchor -= 1
	first = anchor
	while first and isWordCharacter(text[first - 1]):
		first -= 1
	last = anchor + 1
	while last < len(text) and isWordCharacter(text[last]):
		last += 1
	while first < last and text[first] in _JOINERS:
		first += 1
	while last > first and text[last - 1] in _JOINERS:
		last -= 1
	return (first, last) if first < last else None


def _wordKey(word: str) -> str:
	return unicodedata.normalize("NFC", word).casefold()


class LocalDictionary:
	"""Dicionário simples, local ao complemento e gravado de forma atômica."""

	def __init__(self, directory: str):
		self.directory = os.path.abspath(directory)
		self.path = os.path.join(self.directory, DICTIONARY_FILE_NAME)
		self._words: dict[str, str] = {}
		self._writable = True
		self._load()

	@property
	def words(self) -> tuple[str, ...]:
		return tuple(self._words.values())

	def contains(self, word: str) -> bool:
		return _wordKey(word) in self._words

	def add(self, word: str) -> bool:
		word = unicodedata.normalize("NFC", word)
		if not self._writable or not isDictionaryWord(word):
			return False
		key = _wordKey(word)
		if key in self._words:
			return True
		if len(self._words) >= MAX_LOCAL_WORDS:
			return False
		candidate = dict(self._words)
		candidate[key] = word
		if not self._save(candidate):
			return False
		self._words = candidate
		return True

	def _load(self) -> None:
		try:
			if os.path.getsize(self.path) > MAX_DICTIONARY_BYTES:
				raise OSError("o dicionário local excede o limite de tamanho")
			with open(self.path, "r", encoding="utf-8-sig") as stream:
				for rawLine in stream:
					word = unicodedata.normalize("NFC", rawLine.strip())
					if isDictionaryWord(word):
						self._words.setdefault(_wordKey(word), word)
					if len(self._words) > MAX_LOCAL_WORDS:
						raise OSError("o dicionário local contém palavras demais")
		except FileNotFoundError:
			return
		except (OSError, UnicodeError):
			# Não sobrescreve silenciosamente um arquivo que não pôde ser lido.
			self._words.clear()
			self._writable = False
			log.exception("Não foi possível carregar o dicionário local do Diário.")

	def _save(self, words: dict[str, str]) -> bool:
		temporaryPath = None
		try:
			os.makedirs(self.directory, exist_ok=True)
			descriptor, temporaryPath = tempfile.mkstemp(
				prefix="dicionario-",
				suffix=".tmp",
				dir=self.directory,
				text=True,
			)
			with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
				for key in sorted(words):
					stream.write(words[key])
					stream.write("\n")
				stream.flush()
				os.fsync(stream.fileno())
			os.replace(temporaryPath, self.path)
			return True
		except OSError:
			log.exception("Não foi possível salvar o dicionário local do Diário.")
			return False
		finally:
			if temporaryPath:
				try:
					if os.path.exists(temporaryPath):
						os.unlink(temporaryPath)
				except OSError:
					pass


def _failed(result: int) -> bool:
	return result < 0


def _formatHresult(result: int) -> str:
	return f"0x{result & 0xFFFFFFFF:08X}"


def _comMethod(pointer, index: int, resultType, *argumentTypes):
	if not pointer:
		raise SpellCheckerUnavailable("ponte COM sem interface")
	vtable = ctypes.cast(
		pointer,
		ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
	).contents
	address = vtable[index]
	if not address:
		raise SpellCheckerUnavailable("ponte COM sem método")
	return _WINFUNCTYPE(resultType, ctypes.c_void_p, *argumentTypes)(address)


def _release(pointer) -> None:
	if not pointer:
		return
	try:
		method = _comMethod(pointer, 2, ctypes.c_uint32)
		method(pointer)
	except Exception:
		# close() é chamado inclusive durante a recuperação de falhas de COM.
		pass


class WindowsSpellChecker:
	"""Invólucro mínimo das interfaces ISpellChecker do Windows."""

	def __init__(self, languageTagValue: str):
		if os.name != "nt":
			raise SpellCheckerUnavailable("o corretor do Windows só existe no Windows")
		# WinDLL devolve o HRESULT bruto. OleDLL o transformaria em exceção antes
		# de podermos aceitar RPC_E_CHANGED_MODE, que é válido quando o NVDA já
		# inicializou a thread principal em outro modelo COM.
		self._ole32 = ctypes.WinDLL("ole32", use_last_error=True)
		self._factory = ctypes.c_void_p()
		self._checker = ctypes.c_void_p()
		self._ownsComInitialization = False
		self._configureOle32()
		try:
			self._initialize(languageTagValue)
		except Exception:
			self.close()
			raise

	def _configureOle32(self) -> None:
		self._ole32.CoInitializeEx.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
		self._ole32.CoInitializeEx.restype = ctypes.c_int32
		self._ole32.CoUninitialize.argtypes = ()
		self._ole32.CoUninitialize.restype = None
		self._ole32.CoCreateInstance.argtypes = (
			ctypes.POINTER(_GUID),
			ctypes.c_void_p,
			ctypes.c_uint32,
			ctypes.POINTER(_GUID),
			ctypes.POINTER(ctypes.c_void_p),
		)
		self._ole32.CoCreateInstance.restype = ctypes.c_int32
		self._ole32.CoTaskMemFree.argtypes = (ctypes.c_void_p,)
		self._ole32.CoTaskMemFree.restype = None

	def _initialize(self, languageTagValue: str) -> None:
		result = self._ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED)
		if not _failed(result):
			self._ownsComInitialization = True
		elif (result & 0xFFFFFFFF) != _RPC_E_CHANGED_MODE:
			raise SpellCheckerUnavailable(
				f"CoInitializeEx falhou com {_formatHresult(result)}"
			)

		result = self._ole32.CoCreateInstance(
			ctypes.byref(_CLSID_SPELL_CHECKER_FACTORY),
			None,
			_CLSCTX_INPROC_SERVER,
			ctypes.byref(_IID_SPELL_CHECKER_FACTORY),
			ctypes.byref(self._factory),
		)
		if _failed(result) or not self._factory:
			raise SpellCheckerUnavailable(
				f"ISpellCheckerFactory falhou com {_formatHresult(result)}"
			)

		supported = ctypes.c_int(0)
		isSupported = _comMethod(
			self._factory,
			4,
			ctypes.c_int32,
			ctypes.c_wchar_p,
			ctypes.POINTER(ctypes.c_int),
		)
		result = isSupported(self._factory, languageTagValue, ctypes.byref(supported))
		if _failed(result) or not supported.value:
			raise SpellCheckerUnavailable(
				f"o Windows não possui dicionário para {languageTagValue}"
			)

		create = _comMethod(
			self._factory,
			5,
			ctypes.c_int32,
			ctypes.c_wchar_p,
			ctypes.POINTER(ctypes.c_void_p),
		)
		result = create(self._factory, languageTagValue, ctypes.byref(self._checker))
		if _failed(result) or not self._checker:
			raise SpellCheckerUnavailable(
				f"CreateSpellChecker falhou com {_formatHresult(result)}"
			)

	def isMisspelled(self, word: str) -> bool:
		errors = ctypes.c_void_p()
		error = ctypes.c_void_p()
		try:
			check = _comMethod(
				self._checker,
				4,
				ctypes.c_int32,
				ctypes.c_wchar_p,
				ctypes.POINTER(ctypes.c_void_p),
			)
			result = check(self._checker, word, ctypes.byref(errors))
			if _failed(result) or not errors:
				raise SpellCheckerUnavailable(
					f"ISpellChecker.Check falhou com {_formatHresult(result)}"
				)
			nextError = _comMethod(
				errors,
				3,
				ctypes.c_int32,
				ctypes.POINTER(ctypes.c_void_p),
			)
			result = nextError(errors, ctypes.byref(error))
			if _failed(result):
				raise SpellCheckerUnavailable(
					f"IEnumSpellingError.Next falhou com {_formatHresult(result)}"
				)
			return result == _S_OK and bool(error)
		finally:
			_release(error)
			_release(errors)

	def suggestions(self, word: str) -> list[str]:
		values = ctypes.c_void_p()
		collected = []
		try:
			suggest = _comMethod(
				self._checker,
				5,
				ctypes.c_int32,
				ctypes.c_wchar_p,
				ctypes.POINTER(ctypes.c_void_p),
			)
			result = suggest(self._checker, word, ctypes.byref(values))
			if _failed(result) or not values:
				raise SpellCheckerUnavailable(
					f"ISpellChecker.Suggest falhou com {_formatHresult(result)}"
				)
			nextValue = _comMethod(
				values,
				3,
				ctypes.c_int32,
				ctypes.c_uint32,
				ctypes.POINTER(ctypes.c_void_p),
				ctypes.POINTER(ctypes.c_uint32),
			)
			while len(collected) < MAX_SUGGESTIONS:
				value = ctypes.c_void_p()
				fetched = ctypes.c_uint32(0)
				result = nextValue(values, 1, ctypes.byref(value), ctypes.byref(fetched))
				if _failed(result):
					raise SpellCheckerUnavailable(
						f"IEnumString.Next falhou com {_formatHresult(result)}"
					)
				if result != _S_OK or fetched.value != 1 or not value:
					if value:
						self._ole32.CoTaskMemFree(value)
					break
				try:
					text = ctypes.wstring_at(value)
					if text and len(text) <= MAX_WORD_LENGTH:
						collected.append(text)
				finally:
					self._ole32.CoTaskMemFree(value)
			return collected
		finally:
			_release(values)

	def ignore(self, word: str) -> None:
		ignoreWord = _comMethod(
			self._checker,
			7,
			ctypes.c_int32,
			ctypes.c_wchar_p,
		)
		result = ignoreWord(self._checker, word)
		if _failed(result):
			raise SpellCheckerUnavailable(
				f"ISpellChecker.Ignore falhou com {_formatHresult(result)}"
			)

	def close(self) -> None:
		_release(self._checker)
		self._checker = ctypes.c_void_p()
		_release(self._factory)
		self._factory = ctypes.c_void_p()
		if self._ownsComInitialization:
			self._ole32.CoUninitialize()
			self._ownsComInitialization = False


class SpellCheckerService:
	"""Mantém idioma, palavras locais e palavras ignoradas na sessão do NVDA."""

	def __init__(self, dataDirectory: str, backendFactory=None):
		self.localDictionary = LocalDictionary(dataDirectory)
		self._backendFactory = backendFactory or WindowsSpellChecker
		self._backend = None
		self._languageTag = None
		self._failedLanguages: set[str] = set()
		self._ignoredWords: dict[str, str] = {}

	def available(self, languageCode: str) -> bool:
		return self._ensureBackend(languageCode) is not None

	def isMisspelled(self, word: str, languageCode: str) -> bool:
		word = unicodedata.normalize("NFC", word)
		key = _wordKey(word)
		if (
			not isDictionaryWord(word)
			or self.localDictionary.contains(word)
			or key in self._ignoredWords
		):
			return False
		backend = self._ensureBackend(languageCode)
		if backend is None:
			return False
		try:
			return backend.isMisspelled(word)
		except Exception:
			self._disableCurrentBackend("verificar uma palavra")
			return False

	def suggestions(self, word: str, languageCode: str) -> list[str]:
		backend = self._ensureBackend(languageCode)
		if backend is None:
			return []
		try:
			values = backend.suggestions(word)
		except Exception:
			self._disableCurrentBackend("obter sugestões")
			return []
		result = []
		seen = set()
		originalKey = _wordKey(word)
		for value in values:
			if (
				not value
				or len(value) > MAX_WORD_LENGTH
				or any(ord(character) < 0x20 for character in value)
			):
				continue
			key = _wordKey(value)
			if key == originalKey or key in seen:
				continue
			seen.add(key)
			result.append(value)
			if len(result) >= MAX_SUGGESTIONS:
				break
		return result

	def ignoreForSession(self, word: str, languageCode: str) -> None:
		word = unicodedata.normalize("NFC", word)
		if not isDictionaryWord(word):
			return
		self._ignoredWords[_wordKey(word)] = word
		backend = self._ensureBackend(languageCode)
		if backend is not None:
			try:
				backend.ignore(word)
			except Exception:
				self._disableCurrentBackend("ignorar uma palavra")

	def addToLocalDictionary(self, word: str, languageCode: str) -> bool:
		word = unicodedata.normalize("NFC", word)
		if not self.localDictionary.add(word):
			return False
		backend = self._ensureBackend(languageCode)
		if backend is not None:
			try:
				backend.ignore(word)
			except Exception:
				self._disableCurrentBackend("adicionar uma palavra")
		return True

	def close(self) -> None:
		if self._backend is not None:
			self._backend.close()
		self._backend = None
		self._languageTag = None

	def _ensureBackend(self, languageCode: str):
		tag = languageTag(languageCode)
		if self._backend is not None and self._languageTag == tag:
			return self._backend
		if tag in self._failedLanguages:
			return None
		self.close()
		backend = None
		try:
			backend = self._backendFactory(tag)
			for word in self.localDictionary.words:
				backend.ignore(word)
			for word in self._ignoredWords.values():
				backend.ignore(word)
		except Exception as error:
			try:
				if backend is not None:
					backend.close()
			except Exception:
				pass
			self._failedLanguages.add(tag)
			if isinstance(error, SpellCheckerUnavailable):
				log.debug(
					"O corretor ortográfico do Diário não está disponível para %s: %s",
					tag,
					error,
				)
			else:
				log.exception(
					"O corretor ortográfico do Diário não pôde ser iniciado para %s.",
					tag,
				)
			return None
		self._backend = backend
		self._languageTag = tag
		return backend

	def _disableCurrentBackend(self, operation: str) -> None:
		tag = self._languageTag
		log.exception("O corretor ortográfico falhou ao %s.", operation)
		self.close()
		if tag:
			self._failedLanguages.add(tag)
