# -*- coding: UTF-8 -*-

"""Integração acessível do corretor com os campos wx.TextCtrl."""

from __future__ import annotations

try:
	import winsound
except ImportError:  # Somente para testes estáticos fora do Windows.
	winsound = None

import wx
from logHandler import log

from .i18n import getLanguage, translate as _
from .spellcheck import MAX_WORD_LENGTH, SpellCheckerService, finishesWord, wordRangeEnding, wordRangeNear


def _menuLabel(value: str) -> str:
	"""Escapa o marcador de tecla de acesso em sugestões vindas do Windows."""

	return value.replace("&", "&&")


def _eventCharacter(event) -> str | None:
	if event.ControlDown() or event.AltDown() or event.MetaDown():
		return None
	keyCode = event.GetKeyCode()
	if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
		return "\r"
	if keyCode == wx.WXK_TAB:
		return "\t"
	value = event.GetUnicodeKey()
	if value in (getattr(wx, "WXK_NONE", 0), 0):
		value = keyCode
	if value < 0 or value > 0x10FFFF:
		return None
	try:
		return chr(value)
	except ValueError:
		return None


class SpellCheckTextCtrlController:
	"""Acrescenta bip e menu de sugestões a um campo editável."""

	def __init__(self, control: wx.TextCtrl, service: SpellCheckerService):
		self.control = control
		self.service = service
		control.Bind(wx.EVT_CHAR, self._onChar)
		control.Bind(wx.EVT_CONTEXT_MENU, self._onContextMenu)

	def handleShortcut(self, event) -> bool:
		"""Trata Aplicações, Shift+F10 e Alt+F10 no gancho do diálogo."""

		keyCode = event.GetKeyCode()
		applicationKey = getattr(wx, "WXK_WINDOWS_MENU", None)
		requested = applicationKey is not None and keyCode == applicationKey
		if keyCode == wx.WXK_F10 and (event.ShiftDown() or event.AltDown()):
			requested = True
		if not requested:
			return False
		return self.showSuggestions(position=None, invokedByKeyboard=True)

	def showSuggestions(self, position=None, invokedByKeyboard: bool = True) -> bool:
		"""Mostra o menu e informa se o evento de contexto foi consumido."""

		control = self.control
		if not control or control.IsBeingDeleted():
			return False
		language = getLanguage()
		if not self.service.available(language):
			return False

		originalStart, originalEnd = control.GetSelection()
		controlPosition = originalStart
		popupPoint = None
		if position is not None and position.x >= 0 and position.y >= 0:
			invokedByKeyboard = False
			popupPoint = control.ScreenToClient(position)
			hitPosition = self._hitTestPosition(popupPoint)
			if hitPosition is not None:
				controlPosition = hitPosition

		wordInfo = self._wordAtPosition(controlPosition)
		if wordInfo is None:
			return False
		word, wordStart, wordEnd = wordInfo
		if not self.service.isMisspelled(word, language):
			return False

		suggestions = self.service.suggestions(word, language)
		menu = wx.Menu()
		idReferences = []

		def newMenuId():
			reference = wx.NewIdRef()
			idReferences.append(reference)
			return int(reference)

		suggestionIds = {}
		for suggestion in suggestions:
			identifier = newMenuId()
			menu.Append(identifier, _menuLabel(suggestion))
			suggestionIds[identifier] = suggestion
		if not suggestions:
			item = menu.Append(newMenuId(), _("Nenhuma sugestão"))
			item.Enable(False)
		menu.AppendSeparator()
		ignoreId = newMenuId()
		addId = newMenuId()
		menu.Append(ignoreId, _("&Ignorar nesta sessão"))
		menu.Append(
			addId,
			_("&Adicionar \"{word}\" ao dicionário local").format(word=word),
		)

		control.SetSelection(wordStart, wordEnd)
		if popupPoint is None:
			popupPoint = control.PositionToCoords(wordStart)
			if popupPoint == wx.DefaultPosition:
				popupPoint = wx.Point(8, 8)
			else:
				popupPoint = wx.Point(popupPoint.x, popupPoint.y + control.GetCharHeight())
		try:
			selectedId = control.GetPopupMenuSelectionFromUser(menu, popupPoint)
		finally:
			menu.Destroy()

		if selectedId in suggestionIds:
			self._replaceWord(
				wordStart,
				wordEnd,
				suggestionIds[selectedId],
				originalStart,
				originalEnd,
				invokedByKeyboard,
			)
			return True

		control.SetSelection(originalStart, originalEnd)
		if selectedId == ignoreId:
			self.service.ignoreForSession(word, language)
		elif selectedId == addId:
			if not self.service.addToLocalDictionary(word, language):
				self._showDictionaryError()
		control.SetFocus()
		return True

	def _onChar(self, event) -> None:
		character = _eventCharacter(event)
		if character is not None and finishesWord(character):
			selectionStart, selectionEnd = self.control.GetSelection()
			if selectionStart == selectionEnd:
				fragmentStart = max(0, selectionStart - MAX_WORD_LENGTH - 2)
				fragment = self.control.GetRange(fragmentStart, selectionStart)
				rangeValue = wordRangeEnding(fragment, len(fragment))
				if rangeValue is not None:
					first, last = rangeValue
					word = fragment[first:last]
					# O evento é processado antes da consulta: espaço, pontuação ou
					# Enter sempre chegam ao campo, mesmo quando haverá bip.
					wx.CallAfter(self._checkCompletedWord, word)
		event.Skip()

	def _onContextMenu(self, event) -> None:
		position = event.GetPosition()
		invokedByKeyboard = position.x < 0 or position.y < 0
		if self.showSuggestions(position, invokedByKeyboard):
			return
		event.Skip()

	def _checkCompletedWord(self, word: str) -> None:
		try:
			if not self.control or self.control.IsBeingDeleted():
				return
			if not self.service.isMisspelled(word, getLanguage()):
				return
			if winsound is not None:
				winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
			else:
				wx.Bell()
		except Exception:
			# O corretor é auxiliar; jamais pode interromper a digitação.
			log.exception("Não foi possível emitir o aviso ortográfico do Diário.")

	def _hitTestPosition(self, point) -> int | None:
		try:
			value = self.control.HitTestPos(point)
			if isinstance(value, tuple) and len(value) >= 2:
				result, position = value[0], value[1]
				if result != wx.TE_HT_UNKNOWN:
					return int(position)
		except (AttributeError, TypeError, RuntimeError):
			pass
		try:
			value = self.control.HitTest(point)
			if isinstance(value, tuple) and len(value) >= 3:
				result, column, row = value[0], value[1], value[2]
				if result != wx.TE_HT_UNKNOWN:
					position = self.control.XYToPosition(column, row)
					return int(position) if position >= 0 else None
		except (AttributeError, TypeError, RuntimeError):
			pass
		return None

	def _wordAtPosition(self, position: int):
		control = self.control
		position = max(0, min(position, control.GetLastPosition()))
		try:
			converted = control.PositionToXY(position)
		except RuntimeError:
			return None
		if not isinstance(converted, tuple) or len(converted) < 3:
			return None
		success, column, row = converted[0], int(converted[1]), int(converted[2])
		if not success:
			return None
		line = control.GetLineText(row)
		rangeValue = wordRangeNear(line, min(column, len(line)))
		# Se o cursor estiver logo após Enter (ou em uma linha vazia), procura
		# também nas linhas imediatamente anteriores, como o campo nativo do
		# programa independente faz.
		remainingLines = 100
		while rangeValue is None and row > 0 and remainingLines:
			row -= 1
			remainingLines -= 1
			line = control.GetLineText(row)
			rangeValue = wordRangeNear(line, len(line))
		if rangeValue is None:
			return None
		first, last = rangeValue
		wordStart = control.XYToPosition(first, row)
		wordEnd = control.XYToPosition(last, row)
		if wordStart < 0:
			return None
		if wordEnd < 0:
			lineStart = control.XYToPosition(0, row)
			if lineStart < 0:
				return None
			wordEnd = lineStart + last
		word = control.GetRange(wordStart, wordEnd)
		return (word, wordStart, wordEnd)

	def _replaceWord(
		self,
		wordStart: int,
		wordEnd: int,
		replacement: str,
		originalStart: int,
		originalEnd: int,
		invokedByKeyboard: bool,
	) -> None:
		control = self.control
		control.SetSelection(wordStart, wordEnd)
		control.WriteText(replacement)
		if invokedByKeyboard and originalStart == originalEnd and originalStart >= wordEnd:
			caret = originalStart + len(replacement) - (wordEnd - wordStart)
		else:
			caret = wordStart + len(replacement)
		control.SetSelection(max(0, caret), max(0, caret))
		control.SetFocus()

	def _showDictionaryError(self) -> None:
		dialog = wx.MessageDialog(
			self.control.GetParent(),
			_("Não foi possível salvar a palavra no dicionário local."),
			_("Erro no dicionário"),
			wx.OK | wx.ICON_ERROR,
		)
		try:
			dialog.ShowModal()
		finally:
			dialog.Destroy()
