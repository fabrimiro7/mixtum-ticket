# Mixtum Framework — Struttura del progetto e modelli

Documento che descrive la struttura delle directory e tutti i modelli Django con le relative relazioni (ForeignKey, OneToOneField, ManyToManyField).

---

## 1. Struttura del progetto

```
mixtum-framework/
├── mixtum_core/                 # Progetto Django principale
│   ├── settings/                 # Configurazioni (base, envs)
│   ├── urls.py
│   └── ...
├── base_modules/                 # Moduli base (core dell'applicazione)
│   ├── attachment/              # Allegati
│   ├── branding/                # Branding per workspace
│   ├── key_manager/             # Configurazioni chiave-valore
│   ├── links/                   # Link generici (GenericForeignKey)
│   ├── mailer/                  # Email e template email
│   ├── the_watcher/             # Log eccezioni
│   ├── user_manager/             # Utenti e auth
│   ├── workspace/               # Workspace e utenti-workspace
│   └── integrations/
│       └── twilio/              # Integrazione WhatsApp (Twilio)
├── plugins/                     # Plugin modulari
│   ├── academy/                 # Tutorial e note
│   ├── documents/               # Documenti, template, firme
│   ├── finance_manager_accounts/ # Banche e conti
│   ├── finance_manager_core/     # Categorie e transazioni
│   ├── finance_manager_planning/  # Budget, regole ricorrenza, tasse
│   ├── meeting/                 # Meeting
│   ├── payments_manager/        # Abbonamenti
│   ├── per_seo/                 # SEO: siti, run, pagine, issue
│   ├── project_manager/         # Progetti
│   ├── report/                  # Report (ticket/progetto)
│   ├── sprint_manager/          # Fasi di progetto
│   └── ticket_manager/          # Ticket, messaggi, task
├── frontend/                    # Applicazione Angular
│   └── src/
│       └── app/
├── nginx/                       # Configurazione Nginx
├── certbot/                     # SSL/Let's Encrypt
├── staticfiles/                 # File statici raccolti
└── requirements.txt
```

---

## 2. Modelli per app

Di seguito tutti i modelli Django, raggruppati per app, con **campi relazione** evidenziati (FK, OneToOne, M2M, GenericFK).

---

### 2.1 `base_modules.user_manager`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **User** | Utente custom (AbstractBaseUser + PermissionsMixin). Identificativo: `email`. | Nessuna FK (modello radice). |

---

### 2.2 `base_modules.workspace`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Workspace** | Spazio di lavoro (nome, descrizione, logo). | Nessuna FK. |
| **WorkspaceUser** | Collegamento utente ↔ workspace (ruolo, data adesione). | **user** → `User` (CASCADE), **workspace** → `Workspace` (CASCADE). `unique_together`: (user, workspace). |

---

### 2.3 `base_modules.attachment`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Attachment** | Allegato (titolo, file, descrizione). | **author** → `User` (CASCADE). |

---

### 2.4 `base_modules.links`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Link** | Link generico collegabile a qualsiasi modello (es. Project, Ticket, Task). | **content_type** → `ContentType` (CASCADE). **content_object** = GenericForeignKey(content_type, object_id). |

---

### 2.5 `base_modules.branding`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **BrandingSettings** | Colori, logo, favicon per workspace. | **workspace** → `Workspace` (OneToOne, CASCADE, null/blank). |

---

### 2.6 `base_modules.mailer`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **EmailTemplate** | Template email (soggetto, HTML, testo) con variabili Django. | Nessuna FK. |
| **Email** | Singola email (to/cc/bcc, template, contesto, stato). | **template** → `EmailTemplate` (SET_NULL, null/blank). |
| **EmailAttachment** | Allegato di un'email. | **email** → `Email` (CASCADE). |

---

### 2.7 `base_modules.key_manager`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **ConfigSetting** | Chiave-valore per configurazione dinamica. | Nessuna FK. |

---

### 2.8 `base_modules.the_watcher`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Logs** | Log eccezioni (messaggio, tipo, categoria, extra_data JSON). | Nessuna FK. |

---

### 2.9 `base_modules.integrations.twilio`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **WhatsAppConversation** | Conversazione WhatsApp (numero partecipante, numero Twilio). | **user** → `User` (SET_NULL, null/blank). |
| **WhatsAppMessage** | Singolo messaggio WhatsApp (testo, media, direzione, stato). | **conversation** → `WhatsAppConversation` (CASCADE). |
| **WhatsAppTemplate** | Template messaggi WhatsApp pre-approvati. | Nessuna FK. |

---

### 2.10 `plugins.project_manager`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Project** | Progetto (titolo, descrizione, preventivi ore, limite costo). | **client** → `User` (CASCADE). **contributors** → `User` (M2M, blank). |

---

### 2.11 `plugins.ticket_manager`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Ticket** | Ticket (titolo, descrizione, priorità, stato, tipo, SLA). | **client** → `User` (CASCADE, null/blank), **project** → `Project` (CASCADE), **assignees** → `User` (M2M, blank), **attachments** → `Attachment` (M2M, blank), **ticket_workspace** → `Workspace` (CASCADE, null/blank), **ticket_linked** → `Ticket` (self, CASCADE, null/blank). |
| **TicketUserRead** | Ultimo accesso utente a ticket (per messaggi non letti). | **ticket** → `Ticket` (CASCADE), **user** → `User` (CASCADE). `unique_together`: (ticket, user). |
| **Message** | Messaggio in un ticket. | **ticket** → `Ticket` (CASCADE), **author** → `User` (CASCADE), **attachments** → `Attachment` (M2M, blank). |
| **Task** | Attività collegata a ticket/progetto. | **ticket** → `Ticket` (CASCADE, null/blank), **project** → `Project` (CASCADE), **assignee** → `User` (SET_NULL, null/blank), **parent** → `Task` (self, CASCADE, null/blank), **attachments** → `Attachment` (M2M, blank). |

---

### 2.12 `plugins.academy`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Category** | Categoria tutorial (gerarchica). | **parent** → `Category` (self, CASCADE, null/blank). |
| **Tutorial** | Tutorial (titolo, link, durata, livello). | **author** → `User` (CASCADE, null/blank), **projects** → `Project` (M2M, blank), **category** → `Category` (M2M, blank). |
| **Note** | Nota utente su un tutorial. | **user** → `User` (CASCADE), **tutorial** → `Tutorial` (CASCADE). |

---

### 2.13 `plugins.meeting`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Meeting** | Meeting (titolo, date, link streaming, costo, AI summary). | **insert_by** → `User` (CASCADE), **client** → `User` (CASCADE), **users_meeting** → `User` (M2M, blank). |

---

### 2.14 `plugins.payments_manager`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Subscription** | Abbonamento (titolo, date, importo, stato). | **customer** → `User` (CASCADE), **project** → `Project` (M2M, blank). |

---

### 2.15 `plugins.report`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Report** | Report (titolo, descrizione). | **report_ticket** → `Ticket` (CASCADE, null/blank), **report_project** → `Project` (CASCADE, null/blank). |

---

### 2.16 `plugins.sprint_manager`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Phase** | Fase di progetto (titolo, stato, priorità, date). | **project** → `Project` (CASCADE), **owner** → `User` (SET_NULL, null/blank). |

---

### 2.17 `plugins.finance_manager_accounts`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Bank** | Istituto bancario (nome, ABI, SWIFT, paese). | Nessuna FK. |
| **Account** | Conto bancario / cassa (nome, IBAN, saldo iniziale, valuta). | **bank** → `Bank` (PROTECT, null/blank). |

---

### 2.18 `plugins.finance_manager_core`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Category** | Categoria transazioni (gerarchica, tipo income/expense). | **parent** → `Category` (self, CASCADE, null/blank). |
| **Transaction** | Transazione finanziaria (conto, categoria, importo, IVA, date, stato). | **account** → `Account` (PROTECT), **category** → `Category` (PROTECT), **recurring_rule** → `RecurrenceRule` (SET_NULL, null/blank). |

---

### 2.19 `plugins.finance_manager_planning`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Budget** | Budget per categoria/periodo (target, soglia alert). | **category** → `Category` (finance_manager_core) (CASCADE), **account** → `Account` (CASCADE, null/blank). |
| **RecurrenceRule** | Regola per transazioni ricorrenti (frequenza, date). | **template_transaction** → `Transaction` (SET_NULL, null/blank), **account** → `Account` (CASCADE), **category** → `Category` (finance_manager_core) (CASCADE). |
| **TaxConfig** | Configurazione aliquota/regole fiscali. | **applicable_categories** → `Category` (finance_manager_core) (M2M, blank). |

---

### 2.20 `plugins.per_seo`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **Site** | Sito monitorato (nome, base_url, stato). | Nessuna FK. |
| **SiteSitemap** | Sitemap associata a un sito. | **site** → `Site` (DO_NOTHING). |
| **Run** | Esecuzione crawler su un sito. | **site** → `Site` (DO_NOTHING). |
| **Page** | Pagina analizzata in un run (URL, status_code, word_count, ecc.). | **run** → `Run` (DO_NOTHING), **site** → `Site` (DO_NOTHING). |
| **PageIssue** | Issue SEO rilevata su una pagina. | **run** → `Run` (DO_NOTHING), **site** → `Site` (DO_NOTHING), **page** → `Page` (DO_NOTHING). |

---

### 2.21 `plugins.documents`

| Modello | Descrizione | FK / OneToOne / M2M |
|--------|-------------|---------------------|
| **DocumentType** | Tipo documento (es. Contratto, Preventivo). Unico per workspace (`code`). | **workspace** → `Workspace` (CASCADE), **default_template** → `DocumentTemplate` (SET_NULL, null/blank). |
| **DocumentCategory** | Categoria documenti (gerarchica, slug unico per workspace). | **workspace** → `Workspace` (CASCADE), **parent** → `DocumentCategory` (self, SET_NULL, null/blank). |
| **Block** | Blocco riutilizzabile (contenuto con placeholders). | **workspace** → `Workspace` (CASCADE). |
| **DocumentTemplate** | Template documento (insieme di blocchi). | **workspace** → `Workspace` (CASCADE). |
| **DocumentTemplateBlock** | Blocco ordinato in un template (snapshot titolo/contenuto). | **template** → `DocumentTemplate` (CASCADE), **block** → `Block` (PROTECT). |
| **DocumentStatus** | Stato documento (draft, signed, ecc.). Unico per workspace (`code`). | **workspace** → `Workspace` (CASCADE). |
| **Document** | Istanza documento (titolo, stato, tipo, template, blocchi, freeze). | **workspace** → `Workspace` (CASCADE), **status** → `DocumentStatus` (PROTECT), **type** → `DocumentType` (PROTECT), **template** → `DocumentTemplate` (SET_NULL, null/blank), **categories** → `DocumentCategory` (M2M through DocumentCategoryAssignment, blank). |
| **DocumentBlock** | Blocco ordinato in un documento (copia da template o manuale). | **document** → `Document` (CASCADE), **source_template_block** → `DocumentTemplateBlock` (SET_NULL, null/blank). |
| **DocumentCategoryAssignment** | Through: documento ↔ categoria (con flag is_primary). | **document** → `Document` (CASCADE), **category** → `DocumentCategory` (CASCADE). |
| **Party** | Soggetto che può firmare (interno o esterno; user_id è UUID, non FK). | **workspace** → `Workspace` (CASCADE). |
| **DocumentSigner** | Ruolo di firma: Party + Document (ruolo, ordine, stato). | **document** → `Document` (CASCADE), **party** → `Party` (PROTECT). |
| **DocumentSignerEvent** | Evento audit per firma (invited, opened, signed, ecc.). | **document_signer** → `DocumentSigner` (CASCADE). |

---

## 3. Riepilogo relazioni principali

- **User** è il modello centrale referenziato da: WorkspaceUser, Attachment, BrandingSettings (via Workspace), Mailer (indiretto), Twilio (WhatsAppConversation), Project (client, contributors), Ticket (client, assignees), TicketUserRead, Message, Task (assignee), Academy (Category parent, Tutorial author, Note user), Meeting (insert_by, client, users_meeting), Subscription (customer), Phase (owner).
- **Workspace** è referenziato da: WorkspaceUser, BrandingSettings, Ticket (ticket_workspace), Documents (tutti i modelli document-centric).
- **Project** è referenziato da: Ticket, Task, Phase, Tutorial (M2M), Subscription (M2M), Report.
- **Account** (finance) è referenziato da: Transaction, Budget, RecurrenceRule.
- **Category** (finance_manager_core) è referenziata da: Transaction, Budget, RecurrenceRule, TaxConfig (M2M).

---

*Documento generato dalla struttura e dai file `models.py` del repository Mixtum Framework.*
