import ast
import importlib.util
from pathlib import Path
from string import Formatter
import sys
import tempfile
import types
import unittest


MODULE_DIRECTORY = Path(__file__).resolve().parents[1] / "globalPlugins" / "diario"
PACKAGE_NAME = "diario_i18n_tests"


def _loadModule(moduleName: str, fileName: str):
	qualifiedName = f"{PACKAGE_NAME}.{moduleName}"
	spec = importlib.util.spec_from_file_location(qualifiedName, MODULE_DIRECTORY / fileName)
	module = importlib.util.module_from_spec(spec)
	sys.modules[qualifiedName] = module
	spec.loader.exec_module(module)
	return module


class InternationalizationTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		package = types.ModuleType(PACKAGE_NAME)
		package.__path__ = [str(MODULE_DIRECTORY)]
		sys.modules[PACKAGE_NAME] = package
		cls.translations = _loadModule("translations", "translations.py")
		cls.i18n = _loadModule("i18n", "i18n.py")

	@classmethod
	def tearDownClass(cls):
		for name in list(sys.modules):
			if name == PACKAGE_NAME or name.startswith(f"{PACKAGE_NAME}."):
				sys.modules.pop(name, None)

	def test_language_choice_is_saved_and_loaded(self):
		with tempfile.TemporaryDirectory() as directory:
			self.i18n.initialize(directory)
			self.assertEqual("pt_BR", self.i18n.getLanguage())
			self.i18n.setLanguage("es")
			self.assertEqual("Diario", self.i18n.translate("Diário"))

			self.i18n.initialize(directory)
			self.assertEqual("es", self.i18n.getLanguage())
			self.assertEqual("Diario", self.i18n.translate("Diário"))

	def test_invalid_preference_falls_back_to_portuguese(self):
		with tempfile.TemporaryDirectory() as directory:
			Path(directory, "preferencias.json").write_text(
				'{"language": "setealem"}',
				encoding="utf-8",
			)
			self.i18n.initialize(directory)
			self.assertEqual("pt_BR", self.i18n.getLanguage())
			self.assertEqual("Diário", self.i18n.translate("Diário"))

	def test_all_catalogs_preserve_format_fields(self):
		formatter = Formatter()
		for language, messages in self.translations.TRANSLATIONS.items():
			for source, translated in messages.items():
				sourceFields = {field for text, field, spec, conversion in formatter.parse(source) if field}
				translatedFields = {
					field for text, field, spec, conversion in formatter.parse(translated) if field
				}
				self.assertEqual(sourceFields, translatedFields, f"{language}: {source}")

	def test_all_interface_messages_exist_in_every_catalog(self):
		required = set()
		for fileName in ("__init__.py", "dialogs.py", "securityDialogs.py", "settings.py"):
			tree = ast.parse((MODULE_DIRECTORY / fileName).read_text(encoding="utf-8"))
			for node in ast.walk(tree):
				if not (
					isinstance(node, ast.Call)
					and isinstance(node.func, ast.Name)
					and node.func.id == "_"
					and node.args
				):
					continue
				try:
					message = ast.literal_eval(node.args[0])
				except (ValueError, TypeError):
					continue
				if isinstance(message, str):
					required.add(message)
		for language, messages in self.translations.TRANSLATIONS.items():
			self.assertEqual(set(), required - set(messages), language)


if __name__ == "__main__":
	unittest.main()
