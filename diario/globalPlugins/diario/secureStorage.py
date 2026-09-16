# -*- coding: UTF-8 -*-

"""Cofre criptografado do Diário para NVDA.

O arquivo usa uma chave de dados aleatória de 256 bits. Essa chave é protegida
separadamente pela senha e, quando cadastrada, pela frase de recuperação. Assim,
uma senha esquecida pode ser substituída sem que ela precise ser armazenada.
No Windows, o AES-GCM é executado pela API CNG do próprio sistema.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import glob
import hashlib
import hmac
import json
import os
import shutil
import tempfile
import unicodedata
from typing import Iterable

from . import cryptoBackend
from .storage import DiaryStorageError, Entry, LoadResult, SCHEMA_VERSION


VAULT_FILE_NAME = "diario.enc"
VAULT_BACKUP_FILE_NAME = "diario.backup.enc"
VAULT_FORMAT = "diarioNVDA"
VAULT_FORMAT_VERSION = 1
WRAPPER_METADATA_VERSION = 2
KEY_LENGTH = 32
NONCE_LENGTH = 12
SALT_LENGTH = 16
WRAPPED_KEY_LENGTH = KEY_LENGTH + 16
MIN_PASSWORD_LENGTH = 8
MIN_RECOVERY_LENGTH = 16
DATA_AAD = b"diarioNVDA:data:v1"
PASSWORD_WRAP_AAD = b"diarioNVDA:wrap:password:v1"
RECOVERY_WRAP_AAD = b"diarioNVDA:wrap:recovery:v1"
PASSWORD_KDF_AD = b"diarioNVDA:kdf:password:v1"
RECOVERY_KDF_AD = b"diarioNVDA:kdf:recovery:v1"
MIN_PBKDF2_ITERATIONS = 600_000


class SecureDiaryError(DiaryStorageError):
	"""Erro genérico relacionado ao cofre criptografado."""


class InvalidSecretError(SecureDiaryError):
	"""A senha ou frase de recuperação não abriu a chave do cofre."""


class VaultCorruptedError(SecureDiaryError):
	"""O arquivo do cofre está incompleto, alterado ou danificado."""


class CryptoUnavailableError(SecureDiaryError):
	"""O mecanismo criptográfico necessário não está disponível."""


@dataclass(frozen=True)
class KdfParameters:
	"""Parâmetros serializados da derivação da chave."""

	algorithm: str = "pbkdf2-sha256"
	iterations: int = 600_000
	length: int = KEY_LENGTH
	memoryCost: int = 64 * 1024
	lanes: int = 4

	def toDict(self) -> dict:
		if self.algorithm == "pbkdf2-sha256":
			return {
				"name": self.algorithm,
				"iterations": self.iterations,
				"length": self.length,
			}
		if self.algorithm == "argon2id":
			return {
				"name": self.algorithm,
				"memoryCost": self.memoryCost,
				"iterations": self.iterations,
				"lanes": self.lanes,
				"length": self.length,
			}
		raise VaultCorruptedError("O método de proteção da senha não é reconhecido.")

	@classmethod
	def fromDict(cls, value: dict) -> "KdfParameters":
		if not isinstance(value, dict):
			raise VaultCorruptedError("O método de proteção da senha não é reconhecido.")
		algorithm = value.get("name")
		try:
			if algorithm == "pbkdf2-sha256":
				parameters = cls(
					algorithm=algorithm,
					iterations=int(value["iterations"]),
					length=int(value["length"]),
				)
			elif algorithm == "argon2id":
				# Mantém a leitura de cofres experimentais gerados pela 0.2.0
				# em ambientes que possuíam o módulo completo de cryptography.
				parameters = cls(
					algorithm=algorithm,
					memoryCost=int(value["memoryCost"]),
					iterations=int(value["iterations"]),
					lanes=int(value["lanes"]),
					length=int(value["length"]),
				)
			else:
				raise VaultCorruptedError("O método de proteção da senha não é reconhecido.")
		except (KeyError, TypeError, ValueError) as error:
			raise VaultCorruptedError("Os parâmetros de proteção da senha são inválidos.") from error
		if parameters.algorithm == "pbkdf2-sha256":
			if not 1 <= parameters.iterations <= 5_000_000:
				raise VaultCorruptedError("O número de iterações do cofre está fora do limite aceito.")
		else:
			if not 1024 <= parameters.memoryCost <= 256 * 1024:
				raise VaultCorruptedError("O custo de memória do cofre está fora do limite aceito.")
			if not 1 <= parameters.iterations <= 10:
				raise VaultCorruptedError("O número de iterações do cofre está fora do limite aceito.")
			if not 1 <= parameters.lanes <= 16:
				raise VaultCorruptedError("O paralelismo do cofre está fora do limite aceito.")
		if parameters.length != KEY_LENGTH:
			raise VaultCorruptedError("O tamanho da chave derivada é inválido.")
		return parameters


def normalizePassword(value: str) -> bytes:
	"""Mantém a senha exata, normalizando apenas a representação Unicode."""

	return unicodedata.normalize("NFC", value).encode("utf-8")


def normalizeRecoveryPhrase(value: str) -> bytes:
	"""Torna a frase tolerante a caixa e a diferenças de espaços."""

	normalized = unicodedata.normalize("NFC", value)
	normalized = " ".join(normalized.strip().split()).casefold()
	return normalized.encode("utf-8")


def _validateNewPassword(password: str) -> None:
	if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
		raise SecureDiaryError(
			f"A senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres."
		)


def _validateNewRecoveryPhrase(phrase: str) -> None:
	if not isinstance(phrase, str) or len(phrase.strip()) < MIN_RECOVERY_LENGTH:
		raise SecureDiaryError(
			f"A frase de recuperação precisa ter pelo menos {MIN_RECOVERY_LENGTH} caracteres."
		)


def _encode(value: bytes) -> str:
	return base64.b64encode(value).decode("ascii")


def _decode(value, fieldName: str, expectedLength: int | None = None, minimumLength: int | None = None) -> bytes:
	if not isinstance(value, str):
		raise VaultCorruptedError(f"O campo {fieldName} do cofre não é um texto válido.")
	try:
		decoded = base64.b64decode(value.encode("ascii"), validate=True)
	except (UnicodeEncodeError, binascii.Error, ValueError) as error:
		raise VaultCorruptedError(f"O campo {fieldName} do cofre está danificado.") from error
	if expectedLength is not None and len(decoded) != expectedLength:
		raise VaultCorruptedError(f"O campo {fieldName} do cofre possui tamanho inválido.")
	if minimumLength is not None and len(decoded) < minimumLength:
		raise VaultCorruptedError(f"O campo {fieldName} do cofre está incompleto.")
	return decoded


def _wipe(value: bytearray | None) -> None:
	if value is None:
		return
	for index in range(len(value)):
		value[index] = 0


def _deriveKey(secret: bytes, salt: bytes, parameters: KdfParameters, associatedData: bytes) -> bytearray:
	if parameters.algorithm == "pbkdf2-sha256":
		return bytearray(
			hashlib.pbkdf2_hmac(
				"sha256",
				secret,
				salt + b"\x00" + associatedData,
				parameters.iterations,
				dklen=parameters.length,
			)
		)
	try:
		from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
	except (ImportError, ModuleNotFoundError) as error:
		raise CryptoUnavailableError(
			"Este cofre antigo usa Argon2id, que não está disponível nesta instalação do NVDA."
		) from error
	try:
		kdf = Argon2id(
			salt=salt,
			length=parameters.length,
			iterations=parameters.iterations,
			lanes=parameters.lanes,
			memory_cost=parameters.memoryCost,
			ad=associatedData,
			secret=None,
		)
		return bytearray(kdf.derive(secret))
	except Exception as error:
		raise CryptoUnavailableError("Não foi possível executar o Argon2id deste cofre antigo.") from error


def _authenticatedWrapAad(wrapperName: str, parameters: KdfParameters) -> bytes:
	"""Autentica o propósito e todos os parâmetros que controlam a derivação."""

	metadata = {
		"format": VAULT_FORMAT,
		"formatVersion": VAULT_FORMAT_VERSION,
		"kdf": parameters.toDict(),
		"metadataVersion": WRAPPER_METADATA_VERSION,
		"wrapper": wrapperName,
	}
	return b"diarioNVDA:wrap-metadata:" + json.dumps(
		metadata,
		ensure_ascii=True,
		sort_keys=True,
		separators=(",", ":"),
	).encode("ascii")


def _aesEncrypt(key: bytes, nonce: bytes, plaintext: bytes, associatedData: bytes) -> bytes:
	try:
		return cryptoBackend.encrypt(key, nonce, plaintext, associatedData)
	except cryptoBackend.BackendUnavailableError as error:
		raise CryptoUnavailableError(
			"O mecanismo AES-GCM do Windows não pôde ser inicializado."
		) from error


def _aesDecrypt(key: bytes, nonce: bytes, ciphertext: bytes, associatedData: bytes) -> bytes:
	try:
		return cryptoBackend.decrypt(key, nonce, ciphertext, associatedData)
	except cryptoBackend.BackendUnavailableError as error:
		raise CryptoUnavailableError(
			"O mecanismo AES-GCM do Windows não pôde ser inicializado."
		) from error


def _wrapDataKey(
	dataKey: bytes | bytearray,
	secret: bytes,
	parameters: KdfParameters,
	kdfAssociatedData: bytes,
	wrapperName: str,
) -> dict:
	salt = os.urandom(SALT_LENGTH)
	nonce = os.urandom(NONCE_LENGTH)
	wrappingKey = _deriveKey(secret, salt, parameters, kdfAssociatedData)
	try:
		wrappedKey = _aesEncrypt(
			bytes(wrappingKey),
			nonce,
			bytes(dataKey),
			_authenticatedWrapAad(wrapperName, parameters),
		)
	finally:
		_wipe(wrappingKey)
	return {
		"metadataVersion": WRAPPER_METADATA_VERSION,
		"salt": _encode(salt),
		"nonce": _encode(nonce),
		"wrappedKey": _encode(wrappedKey),
	}


def _unwrapDataKey(
	wrapped: dict,
	secret: bytes,
	parameters: KdfParameters,
	kdfAssociatedData: bytes,
	wrapperName: str,
	legacyWrapAssociatedData: bytes,
) -> bytearray:
	if not isinstance(wrapped, dict):
		raise VaultCorruptedError("A proteção da chave do cofre está ausente.")
	salt = _decode(wrapped.get("salt"), "salt", expectedLength=SALT_LENGTH)
	nonce = _decode(wrapped.get("nonce"), "nonce da chave", expectedLength=NONCE_LENGTH)
	wrappedKey = _decode(
		wrapped.get("wrappedKey"),
		"chave protegida",
		expectedLength=WRAPPED_KEY_LENGTH,
	)
	metadataVersion = wrapped.get("metadataVersion", 1)
	if metadataVersion == WRAPPER_METADATA_VERSION:
		if parameters.algorithm == "pbkdf2-sha256" and parameters.iterations < MIN_PBKDF2_ITERATIONS:
			raise VaultCorruptedError("O custo PBKDF2 autenticado está abaixo do mínimo seguro.")
		wrapAssociatedData = _authenticatedWrapAad(wrapperName, parameters)
	elif metadataVersion == 1:
		# Compatibilidade com cofres criados até a versão 1.3.0.
		wrapAssociatedData = legacyWrapAssociatedData
	else:
		raise VaultCorruptedError("A versão dos metadados da chave protegida não é reconhecida.")
	wrappingKey = _deriveKey(secret, salt, parameters, kdfAssociatedData)
	try:
		try:
			dataKey = _aesDecrypt(bytes(wrappingKey), nonce, wrappedKey, wrapAssociatedData)
		except cryptoBackend.AuthenticationError as error:
			raise InvalidSecretError("A senha ou frase de recuperação está incorreta.") from error
	finally:
		_wipe(wrappingKey)
	if len(dataKey) != KEY_LENGTH:
		raise VaultCorruptedError("A chave interna do cofre possui tamanho inválido.")
	return bytearray(dataKey)


def _serializeEntries(entries: Iterable[Entry]) -> bytes:
	payload = {
		"schemaVersion": SCHEMA_VERSION,
		"entries": [entry.toDict() for entry in entries],
	}
	return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _deserializeEntries(payloadBytes: bytes) -> list[Entry]:
	try:
		payload = json.loads(payloadBytes.decode("utf-8"))
	except (UnicodeDecodeError, json.JSONDecodeError) as error:
		raise VaultCorruptedError("O conteúdo descriptografado do Diário é inválido.") from error
	if not isinstance(payload, dict) or payload.get("schemaVersion") != SCHEMA_VERSION:
		raise VaultCorruptedError("A versão dos dados do Diário não é reconhecida.")
	values = payload.get("entries")
	if not isinstance(values, list):
		raise VaultCorruptedError("A lista descriptografada de entradas é inválida.")
	try:
		entries = [Entry.fromDict(value) for value in values]
	except (KeyError, TypeError, ValueError) as error:
		raise VaultCorruptedError("Uma entrada descriptografada está danificada.") from error
	if len({entry.id for entry in entries}) != len(entries):
		raise VaultCorruptedError("Há identificadores repetidos nas entradas descriptografadas.")
	return entries


def _encryptEntries(entries: Iterable[Entry], dataKey: bytes | bytearray) -> dict:
	nonce = os.urandom(NONCE_LENGTH)
	ciphertext = _aesEncrypt(bytes(dataKey), nonce, _serializeEntries(entries), DATA_AAD)
	return {
		"nonce": _encode(nonce),
		"ciphertext": _encode(ciphertext),
	}


def _decryptEntries(data: dict, dataKey: bytes | bytearray) -> list[Entry]:
	if not isinstance(data, dict):
		raise VaultCorruptedError("Os dados criptografados do Diário estão ausentes.")
	nonce = _decode(data.get("nonce"), "nonce dos dados", expectedLength=NONCE_LENGTH)
	ciphertext = _decode(data.get("ciphertext"), "dados criptografados", minimumLength=16)
	try:
		plaintext = _aesDecrypt(bytes(dataKey), nonce, ciphertext, DATA_AAD)
	except cryptoBackend.AuthenticationError as error:
		raise VaultCorruptedError(
			"Não foi possível confirmar a integridade dos dados criptografados do Diário."
		) from error
	return _deserializeEntries(plaintext)


class SecureDiaryStorage:
	"""Cria e abre o arquivo criptografado do Diário."""

	def __init__(self, directory: str, kdfParameters: KdfParameters | None = None):
		self.directory = os.path.abspath(directory)
		self.filePath = os.path.join(self.directory, VAULT_FILE_NAME)
		self.backupPath = os.path.join(self.directory, VAULT_BACKUP_FILE_NAME)
		self.kdfParameters = kdfParameters or KdfParameters()

	@property
	def exists(self) -> bool:
		return os.path.exists(self.filePath) or os.path.exists(self.backupPath)

	def create(
		self,
		entries: Iterable[Entry],
		password: str,
		recoveryPhrase: str | None,
	) -> "UnlockedDiaryStorage":
		if self.exists:
			raise SecureDiaryError("O cofre do Diário já existe.")
		_validateNewPassword(password)
		if recoveryPhrase is not None:
			_validateNewRecoveryPhrase(recoveryPhrase)
		entries = list(entries)
		dataKey = bytearray(os.urandom(KEY_LENGTH))
		try:
			envelope = self._newEnvelope(entries, dataKey, password, recoveryPhrase)
			self._writeEnvelope(envelope, rotateBackup=False, synchronizeBackup=True)
			verifiedEnvelope = self._readEnvelope(self.filePath)
			verifiedEntries = _decryptEntries(verifiedEnvelope["data"], dataKey)
			if verifiedEntries != entries:
				raise SecureDiaryError("A verificação do cofre recém-criado falhou.")
			return UnlockedDiaryStorage(self, verifiedEnvelope, dataKey, entries)
		except Exception:
			_wipe(dataKey)
			raise

	def unlockWithPassword(self, password: str) -> "UnlockedDiaryStorage":
		return self._unlock(
			normalizePassword(password),
			wrapperName="password",
			kdfAssociatedData=PASSWORD_KDF_AD,
			wrapAssociatedData=PASSWORD_WRAP_AAD,
		)

	def unlockWithRecoveryPhrase(self, phrase: str) -> "UnlockedDiaryStorage":
		return self._unlock(
			normalizeRecoveryPhrase(phrase),
			wrapperName="recovery",
			kdfAssociatedData=RECOVERY_KDF_AD,
			wrapAssociatedData=RECOVERY_WRAP_AAD,
		)

	def _unlockWithDataKey(self, dataKey: bytes | bytearray) -> "UnlockedDiaryStorage":
		"""Abre outra cópia do mesmo cofre sem expor a chave fora deste módulo."""

		validEnvelopeFound = False
		for path, recoveredFromBackup in (
			(self.filePath, False),
			(self.backupPath, True),
		):
			try:
				envelope = self._readEnvelope(path)
			except (OSError, VaultCorruptedError, json.JSONDecodeError, UnicodeDecodeError):
				continue
			validEnvelopeFound = True
			candidateKey = bytearray(dataKey)
			try:
				entries = _decryptEntries(envelope["data"], candidateKey)
			except VaultCorruptedError:
				_wipe(candidateKey)
				continue
			except Exception:
				_wipe(candidateKey)
				raise
			return UnlockedDiaryStorage(
				self,
				envelope,
				candidateKey,
				entries,
				recoveredFromBackup=recoveredFromBackup,
			)
		if not validEnvelopeFound:
			raise VaultCorruptedError(
				"Os arquivos criptografados do backup não contêm um cofre válido."
			)
		raise InvalidSecretError("O backup pertence a outro cofre do Diário.")

	def hasRecoveryPhrase(self) -> bool:
		try:
			envelope = self._readEnvelope(self.filePath)
		except Exception:
			envelope = self._readEnvelope(self.backupPath)
		return envelope.get("recovery") is not None

	def legacyPlaintextPaths(self) -> list[str]:
		candidates = [
			os.path.join(self.directory, "entradas.json"),
			os.path.join(self.directory, "entradas.backup.json"),
		]
		candidates.extend(sorted(glob.glob(os.path.join(self.directory, "entradas-corrompidas-*.json"))))
		return [path for path in candidates if os.path.isfile(path)]

	def removeLegacyPlaintextFiles(self) -> list[str]:
		failed = []
		for path in self.legacyPlaintextPaths():
			try:
				os.unlink(path)
			except OSError:
				failed.append(path)
		return failed

	def _newEnvelope(
		self,
		entries: list[Entry],
		dataKey: bytearray,
		password: str,
		recoveryPhrase: str | None,
	) -> dict:
		passwordWrapper = _wrapDataKey(
			dataKey,
			normalizePassword(password),
			self.kdfParameters,
			PASSWORD_KDF_AD,
			"password",
		)
		recoveryWrapper = None
		if recoveryPhrase is not None:
			recoveryWrapper = _wrapDataKey(
				dataKey,
				normalizeRecoveryPhrase(recoveryPhrase),
				self.kdfParameters,
				RECOVERY_KDF_AD,
				"recovery",
			)
		return {
			"format": VAULT_FORMAT,
			"formatVersion": VAULT_FORMAT_VERSION,
			"kdf": self.kdfParameters.toDict(),
			"password": passwordWrapper,
			"recovery": recoveryWrapper,
			"data": _encryptEntries(entries, dataKey),
		}

	def _unlock(
		self,
		secret: bytes,
		wrapperName: str,
		kdfAssociatedData: bytes,
		wrapAssociatedData: bytes,
	) -> "UnlockedDiaryStorage":
		primaryReadFailed = False
		try:
			envelope = self._readEnvelope(self.filePath)
		except (OSError, VaultCorruptedError, json.JSONDecodeError, UnicodeDecodeError):
			primaryReadFailed = True
			envelope = self._readEnvelope(self.backupPath)

		if wrapperName == "recovery" and envelope.get("recovery") is None:
			raise InvalidSecretError("Nenhuma frase de recuperação foi cadastrada.")
		parameters = KdfParameters.fromDict(envelope["kdf"])
		dataKey = _unwrapDataKey(
			envelope[wrapperName],
			secret,
			parameters,
			kdfAssociatedData,
			wrapperName,
			wrapAssociatedData,
		)
		try:
			try:
				entries = _decryptEntries(envelope["data"], dataKey)
			except VaultCorruptedError:
				if primaryReadFailed:
					raise
				backupEnvelope = self._readEnvelope(self.backupPath)
				parameters = KdfParameters.fromDict(backupEnvelope["kdf"])
				backupKey = _unwrapDataKey(
					backupEnvelope[wrapperName],
					secret,
					parameters,
					kdfAssociatedData,
					wrapperName,
					wrapAssociatedData,
				)
				_wipe(dataKey)
				dataKey = backupKey
				envelope = backupEnvelope
				entries = _decryptEntries(envelope["data"], dataKey)
				primaryReadFailed = True
			# Ao desbloquear um cofre antigo, autentica imediatamente os metadados
			# do método utilizado. O outro método será atualizado quando for usado
			# ou alterado, pois sua senha/frase não fica armazenada.
			if envelope[wrapperName].get("metadataVersion", 1) == 1:
				if parameters.algorithm == "pbkdf2-sha256" and parameters.iterations >= MIN_PBKDF2_ITERATIONS:
					upgradedEnvelope = dict(envelope)
					upgradedEnvelope[wrapperName] = _wrapDataKey(
						dataKey,
						secret,
						parameters,
						kdfAssociatedData,
						wrapperName,
					)
					self._writeEnvelope(upgradedEnvelope, rotateBackup=False, synchronizeBackup=True)
					envelope = upgradedEnvelope
			return UnlockedDiaryStorage(
				self,
				envelope,
				dataKey,
				entries,
				recoveredFromBackup=primaryReadFailed,
			)
		except Exception:
			_wipe(dataKey)
			raise

	def _readEnvelope(self, path: str) -> dict:
		if not os.path.isfile(path):
			raise VaultCorruptedError("O arquivo criptografado do Diário não foi encontrado.")
		try:
			with open(path, "r", encoding="utf-8") as stream:
				envelope = json.load(stream)
		except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
			raise VaultCorruptedError("O arquivo criptografado do Diário não pôde ser lido.") from error
		self._validateEnvelope(envelope)
		return envelope

	def _validateEnvelope(self, envelope) -> None:
		if not isinstance(envelope, dict):
			raise VaultCorruptedError("A estrutura do cofre é inválida.")
		if envelope.get("format") != VAULT_FORMAT or envelope.get("formatVersion") != VAULT_FORMAT_VERSION:
			raise VaultCorruptedError("O formato do cofre não é reconhecido.")
		KdfParameters.fromDict(envelope.get("kdf"))
		for wrapperName in ("password", "recovery"):
			wrapper = envelope.get(wrapperName)
			if wrapperName == "recovery" and wrapper is None:
				continue
			if not isinstance(wrapper, dict):
				raise VaultCorruptedError("A proteção da chave do cofre é inválida.")
			_decode(wrapper.get("salt"), "salt", expectedLength=SALT_LENGTH)
			_decode(wrapper.get("nonce"), "nonce da chave", expectedLength=NONCE_LENGTH)
			_decode(wrapper.get("wrappedKey"), "chave protegida", expectedLength=WRAPPED_KEY_LENGTH)
			metadataVersion = wrapper.get("metadataVersion", 1)
			if metadataVersion not in (1, WRAPPER_METADATA_VERSION):
				raise VaultCorruptedError("A versão dos metadados da chave protegida não é reconhecida.")
			if (
				metadataVersion == WRAPPER_METADATA_VERSION
				and KdfParameters.fromDict(envelope["kdf"]).algorithm == "pbkdf2-sha256"
				and KdfParameters.fromDict(envelope["kdf"]).iterations < MIN_PBKDF2_ITERATIONS
			):
				raise VaultCorruptedError("O custo PBKDF2 autenticado está abaixo do mínimo seguro.")
		data = envelope.get("data")
		if not isinstance(data, dict):
			raise VaultCorruptedError("Os dados criptografados estão ausentes.")
		_decode(data.get("nonce"), "nonce dos dados", expectedLength=NONCE_LENGTH)
		_decode(data.get("ciphertext"), "dados criptografados", minimumLength=16)

	def _writeEnvelope(self, envelope: dict, rotateBackup: bool, synchronizeBackup: bool = False) -> None:
		os.makedirs(self.directory, exist_ok=True)
		temporaryPath = self._writeTemporaryEnvelope(envelope, prefix="cofre-")
		try:
			if rotateBackup and os.path.isfile(self.filePath):
				self._copyAtomically(self.filePath, self.backupPath)
			os.replace(temporaryPath, self.filePath)
			if synchronizeBackup:
				self._copyAtomically(self.filePath, self.backupPath)
		except Exception as error:
			try:
				if os.path.exists(temporaryPath):
					os.unlink(temporaryPath)
			except OSError:
				pass
			raise SecureDiaryError("Não foi possível gravar o cofre criptografado do Diário.") from error

	def _writeTemporaryEnvelope(self, envelope: dict, prefix: str) -> str:
		descriptor, path = tempfile.mkstemp(
			prefix=prefix,
			suffix=".tmp",
			dir=self.directory,
			text=True,
		)
		try:
			with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
				json.dump(envelope, stream, ensure_ascii=True, separators=(",", ":"))
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

	def _copyAtomically(self, source: str, destination: str) -> None:
		descriptor, temporaryCopy = tempfile.mkstemp(
			prefix="copia-",
			suffix=".tmp",
			dir=self.directory,
		)
		os.close(descriptor)
		try:
			shutil.copy2(source, temporaryCopy)
			os.replace(temporaryCopy, destination)
		finally:
			if os.path.exists(temporaryCopy):
				os.unlink(temporaryCopy)


class UnlockedDiaryStorage:
	"""Sessão desbloqueada; mantém a chave somente enquanto a janela está aberta."""

	def __init__(
		self,
		vault: SecureDiaryStorage,
		envelope: dict,
		dataKey: bytearray,
		entries: list[Entry],
		recoveredFromBackup: bool = False,
	):
		self.vault = vault
		self._envelope = envelope
		self._dataKey = dataKey
		self._entries = list(entries)
		self._recoveredFromBackup = recoveredFromBackup
		self._locked = False

	@property
	def hasRecoveryPhrase(self) -> bool:
		return self._envelope.get("recovery") is not None

	def load(self) -> LoadResult:
		self._requireUnlocked()
		result = LoadResult(list(self._entries), recoveredFromBackup=self._recoveredFromBackup)
		self._recoveredFromBackup = False
		return result

	def unlockRelatedVault(self, vault: SecureDiaryStorage) -> "UnlockedDiaryStorage":
		"""Abre um backup que compartilhe a chave desta sessão desbloqueada."""

		self._requireUnlocked()
		return vault._unlockWithDataKey(self._dataKey)

	def save(self, entries: Iterable[Entry]) -> None:
		self._requireUnlocked()
		entries = list(entries)
		newEnvelope = dict(self._envelope)
		newEnvelope["data"] = _encryptEntries(entries, self._dataKey)
		# A cópia acompanha o estado atual. Assim, uma entrada excluída não
		# permanece legível com as credenciais do usuário em uma versão anterior.
		self.vault._writeEnvelope(newEnvelope, rotateBackup=False, synchronizeBackup=True)
		self._envelope = newEnvelope
		self._entries = entries

	def changePassword(self, currentPassword: str, newPassword: str) -> None:
		self._requireUnlocked()
		self._verifyPassword(currentPassword)
		self.resetPassword(newPassword)

	def resetPassword(self, newPassword: str) -> None:
		self._requireUnlocked()
		_validateNewPassword(newPassword)
		parameters = KdfParameters.fromDict(self._envelope["kdf"])
		newEnvelope = dict(self._envelope)
		newEnvelope["password"] = _wrapDataKey(
			self._dataKey,
			normalizePassword(newPassword),
			parameters,
			PASSWORD_KDF_AD,
			"password",
		)
		self.vault._writeEnvelope(newEnvelope, rotateBackup=False, synchronizeBackup=True)
		self._envelope = newEnvelope

	def changeRecoveryPhrase(self, currentPassword: str, newPhrase: str | None) -> None:
		self._requireUnlocked()
		self._verifyPassword(currentPassword)
		if newPhrase is not None:
			_validateNewRecoveryPhrase(newPhrase)
		newEnvelope = dict(self._envelope)
		if newPhrase is None:
			newEnvelope["recovery"] = None
		else:
			newEnvelope["recovery"] = _wrapDataKey(
				self._dataKey,
				normalizeRecoveryPhrase(newPhrase),
				KdfParameters.fromDict(self._envelope["kdf"]),
				RECOVERY_KDF_AD,
				"recovery",
			)
		self.vault._writeEnvelope(newEnvelope, rotateBackup=False, synchronizeBackup=True)
		self._envelope = newEnvelope

	def lock(self) -> None:
		if self._locked:
			return
		_wipe(self._dataKey)
		self._entries = []
		self._envelope = {}
		self._locked = True

	def _verifyPassword(self, password: str) -> None:
		candidateKey = _unwrapDataKey(
			self._envelope["password"],
			normalizePassword(password),
			KdfParameters.fromDict(self._envelope["kdf"]),
			PASSWORD_KDF_AD,
			"password",
			PASSWORD_WRAP_AAD,
		)
		try:
			if not hmac.compare_digest(bytes(candidateKey), bytes(self._dataKey)):
				raise InvalidSecretError("A senha atual está incorreta.")
		finally:
			_wipe(candidateKey)

	def _requireUnlocked(self) -> None:
		if self._locked:
			raise SecureDiaryError("O Diário está bloqueado.")
