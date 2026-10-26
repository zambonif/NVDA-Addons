"""Password review: real vault encryption; invented secrets and temporary files only.

The dialog tests exercise value handling with wx stubs, not native Windows UI.
Run with: python -m unittest discover -s diario/tests -p test_passwords.py -v
"""

from datetime import date
import importlib
import json
from pathlib import Path
import string
import sys
import tempfile
import types
import unittest
from unittest import mock


MODULE_DIRECTORY = Path(__file__).resolve().parents[1] / "globalPlugins" / "diario"
PACKAGE_NAME = "diarioPasswordReviewTests"
package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(MODULE_DIRECTORY)]
sys.modules[PACKAGE_NAME] = package
secure = importlib.import_module(f"{PACKAGE_NAME}.secureStorage")
storage = importlib.import_module(f"{PACKAGE_NAME}.storage")
translations = importlib.import_module(f"{PACKAGE_NAME}.translations")

PASSWORD = "initial test password"
RECOVERY = "a separate recovery phrase for tests"


def samplePassword(length, unicode=False):
	pattern = "Ab09" + string.punctuation
	if unicode:
		pattern += "çéΩ🙂"
	return (pattern * (length // len(pattern) + 1))[:length]


class PasswordStorageTests(unittest.TestCase):
	def setUp(self):
		self.directory = tempfile.TemporaryDirectory()
		self.addCleanup(self.directory.cleanup)
		self.vault = secure.SecureDiaryStorage(self.directory.name)
		self.entries = [storage.Entry.create("Private test title", "Private test text", date(2026, 10, 14))]

	def create(self, password=PASSWORD, phrase=None):
		session = self.vault.create(self.entries, password, phrase)
		self.addCleanup(session.lock)
		return session

	def reopen(self, password):
		session = self.vault.unlockWithPassword(password)
		self.addCleanup(session.lock)
		self.assertEqual(self.entries, session.load().entries)
		return session

	def files(self):
		return tuple(Path(path).read_bytes() for path in (self.vault.filePath, self.vault.backupPath))

	def test_long_passwords_round_trip_without_recovery_or_truncation(self):
		session = self.create()
		current = PASSWORD
		originalData = json.loads(self.files()[0])["data"]
		for length in (64, 127, 128, 129, 256, 1024, 4096):
			with self.subTest(length=length):
				password = samplePassword(length)
				with mock.patch.object(secure, "normalizeRecoveryPhrase", side_effect=AssertionError("Unexpected recovery access")):
					session.changePassword(current, password)
				self.assertEqual(self.entries, session.load().entries)
				self.assertFalse(session.hasRecoveryPhrase)
				primary, backup = self.files()
				self.assertEqual(primary, backup)
				envelope = json.loads(primary)
				self.assertEqual(originalData, envelope["data"])
				self.assertIsNone(envelope["recovery"])
				self.assertEqual(600_000, envelope["kdf"]["iterations"])
				for plaintext in (password, self.entries[0].title, self.entries[0].body):
					self.assertNotIn(plaintext.encode("utf-8"), primary)
				session.lock()
				session = self.reopen(password)
				# Differences near the end must not be ignored, even for long secrets.
				with self.assertRaises(secure.InvalidSecretError):
					self.vault.unlockWithPassword(password[:-1] + "Z")
				with self.assertRaises(secure.InvalidSecretError):
					self.vault.unlockWithPassword(current)
				current = password
		session.changePassword(current, "final test password")
		session.lock()
		self.reopen("final test password")

	def test_unicode_and_surrounding_spaces_remain_significant(self):
		password = " " + samplePassword(128, unicode=True) + " "
		session = self.create(password)
		session.lock()
		session = self.reopen(password)
		with self.assertRaises(secure.InvalidSecretError):
			self.vault.unlockWithPassword(password.strip())
		session.changePassword(password, "café " + samplePassword(128, unicode=True))
		session.lock()
		# Existing NFC equivalence is retained; punctuation is literal.
		self.reopen("cafe\u0301 " + samplePassword(128, unicode=True))

	def test_recovery_survives_password_change_and_reset_to_long_password(self):
		session = self.create(phrase=RECOVERY)
		originalRecovery = json.loads(self.files()[0])["recovery"]
		session.changePassword(PASSWORD, samplePassword(128))
		self.assertEqual(originalRecovery, json.loads(self.files()[0])["recovery"])
		session.lock()
		recovered = self.vault.unlockWithRecoveryPhrase(RECOVERY)
		self.addCleanup(recovered.lock)
		self.assertEqual(self.entries, recovered.load().entries)
		recovered.resetPassword(samplePassword(1024, unicode=True))
		recovered.lock()
		session = self.reopen(samplePassword(1024, unicode=True))
		session.changeRecoveryPhrase(samplePassword(1024, unicode=True), None)
		self.assertFalse(session.hasRecoveryPhrase)
		with self.assertRaises(secure.InvalidSecretError):
			self.vault.unlockWithRecoveryPhrase(RECOVERY)

	def test_wrong_current_password_has_specific_message_and_changes_nothing(self):
		session = self.create()
		before = self.files()
		with self.assertRaisesRegex(secure.InvalidSecretError, "^A senha atual está incorreta\\.$"):
			session.changePassword("incorrect current password", samplePassword(128))
		self.assertEqual(before, self.files())
		self.assertEqual(self.entries, session.load().entries)
		self.reopen(PASSWORD)
		# A rejected attempt must not prevent a later valid attempt.
		session.changePassword(PASSWORD, samplePassword(128))
		session.lock()
		self.reopen(samplePassword(128))

	def test_wrong_current_password_while_managing_recovery_is_identified(self):
		session = self.create(phrase=RECOVERY)
		before = self.files()
		with self.assertRaisesRegex(secure.InvalidSecretError, "^A senha atual está incorreta\\.$"):
			session.changeRecoveryPhrase("incorrect current password", None)
		self.assertEqual(before, self.files())
		self.assertTrue(session.hasRecoveryPhrase)

	def test_damaged_metadata_is_not_reported_as_incorrect_current_password(self):
		session = self.create()
		before = self.files()
		session._envelope["password"]["nonce"] = "invalid base64"
		with self.assertRaises(secure.VaultCorruptedError):
			session.changePassword(PASSWORD, samplePassword(128))
		self.assertEqual(before, self.files())

	def test_incorrect_current_password_message_is_translated(self):
		message = "A senha atual está incorreta."
		for language in ("en", "es", "it", "fr"):
			with self.subTest(language=language):
				self.assertTrue(message in translations.TRANSLATIONS[language], language)
				self.assertNotEqual(message, translations.TRANSLATIONS[language][message])


class PasswordDialogValueTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		fakeWx = types.ModuleType("wx")
		fakeWx.Dialog = object
		fakeWx.NewIdRef = lambda: 10001
		fakeWx.ID_OK = 5100
		with mock.patch.dict(sys.modules, {"wx": fakeWx}):
			cls.dialogs = importlib.import_module(f"{PACKAGE_NAME}.securityDialogs")

	def test_change_dialog_passes_full_literal_values_without_recovery(self):
		for length in (128, 1024, 4096):
			with self.subTest(length=length):
				password = samplePassword(length, unicode=True)
				current = " " + samplePassword(128) + " "
				dialog = types.SimpleNamespace(
					_modalEnding=False,
					result=None,
					currentCtrl=mock.Mock(GetValue=lambda: current),
					newCtrl=mock.Mock(GetValue=lambda: password),
					confirmCtrl=mock.Mock(GetValue=lambda: password),
					EndModal=mock.Mock(),
				)
				self.dialogs.ChangePasswordDialog._onAccept(dialog, None)
				self.assertEqual({"currentPassword": current, "newPassword": password}, dialog.result)
				dialog.EndModal.assert_called_once_with(self.dialogs.wx.ID_OK)

	def test_mismatched_long_confirmation_is_rejected_before_storage(self):
		password = samplePassword(128)
		dialog = types.SimpleNamespace(
			_modalEnding=False,
			result=None,
			currentCtrl=mock.Mock(GetValue=lambda: PASSWORD),
			newCtrl=mock.Mock(GetValue=lambda: password),
			confirmCtrl=mock.Mock(GetValue=lambda: password[:-1] + "Z"),
			EndModal=mock.Mock(),
		)
		with mock.patch.object(self.dialogs, "_showWarning") as warning:
			self.dialogs.ChangePasswordDialog._onAccept(dialog, None)
		warning.assert_called_once()
		self.assertIsNone(dialog.result)
		dialog.EndModal.assert_not_called()
		dialog.newCtrl.SetFocus.assert_called_once()


if __name__ == "__main__":
	unittest.main()
