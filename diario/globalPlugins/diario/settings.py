# -*- coding: UTF-8 -*-

"""Painel do Diário nas configurações gerais do NVDA."""

import wx
from gui import guiHelper, settingsDialogs

from .i18n import (
	SUPPORTED_LANGUAGES,
	getLanguage,
	getSpellLanguagePreference,
	getSystemLanguage,
	isSpellSoundEnabled,
	setPreferences,
	translate as _,
)


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
		self._spellLanguageCodes = ["system", "interface"] + self._languageCodes
		self.spellLanguageChoice = helper.addLabeledControl(
			_("Idioma do &corretor ortográfico:"),
			wx.Choice,
			choices=[
				_("Padrão do sistema ({language})").format(language=getSystemLanguage()),
				_("Mesmo idioma da interface"),
			] + [name for code, name in SUPPORTED_LANGUAGES],
		)
		try:
			spellSelection = self._spellLanguageCodes.index(getSpellLanguagePreference())
		except ValueError:
			spellSelection = 0
		self.spellLanguageChoice.SetSelection(spellSelection)
		self.spellSoundCheckBox = wx.CheckBox(
			self,
			label=_("&Emitir som ao encontrar uma palavra possivelmente incorreta"),
		)
		helper.addItem(self.spellSoundCheckBox)
		self.spellSoundCheckBox.SetValue(isSpellSoundEnabled())
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
		spellSelection = self.spellLanguageChoice.GetSelection()
		if selection >= 0 and spellSelection >= 0:
			setPreferences(
				self._languageCodes[selection],
				self._spellLanguageCodes[spellSelection],
				self.spellSoundCheckBox.GetValue(),
			)
