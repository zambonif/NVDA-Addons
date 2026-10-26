# Diario per NVDA

[English](README.md) · [Português do Brasil](README.pt-BR.md) · [Español](README.es.md) · [Italiano](README.it.md) · [Français](README.fr.md)

Versione 1.4.2

## Novità della versione 1.4.2

Se la password attuale viene rifiutata durante la modifica della password o del recupero, il messaggio ora identifica la password attuale senza menzionare una frase di recupero errata. Il messaggio è tradotto in tutte le lingue del componente aggiuntivo.

I test di regressione coprono password fino a 4.096 caratteri, con punteggiatura e Unicode. L’utente che ha segnalato il problema ha confermato che il componente aggiornato funziona con la sua password di 128 caratteri e che il messaggio fuorviante non appare più. La frase di recupero rimane facoltativa.


Diario per NVDA è un diario personale accessibile e offline, integrato con lo screen reader NVDA. La sua combinazione distintiva riunisce voci con data scelta, registrazione automatica della creazione, una cassaforte crittografata protetta da password, recupero facoltativo e controllo ortografico accessibile in tempo reale.

## Funzioni principali

- Creare, elencare, leggere, modificare ed eliminare le voci.
- Scegliere la data di ogni voce conservando data e ora originali di creazione.
- Proteggere titoli, date e testo in una cassaforte con crittografia autenticata AES-256-GCM.
- Cambiare la password e impostare facoltativamente una frase di recupero.
- Sentire un avviso dopo una parola potenzialmente errata senza perdere lo spazio, la punteggiatura o l'interruzione di riga digitata.
- Aprire i suggerimenti con clic destro, Applicazioni, Shift+F10 o Alt+F10.
- Sostituire la parola, ignorarla per la sessione NVDA corrente o aggiungerla al dizionario locale del Diario.
- Esportare i due file crittografati della cassaforte in un ZIP e importare soltanto le voci non ancora presenti nel Diario aperto.
- Usare interfaccia e documentazione in portoghese brasiliano, inglese, spagnolo, italiano o francese.
- Conservare tutti i dati sul computer; il componente aggiuntivo non invia le voci a Internet.

## Requisiti

- NVDA 2025.1 o successivo.
- Windows 8 o successivo per l'API nativa di controllo ortografico. Le versioni correnti di NVDA richiedono una versione di Windows più recente e supportata.
- Un dizionario ortografico di Windows per la lingua selezionata nel Diario. Se non è disponibile, il Diario continua a funzionare normalmente e viene disattivato soltanto il controllo ortografico per quella lingua.

## Installazione e apertura

Installa `diario-1.4.2.nvda-addon` aprendo direttamente il pacchetto e conferma. Riavvia NVDA quando richiesto.

Apri il Diario da menu NVDA > Strumenti > Diario oppure premi NVDA+Alt+D. Il gesto può essere modificato in Gesti e tasti d'immissione, nella categoria Diario.

## Controllo ortografico

I campi titolo e testo vengono controllati durante la digitazione. Dopo una parola seguita da spazio, punteggiatura, Tab o Invio, viene riprodotto un avviso se Windows la considera errata. Il separatore viene sempre inserito, quindi puoi ignorare l'avviso e continuare a scrivere.

Posiziona il cursore sulla parola o subito dopo e premi Applicazioni, Shift+F10 o Alt+F10. Funziona anche il clic destro sulla parola. Il menu accessibile mostra fino a otto suggerimenti di Windows e poi:

- **Ignora per questa sessione:** interrompe gli avvisi per la parola fino al riavvio di NVDA.
- **Aggiungi al dizionario locale:** salva la parola in `dicionario.txt`, nella cartella dati del Diario, ed evita avvisi futuri.

Il dizionario locale è un file di testo UTF-8 contenente solo le parole aggiunte dall'utente. Non è crittografato perché non contiene voci del diario. Lo stesso file è condiviso dalle cinque lingue dell'interfaccia.

## Esportazione e importazione del backup crittografato

I pulsanti **Esporta backup** e **Importa backup** sono disponibili solo dopo aver sbloccato il Diario.

**Esporta backup** apre una finestra per scegliere dove salvare e crea un ZIP contenente esattamente `diario.enc` e `diario.backup.enc`. Entrambi i file restano crittografati; nessun titolo, data o testo delle voci viene scritto in chiaro.

**Importa backup** apre una finestra per scegliere il file, convalida le due copie crittografate in una posizione temporanea e aggiunge soltanto le voci i cui identificatori non sono già presenti nel Diario corrente. Le voci esistenti non vengono mai sostituite, anche se una voce importata con lo stesso identificatore ha contenuto diverso. Date, titoli, testi e orari di creazione delle nuove voci vengono conservati.

Un backup esportato dalla stessa cassaforte viene aperto con la chiave già mantenuta dal Diario sbloccato e non richiede un'altra password. Un backup proveniente da una cassaforte creata separatamente possiede un'altra chiave casuale, anche se il testo della password è uguale; soltanto in questo caso il componente aggiuntivo richiede la password di quel backup. Ciò non modifica la password del Diario corrente. Dopo l'unione, le nuove voci sono protette dalla cassaforte corrente.

Se il ZIP non è valido, la password è errata, l'operazione viene annullata o non ci sono nuove voci, il Diario corrente rimane invariato.

## Dati, privacy e recupero

I dati si trovano sotto la cartella di configurazione di NVDA, nella sottocartella `diario`. La cassaforte principale è `diario.enc`; il backup crittografato è `diario.backup.enc`.

Tutto il contenuto, compresi titoli e date, è protetto con crittografia autenticata AES-256-GCM tramite Windows CNG. La chiave della cassaforte è protetta dalla password con PBKDF2-HMAC-SHA256 e 600.000 iterazioni. Se configurata, la frase di recupero protegge separatamente la stessa chiave casuale.

La frase di recupero non rivela la vecchia password; permette soltanto di crearne una nuova. Se entrambe vengono dimenticate, il componente aggiuntivo non può recuperare le voci. Usa segreti lunghi e difficili da indovinare e conserva copie indipendenti dei file crittografati.

La versione 1.3.0 mantiene il formato della cassaforte crittografata compatibile con la versione 1.1.0.

## Lingua dell'interfaccia

Apri menu NVDA > Preferenze > Impostazioni > Diario per scegliere Português (Brasil), Español, Italiano, Français o English senza cambiare la lingua generale di NVDA. Le nuove finestre applicano subito la scelta. Riavvia NVDA per aggiornare anche la voce Strumenti, la categoria e la descrizione del gesto.

## Build e test

Il repository usa solo la libreria standard di Python:

```text
python build.py
python -m unittest discover -s tests -v
```

Il build legge la versione da `manifest.ini` e crea `dist/diario-<versione>.nvda-addon`, escludendo test, cache e file di sviluppo dal pacchetto installabile. Prima della pubblicazione nello store, l'integrazione nativa deve ricevere una prova finale su Windows con NVDA.

Usa `python build.py --source` per creare anche lo ZIP del codice sorgente e i checksum.

## Licenza e autore

Copyright © Fernando de Paula Zamboni.

Licenza GNU General Public License, versione 2 o successiva. Vedi [LICENSE.txt](LICENSE.txt).
