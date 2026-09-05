# -*- coding: UTF-8 -*-

"""Seleciona um AES-GCM disponível sem quebrar a inicialização do add-on."""

from __future__ import annotations

import os


class AuthenticationError(RuntimeError):
	"""Os dados não passaram pela autenticação do AES-GCM."""


class BackendUnavailableError(RuntimeError):
	"""Nenhum mecanismo AES-GCM pôde ser inicializado."""


if os.name == "nt":
	from . import windowsCrypto as _backend

	def ensureAvailable() -> None:
		try:
			_backend.ensureAvailable()
		except _backend.WindowsCryptoError as error:
			raise BackendUnavailableError(str(error)) from error

	def encrypt(key: bytes, nonce: bytes, plaintext: bytes, associatedData: bytes) -> bytes:
		try:
			return _backend.encrypt(key, nonce, plaintext, associatedData)
		except _backend.WindowsCryptoError as error:
			raise BackendUnavailableError(str(error)) from error

	def decrypt(key: bytes, nonce: bytes, ciphertext: bytes, associatedData: bytes) -> bytes:
		try:
			return _backend.decrypt(key, nonce, ciphertext, associatedData)
		except _backend.AuthenticationError as error:
			raise AuthenticationError(str(error)) from error
		except _backend.WindowsCryptoError as error:
			raise BackendUnavailableError(str(error)) from error
else:
	# Usado pelos testes e por possíveis execuções fora do NVDA. A importação
	# nunca ocorre no Windows, onde o pacote incompleto do NVDA causava o bug.
	try:
		from cryptography.exceptions import InvalidTag as _InvalidTag
		from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
	except (ImportError, ModuleNotFoundError) as _importError:
		_AESGCM = None
	else:
		_importError = None

	def ensureAvailable() -> None:
		if _AESGCM is None:
			raise BackendUnavailableError("Nenhum mecanismo AES-GCM está disponível.") from _importError

	def encrypt(key: bytes, nonce: bytes, plaintext: bytes, associatedData: bytes) -> bytes:
		ensureAvailable()
		return _AESGCM(key).encrypt(nonce, plaintext, associatedData)

	def decrypt(key: bytes, nonce: bytes, ciphertext: bytes, associatedData: bytes) -> bytes:
		ensureAvailable()
		try:
			return _AESGCM(key).decrypt(nonce, ciphertext, associatedData)
		except _InvalidTag as error:
			raise AuthenticationError("A autenticação AES-GCM falhou.") from error
