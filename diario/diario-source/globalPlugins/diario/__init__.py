# -*- coding: UTF-8 -*-

"""Diário pessoal acessível para o NVDA."""

import os

import globalPluginHandler
import globalVars
import gui
import wx
from logHandler import log
from scriptHandler import script

from . import i18n


DATA_DIRECTORY = os.path.join(globalVars.appArgs.configPath, "diario")
i18n.initialize(DATA_DIRECTORY)

from .i18n import translate as _
from .dialogs import DiaryDialog
from .secureStorage import (
	InvalidSecretError,
	SecureDiaryStorage,
)
from .securityDialogs import (
	ID_RECOVER,
	NewPasswordDialog,
	RecoveryPhraseDialog,
	SecuritySetupDialog,
	UnlockDialog,
)
from .storage import DiaryStorage, DiaryStorageError
from .settings import DiarySettingsPanel
from .spellcheck import SpellCheckerService



class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Adiciona o Diário ao menu Ferramentas e aos comandos do NVDA."""

	def __init__(self):
		super().__init__()
		self._dialog = None
		self._opening = False
		self._spellChecker = SpellCheckerService(DATA_DIRECTORY)
		self._toolsMenu = gui.mainFrame.sysTrayIcon.toolsMenu
		self._menuItem = self._toolsMenu.Append(
			wx.ID_ANY,
			_("&Diário..."),
			_("Criar, ler, editar e excluir entradas do diário."),
		)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self._onMenuItem, self._menuItem)
		categoryClasses = gui.settingsDialogs.NVDASettingsDialog.categoryClasses
		if DiarySettingsPanel not in categoryClasses:
			categoryClasses.append(DiarySettingsPanel)

	def terminate(self):
		if self._dialog is not None:
			try:
				self._dialog.Close(force=True)
			except Exception:
				log.exception("Não foi possível fechar a janela do Diário durante a finalização.")
		if self._menuItem is not None:
			try:
				gui.mainFrame.sysTrayIcon.Unbind(wx.EVT_MENU, source=self._menuItem)
				self._toolsMenu.Remove(self._menuItem.GetId())
			except Exception:
				log.exception("Não foi possível remover o item do Diário do menu Ferramentas.")
			self._menuItem = None
		categoryClasses = gui.settingsDialogs.NVDASettingsDialog.categoryClasses
		if DiarySettingsPanel in categoryClasses:
			categoryClasses.remove(DiarySettingsPanel)
		try:
			self._spellChecker.close()
		except Exception:
			log.exception("Não foi possível finalizar o corretor ortográfico do Diário.")
		super().terminate()

	def _onMenuItem(self, event):
		self._requestOpen()

	def _requestOpen(self):
		wx.CallAfter(self._showDialog)

	def _showDialog(self):
		if self._dialog is not None:
			self._dialog.Raise()
			self._dialog.SetFocus()
			return
		if self._opening:
			return

		dataDirectory = DATA_DIRECTORY
		vault = SecureDiaryStorage(dataDirectory)
		session = None
		self._opening = True
		gui.mainFrame.prePopup()
		try:
			session = self._openSession(vault, dataDirectory)
			if session is None:
				return
			self._dialog = DiaryDialog(
				gui.mainFrame,
				session,
				spellChecker=self._spellChecker,
			)
			self._dialog.ShowModal()
		except Exception:
			log.exception("Erro ao abrir o Diário.")
			self._showMessage(
				_(
					"Não foi possível abrir o Diário. Os arquivos existentes não foram "
					"apagados. Consulte o registro do NVDA para obter detalhes."
				),
				_("Erro ao abrir o Diário"),
				wx.ICON_ERROR,
			)
		finally:
			if self._dialog is not None:
				self._dialog.Destroy()
				self._dialog = None
			if session is not None:
				session.lock()
			self._opening = False
			gui.mainFrame.postPopup()

	def _openSession(self, vault: SecureDiaryStorage, dataDirectory: str):
		if vault.exists:
			return self._unlockExistingVault(vault)

		legacyStorage = DiaryStorage(dataDirectory)
		try:
			legacyResult = legacyStorage.load()
		except DiaryStorageError as error:
			self._showMessage(_(str(error)), _("Não foi possível migrar as entradas"), wx.ICON_ERROR)
			return None

		setupDialog = SecuritySetupDialog(gui.mainFrame, len(legacyResult.entries))
		try:
			if setupDialog.ShowModal() != wx.ID_OK or setupDialog.result is None:
				return None
			password = setupDialog.result["password"]
			recoveryPhrase = setupDialog.result["recoveryPhrase"]
		finally:
			setupDialog.Destroy()

		session = vault.create(legacyResult.entries, password, recoveryPhrase)
		failedPaths = vault.removeLegacyPlaintextFiles()
		if failedPaths:
			fileNames = ", ".join(os.path.basename(path) for path in failedPaths)
			self._showMessage(
				_(
					"O cofre foi criado e verificado, mas estes arquivos antigos sem "
					"criptografia não puderam ser removidos: {files}. Feche o NVDA e "
					"remova-os manualmente da pasta do Diário."
				).format(files=fileNames),
				_("Migração concluída com aviso"),
				wx.ICON_WARNING,
			)
		elif legacyResult.entries:
			self._showMessage(
				_(
					"As {count} entradas existentes foram criptografadas e os antigos "
					"arquivos sem criptografia foram removidos."
				).format(count=len(legacyResult.entries)),
				_("Migração concluída"),
				wx.ICON_INFORMATION,
			)
		return session

	def _unlockExistingVault(self, vault: SecureDiaryStorage):
		hasRecoveryPhrase = vault.hasRecoveryPhrase()
		while True:
			unlockDialog = UnlockDialog(gui.mainFrame, hasRecoveryPhrase)
			try:
				result = unlockDialog.ShowModal()
				password = unlockDialog.password
			finally:
				unlockDialog.Destroy()
			if result == wx.ID_CANCEL:
				return None
			if result == ID_RECOVER:
				recoveredSession = self._recoverAccess(vault)
				if recoveredSession is not None:
					return recoveredSession
				continue
			if result != wx.ID_OK:
				return None
			try:
				return vault.unlockWithPassword(password)
			except InvalidSecretError:
				self._showMessage(
					_("A senha está incorreta. Tente novamente."),
					_("Senha incorreta"),
					wx.ICON_WARNING,
				)

	def _recoverAccess(self, vault: SecureDiaryStorage):
		while True:
			recoveryDialog = RecoveryPhraseDialog(gui.mainFrame)
			try:
				result = recoveryDialog.ShowModal()
				phrase = recoveryDialog.phrase
			finally:
				recoveryDialog.Destroy()
			if result != wx.ID_OK:
				return None
			try:
				session = vault.unlockWithRecoveryPhrase(phrase)
				break
			except InvalidSecretError:
				self._showMessage(
					_("A frase de recuperação está incorreta. Tente novamente."),
					_("Frase incorreta"),
					wx.ICON_WARNING,
				)

		passwordDialog = NewPasswordDialog(gui.mainFrame)
		try:
			if passwordDialog.ShowModal() != wx.ID_OK or passwordDialog.result is None:
				session.lock()
				return None
			newPassword = passwordDialog.result
		finally:
			passwordDialog.Destroy()
		try:
			session.resetPassword(newPassword)
		except Exception:
			session.lock()
			raise
		self._showMessage(
			_("A senha foi redefinida. O Diário está desbloqueado."),
			_("Acesso recuperado"),
			wx.ICON_INFORMATION,
		)
		return session

	def _showMessage(self, message: str, caption: str, icon: int) -> None:
		dialog = wx.MessageDialog(gui.mainFrame, message, caption, wx.OK | icon)
		try:
			dialog.ShowModal()
		finally:
			dialog.Destroy()

	@script(
		description=_("Abre o Diário para criar, listar e ler entradas."),
		category=_("Diário"),
		gesture="kb:NVDA+alt+d",
	)
	def script_openDiary(self, gesture):
		self._requestOpen()
