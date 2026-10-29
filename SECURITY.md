# Perimetro di sicurezza

Questa versione contiene una demo locale autenticata e una sandbox statica non autenticata. Non abilita eventi reali o servizi di emergenza.

## Server locale

- Account provisionati solo da CLI, password scrypt con sale casuale per account, ruoli e organizzazioni conservati sul server. Nessun selettore pubblico di privilegi.
- Cookie opaco HttpOnly/SameSite=Strict, token CSRF per mutazioni, scadenza di un'ora, rotazione e logout; account disattivati rifiutati. Le sessioni sono in memoria e si perdono al riavvio.
- Login limitato per indirizzo; richieste limitate a 8192 byte e timeout socket di dieci secondi. Questa protezione non sostituisce una difesa DoS di produzione.
- Host consentiti locali, controllo Origin, niente CORS; ascolto solo loopback. Cookie senza Secure perché l'unico trasporto consentito è HTTP su loopback. Non usare proxy/tunnel: un futuro deployment richiede TLS e cookie Secure.
- Query parametrizzate, controllo organizzazione/evento e proprietà delle iscrizioni, transazioni per approvazioni/capienze/convalide, vincoli univoci di idempotenza e scansione.
- SOS con chiavi limitate a evento/attore. Chiusura consentita al responsabile o a organizzatore/admin; conservazione separata del responsabile e dei dati di chiusura.
- Audit append-only rispetto alle normali query SQL, non resistente al proprietario del database. Database con permessi 0600, nessuna crittografia a riposo. Il computer locale e l'operatore che crea gli account restano nella base di fiducia.
- Database v0.1 rifiutato: nessuna conversione silenziosa delle identità condivise. Usare un nuovo database e conservare il vecchio se necessario.

## Sandbox pubblica

I ruoli sono impersonabili, i token QR pubblici e localStorage modificabile. CSP ed escaping riducono l'esecuzione di contenuti iniettati dall'interfaccia, ma non creano autenticazione o integrità dei dati. Web Locks serializza le operazioni fra schede dello stesso browser/origine; non coordina dispositivi, persone o copie del sito. Nessun dato reale è autorizzato in questo ambiente. Gli header della piattaforma di hosting devono essere verificati separatamente.

## Prima di un uso operativo

L'avvio in produzione è intenzionalmente bloccato finché esistono servizi simulati. Servono una progettazione e una verifica dedicate per TLS, provisioning e recupero account, gestione dei segreti, revoca e autorizzazioni operative, monitoraggio dei versamenti esterni, notifiche e procedure di assistenza, audit resistente a manomissioni, backup/ripristino, privacy, retention, monitoraggio e test della distribuzione. Non rimuovere il blocco limitandosi a cambiare il nome dell'ambiente.

I test automatici verificano regressioni specifiche, non dimostrano assenza di vulnerabilità. Non pubblicare credenziali, informazioni personali o dettagli di incidenti reali in issue pubbliche.
