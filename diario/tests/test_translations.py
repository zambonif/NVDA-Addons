from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from string import Formatter
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_DIRECTORY = ROOT / "globalPlugins" / "diario"
UI_MODULES = (
	"__init__.py",
	"dialogs.py",
	"securityDialogs.py",
	"settings.py",
	"spellcheckUi.py",
)


def loadTranslations():
	spec = importlib.util.spec_from_file_location(
		"diarioTranslationsForTests",
		MODULE_DIRECTORY / "translations.py",
	)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module.TRANSLATIONS


def interfaceMessages() -> set[str]:
	messages = set()
	for fileName in UI_MODULES:
		tree = ast.parse((MODULE_DIRECTORY / fileName).read_text(encoding="utf-8"))
		for node in ast.walk(tree):
			if not (
				isinstance(node, ast.Call)
				and isinstance(node.func, ast.Name)
				and node.func.id == "_"
				and node.args
			):
				continue
			argument = node.args[0]
			if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
				messages.add(argument.value)
	return messages


def placeholders(value: str) -> set[str]:
	return {name for literal, name, formatSpec, conversion in Formatter().parse(value) if name}


class TranslationTests(unittest.TestCase):
	def test_every_literal_interface_message_is_translated(self):
		messages = interfaceMessages()
		for language, catalog in loadTranslations().items():
			with self.subTest(language=language):
				self.assertEqual(messages - set(catalog), set())

	def test_translations_preserve_format_placeholders(self):
		for language, catalog in loadTranslations().items():
			for source, translated in catalog.items():
				with self.subTest(language=language, source=source):
					self.assertEqual(placeholders(source), placeholders(translated))


if __name__ == "__main__":
	unittest.main()
