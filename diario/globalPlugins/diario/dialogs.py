# -*- coding: UTF-8 -*-

"""Janelas acessíveis do Diário."""

from __future__ import annotations

from datetime import date
import os

import ui
import wx
from logHandler import log

from .backup import (
	DiaryBackupError,
	exportEncryptedVault,
	mergeNewEntries,
	stagedImportArchive,
)
from .i18n import translate as _
from .secureStorage import InvalidSecretError, SecureDiaryStorage
from .securityDialogs import (
	ChangePasswordDialog,
	ImportBackupPasswordDialog,
	ManageRecoveryDialog,
)
from .spellcheckUi import SpellCheckTextCtrlController
from .storage import DiaryStorageError, Entry


def formatDate(value: date) -> str:
	return value.strftime("%d/%m/%Y")


def formatDateTime(value) -> str:
	return _("{date} às {time}").format(
		date=formatDate(value.date()),
		time=value.strftime("%H:%M:%S"),
	)


def showMessage(parent, message: str, caption: str, style: int) -> int:
	dialog = wx.MessageDialog(parent, message, caption, style)
	try:
		return dialog.ShowModal()
	finally:
		dialog.Destroy()


def endModalOnce(dialog, result: int) -> None:
	"""Encerra um diálogo uma só vez, mesmo com eventos repetidos na fila."""

	if getattr(dialog, "_modalEnding", False):
		return
	dialog._modalEnding = True
	try:
		dialog.EndModal(result)
	except RuntimeError:
		# O wx pode entregar um segundo evento depois de o objeto C++ desaparecer.
		# O primeiro evento já encerrou o diálogo, portanto não há mais o que fazer.
		return


class EntryEditDialog(wx.Dialog):
	"""Cria ou edita uma entrada."""

	def __init__(self, parent, entry: Entry | None = None, spellChecker=None):
		super().__init__(
			parent,
			title=_("Editar entrada") if entry else _("Nova entrada"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self._modalEnding = False
		self._entry = entry
		self._spellChecker = spellChecker
		self._spellControllers = []
		self.result = None
		self._initialValues = None
		self._buildUi()
		self._loadValues()
		self.SetMinSize((560, 480))
		self.SetSize((720, 620))
		self.CentreOnParent()

	def _buildUi(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)

		titleLabel = wx.StaticText(self, label=_("&Título:"))
		mainSizer.Add(titleLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
		self.titleCtrl = wx.TextCtrl(self)
		self.titleCtrl.SetName(_("Título"))
		self.titleCtrl.SetMaxLength(0)
		mainSizer.Add(self.titleCtrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

		dateBox = wx.StaticBoxSizer(wx.VERTICAL, self, label=_("Data da entrada"))
		dateFields = wx.BoxSizer(wx.HORIZONTAL)
		self.dayCtrl = self._addDateField(dateFields, _("&Dia:"), 1, 31)
		self.monthCtrl = self._addDateField(dateFields, _("&Mês:"), 1, 12)
		self.yearCtrl = self._addDateField(dateFields, _("&Ano:"), 1, 9999)
		dateBox.Add(dateFields, 0, wx.EXPAND | wx.ALL, 6)
		mainSizer.Add(dateBox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

		bodyLabel = wx.StaticText(self, label=_("&Texto da entrada:"))
		mainSizer.Add(bodyLabel, 0, wx.LEFT | wx.RIGHT, 12)
		self.bodyCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_RICH2)
		self.bodyCtrl.SetName(_("Texto da entrada"))
		self.bodyCtrl.SetMaxLength(0)
		mainSizer.Add(self.bodyCtrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

		buttonSizer = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
		mainSizer.Add(buttonSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
		self.SetSizer(mainSizer)

		okButton = self.FindWindowById(wx.ID_OK)
		okButton.SetLabel(_("&Salvar"))
		cancelButton = self.FindWindowById(wx.ID_CANCEL)
		cancelButton.SetLabel(_("&Cancelar"))
		okButton.Bind(wx.EVT_BUTTON, self._onSave)
		cancelButton.Bind(wx.EVT_BUTTON, self._onCancel)
		self.Bind(wx.EVT_CLOSE, self._onClose)
		if self._spellChecker is not None:
			for control in (self.titleCtrl, self.bodyCtrl):
				self._spellControllers.append(
					SpellCheckTextCtrlController(control, self._spellChecker)
				)
			self.Bind(wx.EVT_CHAR_HOOK, self._onCharHook)

	def _addDateField(self, parentSizer, label: str, minimum: int, maximum: int):
		fieldSizer = wx.BoxSizer(wx.VERTICAL)
		fieldLabel = wx.StaticText(self, label=label)
		fieldSizer.Add(fieldLabel, 0, wx.BOTTOM, 3)
		control = wx.SpinCtrl(self, min=minimum, max=maximum)
		control.SetName(label.replace("&", "").rstrip(":"))
		fieldSizer.Add(control, 0)
		parentSizer.Add(fieldSizer, 1, wx.RIGHT, 12)
		return control

	def _loadValues(self):
		if self._entry:
			selectedDate = self._entry.entryDate
			self.titleCtrl.SetValue(self._entry.title)
			self.bodyCtrl.SetValue(self._entry.body)
		else:
			selectedDate = date.today()
		self.dayCtrl.SetValue(selectedDate.day)
		self.monthCtrl.SetValue(selectedDate.month)
		self.yearCtrl.SetValue(selectedDate.year)
		self._initialValues = self._currentValues()
		self.titleCtrl.SetFocus()
		self.titleCtrl.SetInsertionPointEnd()

	def _currentValues(self):
		return (
			self.titleCtrl.GetValue(),
			self.bodyCtrl.GetValue(),
			self.dayCtrl.GetValue(),
			self.monthCtrl.GetValue(),
			self.yearCtrl.GetValue(),
		)

	def _confirmDiscard(self) -> bool:
		if self._initialValues == self._currentValues():
			return True
		answer = showMessage(
			self,
			_("Descartar as alterações que ainda não foram salvas?"),
			_("Confirmar cancelamento"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
		)
		return answer == wx.ID_YES

	def _onCancel(self, event):
		if self._modalEnding:
			return
		if self._confirmDiscard():
			endModalOnce(self, wx.ID_CANCEL)

	def _onClose(self, event):
		if self._modalEnding:
			return
		if self._confirmDiscard():
			endModalOnce(self, wx.ID_CANCEL)
		elif event.CanVeto():
			event.Veto()

	def _onSave(self, event):
		if self._modalEnding:
			return
		title = self.titleCtrl.GetValue().strip()
		if not title:
			showMessage(
				self,
				_("Digite um título para a entrada."),
				_("Título obrigatório"),
				wx.OK | wx.ICON_WARNING,
			)
			self.titleCtrl.SetFocus()
			return

		try:
			selectedDate = date(
				self.yearCtrl.GetValue(),
				self.monthCtrl.GetValue(),
				self.dayCtrl.GetValue(),
			)
		except ValueError:
			showMessage(
				self,
				_("A data informada não existe. Confira o dia, o mês e o ano."),
				_("Data inválida"),
				wx.OK | wx.ICON_WARNING,
			)
			self.dayCtrl.SetFocus()
			return

		self.result = {
			"title": title,
			"body": self.bodyCtrl.GetValue(),
			"entryDate": selectedDate,
		}
		endModalOnce(self, wx.ID_OK)

	def _onCharHook(self, event):
		focus = wx.Window.FindFocus()
		controller = next(
			(item for item in self._spellControllers if item.control == focus),
			None,
		)
		if controller is not None and controller.handleShortcut(event):
			return
		event.Skip()


class EntryReadDialog(wx.Dialog):
	"""Mostra uma entrada em uma caixa de texto somente para leitura."""

	def __init__(self, parent, entry: Entry):
		super().__init__(
			parent,
			title=_("Ler entrada: {title}").format(title=entry.title),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self._modalEnding = False
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		self.textCtrl = wx.TextCtrl(
			self,
			value=self._composeText(entry),
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
		)
		self.textCtrl.SetName(_("Entrada do diário"))
		self.textCtrl.SetMaxLength(0)
		mainSizer.Add(self.textCtrl, 1, wx.EXPAND | wx.ALL, 12)

		buttonSizer = self.CreateSeparatedButtonSizer(wx.CLOSE)
		mainSizer.Add(buttonSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
		self.SetSizer(mainSizer)
		closeButton = self.FindWindowById(wx.ID_CLOSE)
		closeButton.SetLabel(_("&Fechar"))
		closeButton.Bind(wx.EVT_BUTTON, self._onCloseButton)
		self.Bind(wx.EVT_CHAR_HOOK, self._onCharHook)
		self.Bind(wx.EVT_CLOSE, self._onWindowClose)

		self.SetMinSize((560, 420))
		self.SetSize((720, 600))
		self.CentreOnParent()
		self.textCtrl.SetInsertionPoint(0)
		self.textCtrl.SetFocus()

	def _onCharHook(self, event):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			endModalOnce(self, wx.ID_CLOSE)
			return
		event.Skip()

	def _onCloseButton(self, event):
		endModalOnce(self, wx.ID_CLOSE)

	def _onWindowClose(self, event):
		endModalOnce(self, wx.ID_CLOSE)

	def _composeText(self, entry: Entry) -> str:
		parts = [
			entry.title,
			_("Criada em: {dateTime}").format(dateTime=formatDateTime(entry.createdAt)),
			_("Data da entrada: {date}").format(date=formatDate(entry.entryDate)),
		]
		if entry.updatedAt:
			parts.append(_("Última edição: {dateTime}").format(dateTime=formatDateTime(entry.updatedAt)))
		parts.extend(["", entry.body])
		return "\r\n".join(parts)


class DiaryDialog(wx.Dialog):
	"""Lista e gerencia as entradas do Diário."""

	def __init__(self, parent, storage, spellChecker=None):
		super().__init__(
			parent,
			title=_("Diário para NVDA"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self._modalEnding = False
		self.storage = storage
		self.spellChecker = spellChecker
		self.entries = []
		self._rowEntryIds = []
		self._buildUi()
		self._loadEntries()
		self.SetMinSize((620, 480))
		self.SetSize((820, 610))
		self.CentreOnParent()
		if self.entries:
			self.listCtrl.SetFocus()
		else:
			self.newButton.SetFocus()

	def _buildUi(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		listLabel = wx.StaticText(self, label=_("&Entradas do diário:"))
		mainSizer.Add(listLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)

		self.listCtrl = wx.ListCtrl(
			self,
			style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
		)
		self.listCtrl.SetName(_("Entradas do diário"))
		self.listCtrl.InsertColumn(0, _("Título"), width=360)
		self.listCtrl.InsertColumn(1, _("Data da entrada"), width=130)
		self.listCtrl.InsertColumn(2, _("Criada em"), width=210)
		mainSizer.Add(self.listCtrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

		self.statusLabel = wx.StaticText(self, label="")
		mainSizer.Add(self.statusLabel, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

		buttons = wx.BoxSizer(wx.HORIZONTAL)
		self.newButton = wx.Button(self, label=_("&Nova entrada"))
		self.readButton = wx.Button(self, label=_("&Ler"))
		self.editButton = wx.Button(self, label=_("&Editar"))
		self.deleteButton = wx.Button(self, label=_("E&xcluir"))
		for button in (
			self.newButton,
			self.readButton,
			self.editButton,
			self.deleteButton,
		):
			buttons.Add(button, 0, wx.RIGHT, 8)
		mainSizer.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

		backupButtons = wx.BoxSizer(wx.HORIZONTAL)
		self.exportButton = wx.Button(self, label=_("Expor&tar backup..."))
		self.importButton = wx.Button(self, label=_("&Importar backup..."))
		for button in (self.exportButton, self.importButton):
			backupButtons.Add(button, 0, wx.RIGHT, 8)
		mainSizer.Add(backupButtons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

		securityButtons = wx.BoxSizer(wx.HORIZONTAL)
		self.changePasswordButton = wx.Button(self, label=_("Alterar &senha..."))
		self.recoveryButton = wx.Button(self, label=_("Frase de &recuperação..."))
		# wx.ID_CANCEL possui tratamento nativo confiável em wx.Dialog. O ID_CLOSE
		# direto era anunciado pelo NVDA, mas não ativava o botão em algumas
		# instalações do wxPython com Enter ou Espaço.
		self.closeButton = wx.Button(self, wx.ID_CANCEL, label=_("&Bloquear e fechar"))
		for button in (
			self.changePasswordButton,
			self.recoveryButton,
			self.closeButton,
		):
			securityButtons.Add(button, 0, wx.RIGHT, 8)
		mainSizer.Add(securityButtons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
		self.SetSizer(mainSizer)

		self.newButton.Bind(wx.EVT_BUTTON, self._onNew)
		self.readButton.Bind(wx.EVT_BUTTON, self._onRead)
		self.editButton.Bind(wx.EVT_BUTTON, self._onEdit)
		self.deleteButton.Bind(wx.EVT_BUTTON, self._onDelete)
		self.exportButton.Bind(wx.EVT_BUTTON, self._onExport)
		self.importButton.Bind(wx.EVT_BUTTON, self._onImport)
		self.changePasswordButton.Bind(wx.EVT_BUTTON, self._onChangePassword)
		self.recoveryButton.Bind(wx.EVT_BUTTON, self._onManageRecovery)
		self.closeButton.Bind(wx.EVT_BUTTON, self._onCloseButton)
		self.closeButton.Bind(wx.EVT_KEY_DOWN, self._onCloseButtonKey)
		self.listCtrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._onRead)
		self.listCtrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self._onSelectionChanged)
		self.listCtrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._onSelectionChanged)
		self.Bind(wx.EVT_CHAR_HOOK, self._onCharHook)
		self.Bind(wx.EVT_CLOSE, self._onWindowClose)

	def _loadEntries(self, selectId: str | None = None):
		try:
			result = self.storage.load()
		except DiaryStorageError as error:
			log.exception("Não foi possível carregar as entradas do Diário.")
			self.entries = []
			self._populateList()
			wx.CallAfter(
				showMessage,
				self,
				_(str(error)),
				_("Erro ao abrir o Diário"),
				wx.OK | wx.ICON_ERROR,
			)
			return

		self.entries = sorted(
			result.entries,
			key=lambda entry: (entry.entryDate, entry.createdAt),
			reverse=True,
		)
		self._populateList(selectId)
		if result.recoveredFromBackup:
			wx.CallAfter(
				showMessage,
				self,
				_(
					"O cofre principal não pôde ser lido. As entradas foram recuperadas "
					"da cópia de segurança criptografada. Na próxima alteração, as duas "
					"cópias serão reparadas."
				),
				_("Entradas recuperadas"),
				wx.OK | wx.ICON_WARNING,
			)

	def _populateList(self, selectId: str | None = None):
		self.listCtrl.DeleteAllItems()
		self._rowEntryIds = []
		selectedRow = -1
		for row, entry in enumerate(self.entries):
			index = self.listCtrl.InsertItem(row, entry.title)
			self.listCtrl.SetItem(index, 1, formatDate(entry.entryDate))
			self.listCtrl.SetItem(index, 2, formatDateTime(entry.createdAt))
			self._rowEntryIds.append(entry.id)
			if entry.id == selectId:
				selectedRow = index

		count = len(self.entries)
		self.statusLabel.SetLabel(
			_("{count} entrada.").format(count=count)
			if count == 1
			else _("{count} entradas.").format(count=count)
		)
		if selectedRow >= 0:
			self.listCtrl.Select(selectedRow)
			self.listCtrl.Focus(selectedRow)
			self.listCtrl.EnsureVisible(selectedRow)
		self._updateButtons()

	def _selectedEntry(self) -> Entry | None:
		row = self.listCtrl.GetFirstSelected()
		if row < 0 or row >= len(self._rowEntryIds):
			return None
		entryId = self._rowEntryIds[row]
		return next((entry for entry in self.entries if entry.id == entryId), None)

	def _requireSelectedEntry(self) -> Entry | None:
		entry = self._selectedEntry()
		if entry is None:
			ui.message(_("Selecione uma entrada primeiro."))
			self.listCtrl.SetFocus()
		return entry

	def _onSelectionChanged(self, event):
		self._updateButtons()
		event.Skip()

	def _updateButtons(self):
		hasSelection = self._selectedEntry() is not None
		self.readButton.Enable(hasSelection)
		self.editButton.Enable(hasSelection)
		self.deleteButton.Enable(hasSelection)

	def _onNew(self, event):
		dialog = EntryEditDialog(self, spellChecker=self.spellChecker)
		try:
			if dialog.ShowModal() != wx.ID_OK or dialog.result is None:
				return
			entry = Entry.create(**dialog.result)
			newEntries = [*self.entries, entry]
			if self._saveEntries(newEntries):
				self._loadEntries(selectId=entry.id)
				self.listCtrl.SetFocus()
				ui.message(_("Entrada criada."))
		finally:
			dialog.Destroy()

	def _onRead(self, event):
		entry = self._requireSelectedEntry()
		if entry is None:
			return
		dialog = EntryReadDialog(self, entry)
		try:
			dialog.ShowModal()
		finally:
			dialog.Destroy()
		self.listCtrl.SetFocus()

	def _onEdit(self, event):
		entry = self._requireSelectedEntry()
		if entry is None:
			return
		dialog = EntryEditDialog(self, entry, spellChecker=self.spellChecker)
		try:
			if dialog.ShowModal() != wx.ID_OK or dialog.result is None:
				return
			editedEntry = entry.edited(**dialog.result)
			newEntries = [editedEntry if item.id == entry.id else item for item in self.entries]
			if self._saveEntries(newEntries):
				self._loadEntries(selectId=entry.id)
				self.listCtrl.SetFocus()
				ui.message(_("Entrada atualizada."))
		finally:
			dialog.Destroy()

	def _onDelete(self, event):
		entry = self._requireSelectedEntry()
		if entry is None:
			return
		answer = showMessage(
			self,
			_("Excluir a entrada ‘{title}’?").format(title=entry.title),
			_("Confirmar exclusão"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
		)
		if answer != wx.ID_YES:
			return
		newEntries = [item for item in self.entries if item.id != entry.id]
		if self._saveEntries(newEntries):
			self._loadEntries()
			if self.entries:
				self.listCtrl.Select(0)
				self.listCtrl.Focus(0)
				self.listCtrl.SetFocus()
			else:
				self.newButton.SetFocus()
			ui.message(_("Entrada excluída."))

	def _saveEntries(self, entries: list[Entry]) -> bool:
		try:
			self.storage.save(entries)
			return True
		except DiaryStorageError as error:
			log.exception("Não foi possível gravar as entradas do Diário.")
			showMessage(
				self,
				_(str(error)),
				_("Erro ao salvar"),
				wx.OK | wx.ICON_ERROR,
			)
			return False

	def _onExport(self, event):
		fileDialog = wx.FileDialog(
			self,
			message=_("Salvar backup criptografado"),
			defaultFile=f"diario-backup-{date.today().isoformat()}.zip",
			wildcard=_("Backups do Diário (*.zip)|*.zip|Todos os arquivos (*.*)|*.*"),
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		)
		try:
			if fileDialog.ShowModal() != wx.ID_OK:
				return
			selectedPath = fileDialog.GetPath()
		finally:
			fileDialog.Destroy()

		destinationPath = selectedPath
		if not destinationPath.lower().endswith(".zip"):
			destinationPath += ".zip"
			if os.path.exists(destinationPath):
				answer = showMessage(
					self,
					_("O arquivo já existe. Deseja substituí-lo?"),
					_("Confirmar substituição"),
					wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
				)
				if answer != wx.ID_YES:
					return

		try:
			exportEncryptedVault(
				self.storage.vault.filePath,
				self.storage.vault.backupPath,
				destinationPath,
			)
		except DiaryBackupError as error:
			log.exception("Não foi possível exportar o backup criptografado do Diário.")
			showMessage(
				self,
				_(str(error)),
				_("Erro ao exportar backup"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		showMessage(
			self,
			_("O backup criptografado foi salvo em:\n{path}").format(path=destinationPath),
			_("Backup exportado"),
			wx.OK | wx.ICON_INFORMATION,
		)

	def _onImport(self, event):
		fileDialog = wx.FileDialog(
			self,
			message=_("Abrir backup criptografado"),
			wildcard=_("Backups do Diário (*.zip)|*.zip|Todos os arquivos (*.*)|*.*"),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		)
		try:
			if fileDialog.ShowModal() != wx.ID_OK:
				return
			archivePath = fileDialog.GetPath()
		finally:
			fileDialog.Destroy()

		try:
			with stagedImportArchive(archivePath) as stagedDirectory:
				importedVault = SecureDiaryStorage(stagedDirectory)
				importedSession = self._unlockImportedVault(importedVault)
				if importedSession is None:
					return
				try:
					importedEntries = importedSession.load().entries
				finally:
					importedSession.lock()
			mergedEntries, addedEntries = mergeNewEntries(self.entries, importedEntries)
			if not addedEntries:
				showMessage(
					self,
					_("O backup não contém entradas novas para importar."),
					_("Nenhuma entrada nova"),
					wx.OK | wx.ICON_INFORMATION,
				)
				return
			if not self._saveEntries(mergedEntries):
				return
		except DiaryBackupError as error:
			log.exception("Não foi possível importar o backup criptografado do Diário.")
			showMessage(
				self,
				_(str(error)),
				_("Erro ao importar backup"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		except DiaryStorageError:
			log.exception("Não foi possível abrir o cofre criptografado importado.")
			showMessage(
				self,
				_(
					"Os arquivos criptografados do backup não puderam ser abertos. "
					"O ZIP pode estar danificado ou não ter sido criado pelo Diário."
				),
				_("Erro ao importar backup"),
				wx.OK | wx.ICON_ERROR,
			)
			return

		self._loadEntries(selectId=addedEntries[0].id)
		self.listCtrl.SetFocus()
		count = len(addedEntries)
		message = (
			_("{count} entrada nova foi importada.")
			if count == 1
			else _("{count} entradas novas foram importadas.")
		).format(count=count)
		showMessage(
			self,
			message,
			_("Importação concluída"),
			wx.OK | wx.ICON_INFORMATION,
		)

	def _unlockImportedVault(self, importedVault: SecureDiaryStorage):
		try:
			return self.storage.unlockRelatedVault(importedVault)
		except InvalidSecretError:
			pass

		while True:
			dialog = ImportBackupPasswordDialog(self)
			try:
				result = dialog.ShowModal()
				password = dialog.password
			finally:
				dialog.Destroy()
			if result != wx.ID_OK:
				return None
			try:
				return importedVault.unlockWithPassword(password)
			except InvalidSecretError:
				showMessage(
					self,
					_("A senha do backup está incorreta. Tente novamente."),
					_("Senha do backup incorreta"),
					wx.OK | wx.ICON_WARNING,
				)

	def _onChangePassword(self, event):
		dialog = ChangePasswordDialog(self)
		try:
			if dialog.ShowModal() != wx.ID_OK or dialog.result is None:
				return
			try:
				self.storage.changePassword(**dialog.result)
			except DiaryStorageError as error:
				showMessage(
					self,
					_(str(error)),
					_("Não foi possível alterar a senha"),
					wx.OK | wx.ICON_ERROR,
				)
				return
			ui.message(_("Senha alterada."))
		finally:
			dialog.Destroy()

	def _onManageRecovery(self, event):
		dialog = ManageRecoveryDialog(self, self.storage.hasRecoveryPhrase)
		try:
			if dialog.ShowModal() != wx.ID_OK or dialog.result is None:
				return
			try:
				self.storage.changeRecoveryPhrase(**dialog.result)
			except DiaryStorageError as error:
				showMessage(
					self,
					_(str(error)),
					_("Não foi possível alterar a frase"),
					wx.OK | wx.ICON_ERROR,
				)
				return
			if dialog.result["newPhrase"] is None:
				ui.message(_("Frase de recuperação removida."))
			else:
				ui.message(_("Frase de recuperação salva."))
		finally:
			dialog.Destroy()

	def _onCharHook(self, event):
		keyCode = event.GetKeyCode()
		if keyCode == wx.WXK_ESCAPE:
			endModalOnce(self, wx.ID_CLOSE)
			return
		if event.ControlDown() and keyCode in (ord("N"), ord("n")):
			self._onNew(event)
			return
		if event.ControlDown() and keyCode in (ord("E"), ord("e")):
			self._onEdit(event)
			return
		if keyCode == wx.WXK_F2:
			self._onEdit(event)
			return
		if keyCode == wx.WXK_DELETE:
			self._onDelete(event)
			return
		event.Skip()

	def _onCloseButton(self, event):
		endModalOnce(self, wx.ID_CANCEL)

	def _onCloseButtonKey(self, event):
		if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_SPACE):
			endModalOnce(self, wx.ID_CANCEL)
			return
		event.Skip()

	def _onWindowClose(self, event):
		endModalOnce(self, wx.ID_CLOSE)
