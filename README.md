# Progetto Europa

Repository della demo eseguibile e del relativo adattamento web. I documenti di progettazione sono mantenuti separatamente.

Prima verticale eseguibile, 28 ottobre 2026. Baseline: Documento programmatico v1.0 allegato, letto integralmente. Questo pacchetto contiene codice funzionante e progetto del prodotto completo; non è un sistema pronto per eventi reali.

## Avvio

Python 3.11 o superiore. Nessun servizio a pagamento o account esterno richiesto. La libreria QR qrcode 8.2 è inclusa in vendor con la relativa licenza.

```sh
cd europa
python3 server.py
```

Aprire http://localhost:3000. Su smartphone nella stessa rete usare http://IP-DEL-COMPUTER:3000; consentire solo la rete locale fidata. Non esporre il server a Internet. La demo usa profili selezionabili, senza autenticazione reale. Il database demo.sqlite3 viene creato automaticamente. Per azzerare i dati, arrestare il server ed eliminare quel file. Non utilizzare nominativi, posizioni o denaro reali.

```sh
python3 -m unittest discover -s tests -v
node --check web/app.js
```

## Prova guidata

1. Partecipante → Il raduno → inserire Alex Demo, scegliere il pranzo, confermare la natura dimostrativa.
2. Simulare pagamento riuscito. In I miei pass appare un QR realmente generato; copiare il codice. Ripetere per un accompagnatore: ogni persona ha un pass distinto.
3. Scegliere Staff → Operazioni → incollare codice → convalidare Pasto. Ripetere: deve apparire errore e il conteggio resta invariato.
4. Scegliere Organizzatore → Operazioni: controllare quote simulate e rendiconto coperti CSV.
5. Itinerario: aprire le tappe, scaricare il GPX. Il GPX contiene waypoint illustrativi, non una navigazione verificata.
6. Partecipante → SOS staff → tenere premuto tre secondi. Deve apparire ricevuto dal server. Passare a Staff e prendere in carico; chiudere con motivazione.
7. Senza rete la pagina aperta mostra le tappe già salvate e l'SOS non viene dichiarato inviato. La riapertura completa offline non è implementata.
8. NON premere Chiama il 112 durante i test: è un vero collegamento telefonico, esclusivamente manuale.

## Stato reale

Implementati: SQLite transazionale, prenotazioni con scadenza, limiti evento/pranzo, pagamento fittizio, QR SVG individuali, controllo online pass, contatori, CSV, viste responsive per cinque profili demo, SOS e casella staff persistente, presa in carico e chiusura motivata, controlli di ambito organizzazione, audit protetto da trigger, CSRF e header di sicurezza.

Simulati: identità e ruoli (selettore pubblico intenzionale), pagamento senza PSP, casella notifiche interna. Assenti: scanner fotocamera, notifiche push/email/SMS, geolocalizzazione dal dispositivo, rimborsi, ledger a partita doppia, onboarding organizzazioni, configurazione ristoranti, editing itinerari, retry SOS, check-in offline e pacchetti nativi. Non dichiarare la demo conforme GDPR o certificata per emergenze.

## Demo web ospitata

La cartella `dist/` contiene l'adattamento web senza server, con dati di prova salvati esclusivamente nel browser. Non sincronizza dispositivi né utenti: il selettore consente di impersonare i diversi ruoli dimostrativi nello stesso browser. Usa solo dati fittizi. I QR sono reali ma hanno codici pubblici di test, senza valore di accesso reale.

Flusso web: Partecipante → richiesta → Amministratore/Operazioni → approvazione o rifiuto → Partecipante/I miei pass → pagamento simulato → QR → Staff/Operazioni → convalida. L'approvazione è implementata nell'adattamento web; il server Python originale v0.1 conserva il flusso precedente. SOS e conteggi sono simulati nello stesso browser, senza notifiche o soccorsi esterni. Il pulsante in fondo pagina azzera le prove locali.

Demo web: https://progetto-europa-demo.silkybass24.chatgpt.site (accesso con l'account proprietario).
