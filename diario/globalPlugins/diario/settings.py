# -*- coding: UTF-8 -*-

"""Painel do Diário nas configurações gerais do NVDA."""

import wx
from gui import guiHelper, settingsDialogs

from .i18n import SUPPORTED_LANGUAGES, getLanguage, setLanguage, translate as _


class DiarySettingsPanel(settingsDialogs.SettingsPanel):
	"""Permite escolher um idioma sem alterar o idioma geral do NVDA."""

	title = _("Diário")

	def makeSettings(self, settingsSizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self._languageCodes = [code for code, name in SUPPORTED_LANGUAGES]
		self.languageChoice = helper.addLabeledControl(
			_("Idioma do &Diário:"),
			wx.Choice,
			choices=[name for code, name in SUPPORTED_LANGUAGES],
		)
		try:
			selection = self._languageCodes.index(getLanguage())
		except ValueError:
			selection = 0
		self.languageChoice.SetSelection(selection)
		notice = wx.StaticText(
			self,
			label=_(
				"As novas janelas do Diário usarão o idioma escolhido. Reinicie o NVDA "
				"para atualizar também o item do menu Ferramentas e a categoria de configurações."
			),
		)
		notice.Wrap(520)
		helper.addItem(notice)

	def onSave(self):
		selection = self.languageChoice.GetSelection()
		if selection >= 0:
			setLanguage(self._languageCodes[selection])
