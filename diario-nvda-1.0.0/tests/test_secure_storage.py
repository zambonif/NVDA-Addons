from datetime import date
import builtins
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


MODULE_DIRECTORY = Path(__file__).resolve().parents[1] / "globalPlugins" / "diario"
PACKAGE_NAME = "diario_storage_tests"
package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(MODULE_DIRECTORY)]
sys.modules.setdefault(PACKAGE_NAME, package)


def _loadModule(moduleName: str, fileName: str):
	qualifiedName = f"{PACKAGE_NAME}.{moduleName}"
	if qualifiedName in sys.modules:
		return sys.modules[qualifiedName]
	spec = importlib.util.spec_from_file_location(qualifiedName, MODULE_DIRECTORY / fileName)
	module = importlib.util.module_from_spec(spec)
	sys.modules[qualifiedName] = module
	spec.loader.exec_module(module)
	return module


storageModule = _loadModule("storage", "storage.py")
secureModule = _loadModule("secureStorage", "secureStorage.py")
cryptoBackend = sys.modules[f"{PACKAGE_NAME}.cryptoBackend"]
Entry = storageModule.Entry
DiaryStorage = storageModule.DiaryStorage
InvalidSecretError = secureModule.InvalidSecretError
KdfParameters = secureModule.KdfParameters
SecureDiaryStorage = secureModule.SecureDiaryStorage


FAST_KDF = KdfParameters(memoryCost=1024, iterations=1, lanes=1)
PASSWORD = "senha forte 123"
RECOVERY = "quatro palavras longas para recuperar"


class SecureDiaryStorageTests(unittest.TestCase):
	def _vault(self, directory):
		return SecureDiaryStorage(directory, kdfParameters=FAST_KDF)

	def test_encrypted_round_trip_hides_entry_and_secrets(self):
		with tempfile.TemporaryDirectory() as directory:
			entry = Entry.create(
				"Segredo com acentuação",
				"conteúdo ultrassecreto\n" + ("texto comprido " * 10000),
				date(2026, 9, 1),
			)
			vault = self._vault(directory)
			session = vault.create([entry], PASSWORD, RECOVERY)
			self.assertEqual([entry], session.load().entries)
			session.lock()

			for path in (vault.filePath, vault.backupPath):
				contents = Path(path).read_text(encoding="utf-8")
				self.assertNotIn(entry.title, contents)
				self.assertNotIn("conteúdo ultrassecreto", contents)
				self.assertNotIn(PASSWORD, contents)
				self.assertNotIn(RECOVERY, contents)

			unlocked = vault.unlockWithPassword(PASSWORD)
			self.assertEqual([entry], unlocked.load().entries)
			unlocked.lock()

	def test_wrong_password_is_rejected(self):
		with tempfile.TemporaryDirectory() as directory:
			vault = self._vault(directory)
			vault.create([], PASSWORD, None).lock()
			with self.assertRaises(InvalidSecretError):
				vault.unlockWithPassword("senha completamente errada")

	def test_default_kdf_is_pbkdf2_with_600_thousand_iterations(self):
		parameters = KdfParameters().toDict()
		self.assertEqual("pbkdf2-sha256", parameters["name"])
		self.assertEqual(600_000, parameters["iterations"])

	def test_aes_backend_matches_known_aes_256_gcm_vector(self):
		result = cryptoBackend.encrypt(bytes(32), bytes(12), bytes(16), b"")
		self.assertEqual(
			bytes.fromhex(
				"cea7403d4d606b6e074ec5d3baf39d18"
				"d0d1c8a799996bf0265b98b5d48ab919"
			),
			result,
		)
		self.assertEqual(bytes(16), cryptoBackend.decrypt(bytes(32), bytes(12), result, b""))
		with self.assertRaises(cryptoBackend.AuthenticationError):
			cryptoBackend.decrypt(bytes(32), bytes(12), result[:-1] + b"\x00", b"")

	def test_windows_backend_import_does_not_require_cryptography_submodules(self):
		packageName = "diario_windows_import_test"
		windowsPackage = types.ModuleType(packageName)
		windowsPackage.__path__ = [str(MODULE_DIRECTORY)]
		sys.modules[packageName] = windowsPackage
		spec = importlib.util.spec_from_file_location(
			f"{packageName}.cryptoBackend",
			MODULE_DIRECTORY / "cryptoBackend.py",
		)
		module = importlib.util.module_from_spec(spec)
		sys.modules[spec.name] = module
		originalImport = builtins.__import__

		def guardedImport(name, *args, **kwargs):
			if name.startswith("cryptography"):
				raise AssertionError("O backend do Windows tentou importar cryptography.")
			return originalImport(name, *args, **kwargs)

		try:
			with mock.patch.object(os, "name", "nt"), mock.patch.object(
				builtins,
				"__import__",
				side_effect=guardedImport,
			):
				spec.loader.exec_module(module)
			self.assertTrue(module._backend.__name__.endswith("windowsCrypto"))
			if ctypes.sizeof(ctypes.c_void_p) == 8:
				self.assertEqual(88, ctypes.sizeof(module._backend._AuthenticatedCipherModeInfo))
		finally:
			for moduleName in list(sys.modules):
				if moduleName == packageName or moduleName.startswith(f"{packageName}."):
					sys.modules.pop(moduleName, None)

	def test_recovery_phrase_ignores_case_and_repeated_spaces_then_resets_password(self):
		with tempfile.TemporaryDirectory() as directory:
			entry = Entry.create("Entrada", "Texto", date(2026, 9, 1))
			vault = self._vault(directory)
			vault.create([entry], PASSWORD, "Minha Frase Muito Longa e Memorável").lock()

			session = vault.unlockWithRecoveryPhrase("  MINHA   frase muito longa E memorável ")
			session.resetPassword("minha senha nova 456")
			session.lock()
			with self.assertRaises(InvalidSecretError):
				vault.unlockWithPassword(PASSWORD)
			unlocked = vault.unlockWithPassword("minha senha nova 456")
			self.assertEqual([entry], unlocked.load().entries)

	def test_password_change_updates_primary_and_backup(self):
		with tempfile.TemporaryDirectory() as directory:
			vault = self._vault(directory)
			session = vault.create([], PASSWORD, RECOVERY)
			session.changePassword(PASSWORD, "uma senha substituta 789")
			session.lock()
			with self.assertRaises(InvalidSecretError):
				vault.unlockWithPassword(PASSWORD)

			os.unlink(vault.filePath)
			backupSession = vault.unlockWithPassword("uma senha substituta 789")
			self.assertTrue(backupSession.load().recoveredFromBackup)

	def test_recovery_phrase_can_be_removed(self):
		with tempfile.TemporaryDirectory() as directory:
			vault = self._vault(directory)
			session = vault.create([], PASSWORD, RECOVERY)
			session.changeRecoveryPhrase(PASSWORD, None)
			self.assertFalse(session.hasRecoveryPhrase)
			session.lock()
			self.assertFalse(vault.hasRecoveryPhrase())
			with self.assertRaises(InvalidSecretError):
				vault.unlockWithRecoveryPhrase(RECOVERY)

	def test_corrupted_primary_uses_encrypted_backup_and_repairs_both_copies(self):
		with tempfile.TemporaryDirectory() as directory:
			first = Entry.create("Primeira", "Um", date(2026, 8, 30))
			second = Entry.create("Segunda", "Dois", date(2026, 8, 31))
			vault = self._vault(directory)
			session = vault.create([first], PASSWORD, RECOVERY)
			session.save([first, second])
			session.lock()

			envelope = json.loads(Path(vault.filePath).read_text(encoding="utf-8"))
			ciphertext = envelope["data"]["ciphertext"]
			envelope["data"]["ciphertext"] = ("A" if ciphertext[0] != "A" else "B") + ciphertext[1:]
			Path(vault.filePath).write_text(json.dumps(envelope), encoding="utf-8")

			recovered = vault.unlockWithPassword(PASSWORD)
			result = recovered.load()
			self.assertTrue(result.recoveredFromBackup)
			self.assertEqual([first, second], result.entries)
			recovered.save(result.entries)
			recovered.lock()
			self.assertFalse(vault.unlockWithPassword(PASSWORD).load().recoveredFromBackup)

	def test_plaintext_files_are_removed_only_when_cleanup_is_requested(self):
		with tempfile.TemporaryDirectory() as directory:
			legacy = DiaryStorage(directory)
			entry = Entry.create("Título antigo", "Texto antigo", date(2026, 8, 29))
			legacy.save([entry])
			legacy.save([entry])
			corruptedPath = Path(directory) / "entradas-corrompidas-20260901-120000.json"
			corruptedPath.write_text("texto antigo", encoding="utf-8")
			vault = self._vault(directory)
			vault.create(legacy.load().entries, PASSWORD, RECOVERY).lock()
			self.assertTrue(vault.legacyPlaintextPaths())
			self.assertEqual([], vault.removeLegacyPlaintextFiles())
			self.assertEqual([], vault.legacyPlaintextPaths())
			self.assertEqual([entry], vault.unlockWithPassword(PASSWORD).load().entries)


if __name__ == "__main__":
	unittest.main()
