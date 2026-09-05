# Diary for NVDA

[English](README.md) · [Português do Brasil](diario/README.pt-BR.md) · [Español](diario/README.es.md) · [Italiano](diario/README.it.md) · [Français](diario/README.fr.md)

Version 1.3.0

Diary for NVDA is an accessible, offline personal diary integrated with the NVDA screen reader. Its distinguishing combination is dated entries and automatic creation timestamps inside a password-protected encrypted vault, with optional recovery and an accessible real-time spell checker.

## Main features

* Create, list, read, edit and delete diary entries.
* Choose the date of each entry while retaining its original creation date and time.
* Protect titles, dates and entry text in an authenticated AES-256-GCM encrypted vault.
* Change the password and optionally set a recovery phrase.
* Hear a warning sound after completing a misspelled word without losing the typed space, punctuation or line break.
* Open spelling suggestions with right-click, Applications, Shift+F10 or Alt+F10.
* Replace a word, ignore it for the current NVDA session or add it to the Diary's local dictionary.
* Export the two encrypted vault files to a ZIP and import only entries that do not yet exist in the open Diary.
* Use the interface and documentation in Brazilian Portuguese, English, Spanish, Italian or French.
* Keep all diary data on the computer; the add-on does not send entries to the internet.

## Requirements

* NVDA 2025.1 or later.
* Windows 8 or later for the native Windows Spell Checking API. Current NVDA versions require a newer supported Windows release.
* A Windows spelling dictionary for the language selected in the Diary. If that dictionary is unavailable, the Diary continues to work normally and only spell checking is disabled for that language.

## Installation and opening

Install `diario-1.3.0.nvda-addon` through NVDA's Add-on Store or open the package directly and confirm installation. Restart NVDA when requested.

Open the Diary from NVDA menu > Tools > Diary, or press NVDA+Alt+D. The gesture can be changed in NVDA's Input Gestures dialog, under the Diary category.

## Spell checking

The title and entry text fields are checked as you type. After a word is followed by a space, punctuation, Tab or Enter, a warning sound is played if Windows considers it misspelled. The delimiter is always entered, so the warning can simply be ignored.

Place the caret on or after the word and press Applications, Shift+F10 or Alt+F10. A right-click on the word works as well. The accessible menu contains up to eight Windows suggestions followed by:

* **Ignore for this session:** stops warnings for that word until NVDA is restarted.
* **Add to local dictionary:** saves the word in `dicionario.txt`, inside the Diary data folder, and stops future warnings.

The local dictionary is a UTF-8 text file containing only words explicitly added by the user. It is not encrypted because it contains no diary entries. It is shared by the five Diary interface languages.

## Encrypted backup export and import

The **Export backup** and **Import backup** buttons are available only after the Diary is unlocked.

**Export backup** opens a Save dialog and creates a ZIP containing exactly `diario.enc` and `diario.backup.enc`. Both files remain encrypted; no title, date or entry text is written in plaintext.

**Import backup** opens a file-selection dialog, validates both encrypted files in a temporary location and adds only entries whose identifiers do not exist in the current Diary. Existing entries are never replaced, even if an imported entry with the same identifier has different content. Imported dates, titles, text and creation timestamps are preserved.

A backup exported from the same vault opens with the key already held by the unlocked Diary and requires no additional password. A backup from an independently created vault has a different random key, even when its password text happens to be the same; only in that case the add-on requests the password of the imported backup. This does not change the current Diary password. After the merge, new entries are protected by the current vault.

If the ZIP is invalid, its password is incorrect, the operation is canceled or it contains no new entries, the current Diary remains unchanged.

## Data, privacy and recovery

Diary data is stored below the NVDA configuration directory, in the `diario` folder. The main vault is `diario.enc`; its encrypted backup is `diario.backup.enc`.

All entry content, including titles and dates, is protected with authenticated AES-256-GCM encryption through Windows CNG. The vault key is protected from the password with PBKDF2-HMAC-SHA256 using 600,000 iterations. When configured, the recovery phrase protects the same random vault key separately.

The recovery phrase does not reveal the old password. It only permits the user to create a new password. If both the password and recovery phrase are forgotten, the add-on cannot recover the entries. Choose long, hard-to-guess secrets and keep independent backups of the encrypted files.

Version 1.3.0 keeps the encrypted vault format compatible with version 1.1.0.

## Interface language

Open NVDA menu > Preferences > Settings > Diary to choose Brazilian Portuguese, Spanish, Italian, French or English without changing NVDA's general language. New Diary windows use the selection immediately. Restart NVDA to update the Tools menu item, settings category and input-gesture description as well.

## Building and testing from source

The repository uses only Python's standard library for its build and unit tests:

```text
python diario/build.py
python -m unittest discover -s diario/tests -v
```

The build command reads the version from `diario/manifest.ini` and creates `diario/dist/diario-<version>.nvda-addon`. It excludes tests, caches and development files from the installable package.

Use `python diario/build.py --source` to also create the repository source ZIP and checksums inside `diario/dist`.

The Windows spell checker bridge uses `ctypes`; no third-party Python package is required. Because the build can run on any platform but the add-on itself runs inside NVDA, the native spelling integration must receive a final smoke test on Windows with NVDA before a store release.

## License and author

Copyright © Fernando de Paula Zamboni.

Licensed under the GNU General Public License, version 2 or later. See [LICENSE.txt](diario/LICENSE.txt).
