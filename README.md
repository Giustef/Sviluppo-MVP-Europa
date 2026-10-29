# Progetto Europa — demo con controlli di accesso

Questo repository contiene due ambienti di prova distinti. **Nessuno dei due è pronto per eventi reali, emergenze o denaro reale.** I documenti di prodotto sono mantenuti separatamente.

| Garanzia | Server Python (`web/`) | Sandbox statica (`dist/`) |
| --- | --- | --- |
| Identità | Account distinti con password scrypt; nessun account predefinito | Un unico spazio di prova nel browser; ruoli impersonabili |
| Autorizzazioni | Ruoli e organizzazione derivati dall'account, verificati sul server | Controlli dimostrativi modificabili dall'utente; nessuna autorità di sicurezza |
| Persistenza | SQLite con transazioni e vincoli | localStorage, serializzato tra schede con Web Locks |
| Approvazione | Organizzatore/amministratore, prima del pagamento simulato | Stesso flusso simulato |
| Capienza | Verificata atomicamente all'approvazione | Verificata sotto lock all'approvazione |
| QR | Token casuali, convalida online e vincolo antiriuso | Token pubblici di test senza valore reale, riutilizzati dopo scadenza/rifiuto |
| SOS | Persistenza server, presa in carico e chiusura tracciate | Solo nello stesso browser; nessun invio esterno |
| Audit | Trigger contro UPDATE/DELETE SQL ordinari; il proprietario del file può modificarlo | Nessun audit protetto |
| CSRF/header | CSRF, Host/Origin, cookie HttpOnly/SameSite, CSP e no-store | CSP nel documento; nessuna sessione autenticata o garanzia sugli header dell'hosting |
| Pubblicazione | Solo loopback; avvio in modalità produzione bloccato | Pubblicabile esclusivamente come sandbox fittizia |

## Avvio del server autenticato

Python 3.11 o superiore; `qrcode` 8.2 è incluso in `vendor/`. Dalla cartella clonata del repository:

```sh
python3 server.py --create-user partecipante --role participant
python3 server.py --create-user organizzatore --role organizer
python3 server.py --create-user operatore --role staff
python3 server.py
```

Ogni comando di creazione chiede una password di almeno 12 caratteri, senza mostrarla o salvarla in chiaro. Username univoci; ruoli disponibili: `participant`, `staff`, `organizer`, `restaurant`, `admin`. L'organizzazione predefinita è `club-demo`; `--tenant club-other` crea un account per il secondo evento di prova. Non condividere gli account fra persone.

Aprire http://127.0.0.1:3000 e accedere con l'account creato. Il server **non è più accessibile da smartphone nella LAN**: ascolta solo su loopback e rifiuta Host/Origin diversi da quelli locali previsti. Non usare reverse proxy, tunnel o esposizione Internet per aggirare questa restrizione. La modalità `EUROPA_MODE=production` viene rifiutata: i flussi economici e di assistenza sono ancora simulati. Nessuna password o chiave reale va committata.

Le sessioni scadono dopo un'ora; logout e nuovo login invalidano la sessione corrente. Il limite di login è dieci tentativi ogni cinque minuti per indirizzo, inclusi quelli riusciti. Disattivare un account locale con:

```sh
python3 server.py --disable-user partecipante
```

Le sessioni di quell'account non sono più accettate alla richiesta successiva. Per riattivarlo o sostituirlo, predisporre un nuovo account; non è implementato un portale di recupero password.

Il file `demo.sqlite3` è creato con permessi 0600. **Il database v0.1 viene rifiutato senza modificarlo**: le identità simulate non possono diventare proprietari attendibili. Conservarne un backup e scegliere un nuovo percorso con `EUROPA_DB=/percorso/nuova-demo.sqlite3`, oppure archiviare il vecchio file a server spento. Non cancellare dati che si vogliono conservare.

## Prova guidata: server Python

1. Accedere come partecipante; inserire un nome fittizio e inviare la richiesta. Lo stato è `requested`: nessun pass attivo, nessun posto ancora riservato.
2. In un altro profilo browser accedere come organizzatore; Operazioni → approvare o rifiutare. L'approvazione riserva posto e pasto per dieci minuti e verifica le capienze. Un partecipante non può approvare.
3. Nel profilo partecipante riaprire I miei pass per aggiornare lo stato. Dopo l'approvazione, simulare il pagamento; il QR si attiva solo con esito riuscito. L'esito fallito o la scadenza sono terminali: inviare una nuova richiesta.
4. Con l'account staff incollare il codice in Operazioni e convalidare Pasto. Una seconda convalida deve fallire senza incrementare i conteggi. Il ristorante può convalidare solo pasti e vede solo i conteggi.
5. Con il partecipante inviare un SOS tenendo premuto tre secondi. Lo staff lo vede nella casella interna, lo prende in carico e lo chiude con motivo. Può chiudere il responsabile, oppure un organizzatore/amministratore della stessa organizzazione; il responsabile originale resta registrato separatamente da chi chiude.
6. Le tappe restano consultabili nella pagina già aperta senza rete. Il GPX è illustrativo, non una navigazione stradale verificata. Il 112 è un vero collegamento telefonico esclusivamente manuale: non premerlo durante i test.

## Prova guidata: sandbox web

`dist/` non usa il server Python. Servire la cartella tramite HTTPS o localhost con un browser aggiornato che supporti Web Locks. Il selettore **Simula ruolo** impersona partecipante, organizzatore, staff, ristorante e amministratore nello stesso spazio locale. Nessuna separazione fra persone o dispositivi è promessa.

Seguire richiesta → cambio ruolo → approvazione → partecipante/pass → pagamento simulato → staff/convalida. I QR vengono assegnati all'approvazione; richieste rifiutate o scadute non esauriscono il catalogo. Le operazioni fra schede sono serializzate; senza Web Locks la sandbox rifiuta le operazioni anziché simulare garanzie di concorrenza. Il limite tecnico è di 1000 richieste contemporaneamente in attesa.

I dati v0.1 non vengono caricati nella nuova sandbox v2. Il pulsante Azzera dati di prova elimina entrambe le versioni locali. LocalStorage è modificabile, cancellabile e non adatto a dati sensibili. I codici QR sono pubblici, privi di valore di accesso reale. SOS e conteggi non vengono sincronizzati verso altri utenti.

## SOS, pagamenti e limiti operativi

Un SOS salvato non è un SOS letto o un soccorso attivato. Nessuna notifica push/email/SMS, geolocalizzazione, escalation o chiamata automatica viene inviata. Senza rete l'interfaccia mostra NON INVIATO; su errore ambiguo mostra NON CONFERMATO. Un tentativo manuale nella stessa pagina riusa la chiave della richiesta non confermata per ridurre i duplicati. Non esistono coda persistente, retry automatico o garanzia di consegna dopo chiusura della pagina.

I pagamenti sono esclusivamente fittizi: il client può simulare esito positivo/negativo solo su una propria iscrizione approvata (organizzatore/amministratore possono gestire quelle dell'organizzazione). Non ci sono incassi reali, PSP, rimborsi, riconciliazione o ledger. Prima di una versione operativa andrà implementato il monitoraggio dei versamenti gestiti dall'organizzatore, separato dalla simulazione.

Assenti anche: scanner fotocamera, check-in offline, onboarding organizzazioni, configurazione ristoranti, editing itinerari, pacchetti nativi e processi operativi di recupero account. Non dichiarare conformità GDPR o certificazione per emergenze. Consultare `SECURITY.md` per il perimetro di sicurezza.

## Verifiche

```sh
python3 -m unittest discover -s tests -v
node tests/test_web.cjs
node tests/test_ui.cjs
node --check web/app.js
node --check dist/app.js
node --check dist/demo-api.js
```

La CI esegue test Python, regressioni JavaScript e controlli sintattici di entrambi gli ambienti. I test coprono isolamento fra utenti/organizzazioni, credenziali e sessioni HTTP, ruoli, approvazioni, scadenze/capienze, convalide duplicate, SOS e concorrenza fra due contesti web. I test degli handler UI usano un adattatore DOM minimo: non verificano layout o accessibilità in un browser reale. Non equivalgono a un penetration test o a una certificazione della distribuzione ospitata.
