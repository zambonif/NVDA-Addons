# Idiomas da interface

A versão 1.0 inclui português do Brasil, espanhol, italiano, francês e inglês.
Como o idioma é escolhido independentemente do idioma geral do NVDA, os
catálogos ficam em `globalPlugins/diario/translations.py` e são selecionados por
`globalPlugins/diario/i18n.py`.

O português é o texto-fonte e serve como retorno seguro para mensagens ainda
não traduzidas. Toda tradução deve preservar exatamente marcadores como
`{title}`, `{count}`, `{date}` e `{time}`. Os testes automatizados verificam
esses marcadores.

O manifesto e a documentação ainda podem receber traduções convencionais em
`locale/IDIOMA/manifest.ini` e `doc/IDIOMA/readme.html`; essas partes seguem o
idioma geral do NVDA, pois são lidas antes de a preferência própria do Diário
ser aplicada.
