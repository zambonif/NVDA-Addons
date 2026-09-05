import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
	Path(__file__).resolve().parents[1]
	/ "globalPlugins"
	/ "diario"
	/ "spellcheck.py"
)
SPEC = importlib.util.spec_from_file_location("diarioSpellcheckForTests", MODULE_PATH)
spellcheck = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(spellcheck)


class FakeBackend:
	createdTags = []

	def __init__(self, tag):
		self.createdTags.append(tag)
		self.ignored = []
		self.closed = False

	def isMisspelled(self, word):
		return word.casefold() in {"erradu", "palavvra"}

	def suggestions(self, word):
		return {
			"erradu": ["errado", "errado", "errada"],
			"palavvra": ["palavra"],
		}.get(word.casefold(), [])

	def ignore(self, word):
		self.ignored.append(word)

	def close(self):
		self.closed = True


class UnavailableBackend:
	created = 0

	def __init__(self, tag):
		type(self).created += 1
		raise spellcheck.SpellCheckerUnavailable("dicionário ausente")


class WordParsingTests(unittest.TestCase):
	def test_delimiters_finish_words_but_backspace_does_not(self):
		for character in (" ", ".", ",", "!", "\t", "\r", "\n"):
			self.assertTrue(spellcheck.finishesWord(character))
		for character in ("a", "ç", "'", "-", "\b", "\x7f"):
			self.assertFalse(spellcheck.finishesWord(character))

	def test_word_ending_accepts_accents_apostrophes_and_hyphens(self):
		for text in ("d'água", "l’école", "bem-vindo", "informação"):
			rangeValue = spellcheck.wordRangeEnding(text, len(text))
			self.assertIsNotNone(rangeValue)
			self.assertEqual(text[slice(*rangeValue)], text)

	def test_word_ending_trims_joiners(self):
		text = "-teste-"
		self.assertEqual(spellcheck.wordRangeEnding(text, len(text)), (1, 6))

	def test_word_near_uses_previous_word_after_spaces(self):
		text = "palavvra   "
		rangeValue = spellcheck.wordRangeNear(text, len(text))
		self.assertEqual(text[slice(*rangeValue)], "palavvra")

	def test_numbers_alone_are_not_dictionary_words(self):
		self.assertFalse(spellcheck.isDictionaryWord("2026"))
		self.assertTrue(spellcheck.isDictionaryWord("NVDA2026"))


class LocalDictionaryTests(unittest.TestCase):
	def test_dictionary_is_utf8_case_insensitive_and_persistent(self):
		with tempfile.TemporaryDirectory() as directory:
			dictionary = spellcheck.LocalDictionary(directory)
			self.assertTrue(dictionary.add("Zambôni"))
			self.assertTrue(dictionary.contains("ZAMBÔNI"))
			loaded = spellcheck.LocalDictionary(directory)
			self.assertTrue(loaded.contains("zambôni"))
			self.assertEqual(
				Path(directory, spellcheck.DICTIONARY_FILE_NAME).read_text(encoding="utf-8"),
				"Zambôni\n",
			)


class ServiceTests(unittest.TestCase):
	def setUp(self):
		FakeBackend.createdTags.clear()

	def test_language_mapping(self):
		self.assertEqual(spellcheck.languageTag("pt_BR"), "pt-BR")
		self.assertEqual(spellcheck.languageTag("es"), "es-ES")
		self.assertEqual(spellcheck.languageTag("it"), "it-IT")
		self.assertEqual(spellcheck.languageTag("fr"), "fr-FR")
		self.assertEqual(spellcheck.languageTag("en"), "en-US")

	def test_suggestions_and_ignore_for_session(self):
		with tempfile.TemporaryDirectory() as directory:
			service = spellcheck.SpellCheckerService(directory, FakeBackend)
			self.assertTrue(service.isMisspelled("erradu", "pt_BR"))
			self.assertEqual(service.suggestions("erradu", "pt_BR"), ["errado", "errada"])
			service.ignoreForSession("erradu", "pt_BR")
			self.assertFalse(service.isMisspelled("ERRADU", "pt_BR"))
			self.assertEqual(FakeBackend.createdTags, ["pt-BR"])
			service.close()

	def test_local_word_is_not_checked_again_and_survives_new_service(self):
		with tempfile.TemporaryDirectory() as directory:
			service = spellcheck.SpellCheckerService(directory, FakeBackend)
			self.assertTrue(service.addToLocalDictionary("palavvra", "pt_BR"))
			self.assertFalse(service.isMisspelled("PALAVVRA", "pt_BR"))
			service.close()

			service = spellcheck.SpellCheckerService(directory, FakeBackend)
			self.assertFalse(service.isMisspelled("palavvra", "pt_BR"))
			service.close()

	def test_missing_windows_dictionary_only_disables_spellchecking(self):
		with tempfile.TemporaryDirectory() as directory:
			UnavailableBackend.created = 0
			service = spellcheck.SpellCheckerService(directory, UnavailableBackend)
			self.assertFalse(service.available("fr"))
			self.assertFalse(service.isMisspelled("palavvra", "fr"))
			self.assertEqual(UnavailableBackend.created, 1)


if __name__ == "__main__":
	unittest.main()
