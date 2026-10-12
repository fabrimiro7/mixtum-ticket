# Mixtum Framework — Struttura completa cartelle e file

Elenco di tutte le cartelle e i file del progetto (esclusi `.git`, `node_modules`, `__pycache__`, `.angular`, `staticfiles`, `.env` e file generati).

---

## Albero principale (solo cartelle)

```
mixtum-framework/
├── base_modules/          # Moduli Django base
│   ├── attachment/
│   ├── branding/
│   ├── celery/
│   ├── integrations/
│   │   ├── n8n/
│   │   ├── slack/
│   │   └── twilio/
│   ├── key_manager/
│   ├── links/
│   ├── mailer/
│   ├── the_watcher/
│   ├── user_manager/
│   │   └── integrations/
│   └── workspace/
├── certbot/               # Script Let's Encrypt
├── frontend/              # App Angular
│   └── src/
│       ├── app/
│       │   ├── constants/
│       │   ├── ed-theme/
│       │   ├── guards/
│       │   ├── interceptors/
│       │   ├── models/
│       │   ├── modules/
│       │   ├── pages/
│       │   ├── services/
│       │   ├── shared/
│       │   └── util/
│       ├── assets/
│       ├── environments/
│       └── ...
├── mixtum_core/           # Progetto Django
│   └── settings/
│       └── envs/
├── nginx/                 # Config e script Nginx
├── plugins/               # Plugin Django
│   ├── academy/
│   ├── ai_integrations/
│   ├── documents/
│   ├── finance_manager_accounts/
│   ├── finance_manager_core/
│   ├── finance_manager_planning/
│   ├── meeting/
│   ├── payments_manager/
│   ├── per_seo/
│   │   ├── crawler/
│   │   └── scraper/
│   ├── plugin_example/
│   ├── project_manager/
│   ├── report/
│   ├── sprint_manager/
│   └── ticket_manager/
└── scripts/               # Entrypoint container
```

---

## File root

| File | Descrizione |
|------|-------------|
| `.dockerignore` | Esclusioni per build Docker |
| `.env.example` | Esempio variabili d'ambiente |
| `.gitignore` | Esclusioni Git |
| `Dockerfile` | Immagine Docker backend (Django) |
| `PROJECT_STRUCTURE.md` | Documentazione struttura e modelli |
| `PROJECT_FILES.md` | Questo file |
| `README.md` | Readme progetto |
| `deploy.sh` | Script deploy produzione con certificati |
| `docker-compose.yml` | Compose base (web, worker, beat, db, redis, nginx, keycloak, metabase) |
| `docker-compose.override.yml` | Override locale |
| `docker-compose.prod.yml` | Override produzione (nginx, certbot) |
| `manage.py` | Entry point Django |
| `requirements.txt` | Dipendenze Python |

---

## base_modules/

Moduli condivisi dell’applicazione Django.

- `__init__.py`
- **attachment/** — Allegati  
  `__init__.py`, `admin.py`, `apps.py`, `models.py`, `serializers.py`, `tests.py`, `urls.py`, `views.py`, `migrations/`
- **branding/** — Branding workspace  
  `__init__.py`, `admin.py`, `apps.py`, `constants.py`, `models.py`, `serializers.py`, `urls.py`, `views.py`, `migrations/`
- **celery/** — `views.py`
- **integrations/**  
  - **n8n/** — `__init__.py`, `apps.py`, `serializers.py`, `services.py`, `urls.py`, `views.py`, `migrations/`  
  - **slack/** — stessi file di n8n  
  - **twilio/** — integrazione WhatsApp: `__init__.py`, `admin.py`, `apps.py`, `models.py`, `serializers.py`, `services.py`, `tests.py`, `urls.py`, `views.py`, `webhooks.py`, `migrations/`
- **key_manager/** — Config chiave-valore  
  `admin.py`, `models.py`, `utils.py`, `migrations/`
- **links/** — Link generici  
  `__init__.py`, `admin.py`, `apps.py`, `filters.py`, `models.py`, `serializers.py`, `urls.py`, `views.py`, `migrations/`
- **mailer/** — Email e template  
  `__init__.py`, `admin.py`, `apps.py`, `models.py`, `serializers.py`, `services.py`, `tasks.py`, `urls.py`, `views.py`, `migrations/`
- **the_watcher/** — Log eccezioni  
  `__init__.py`, `admin.py`, `apps.py`, `models.py`, `tests.py`, `views.py`, `migrations/`
- **user_manager/** — Utenti e auth  
  `__init__.py`, `admin.py`, `apps.py`, `authentication.py`, `models.py`, `serializers.py`, `signals.py`, `urls.py`, `views.py`, `integrations/auth_keycloak.py`, `migrations/`
- **workspace/** — Workspace e membri  
  `admin.py`, `apps.py`, `models.py`, `serializers.py`, `tests.py`, `urls.py`, `utility.py`, `views.py`, `migrations/`

---

## certbot/

- **entrypoint.sh** — Avvio Certbot (primo certificato + loop rinnovi, deploy-hook per reload Nginx)

---

## frontend/

Applicazione Angular (config, sorgenti, asset).

- Root: `angular.json`, `package.json`, `package-lock.json`, `karma.conf.js`, `netlify.toml`, `postcss.config.js`, `server.ts`, `tailwind.config.js`, `tsconfig*.json`, `README.md`, `.gitkeep`
- **src/** — `index.html`, `main.ts`, `main.server.ts`, `polyfills.ts`, `styles.css`, `theme.less`, `custom-theme.scss`, `test.ts`, `favicon.ico`
- **src/app/** — `app-routing.module.ts`, `app.module.ts`, `app.component.*`, `app.server.module.ts`, `icons-provider.module.ts`
- **src/app/constants/** — `attachment.ts`, `branding.ts`
- **src/app/ed-theme/** — elementi (cards), parts (body, breadcrumbs, footer, header, sidenav), templates (default, full-width)
- **src/app/guards/** — `is-admin`, `is-super-admin`, `is-user`, `isAuthenticated`
- **src/app/interceptors/** — `auth.interceptor.ts`, `workspace.interceptor.ts`
- **src/app/models/** — Modelli TS (branding, category, document, finance, link, message, per-seo, phase, project, report, task, ticket, tutorial, user, workspace, ecc.)
- **src/app/modules/** — Moduli feature: academy, documents, finance_manager, meetings, payments-manager, per_seo, project-manager, sprint-manager, ticket-manager (componenti *-list, *-detail, *-add, *-edit, ecc.)
- **src/app/pages/** — academy, auth (login, registration, reset-password, insert-email), dashboard, profile (avatar, profile-details, profile-edit), settings (customizer, user-manager)
- **src/app/services/** — `api/` (servizi API per modulo), `auth/`, `theme/branding.service.ts`, `workspace/`, `utils/`
- **src/app/shared/** — notion-block-editor, rich-text-editor, tw-select, workspace-selector, `shared.module.ts`
- **src/app/util/** — `date_parse`, `jwt_validator`, `must_match_validator`, `safe-html.util`, `youtube-url.util`
- **src/assets/** — font (cabin, lexend), img, `article.json`
- **src/environments/** — `environment.ts`, `environment.prod.ts`, `django.ts`

---

## mixtum_core/

Progetto Django: settings, URL, WSGI/ASGI, Celery.

- `__init__.py`, `asgi.py`, `celery.py`, `urls.py`, `wsgi.py`
- **settings/** — `__init__.py`, `base.py`, `auth.py`, `bedrock.py`, `cashirecat.py`, `celery_conf.py`, `db.py`, `email.py`, `logging_conf.py`, `oidc.py`, `static_media.py`, `storage_s3.py`, `twilio_conf.py`
- **settings/envs/** — `local.py`, `productions.py`

---

## nginx/

Configurazione e script per Nginx in Docker.

- **Dockerfile** — Multi-stage: build Angular + immagine nginx con SPA
- **default.dev.conf** — Config sviluppo: proxy a `web:8000` (api, admin, static, media), frontend su `host.docker.internal:4200`
- **default.http.conf.template** — Template HTTP (ACME challenge + proxy backend)
- **default.https.conf.template** — Template HTTPS (certificati, Metabase, backend)
- **default.http.frontend.conf.template** — Template HTTP per SPA (api, admin, static, media + static SPA)
- **default.https.frontend.conf.template** — Template HTTPS per SPA (stesso + SSL)
- **init.sh** — Scelta template HTTP/HTTPS e generazione `default.conf` (envsubst)
- **ssl-watch.sh** — Attesa primo certificato + loop reload su flag da Certbot

---

## plugins/

Plugin Django: ogni plugin ha tipicamente `__init__.py`, `apps.py`, `models.py`, `admin.py`, `serializers.py`, `urls.py`, `views.py`, `migrations/`.

- **academy** — Tutorial, categorie, note
- **ai_integrations/cashirecat** — `cat_client.py`, `urls.py`, `views.py`
- **documents** — Documenti, template, blocchi, firme (`permissions.py`, `services.py`)
- **finance_manager_accounts** — Banche e conti
- **finance_manager_core** — Categorie e transazioni (`managers.py`, `services.py`, `signals.py`)
- **finance_manager_planning** — Budget, ricorrenze, tasse (`logic_forecasting.py`, `tasks.py`)
- **meeting** — Meeting
- **payments_manager** — Abbonamenti
- **per_seo** — SEO: siti, run, pagine, issue (`config.py`, `crawler/runner.py`, `scraper/analyzer.py`, `scraper/sitemap.py`, `tasks.py`, `permissions.py`)
- **plugin_example** — Template plugin (solo `__init__.py`, `migrations/`, `templates/`)
- **project_manager** — Progetti (`permissions.py`)
- **report** — Report
- **sprint_manager** — Fasi progetto
- **ticket_manager** — Ticket, messaggi, task (`pagination.py`, `permissions.py`, `signals.py`)

---

## scripts/

- **entrypoint.sh** — Entrypoint container: attesa Postgres, comando per ruolo (`web` = migrate + gunicorn, `dev` = runserver con eventuale watchdog, `worker` = Celery worker, `beat` = Celery beat).

---

## Riepilogo conteggio

- **Root:** file Docker/Compose, script deploy, manage, requirements, README, documentazione.
- **base_modules:** ~10 moduli (attachment, branding, integrations, key_manager, links, mailer, the_watcher, user_manager, workspace).
- **frontend:** app Angular con moduli, pagine, servizi, guard, shared, assets.
- **mixtum_core:** progetto Django e settings.
- **nginx:** 2 Dockerfile (backend usa immagine nginx standard; frontend usa `nginx/Dockerfile`), template e script init/ssl-watch.
- **plugins:** 14 plugin + sottocartelle (per_seo con crawler/scraper, ai_integrations con cashirecat).
- **certbot:** 1 script. **scripts:** 1 entrypoint.

*Per l’elenco riga-per-riga di tutti i path, è possibile generarlo con `find` come indicato in apertura.*
