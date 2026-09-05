# Changelog

## 1.3.0

- Added Export backup and Import backup to the unlocked Diary window.
- Exported exactly `diario.enc` and `diario.backup.enc` to a ZIP while keeping their contents encrypted; no plaintext entry content is exported.
- Validated ZIP structure and size before opening imported vault files in a temporary directory.
- Merged entries by immutable identifier, preserving existing entries and the imported entries' dates, titles, text and timestamps.
- Reused the current in-memory vault key for backups from the same vault and requested the source password only for independently created vaults.
- Kept the current Diary unchanged after invalid archives, wrong passwords, cancellation or imports with no new entries.
- Updated the interface, repository documentation and packaged help in all five supported languages.
- Added backup, merge and related-vault unit tests while retaining vault compatibility with version 1.1.0.

## 1.2.0

- Added real-time spell checking to the title and entry text fields through the native Windows Spell Checking API.
- Added an accessible suggestions menu for right-click, Applications, Shift+F10 and Alt+F10.
- Added Ignore for this session and a persistent local dictionary.
- Added complete user documentation in English, Brazilian Portuguese, Spanish, Italian and French.
- Added a root-level English README and localized repository README files.
- Added a reproducible standard-library build script and spell-checking unit tests.
- Kept the encrypted vault format compatible with version 1.1.0.

## 1.1.0

- Prepared the add-on metadata and localized manifests for submission to the NVDA Add-on Store.
- Added selectable Brazilian Portuguese, Spanish, Italian, French and English interfaces.
- Kept diary data and encryption compatible with previous encrypted releases.
