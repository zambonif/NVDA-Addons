import builtins
import importlib.util
from pathlib import Path
import sys
import types
import unittest


MODULE_DIRECTORY = Path(__file__).resolve().parents[1] / "globalPlugins" / "diario"


class _WindowIdRef:
	def __init__(self, value):
		self.value = value

	def __int__(self):
		return self.value


class UiLifecycleTests(unittest.TestCase):
	def setUp(self):
		self._savedModules = {
			name: sys.modules.get(name)
			for name in ("addonHandler", "ui", "wx", "logHandler")
		}
		self._savedTranslation = getattr(builtins, "_", None)
		builtins._ = lambda value: value
		addonHandler = types.ModuleType("addonHandler")
		addonHandler.initTranslation = lambda: None
		sys.modules["addonHandler"] = addonHandler
		sys.modules["ui"] = types.ModuleType("ui")
		logHandler = types.ModuleType("logHandler")
		logHandler.log = types.SimpleNamespace(exception=lambda *args, **kwargs: None)
		sys.modules["logHandler"] = logHandler

	def tearDown(self):
		for moduleName in list(sys.modules):
			if moduleName.startswith("diario_ui_lifecycle_tests"):
				sys.modules.pop(moduleName, None)
		for name, module in self._savedModules.items():
			if module is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = module
		if self._savedTranslation is None:
			del builtins._
		else:
			builtins._ = self._savedTranslation

	def _newPackage(self):
		packageName = "diario_ui_lifecycle_tests"
		package = types.ModuleType(packageName)
		package.__path__ = [str(MODULE_DIRECTORY)]
		sys.modules[packageName] = package
		return packageName

	def _load(self, qualifiedName, fileName):
		spec = importlib.util.spec_from_file_location(qualifiedName, MODULE_DIRECTORY / fileName)
		module = importlib.util.module_from_spec(spec)
		sys.modules[qualifiedName] = module
		spec.loader.exec_module(module)
		return module

	def test_recovery_button_keeps_window_id_reference_alive(self):
		windowIdReference = _WindowIdRef(43210)
		wx = types.ModuleType("wx")
		wx.Dialog = type("Dialog", (object,), {})
		wx.NewIdRef = lambda: windowIdReference
		sys.modules["wx"] = wx
		packageName = self._newPackage()
		module = self._load(f"{packageName}.securityDialogs", "securityDialogs.py")
		self.assertIs(windowIdReference, module._RECOVER_ID_REF)
		self.assertEqual(43210, module.ID_RECOVER)

		class FakeDialog:
			_modalEnding = False
			calls = []

			def EndModal(self, result):
				self.calls.append(result)

		dialog = FakeDialog()
		module._endModalOnce(dialog, 1)
		module._endModalOnce(dialog, 2)
		self.assertEqual([1], dialog.calls)

	def test_end_modal_ignores_repeated_close_events(self):
		wx = types.ModuleType("wx")
		wx.Dialog = type("Dialog", (object,), {})
		wx.ID_CANCEL = 5101
		wx.WXK_RETURN = 13
		wx.WXK_NUMPAD_ENTER = 370
		wx.WXK_SPACE = 32
		sys.modules["wx"] = wx
		packageName = self._newPackage()
		storage = self._load(f"{packageName}.storage", "storage.py")
		securityDialogs = types.ModuleType(f"{packageName}.securityDialogs")
		securityDialogs.ChangePasswordDialog = object
		securityDialogs.ManageRecoveryDialog = object
		sys.modules[securityDialogs.__name__] = securityDialogs
		module = self._load(f"{packageName}.dialogs", "dialogs.py")

		class FakeDialog:
			def __init__(self):
				self._modalEnding = False
				self.calls = []

			def EndModal(self, result):
				self.calls.append(result)

		dialog = FakeDialog()
		module.endModalOnce(dialog, 7)
		module.endModalOnce(dialog, 8)
		self.assertEqual([7], dialog.calls)
		self.assertTrue(dialog._modalEnding)

		mainDialog = object.__new__(module.DiaryDialog)
		mainDialog._modalEnding = False
		mainDialog.calls = []
		mainDialog.EndModal = lambda result: mainDialog.calls.append(result)
		mainDialog._onCloseButton(None)
		self.assertEqual([wx.ID_CANCEL], mainDialog.calls)

		keyboardDialog = object.__new__(module.DiaryDialog)
		keyboardDialog._modalEnding = False
		keyboardDialog.calls = []
		keyboardDialog.EndModal = lambda result: keyboardDialog.calls.append(result)
		spaceEvent = types.SimpleNamespace(GetKeyCode=lambda: wx.WXK_SPACE)
		keyboardDialog._onCloseButtonKey(spaceEvent)
		self.assertEqual([wx.ID_CANCEL], keyboardDialog.calls)


if __name__ == "__main__":
	unittest.main()
