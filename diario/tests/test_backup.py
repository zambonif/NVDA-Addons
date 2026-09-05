from __future__ import annotations

from datetime import date, datetime, timezone
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]

PACKAGE_NAME = "diarioBackupTestsPackage"
PACKAGE_DIRECTORY = ROOT / "globalPlugins" / "diario"
package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(PACKAGE_DIRECTORY)]
sys.modules[PACKAGE_NAME] = package


def loadModule(name: str):
	qualifiedName = f"{PACKAGE_NAME}.{name}"
	spec = importlib.util.spec_from_file_location(qualifiedName, PACKAGE_DIRECTORY / f"{name}.py")
	module = importlib.util.module_from_spec(spec)
	sys.modules[qualifiedName] = module
	spec.loader.exec_module(module)
	return module


storage = loadModule("storage")
loadModule("cryptoBackend")
secureStorage = loadModule("secureStorage")
backupModule = loadModule("backup")

ARCHIVE_FILE_NAMES = backupModule.ARCHIVE_FILE_NAMES
DiaryBackupError = backupModule.DiaryBackupError
exportEncryptedVault = backupModule.exportEncryptedVault
mergeNewEntries = backupModule.mergeNewEntries
stagedImportArchive = backupModule.stagedImportArchive
InvalidSecretError = secureStorage.InvalidSecretError
KdfParameters = secureStorage.KdfParameters
SecureDiaryStorage = secureStorage.SecureDiaryStorage
Entry = storage.Entry


def makeEntry(entryId: str, title: str) -> Entry:
	created = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
	return Entry(entryId, title, f"Texto de {title}", date(2026, 9, 5), created)


class BackupArchiveTests(unittest.TestCase):
	def test_export_contains_only_the_two_encrypted_files(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			primary = root / "diario.enc"
			backup = root / "diario.backup.enc"
			primary.write_bytes(b"primary encrypted bytes")
			backup.write_bytes(b"backup encrypted bytes")
			destination = root / "export.zip"

			exportEncryptedVault(str(primary), str(backup), str(destination))

			with zipfile.ZipFile(destination) as archive:
				self.assertEqual(set(archive.namelist()), set(ARCHIVE_FILE_NAMES))
				self.assertEqual(archive.read("diario.enc"), primary.read_bytes())
				self.assertEqual(archive.read("diario.backup.enc"), backup.read_bytes())

	def test_staging_rejects_extra_or_nested_members(self):
		with tempfile.TemporaryDirectory() as directory:
			archivePath = Path(directory) / "invalid.zip"
			with zipfile.ZipFile(archivePath, "w") as archive:
				archive.writestr("diario.enc", b"one")
				archive.writestr("folder/diario.backup.enc", b"two")

			with self.assertRaises(DiaryBackupError):
				with stagedImportArchive(str(archivePath)):
					pass

	def test_staging_copies_valid_archive_without_plaintext(self):
		with tempfile.TemporaryDirectory() as directory:
			archivePath = Path(directory) / "valid.zip"
			with zipfile.ZipFile(archivePath, "w") as archive:
				archive.writestr("diario.enc", b"one")
				archive.writestr("diario.backup.enc", b"two")

			with stagedImportArchive(str(archivePath)) as staged:
				self.assertEqual((Path(staged) / "diario.enc").read_bytes(), b"one")
				self.assertEqual((Path(staged) / "diario.backup.enc").read_bytes(), b"two")
				self.assertEqual(set(os.listdir(staged)), set(ARCHIVE_FILE_NAMES))

	def test_merge_adds_only_unknown_ids_and_preserves_existing_entries(self):
		current = [makeEntry("same", "Local"), makeEntry("local", "Only local")]
		imported = [makeEntry("same", "Imported replacement"), makeEntry("new", "New")]

		merged, added = mergeNewEntries(current, imported)

		self.assertEqual([entry.title for entry in merged], ["Local", "Only local", "New"])
		self.assertEqual([entry.id for entry in added], ["new"])


class RelatedVaultTests(unittest.TestCase):
	def test_related_backup_opens_with_current_session_key(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			currentDirectory = root / "current"
			copyDirectory = root / "copy"
			parameters = KdfParameters(iterations=1)
			currentVault = SecureDiaryStorage(str(currentDirectory), parameters)
			currentSession = currentVault.create(
				[makeEntry("one", "One")],
				"password",
				None,
			)
			copyDirectory.mkdir()
			for name in ARCHIVE_FILE_NAMES:
				(copyDirectory / name).write_bytes((currentDirectory / name).read_bytes())
			try:
				copySession = currentSession.unlockRelatedVault(SecureDiaryStorage(str(copyDirectory)))
				try:
					self.assertEqual([entry.id for entry in copySession.load().entries], ["one"])
				finally:
					copySession.lock()
			finally:
				currentSession.lock()

	def test_related_backup_recovers_from_its_encrypted_secondary_copy(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			currentDirectory = root / "current"
			copyDirectory = root / "copy"
			currentVault = SecureDiaryStorage(
				str(currentDirectory),
				KdfParameters(iterations=1),
			)
			currentSession = currentVault.create(
				[makeEntry("one", "One")],
				"password",
				None,
			)
			copyDirectory.mkdir()
			for name in ARCHIVE_FILE_NAMES:
				(copyDirectory / name).write_bytes((currentDirectory / name).read_bytes())
			(copyDirectory / "diario.enc").write_bytes(b"damaged")
			try:
				copySession = currentSession.unlockRelatedVault(SecureDiaryStorage(str(copyDirectory)))
				try:
					result = copySession.load()
					self.assertTrue(result.recoveredFromBackup)
					self.assertEqual([entry.id for entry in result.entries], ["one"])
				finally:
					copySession.lock()
			finally:
				currentSession.lock()

	def test_independent_backup_requires_its_own_password(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			parameters = KdfParameters(iterations=1)
			currentVault = SecureDiaryStorage(str(root / "current"), parameters)
			otherVault = SecureDiaryStorage(str(root / "other"), parameters)
			currentSession = currentVault.create([], "password", None)
			otherSession = otherVault.create([makeEntry("new", "New")], "otherpass", None)
			otherSession.lock()
			try:
				with self.assertRaises(InvalidSecretError):
					currentSession.unlockRelatedVault(otherVault)
				unlockedOther = otherVault.unlockWithPassword("otherpass")
				try:
					self.assertEqual([entry.id for entry in unlockedOther.load().entries], ["new"])
				finally:
					unlockedOther.lock()
			finally:
				currentSession.lock()

	def test_independent_export_can_be_staged_merged_and_saved(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			parameters = KdfParameters(iterations=1)
			currentVault = SecureDiaryStorage(str(root / "current"), parameters)
			otherVault = SecureDiaryStorage(str(root / "other"), parameters)
			localEntry = makeEntry("local", "Local")
			newEntry = makeEntry("new", "Imported")
			currentSession = currentVault.create([localEntry], "password", None)
			otherSession = otherVault.create(
				[makeEntry("local", "Must not replace"), newEntry],
				"otherpass",
				None,
			)
			otherSession.lock()
			archivePath = root / "other.zip"
			exportEncryptedVault(otherVault.filePath, otherVault.backupPath, str(archivePath))

			try:
				with stagedImportArchive(str(archivePath)) as staged:
					importedVault = SecureDiaryStorage(staged)
					importedSession = importedVault.unlockWithPassword("otherpass")
					try:
						merged, added = mergeNewEntries(
							currentSession.load().entries,
							importedSession.load().entries,
						)
					finally:
						importedSession.lock()
				currentSession.save(merged)
				result = currentSession.load().entries
				self.assertEqual([entry.title for entry in result], ["Local", "Imported"])
				self.assertEqual(added, [newEntry])
			finally:
				currentSession.lock()


if __name__ == "__main__":
	unittest.main()
