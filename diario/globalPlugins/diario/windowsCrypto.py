# -*- coding: UTF-8 -*-

"""AES-GCM usando a API criptográfica nativa do Windows (CNG).

Este módulo evita depender de submódulos que o empacotamento do NVDA pode
retirar da biblioteca ``cryptography``. O formato produzido é o AES-GCM
convencional: texto cifrado seguido de uma etiqueta de autenticação de 16 bytes.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os


TAG_LENGTH = 16
STATUS_SUCCESS = 0
STATUS_AUTH_TAG_MISMATCH = 0xC000A002
BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO_VERSION = 1


class WindowsCryptoError(RuntimeError):
	"""A API criptográfica do Windows não pôde executar a operação."""


class AuthenticationError(WindowsCryptoError):
	"""A etiqueta do AES-GCM não confirmou a autenticidade dos dados."""


class _AuthenticatedCipherModeInfo(ctypes.Structure):
	_fields_ = (
		("cbSize", ctypes.c_uint32),
		("dwInfoVersion", ctypes.c_uint32),
		("pbNonce", ctypes.c_void_p),
		("cbNonce", ctypes.c_uint32),
		("pbAuthData", ctypes.c_void_p),
		("cbAuthData", ctypes.c_uint32),
		("pbTag", ctypes.c_void_p),
		("cbTag", ctypes.c_uint32),
		("pbMacContext", ctypes.c_void_p),
		("cbMacContext", ctypes.c_uint32),
		("cbAAD", ctypes.c_uint32),
		("cbData", ctypes.c_uint64),
		("dwFlags", ctypes.c_uint32),
	)


def _requireWindows() -> None:
	if os.name != "nt":
		raise WindowsCryptoError("A API CNG só está disponível no Windows.")


def _loadBcrypt():
	_requireWindows()
	dll = ctypes.WinDLL("bcrypt.dll")
	bytePointer = ctypes.POINTER(ctypes.c_ubyte)
	handlePointer = ctypes.POINTER(ctypes.c_void_p)
	statusType = wintypes.LONG

	dll.BCryptOpenAlgorithmProvider.argtypes = (
		handlePointer,
		wintypes.LPCWSTR,
		wintypes.LPCWSTR,
		ctypes.c_uint32,
	)
	dll.BCryptOpenAlgorithmProvider.restype = statusType
	dll.BCryptCloseAlgorithmProvider.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
	dll.BCryptCloseAlgorithmProvider.restype = statusType
	dll.BCryptSetProperty.argtypes = (
		ctypes.c_void_p,
		wintypes.LPCWSTR,
		bytePointer,
		ctypes.c_uint32,
		ctypes.c_uint32,
	)
	dll.BCryptSetProperty.restype = statusType
	dll.BCryptGetProperty.argtypes = (
		ctypes.c_void_p,
		wintypes.LPCWSTR,
		bytePointer,
		ctypes.c_uint32,
		ctypes.POINTER(ctypes.c_uint32),
		ctypes.c_uint32,
	)
	dll.BCryptGetProperty.restype = statusType
	dll.BCryptGenerateSymmetricKey.argtypes = (
		ctypes.c_void_p,
		handlePointer,
		bytePointer,
		ctypes.c_uint32,
		bytePointer,
		ctypes.c_uint32,
		ctypes.c_uint32,
	)
	dll.BCryptGenerateSymmetricKey.restype = statusType
	dll.BCryptDestroyKey.argtypes = (ctypes.c_void_p,)
	dll.BCryptDestroyKey.restype = statusType
	cryptArguments = (
		ctypes.c_void_p,
		bytePointer,
		ctypes.c_uint32,
		ctypes.c_void_p,
		bytePointer,
		ctypes.c_uint32,
		bytePointer,
		ctypes.c_uint32,
		ctypes.POINTER(ctypes.c_uint32),
		ctypes.c_uint32,
	)
	dll.BCryptEncrypt.argtypes = cryptArguments
	dll.BCryptEncrypt.restype = statusType
	dll.BCryptDecrypt.argtypes = cryptArguments
	dll.BCryptDecrypt.restype = statusType
	return dll


def _unsignedStatus(status: int) -> int:
	return int(status) & 0xFFFFFFFF


def _check(status: int, operation: str) -> None:
	if status == STATUS_SUCCESS:
		return
	raise WindowsCryptoError(
		f"A operação criptográfica {operation} falhou (0x{_unsignedStatus(status):08X})."
	)


def _byteBuffer(value: bytes):
	if not value:
		return None
	return (ctypes.c_ubyte * len(value)).from_buffer_copy(value)


def _pointer(buffer):
	if buffer is None:
		return None
	return ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))


class _AesKey:
	def __init__(self, key: bytes):
		if len(key) not in (16, 24, 32):
			raise WindowsCryptoError("O tamanho da chave AES é inválido.")
		self._bcrypt = _loadBcrypt()
		self.algorithmHandle = ctypes.c_void_p()
		self.keyHandle = ctypes.c_void_p()
		self.keyObject = None
		try:
			_check(
				self._bcrypt.BCryptOpenAlgorithmProvider(
					ctypes.byref(self.algorithmHandle),
					"AES",
					None,
					0,
				),
				"abrir AES",
			)
			chainingMode = ctypes.create_unicode_buffer("ChainingModeGCM")
			_check(
				self._bcrypt.BCryptSetProperty(
					self.algorithmHandle,
					"ChainingMode",
					ctypes.cast(chainingMode, ctypes.POINTER(ctypes.c_ubyte)),
					ctypes.sizeof(chainingMode),
					0,
				),
				"selecionar AES-GCM",
			)
			objectLength = ctypes.c_uint32()
			bytesWritten = ctypes.c_uint32()
			_check(
				self._bcrypt.BCryptGetProperty(
					self.algorithmHandle,
					"ObjectLength",
					ctypes.cast(ctypes.byref(objectLength), ctypes.POINTER(ctypes.c_ubyte)),
					ctypes.sizeof(objectLength),
					ctypes.byref(bytesWritten),
					0,
				),
				"consultar AES",
			)
			if objectLength.value <= 0:
				raise WindowsCryptoError("O Windows informou um objeto AES de tamanho inválido.")
			self.keyObject = (ctypes.c_ubyte * objectLength.value)()
			keyBuffer = _byteBuffer(key)
			_check(
				self._bcrypt.BCryptGenerateSymmetricKey(
					self.algorithmHandle,
					ctypes.byref(self.keyHandle),
					_pointer(self.keyObject),
					objectLength.value,
					_pointer(keyBuffer),
					len(key),
					0,
				),
				"criar chave AES",
			)
		finally:
			if not self.keyHandle.value and self.algorithmHandle.value:
				self.close()

	def close(self) -> None:
		if self.keyHandle.value:
			self._bcrypt.BCryptDestroyKey(self.keyHandle)
			self.keyHandle = ctypes.c_void_p()
		if self.algorithmHandle.value:
			self._bcrypt.BCryptCloseAlgorithmProvider(self.algorithmHandle, 0)
			self.algorithmHandle = ctypes.c_void_p()
		if self.keyObject is not None:
			ctypes.memset(self.keyObject, 0, ctypes.sizeof(self.keyObject))
			self.keyObject = None

	def __enter__(self):
		return self

	def __exit__(self, exceptionType, exception, traceback):
		self.close()


def _authInfo(nonceBuffer, aadBuffer, tagBuffer) -> _AuthenticatedCipherModeInfo:
	info = _AuthenticatedCipherModeInfo()
	info.cbSize = ctypes.sizeof(_AuthenticatedCipherModeInfo)
	info.dwInfoVersion = BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO_VERSION
	info.pbNonce = ctypes.cast(nonceBuffer, ctypes.c_void_p).value if nonceBuffer is not None else None
	info.cbNonce = ctypes.sizeof(nonceBuffer) if nonceBuffer is not None else 0
	info.pbAuthData = ctypes.cast(aadBuffer, ctypes.c_void_p).value if aadBuffer is not None else None
	info.cbAuthData = ctypes.sizeof(aadBuffer) if aadBuffer is not None else 0
	info.pbTag = ctypes.cast(tagBuffer, ctypes.c_void_p).value
	info.cbTag = ctypes.sizeof(tagBuffer)
	return info


def _encryptRaw(key: bytes, nonce: bytes, plaintext: bytes, associatedData: bytes) -> bytes:
	if len(nonce) != 12:
		raise WindowsCryptoError("O nonce do AES-GCM precisa ter 12 bytes.")
	nonceBuffer = _byteBuffer(nonce)
	aadBuffer = _byteBuffer(associatedData)
	inputBuffer = _byteBuffer(plaintext)
	outputBuffer = (ctypes.c_ubyte * max(1, len(plaintext)))()
	tagBuffer = (ctypes.c_ubyte * TAG_LENGTH)()
	info = _authInfo(nonceBuffer, aadBuffer, tagBuffer)
	resultLength = ctypes.c_uint32()
	with _AesKey(key) as aesKey:
		_check(
			aesKey._bcrypt.BCryptEncrypt(
				aesKey.keyHandle,
				_pointer(inputBuffer),
				len(plaintext),
				ctypes.byref(info),
				None,
				0,
				_pointer(outputBuffer),
				len(plaintext),
				ctypes.byref(resultLength),
				0,
			),
			"criptografar",
		)
	if resultLength.value != len(plaintext):
		raise WindowsCryptoError("O Windows devolveu um texto cifrado de tamanho inesperado.")
	return bytes(outputBuffer[: resultLength.value]) + bytes(tagBuffer)


def _decryptRaw(key: bytes, nonce: bytes, ciphertextAndTag: bytes, associatedData: bytes) -> bytes:
	if len(nonce) != 12:
		raise AuthenticationError("O nonce do AES-GCM é inválido.")
	if len(ciphertextAndTag) < TAG_LENGTH:
		raise AuthenticationError("Os dados AES-GCM estão incompletos.")
	ciphertext = ciphertextAndTag[:-TAG_LENGTH]
	tag = ciphertextAndTag[-TAG_LENGTH:]
	nonceBuffer = _byteBuffer(nonce)
	aadBuffer = _byteBuffer(associatedData)
	inputBuffer = _byteBuffer(ciphertext)
	outputBuffer = (ctypes.c_ubyte * max(1, len(ciphertext)))()
	tagBuffer = _byteBuffer(tag)
	info = _authInfo(nonceBuffer, aadBuffer, tagBuffer)
	resultLength = ctypes.c_uint32()
	with _AesKey(key) as aesKey:
		status = aesKey._bcrypt.BCryptDecrypt(
			aesKey.keyHandle,
			_pointer(inputBuffer),
			len(ciphertext),
			ctypes.byref(info),
			None,
			0,
			_pointer(outputBuffer),
			len(ciphertext),
			ctypes.byref(resultLength),
			0,
		)
	if status != STATUS_SUCCESS:
		if _unsignedStatus(status) == STATUS_AUTH_TAG_MISMATCH:
			raise AuthenticationError("A autenticação AES-GCM falhou.")
		raise WindowsCryptoError(
			f"A descriptografia falhou (0x{_unsignedStatus(status):08X})."
		)
	if resultLength.value != len(ciphertext):
		raise WindowsCryptoError("O Windows devolveu um texto aberto de tamanho inesperado.")
	return bytes(outputBuffer[: resultLength.value])


_selfTestCompleted = False


def ensureAvailable() -> None:
	"""Executa uma vez um vetor conhecido AES-256-GCM do NIST."""

	global _selfTestCompleted
	if _selfTestCompleted:
		return
	key = bytes(32)
	nonce = bytes(12)
	plaintext = bytes(16)
	expected = bytes.fromhex(
		"cea7403d4d606b6e074ec5d3baf39d18"
		"d0d1c8a799996bf0265b98b5d48ab919"
	)
	actual = _encryptRaw(key, nonce, plaintext, b"")
	if actual != expected or _decryptRaw(key, nonce, expected, b"") != plaintext:
		raise WindowsCryptoError("O autoteste AES-256-GCM do Windows falhou.")
	_selfTestCompleted = True


def encrypt(key: bytes, nonce: bytes, plaintext: bytes, associatedData: bytes) -> bytes:
	ensureAvailable()
	return _encryptRaw(key, nonce, plaintext, associatedData)


def decrypt(key: bytes, nonce: bytes, ciphertextAndTag: bytes, associatedData: bytes) -> bytes:
	ensureAvailable()
	return _decryptRaw(key, nonce, ciphertextAndTag, associatedData)
