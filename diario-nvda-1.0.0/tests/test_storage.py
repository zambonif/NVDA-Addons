from datetime import date
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "globalPlugins" / "diario"))

from storage import DiaryStorage, DiaryStorageError, Entry


class DiaryStorageTests(unittest.TestCase):
	def test_round_trip_preserves_unicode_and_long_body(self):
		with tempfile.TemporaryDirectory() as directory:
			storage = DiaryStorage(directory)
			entry = Entry.create("Um título com acentuação", "áéíóú\n" + ("texto " * 50000), date(2026, 9, 1))
			storage.save([entry])
			result = storage.load()
			self.assertEqual([entry], result.entries)
			self.assertFalse(result.recoveredFromBackup)

	def test_edit_keeps_creation_time_and_sets_update_time(self):
		entry = Entry.create("Original", "Texto", date(2026, 8, 31))
		edited = entry.edited("Novo", "Outro texto", date(2026, 9, 1))
		self.assertEqual(entry.id, edited.id)
		self.assertEqual(entry.createdAt, edited.createdAt)
		self.assertIsNotNone(edited.updatedAt)

	def test_backup_recovers_entries_from_invalid_primary(self):
		with tempfile.TemporaryDirectory() as directory:
			storage = DiaryStorage(directory)
			first = Entry.create("Primeira", "Um", date(2026, 8, 30))
			second = Entry.create("Segunda", "Dois", date(2026, 8, 31))
			storage.save([first])
			storage.save([first, second])
			with open(storage.filePath, "w", encoding="utf-8") as stream:
				stream.write("arquivo inválido")

			result = storage.load()
			self.assertTrue(result.recoveredFromBackup)
			self.assertEqual([first], result.entries)

			storage.save(result.entries)
			self.assertEqual([first], storage.load().entries)
			preserved = [name for name in os.listdir(directory) if name.startswith("entradas-corrompidas-")]
			self.assertEqual(1, len(preserved))

	def test_rejects_duplicate_ids(self):
		with tempfile.TemporaryDirectory() as directory:
			storage = DiaryStorage(directory)
			entry = Entry.create("Entrada", "Texto", date(2026, 9, 1))
			payload = {"schemaVersion": 1, "entries": [entry.toDict(), entry.toDict()]}
			os.makedirs(directory, exist_ok=True)
			with open(storage.filePath, "w", encoding="utf-8") as stream:
				json.dump(payload, stream)
			with self.assertRaises(DiaryStorageError):
				storage.load()

	def test_uses_backup_when_primary_is_missing(self):
		with tempfile.TemporaryDirectory() as directory:
			storage = DiaryStorage(directory)
			entry = Entry.create("Entrada", "Texto", date(2026, 9, 1))
			storage.save([entry])
			storage.save([entry])
			os.unlink(storage.filePath)
			result = storage.load()
			self.assertTrue(result.recoveredFromBackup)
			self.assertEqual([entry], result.entries)


if __name__ == "__main__":
	unittest.main()
