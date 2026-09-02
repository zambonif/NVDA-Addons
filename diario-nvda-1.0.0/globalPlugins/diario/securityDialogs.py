# -*- coding: UTF-8 -*-

"""Janelas acessíveis para configurar e desbloquear o cofre do Diário."""

from __future__ import annotations

import unicodedata
import wx

from .i18n import translate as _


# O WindowIDRef precisa permanecer vivo enquanto seu valor inteiro estiver em
# uso. Guardar apenas int(wx.NewIdRef()) libera a reserva imediatamente e faz o
# wxPython disparar uma asserção ao construir o segundo diálogo de desbloqueio.
_RECOVER_ID_REF = wx.NewIdRef()
ID_RECOVER = int(_RECOVER_ID_REF)
MIN_PASSWORD_LENGTH = 8
MIN_RECOVERY_LENGTH = 16


def _endModalOnce(dialog, result: int) -> None:
	if getattr(dialog, "_modalEnding", False):
		return
	dialog._modalEnding = True
	try:
		dialog.EndModal(result)
	except RuntimeError:
		return


def _showWarning(parent, message: str, caption: str) -> None:
	dialog = wx.MessageDialog(parent, message, caption, wx.OK | wx.ICON_WARNING)
	try:
		dialog.ShowModal()
	finally:
		dialog.Destroy()


def _addPasswordField(parent, sizer, label: str, name: str):
	fieldLabel = wx.StaticText(parent, label=label)
	sizer.Add(fieldLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
	control = wx.TextCtrl(parent, style=wx.TE_PASSWORD)
	control.SetName(name)
	sizer.Add(control, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
	return control


def _validPassword(parent, password: str, confirmation: str) -> bool:
	if len(password) < MIN_PASSWORD_LENGTH:
		_showWarning(
			parent,
			_("A senha precisa ter pelo menos {count} caracteres.").format(
				count=MIN_PASSWORD_LENGTH,
			),
			_("Senha muito curta"),
		)
		return False
	if password != confirmation:
		_showWarning(parent, _("As duas senhas são diferentes."), _("Senhas diferentes"))
		return False
	return True


def _validRecoveryPhrase(parent, phrase: str, confirmation: str) -> bool:
	if len(phrase.strip()) < MIN_RECOVERY_LENGTH:
		_showWarning(
			parent,
			_("A frase de recuperação precisa ter pelo menos {count} caracteres.").format(
				count=MIN_RECOVERY_LENGTH,
			),
			_("Frase muito curta"),
		)
		return False
	def normalize(value: str) -> str:
		return " ".join(unicodedata.normalize("NFC", value).strip().split()).casefold()

	if normalize(phrase) != normalize(confirmation):
		_showWarning(
			parent,
			_("As duas frases de recuperação são diferentes."),
			_("Frases diferentes"),
		)
		return False
	return True


class SecuritySetupDialog(wx.Dialog):
	"""Cadastra a senha e, opcionalmente, a frase de recuperação."""

	def __init__(self, parent, existingCount: int):
		super().__init__(
			parent,
			title=_("Proteger o Diário"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self._modalEnding = False
		self.result = None
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		if existingCount:
			intro = _(
				"Foram encontradas {count} entradas da versão anterior. "
				"Ao continuar, elas serão criptografadas. Os antigos arquivos sem "
				"criptografia só serão removidos depois que o novo cofre for verificado."
			).format(count=existingCount)
		else:
			intro = _(
				"Crie uma senha para proteger o Diário. A lista de entradas e os botões "
				"do Diário só aparecerão depois do desbloqueio."
			)
		introLabel = wx.StaticText(self, label=intro)
		introLabel.Wrap(610)
		mainSizer.Add(introLabel, 0, wx.EXPAND | wx.ALL, 12)

		self.passwordCtrl = _addPasswordField(
			self,
			mainSizer,
			_("&Senha nova:"),
			_("Senha nova"),
		)
		self.confirmCtrl = _addPasswordField(
			self,
			mainSizer,
			_("&Confirme a senha:"),
			_("Confirmação da senha"),
		)

		self.recoveryCheck = wx.CheckBox(self, label=_("Cadastrar &frase de recuperação"))
		self.recoveryCheck.SetValue(True)
		mainSizer.Add(self.recoveryCheck, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
		helpLabel = wx.StaticText(
			self,
			label=_(
				"Se você esquecer a senha, a frase permitirá criar outra. Use uma frase "
				"longa e difícil de adivinhar. Maiúsculas e espaços repetidos não fazem diferença."
			),
		)
		helpLabel.Wrap(610)
		mainSizer.Add(helpLabel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
		self.phraseCtrl = _addPasswordField(
			self,
			mainSizer,
			_("&Frase de recuperação:"),
			_("Frase de recuperação"),
		)
		self.phraseConfirmCtrl = _addPasswordField(
			self,
			mainSizer,
			_("C&onfirme a frase:"),
			_("Confirmação da frase de recuperação"),
		)

		buttonSizer = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
		mainSizer.Add(buttonSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
		self.SetSizer(mainSizer)
		self.FindWindowById(wx.ID_OK).SetLabel(_("&Criar cofre"))
		self.FindWindowById(wx.ID_CANCEL).SetLabel(_("&Cancelar"))
		self.FindWindowById(wx.ID_OK).Bind(wx.EVT_BUTTON, self._onAccept)
		self.recoveryCheck.Bind(wx.EVT_CHECKBOX, self._onRecoveryToggle)
		self._onRecoveryToggle(None)
		self.SetMinSize((590, 600))
		self.SetSize((680, 690))
		self.CentreOnParent()
		self.passwordCtrl.SetFocus()

	def _onRecoveryToggle(self, event):
		enabled = self.recoveryCheck.GetValue()
		self.phraseCtrl.Enable(enabled)
		self.phraseConfirmCtrl.Enable(enabled)

	def _onAccept(self, event):
		if self._modalEnding:
			return
		password = self.passwordCtrl.GetValue()
		if not _validPassword(self, password, self.confirmCtrl.GetValue()):
			self.passwordCtrl.SetFocus()
			return
		phrase = None
		if self.recoveryCheck.GetValue():
			phrase = self.phraseCtrl.GetValue()
			if not _validRecoveryPhrase(self, phrase, self.phraseConfirmCtrl.GetValue()):
				self.phraseCtrl.SetFocus()
				return
		self.result = {"password": password, "recoveryPhrase": phrase}
		_endModalOnce(self, wx.ID_OK)


class UnlockDialog(wx.Dialog):
	"""Solicita a senha sem construir a janela que contém as entradas."""

	def __init__(self, parent, hasRecoveryPhrase: bool):
		super().__init__(parent, title=_("Desbloquear o Diário"))
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		intro = wx.StaticText(
			self,
			label=_("Digite a senha. As entradas continuarão ocultas até o desbloqueio."),
		)
		mainSizer.Add(intro, 0, wx.EXPAND | wx.ALL, 12)
		self.passwordCtrl = _addPasswordField(
			self,
			mainSizer,
			_("&Senha:"),
			_("Senha do Diário"),
		)
		buttons = wx.StdDialogButtonSizer()
		unlockButton = wx.Button(self, wx.ID_OK, label=_("&Desbloquear"))
		self.recoverButton = wx.Button(self, ID_RECOVER, label=_("&Esqueci a senha..."))
		cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("&Cancelar"))
		buttons.AddButton(unlockButton)
		buttons.AddButton(self.recoverButton)
		buttons.AddButton(cancelButton)
		buttons.Realize()
		mainSizer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
		self.SetSizerAndFit(mainSizer)
		self.recoverButton.Enable(hasRecoveryPhrase)
		if not hasRecoveryPhrase:
			self.recoverButton.SetToolTip(_("Nenhuma frase de recuperação foi cadastrada."))
		self.SetSize((560, self.GetSize().GetHeight()))
		self.CentreOnParent()
		unlockButton.SetDefault()
		self.passwordCtrl.SetFocus()

	@property
	def password(self) -> str:
		return self.passwordCtrl.GetValue()


class RecoveryPhraseDialog(wx.Dialog):
	"""Solicita a frase que protege a chave alternativa do cofre."""

	def __init__(self, parent):
		super().__init__(parent, title=_("Recuperar acesso ao Diário"))
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		helpLabel = wx.StaticText(
			self,
			label=_(
				"Digite a frase de recuperação cadastrada. Ela não mostrará a senha antiga; "
				"depois da confirmação, você criará uma senha nova."
			),
		)
		helpLabel.Wrap(540)
		mainSizer.Add(helpLabel, 0, wx.EXPAND | wx.ALL, 12)
		self.phraseCtrl = _addPasswordField(
			self,
			mainSizer,
			_("&Frase de recuperação:"),
			_("Frase de recuperação"),
		)
		mainSizer.Add(self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 12)
		self.SetSizerAndFit(mainSizer)
		self.FindWindowById(wx.ID_OK).SetLabel(_("&Continuar"))
		self.FindWindowById(wx.ID_CANCEL).SetLabel(_("&Cancelar"))
		self.SetSize((610, self.GetSize().GetHeight()))
		self.CentreOnParent()
		self.phraseCtrl.SetFocus()

	@property
	def phrase(self) -> str:
		return self.phraseCtrl.GetValue()


class NewPasswordDialog(wx.Dialog):
	"""Define uma senha nova durante a recuperação."""

	def __init__(self, parent):
		super().__init__(parent, title=_("Criar senha nova"))
		self._modalEnding = False
		self.result = None
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		info = wx.StaticText(
			self,
			label=_("A frase foi confirmada. Agora crie uma senha nova para o Diário."),
		)
		mainSizer.Add(info, 0, wx.EXPAND | wx.ALL, 12)
		self.passwordCtrl = _addPasswordField(
			self,
			mainSizer,
			_("&Senha nova:"),
			_("Senha nova"),
		)
		self.confirmCtrl = _addPasswordField(
			self,
			mainSizer,
			_("&Confirme a senha:"),
			_("Confirmação da senha"),
		)
		mainSizer.Add(self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 12)
		self.SetSizerAndFit(mainSizer)
		self.FindWindowById(wx.ID_OK).SetLabel(_("&Redefinir senha"))
		self.FindWindowById(wx.ID_CANCEL).SetLabel(_("&Cancelar"))
		self.FindWindowById(wx.ID_OK).Bind(wx.EVT_BUTTON, self._onAccept)
		self.SetSize((560, self.GetSize().GetHeight()))
		self.CentreOnParent()
		self.passwordCtrl.SetFocus()

	def _onAccept(self, event):
		if self._modalEnding:
			return
		password = self.passwordCtrl.GetValue()
		if not _validPassword(self, password, self.confirmCtrl.GetValue()):
			self.passwordCtrl.SetFocus()
			return
		self.result = password
		_endModalOnce(self, wx.ID_OK)


class ChangePasswordDialog(wx.Dialog):
	"""Confirma a senha atual antes de substituí-la."""

	def __init__(self, parent):
		super().__init__(parent, title=_("Alterar senha"))
		self._modalEnding = False
		self.result = None
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		self.currentCtrl = _addPasswordField(
			self,
			mainSizer,
			_("Senha &atual:"),
			_("Senha atual"),
		)
		self.newCtrl = _addPasswordField(
			self,
			mainSizer,
			_("Senha &nova:"),
			_("Senha nova"),
		)
		self.confirmCtrl = _addPasswordField(
			self,
			mainSizer,
			_("&Confirme a senha nova:"),
			_("Confirmação da senha nova"),
		)
		mainSizer.Add(self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 12)
		self.SetSizerAndFit(mainSizer)
		self.FindWindowById(wx.ID_OK).SetLabel(_("&Alterar"))
		self.FindWindowById(wx.ID_CANCEL).SetLabel(_("&Cancelar"))
		self.FindWindowById(wx.ID_OK).Bind(wx.EVT_BUTTON, self._onAccept)
		self.SetSize((560, self.GetSize().GetHeight()))
		self.CentreOnParent()
		self.currentCtrl.SetFocus()

	def _onAccept(self, event):
		if self._modalEnding:
			return
		newPassword = self.newCtrl.GetValue()
		if not _validPassword(self, newPassword, self.confirmCtrl.GetValue()):
			self.newCtrl.SetFocus()
			return
		self.result = {
			"currentPassword": self.currentCtrl.GetValue(),
			"newPassword": newPassword,
		}
		_endModalOnce(self, wx.ID_OK)


class ManageRecoveryDialog(wx.Dialog):
	"""Cadastra, substitui ou remove a frase de recuperação."""

	def __init__(self, parent, currentlyEnabled: bool):
		title = _("Alterar frase de recuperação") if currentlyEnabled else _("Cadastrar frase de recuperação")
		super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._modalEnding = False
		self.result = None
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		info = wx.StaticText(
			self,
			label=_(
				"A senha atual confirma esta alteração. Ao cadastrar ou substituir a frase, "
				"use algo longo e difícil de adivinhar."
			),
		)
		info.Wrap(560)
		mainSizer.Add(info, 0, wx.EXPAND | wx.ALL, 12)
		self.currentCtrl = _addPasswordField(
			self,
			mainSizer,
			_("Senha &atual:"),
			_("Senha atual"),
		)
		self.enableCheck = wx.CheckBox(self, label=_("&Usar frase de recuperação"))
		self.enableCheck.SetValue(currentlyEnabled)
		mainSizer.Add(self.enableCheck, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
		self.phraseCtrl = _addPasswordField(
			self,
			mainSizer,
			_("Frase de recuperação &nova:"),
			_("Frase de recuperação nova"),
		)
		self.confirmCtrl = _addPasswordField(
			self,
			mainSizer,
			_("&Confirme a frase nova:"),
			_("Confirmação da frase de recuperação nova"),
		)
		mainSizer.Add(self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 12)
		self.SetSizer(mainSizer)
		self.FindWindowById(wx.ID_OK).SetLabel(_("&Salvar"))
		self.FindWindowById(wx.ID_CANCEL).SetLabel(_("&Cancelar"))
		self.FindWindowById(wx.ID_OK).Bind(wx.EVT_BUTTON, self._onAccept)
		self.enableCheck.Bind(wx.EVT_CHECKBOX, self._onToggle)
		self._onToggle(None)
		self.SetMinSize((580, 500))
		self.SetSize((640, 570))
		self.CentreOnParent()
		self.currentCtrl.SetFocus()

	def _onToggle(self, event):
		enabled = self.enableCheck.GetValue()
		self.phraseCtrl.Enable(enabled)
		self.confirmCtrl.Enable(enabled)

	def _onAccept(self, event):
		if self._modalEnding:
			return
		phrase = None
		if self.enableCheck.GetValue():
			phrase = self.phraseCtrl.GetValue()
			if not _validRecoveryPhrase(self, phrase, self.confirmCtrl.GetValue()):
				self.phraseCtrl.SetFocus()
				return
		self.result = {
			"currentPassword": self.currentCtrl.GetValue(),
			"newPhrase": phrase,
		}
		_endModalOnce(self, wx.ID_OK)
