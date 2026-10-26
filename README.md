# Diary for NVDA 1.4.2

Diary for NVDA is an accessible personal diary integrated with the NVDA screen
reader. It provides dated entries, password protection, an optional recovery
phrase, an encrypted vault, encrypted backup import and export, and accessible
real-time spell checking.

## Changes in version 1.4.2

When the current password is rejected while changing the password or recovery settings, the message now identifies the current password without referring to an incorrect recovery phrase. The message is translated into every supported language.

Regression tests cover passwords up to 4,096 characters, including punctuation and Unicode. The user who reported the issue confirmed that the updated add-on works with his 128-character password and that the misleading message no longer appears. The recovery phrase remains optional.

Run `python -m unittest discover -s tests -v` for the 29 regression tests.

## Changes in version 1.4.1

- The spell-checking language can now be selected independently from the
  interface language.
- By default, spell checking follows the interface language, preserving the
  behavior of previous versions.
- The System default option supports any language provided by the Windows Spell
  Checking API, including Romanian.
- Spelling-warning sounds can be disabled without disabling suggestions, the
  accessible context menu or the personal dictionary.
- Preferences saved by previous versions remain compatible.

## Changes in version 1.4.0

- Authenticated the complete PBKDF2 key-derivation metadata with AES-GCM after
  a responsibly submitted security report.
- Enforced a minimum of 600,000 PBKDF2 iterations.
- Preserved compatibility and automatic protection upgrades for older vaults.
- Added UTF-8 export and validated merge import for the personal dictionary.

## Building the add-on

Python 3 is required. From the root of this source directory, run:

```powershell
python build.py
```

The add-on will be created at:

```text
dist\diario-1.4.2.nvda-addon
```

The source directory keeps `manifest.ini`, `README.md` and `build.py` at its
root. Inside the generated `.nvda-addon` package, `manifest.ini` is also at the
root, next to the `globalPlugins`, `locale` and `doc` directories.

## Author and license

Author: Fernando de Paula Zamboni — nando_zb@yahoo.com.br

License: GNU General Public License, version 2 or later.
