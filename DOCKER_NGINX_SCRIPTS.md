# Docker, Nginx e Scripts — Contenuto e spiegazione

Questo documento riporta il contenuto dei file relativi a **Docker**, **Nginx** e **script** di deploy/entrypoint, con spiegazioni per blocco.

---

# 1. Docker

## 1.1 `Dockerfile` (root)

Immagine del backend Django (web, worker, beat).

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (per psycopg2, ecc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl postgresql-client \
 && rm -rf /var/lib/apt/lists/*

# Requirements prima per caching
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# Codice
COPY . /app

# Entrypoint eseguibile
RUN chmod +x /app/scripts/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
```

**Spiegazione:**

- **Base:** `python:3.12-slim`.
- **ENV:** niente bytecode su disco, output Python non bufferizzato, pip senza cache.
- **Dipendenze di sistema:** compilatori e `libpq-dev` per `psycopg2`, `postgresql-client` per `pg_isready`, `curl` per health check o script.
- **Python:** prima si copiano e installano i `requirements` per sfruttare la cache degli layer; poi si copia tutto il codice.
- **Entrypoint:** lo script `scripts/entrypoint.sh` viene reso eseguibile e usato come `ENTRYPOINT`; il comando effettivo (es. `web`, `worker`, `beat`) si passa da `docker-compose` (`command`).
- **Porta 8000:** usata da Gunicorn.

---

## 1.2 `nginx/Dockerfile`

Immagine Nginx che serve la **SPA Angular** (build inclusa nel multi-stage).

```dockerfile
# syntax=docker/dockerfile:1
FROM node:20-alpine AS build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build -- --configuration production

FROM nginx:alpine
COPY --from=build /app/frontend/dist/ /usr/share/nginx/html
```

**Spiegazione:**

- **Stage 1 (build):** da `node:20-alpine` si installano le dipendenze con `npm ci`, si copia il resto del frontend e si esegue `npm run build -- --configuration production`. L’output va in `dist/`.
- **Stage 2 (runtime):** immagine `nginx:alpine`; si copia solo la cartella `dist/` nello standard Nginx `/usr/share/nginx/html`. La config Nginx (template + init/ssl-watch) viene montata a runtime da `docker-compose`.

---

## 1.3 `docker-compose.yml`

Compose base: servizi sempre attivi + servizi con profili.

```yaml
services:
  web:
    build: .
    env_file: [.env]
    command: ["web"]
    volumes: [.:/app]
    expose: ["8000"]
    depends_on: [db, redis]
    environment:
      DJANGO_SETTINGS_MODULE: mixtum_core.settings
    restart: unless-stopped

  worker:
    build: .
    env_file: [.env]
    command: ["worker"]
    depends_on: [db, redis]
    volumes: [.:/app]
    restart: unless-stopped

  beat:
    build: .
    env_file: [.env]
    command: ["beat"]
    depends_on: [db, redis]
    volumes: [.:/app]
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    container_name: app-nginx-backend
    profiles: ["backend"]
    depends_on:
      - web
    ports:
      - "80:80"
      - "443:443"
    restart: unless-stopped

  nginx_frontend:
    build:
      context: .
      dockerfile: nginx/Dockerfile
    container_name: app-nginx-frontend
    profiles: ["frontend"]
    depends_on:
      - web
    ports:
      - "80:80"
      - "443:443"
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-mixtumdb}
      POSTGRES_USER: ${POSTGRES_USER:-mixtumuser}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-mixtumpassword}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  keycloak:
    image: quay.io/keycloak/keycloak:latest
    profiles: ["oidc"]
    environment:
      KEYCLOAK_ADMIN: ${KEYCLOAK_ADMIN:-admin}
      KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD:-admin}
    command: ["start-dev"]
    ports: ["8080:8080"]
    restart: unless-stopped

  metabase:
    profiles: ["metabase"]
    image: metabase/metabase:latest
    depends_on:
      - metabase_db
      - db
    environment:
      MB_DB_TYPE: postgres
      MB_DB_DBNAME: metabase
      MB_DB_PORT: 5432
      MB_DB_USER: metabase
      MB_DB_PASS: metabase_password
      MB_DB_HOST: metabase_db
      MB_SITE_URL: "https://${SERVER_NAME}/metabase"
      MB_SITE_LOCALE: "it"
      JAVA_TOOL_OPTIONS: "-Xms256m -Xmx768m"
    expose:
      - "3000"
    restart: unless-stopped

  metabase_db:
    profiles: ["metabase"]
    image: postgres:16-alpine
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 1g
    environment:
      POSTGRES_DB: metabase
      POSTGRES_USER: metabase
      POSTGRES_PASSWORD: metabase_password
    volumes:
      - metabase_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
  metabase_data:
```

**Spiegazione:**

- **web:** build dal `Dockerfile` in root, comando `web` (Gunicorn), volume codice, dipende da `db` e `redis`, espone 8000.
- **worker / beat:** stessa immagine, comandi `worker` e `beat` per Celery.
- **nginx (profile backend):** solo immagine `nginx:alpine`; la config si monta con `docker-compose.prod.yml`.
- **nginx_frontend (profile frontend):** build da `nginx/Dockerfile` (Nginx + SPA compilata), stesse porte 80/443.
- **redis:** cache/queue per Celery.
- **db:** PostgreSQL 16 con variabili da `.env` e volume persistente.
- **keycloak (profile oidc):** solo con `--profile oidc`.
- **metabase + metabase_db (profile metabase):** Metabase con DB dedicato e limite risorse; esposto su porta 3000, raggiungibile via Nginx su `/metabase/`.

---

## 1.4 `docker-compose.prod.yml`

Override per produzione: Nginx con template e Certbot.

```yaml
services:
  nginx:
    env_file: [.env]
    environment:
      NGINX_ENVSUBST_TEMPLATE_DIR: /tmp/no-templates
      NGINX_ENVSUBST_OUTPUT_DIR: /tmp/not-used
      SERVER_NAME: "${SERVER_NAME}"
    volumes:
      - ./nginx/default.http.conf.template:/etc/nginx/custom-templates/default.http.conf.template:ro
      - ./nginx/default.https.conf.template:/etc/nginx/custom-templates/default.https.conf.template:ro
      - ./nginx/init.sh:/docker-entrypoint.d/10-init.sh:ro
      - ./nginx/ssl-watch.sh:/docker-entrypoint.d/20-ssl-watch.sh:ro
      - ./letsencrypt_data:/etc/letsencrypt
      - ./certbot-www:/var/www/certbot
    ports:
      - "80:80"
      - "443:443"

  nginx_frontend:
    env_file: [.env]
    environment:
      NGINX_ENVSUBST_TEMPLATE_DIR: /tmp/no-templates
      NGINX_ENVSUBST_OUTPUT_DIR: /tmp/not-used
      SERVER_NAME: "${SERVER_NAME}"
    volumes:
      - ./nginx/default.http.frontend.conf.template:/etc/nginx/custom-templates/default.http.conf.template:ro
      - ./nginx/default.https.frontend.conf.template:/etc/nginx/custom-templates/default.https.conf.template:ro
      - ./nginx/init.sh:/docker-entrypoint.d/10-init.sh:ro
      - ./nginx/ssl-watch.sh:/docker-entrypoint.d/20-ssl-watch.sh:ro
      - ./letsencrypt_data:/etc/letsencrypt
      - ./certbot-www:/var/www/certbot
    ports:
      - "80:80"
      - "443:443"

  certbot:
    image: certbot/certbot:latest
    env_file: [.env]
    depends_on:
      - nginx
    restart: unless-stopped
    volumes:
      - ./letsencrypt_data:/etc/letsencrypt
      - ./certbot-www:/var/www/certbot
      - ./certbot/entrypoint.sh:/entrypoint.sh:ro
    entrypoint: ["/bin/sh", "/entrypoint.sh"]
```

**Spiegazione:**

- **nginx / nginx_frontend:**  
  - Disabilitato l’envsubst built-in di Nginx (directory “no-templates”).  
  - Template montati in `/etc/nginx/custom-templates/`.  
  - `init.sh` e `ssl-watch.sh` in `docker-entrypoint.d` per generare la config e fare reload quando arrivano i certificati.  
  - `letsencrypt_data` e `certbot-www` condivisi con Certbot.
- **certbot:** immagine ufficiale, entrypoint sostituito con `certbot/entrypoint.sh` (primo cert + loop rinnovi + deploy-hook che tocca il file per ssl-watch).

---

## 1.5 `.dockerignore`

```text
.git
.gitignore
__pycache__/
*.pyc
letsencrypt_data/
frontend/node_modules/
frontend/dist/
frontend/.angular/
```

**Spiegazione:** Riduce il contesto di build e evita di copiare repository Git, cache Python, dati Let’s Encrypt e artefatti del frontend (node_modules, dist, .angular).

---

# 2. Nginx

## 2.1 `nginx/default.dev.conf`

Config **sviluppo**: un solo server in ascolto sulla porta 80; backend su `web:8000`, frontend su host (Angular in dev).

```nginx
map $http_upgrade $connection_upgrade { default upgrade; '' close; }

upstream backend {
  server web:8000;
}

server {
  listen 80;
  server_name _;
  client_max_body_size 50M;

  resolver 127.0.0.11 ipv6=off valid=10s;
  resolver_timeout 5s;

  location /api/ {
    proxy_pass http://backend;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $host;
  }

  location /admin/ {
    proxy_pass http://backend;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $host;
  }

  location /static/ {
    proxy_pass http://backend;
    ...
  }

  location /media/ {
    proxy_pass http://backend;
    ...
  }

  location / {
    proxy_pass http://host.docker.internal:4200;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
  }
}
```

**Spiegazione:**

- **map:** abilita WebSocket (upgrade) per il frontend in dev.
- **upstream backend:** riferimento a `web:8000`.
- **resolver:** DNS interno Docker (127.0.0.11) per risolvere nomi dei servizi.
- **/api/, /admin/, /static/, /media/:** proxy al backend Django.
- **location /:** proxy alla SPA in esecuzione su `host.docker.internal:4200` (ng serve), con header per WebSocket.

---

## 2.2 `nginx/default.http.conf.template`

Template **HTTP** (primo avvio o solo HTTP): ACME challenge + proxy al backend.

```nginx
map $http_upgrade $connection_upgrade { default upgrade; '' close; }

server {
  listen 80;
  server_name ${SERVER_NAME};

  client_max_body_size 50M;

  location /.well-known/acme-challenge/ {
    root /var/www/certbot;
    try_files $uri =404;
  }

  location = / { return 301 http://$host/admin/; }

  location / {
    proxy_pass http://web:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
  }
}
```

**Spiegazione:**

- **server_name:** sostituito da `envsubst` con `SERVER_NAME` (es. dominio di produzione).
- **/.well-known/acme-challenge/:** root su `/var/www/certbot` per la validazione HTTP-01 di Let’s Encrypt.
- **/:** redirect a `/admin/` per la root; tutto il resto va a `web:8000`.

---

## 2.3 `nginx/default.https.conf.template`

Template **HTTPS**: redirect da HTTP a HTTPS, server 443 con certificati e (se risolto) Metabase.

```nginx
map $http_upgrade $connection_upgrade { default upgrade; '' close; }

server {
  listen 80;
  server_name ${SERVER_NAME};

  location /.well-known/acme-challenge/ {
    root /var/www/certbot;
    try_files $uri =404;
  }

  location / {
    return 301 https://$host$request_uri;
  }
}

server {
  listen 443 ssl;
  http2 on;
  server_name ${SERVER_NAME};

  client_max_body_size 50M;

  ssl_certificate     /etc/letsencrypt/live/${SERVER_NAME}/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/${SERVER_NAME}/privkey.pem;
  ssl_session_timeout 1d;
  ssl_protocols TLSv1.2 TLSv1.3;
  ssl_ciphers HIGH:!aNULL:!MD5;
  ssl_prefer_server_ciphers on;

  resolver 127.0.0.11 ipv6=off valid=10s;
  resolver_timeout 5s;

  location = / { return 301 https://$host/admin/; }

  # Metabase (HTTPS)
  location /metabase/ {
    proxy_pass http://metabase:3000/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
  }

  location = /metabase {
    return 301 /metabase/;
  }

  location / {
    proxy_pass http://web:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
  }
}
```

**Spiegazione:**

- **Server 80:** solo ACME e redirect 301 a HTTPS.
- **Server 443:** certificati in `/etc/letsencrypt/live/${SERVER_NAME}/`, TLS 1.2/1.3.
- **/metabase/:** proxy a `metabase:3000` (solo se il servizio Metabase è attivo; altrimenti `init.sh` può usare un template senza blocco Metabase).
- **/:** tutto il resto va a Django (`web:8000`).

---

## 2.4 `nginx/default.http.frontend.conf.template`

Template **HTTP per SPA**: stesso schema del backend + route per la SPA (file statici e fallback).

```nginx
map $http_upgrade $connection_upgrade { default upgrade; '' close; }

server {
  listen 80;
  server_name ${SERVER_NAME};
  client_max_body_size 50M;

  location /.well-known/acme-challenge/ {
    root /var/www/certbot;
    try_files $uri =404;
  }

  location /api/ { proxy_pass http://web:8000; ... }
  location /admin/ { proxy_pass http://web:8000; ... }
  location /static/ { proxy_pass http://web:8000; ... }
  location /media/ { proxy_pass http://web:8000; ... }

  location ~* \.(?:js|css|map|png|jpg|jpeg|gif|svg|ico|webp|woff2?|ttf|eot)$ {
    root /usr/share/nginx/html;
    try_files $uri =404;
    expires 1y;
    add_header Cache-Control "public, immutable";
  }

  location = /index.html {
    root /usr/share/nginx/html;
    try_files $uri =404;
    add_header Cache-Control "no-cache, no-store, must-revalidate";
    ...
  }

  location / {
    root /usr/share/nginx/html;
    try_files $uri $uri/ /index.html;
  }
}
```

**Spiegazione:**

- **Backend:** `/api/`, `/admin/`, `/static/`, `/media/` → `web:8000`.
- **Asset SPA:** estensioni comuni servite da `/usr/share/nginx/html` con cache lunga.
- **index.html:** no-cache per aggiornamenti app.
- **location /:** fallback SPA: `try_files` e poi `index.html` per il routing client-side.

---

## 2.5 `nginx/default.https.frontend.conf.template`

Come il template HTTP frontend ma con:

- Server 80: solo ACME + redirect a HTTPS.
- Server 443: stessi blocchi del frontend (api, admin, static, media, asset SPA, fallback) più blocco `/metabase/` se usato.

(Contenuto completo omesso per brevità; struttura identica a `default.https.conf.template` con in più le `location` per asset e fallback SPA da `/usr/share/nginx/html`.)

---

## 2.6 `nginx/init.sh`

Eseguito all’avvio del container Nginx (`docker-entrypoint.d/10-init.sh`): sceglie il template (HTTP o HTTPS) e genera `/etc/nginx/conf.d/default.conf`.

```sh
#!/bin/sh
set -eu

: "${SERVER_NAME:?SERVER_NAME missing}"

CERT_DIR="/etc/letsencrypt/live/${SERVER_NAME}"

if [ -f "${CERT_DIR}/fullchain.pem" ] && [ -f "${CERT_DIR}/privkey.pem" ]; then
  TEMPLATE="/etc/nginx/custom-templates/default.https.conf.template"
  MODE="HTTPS"
else
  TEMPLATE="/etc/nginx/custom-templates/default.http.conf.template"
  MODE="HTTP_ONLY"
fi

# Se HTTPS e Metabase non risolvibile, rimuovi blocchi Metabase dal template
TEMP_TEMPLATE="$TEMPLATE"
if [ "$MODE" = "HTTPS" ]; then
  if ! getent hosts metabase >/dev/null 2>&1; then
    TEMP_TEMPLATE="/tmp/nginx_template_no_metabase"
    awk '
      /# Metabase \(HTTPS\)/ { skip=1; next }
      skip && /^  location \// && !/metabase/ { skip=0; print; next }
      !skip { print }
    ' "$TEMPLATE" > "$TEMP_TEMPLATE"
    echo "Metabase service not available, removed metabase location blocks"
  else
    echo "Metabase service available, including metabase location blocks"
  fi
fi

envsubst '$SERVER_NAME' < "$TEMP_TEMPLATE" > /etc/nginx/conf.d/default.conf
echo "Nginx config created for ${SERVER_NAME} (${MODE})"
```

**Spiegazione:**

- **SERVER_NAME** obbligatorio.
- Se esistono i certificati in `CERT_DIR` → si usa il template HTTPS, altrimenti HTTP.
- In modalità HTTPS, se il nome `metabase` non si risolve (servizio non avviato), si crea una copia del template senza i blocchi `# Metabase (HTTPS)` così Nginx non va in errore.
- `envsubst` sostituisce `$SERVER_NAME` e scrive la config in `conf.d/default.conf`.

---

## 2.7 `nginx/ssl-watch.sh`

Eseguito dopo init (`20-ssl-watch.sh`): attende il primo certificato e fa reload quando Certbot segnala un rinnovo.

```sh
#!/bin/sh
set -eu

: "${SERVER_NAME:?SERVER_NAME missing}"

CERT_DIR="/etc/letsencrypt/live/${SERVER_NAME}"
RELOAD_FLAG="/var/www/certbot/.nginx-reload"

# 1) Primo deploy: aspetta cert poi passa a HTTPS e reload
(
  if [ ! -f "${CERT_DIR}/fullchain.pem" ] || [ ! -f "${CERT_DIR}/privkey.pem" ]; then
    echo "[ssl-watch] Waiting for first certificate for ${SERVER_NAME}..."
    while [ ! -f "${CERT_DIR}/fullchain.pem" ] || [ ! -f "${CERT_DIR}/privkey.pem" ]; do
      sleep 2
    done
    echo "[ssl-watch] Certificate found. Switching Nginx config to HTTPS..."
    sh /docker-entrypoint.d/10-init.sh
    nginx -t && nginx -s reload || true
  fi
) &

# 2) Loop: reload quando certbot tocca il flag (deploy-hook)
(
  last_mtime=0
  while :; do
    if [ -f "$RELOAD_FLAG" ]; then
      mtime="$(stat -c %Y "$RELOAD_FLAG" 2>/dev/null || stat -f %m "$RELOAD_FLAG" 2>/dev/null || echo 0)"
      if [ "$mtime" -gt "$last_mtime" ]; then
        echo "[ssl-watch] Reload requested. Reloading Nginx..."
        nginx -t && nginx -s reload || true
        last_mtime="$mtime"
      fi
    fi
    sleep 30
  done
) &

exit 0
```

**Spiegazione:**

- **Sottoprocesso 1:** se i certificati non ci sono, loop ogni 2 secondi fino a quando non compaiono; poi riesegue `10-init.sh` (che passerà a template HTTPS) e fa `nginx -s reload`.
- **Sottoprocesso 2:** ogni 30 secondi controlla la data di modifica di `/var/www/certbot/.nginx-reload`; se è cambiata (Certbot ha eseguito il deploy-hook), fa `nginx -t` e `nginx -s reload`.
- **exit 0:** lo script termina subito lasciando i due loop in background (comportamento tipico per script in `docker-entrypoint.d`).

---

# 3. Script

## 3.1 `scripts/entrypoint.sh`

Entrypoint del container backend: attende Postgres e avvia il processo in base al primo argomento (`web`, `dev`, `worker`, `beat`).

```bash
#!/usr/bin/env bash
set -euo pipefail

ROLE="${1:-web}"

wait_for_pg() {
  if [[ -n "${POSTGRES_HOST:-}" && -n "${POSTGRES_USER:-}" ]]; then
    echo "Waiting for Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT:-5432}..."
    until pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER}" >/dev/null 2>&1; do
      sleep 1
    done
    echo "Postgres is ready."
  fi
}

has_module() {
  local module="${1:-}"
  python - "$module" <<'PY'
import importlib, sys
if len(sys.argv) < 2 or not sys.argv[1]:
    print("NO")
else:
    mod = sys.argv[1]
    try:
        importlib.import_module(mod)
        print("YES")
    except Exception:
        print("NO")
PY
}

wait_for_pg

case "$ROLE" in
  web)
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput || true
    exec gunicorn mixtum_core.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers ${GUNICORN_WORKERS:-3} \
      --timeout ${GUNICORN_TIMEOUT:-120}
    ;;

  dev)
    python manage.py migrate --noinput
    if [[ "$(has_module watchdog.cli.watchmedo)" == "YES" ]]; then
      echo "Running DEV with watchdog auto-restart"
      exec python -m watchdog.cli.watchmedo auto-restart \
        --directory=/app \
        --recursive \
        --pattern="*.py;*.html;*.jinja;*.jinja2;*.tmpl;*.txt" \
        -- \
        python manage.py runserver 0.0.0.0:8000
    else
      echo "Running DEV with Django autoreloader"
      exec python manage.py runserver 0.0.0.0:8000
    fi
    ;;

  worker)
    if celery --help 2>/dev/null | grep -q -- "--autoreload"; then
      exec celery -A mixtum_core worker --loglevel=${CELERY_LOG_LEVEL:-INFO} --pool=solo --autoreload
    elif [[ "$(has_module watchdog.cli.watchmedo)" == "YES" ]]; then
      exec python -m watchdog.cli.watchmedo auto-restart \
        --directory=/app --recursive --pattern="*.py" -- \
        celery -A mixtum_core worker --loglevel=${CELERY_LOG_LEVEL:-INFO} --pool=solo
    else
      exec celery -A mixtum_core worker --loglevel=${CELERY_LOG_LEVEL:-INFO}
    fi
    ;;

  beat)
    if [[ "$(has_module watchdog.cli.watchmedo)" == "YES" ]]; then
      exec python -m watchdog.cli.watchmedo auto-restart \
        --directory=/app --recursive --pattern="*.py" -- \
        celery -A mixtum_core beat --loglevel=${CELERY_LOG_LEVEL:-INFO} --scheduler django_celery_beat.schedulers:DatabaseScheduler
    else
      exec celery -A mixtum_core beat --loglevel=${CELERY_LOG_LEVEL:-INFO} --scheduler django_celery_beat.schedulers:DatabaseScheduler
    fi
    ;;

  *)
    exec "$ROLE" "${@:2}"
    ;;
esac
```

**Spiegazione:**

- **wait_for_pg:** se sono impostati `POSTGRES_HOST` e `POSTGRES_USER`, usa `pg_isready` in loop fino a quando il DB non è pronto.
- **has_module:** verifica se un modulo Python è installato (es. `watchdog.cli.watchmedo`) per abilitare il reload automatico.
- **web:** migrate, collectstatic, avvio Gunicorn su 0.0.0.0:8000 con workers e timeout configurabili.
- **dev:** migrate; se c’è watchdog si usa `watchmedo auto-restart` sui file Python/HTML/template, altrimenti il runserver Django.
- **worker:** Celery worker con eventuale `--autoreload` o watchdog; pool `solo` quando si usa autoreload.
- **beat:** Celery beat con scheduler DB; opzionalmente wrapped da watchdog.
- **\*:** qualsiasi altro comando viene eseguito come comando (es. `python manage.py shell`).

---

## 3.2 `certbot/entrypoint.sh`

Entrypoint del container Certbot: primo certificato (se manca) e loop di rinnovo con deploy-hook per Nginx.

```sh
#!/bin/sh
set -eu

: "${SERVER_NAME:?SERVER_NAME missing}"
: "${CERTBOT_EMAIL:?CERTBOT_EMAIL missing}"

WEBROOT="/var/www/certbot"
CERT_PATH="/etc/letsencrypt/live/${SERVER_NAME}/fullchain.pem"
RSA_KEY_SIZE="${RSA_KEY_SIZE:-4096}"
STAGING="${CERTBOT_STAGING:-0}"

mkdir -p "$WEBROOT"

sleep 3

if [ ! -f "$CERT_PATH" ]; then
  echo "[certbot] Requesting first certificate for ${SERVER_NAME}..."
  staging_flag=""
  if [ "$STAGING" = "1" ]; then staging_flag="--staging"; fi

  certbot certonly --webroot -w "$WEBROOT" -d "$SERVER_NAME" \
    --email "$CERTBOT_EMAIL" --agree-tos --non-interactive \
    --rsa-key-size "$RSA_KEY_SIZE" $staging_flag

  echo "[certbot] First certificate obtained."
  touch "$WEBROOT/.nginx-reload"
else
  echo "[certbot] Certificate already present."
fi

echo "[certbot] Starting renew loop..."
while :; do
  certbot renew --webroot -w "$WEBROOT" --quiet \
    --deploy-hook "touch $WEBROOT/.nginx-reload"
  sleep 12h
done
```

**Spiegazione:**

- **Variabili obbligatorie:** `SERVER_NAME` e `CERTBOT_EMAIL`.
- **WEBROOT:** directory montata in comune con Nginx per HTTP-01.
- **sleep 3:** dà tempo a Nginx di avviarsi prima della prima richiesta.
- **Primo certificato:** se `fullchain.pem` non esiste, `certbot certonly --webroot`; opzionale `--staging` e `RSA_KEY_SIZE`. Dopo la richiesta viene toccato `.nginx-reload` per far scattare ssl-watch.
- **Loop:** `certbot renew` ogni 12 ore con `--deploy-hook "touch $WEBROOT/.nginx-reload"` così a ogni rinnovo Nginx ricarica la config.

---

## 3.3 `deploy.sh`

Script di deploy produzione: avvio stack con profilo, verifica Nginx, certificato e rinnovi, avvio Certbot.

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

COMPOSE_BASE="${ROOT_DIR}/docker-compose.yml"
COMPOSE_PROD="${ROOT_DIR}/docker-compose.prod.yml"
ENV_FILE="${ROOT_DIR}/.env"
PROFILE="${DEPLOY_PROFILE:-backend}"
NGINX_SERVICE="nginx"

log() { echo -e "✅ $*"; }
warn(){ echo -e "⚠️  $*" >&2; }
err() { echo -e "❌ $*" >&2; }

compose() {
  docker compose -f "$COMPOSE_BASE" -f "$COMPOSE_PROD" --profile "$PROFILE" "$@"
}

require_file() {
  [[ -f "$1" ]] || { err "Missing file: $1"; exit 1; }
}

load_env() {
  set -a
  source "$ENV_FILE"
  set +a
}

cd "$ROOT_DIR"

require_file "$COMPOSE_BASE"
require_file "$COMPOSE_PROD"
require_file "$ENV_FILE"
require_file "$ROOT_DIR/nginx/init.sh"
require_file "$ROOT_DIR/nginx/ssl-watch.sh"
require_file "$ROOT_DIR/certbot/entrypoint.sh"
require_file "$ROOT_DIR/scripts/entrypoint.sh"

load_env
: "${SERVER_NAME:?SERVER_NAME missing in .env}"
: "${CERTBOT_EMAIL:?CERTBOT_EMAIL missing in .env}"

if [[ "$PROFILE" == "frontend" ]]; then
  NGINX_SERVICE="nginx_frontend"
fi

log "Setting executable permissions..."
chmod +x \
  "$ROOT_DIR/nginx/init.sh" \
  "$ROOT_DIR/nginx/ssl-watch.sh" \
  "$ROOT_DIR/certbot/entrypoint.sh" \
  "$ROOT_DIR/scripts/entrypoint.sh" || true

mkdir -p "$ROOT_DIR/letsencrypt_data" "$ROOT_DIR/certbot-www"

CERT_PATH_HOST="$ROOT_DIR/letsencrypt_data/live/${SERVER_NAME}/fullchain.pem"
RENEW_CONF_HOST="$ROOT_DIR/letsencrypt_data/renewal/${SERVER_NAME}.conf"

log "Building and starting stack (PROD, profile: ${PROFILE})..."
compose up -d --build

log "Waiting for Nginx on port 80 (best-effort)..."
for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1/.well-known/acme-challenge/ping" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

# Sanity renewal config (host)
if [[ -f "$RENEW_CONF_HOST" ]]; then
  if ! grep -qE '^(cert|privkey|chain|fullchain)\s*=' "$RENEW_CONF_HOST"; then
    warn "Renewal config looks broken: $RENEW_CONF_HOST"
    cp "$RENEW_CONF_HOST" "${RENEW_CONF_HOST}.bak.$(date +%Y%m%d_%H%M%S)" || true
    mv "$RENEW_CONF_HOST" "${RENEW_CONF_HOST}.broken.$(date +%Y%m%d_%H%M%S)" || true
    warn "Moved broken renewal config aside so it can be regenerated."
  fi
fi

log "Ensuring certificate exists and renewal config is valid..."
compose run --rm --entrypoint certbot certbot \
  certonly --webroot -w /var/www/certbot \
  -d "${SERVER_NAME}" \
  --email "${CERTBOT_EMAIL}" \
  --agree-tos --non-interactive \
  --rsa-key-size 4096 \
  --keep-until-expiring

touch "$ROOT_DIR/certbot-www/.nginx-reload" || true

log "Reloading Nginx (safe)..."
compose exec -T "$NGINX_SERVICE" nginx -t
compose exec -T "$NGINX_SERVICE" nginx -s reload || true

log "Starting certbot service (renew loop)..."
compose up -d certbot

log "Quick dry-run renew test..."
set +e
compose run --rm --entrypoint certbot certbot renew --dry-run --webroot -w /var/www/certbot
DRY_RUN_RC=$?
set -e
if [[ $DRY_RUN_RC -ne 0 ]]; then
  warn "Dry-run renew failed. Check certbot logs: ..."
else
  log "Dry-run renew OK."
fi

log "Stack status:"
compose ps

log "Deployment complete! 👉 https://${SERVER_NAME}"
```

**Spiegazione:**

- **Compose:** usa sempre `docker-compose.yml` + `docker-compose.prod.yml` e il profilo `DEPLOY_PROFILE` (default `backend`); con `frontend` il servizio Nginx è `nginx_frontend`.
- **Controlli:** verifica presenza di file Compose, `.env`, init.sh, ssl-watch.sh, entrypoint certbot e scripts; carica `.env` e richiede `SERVER_NAME` e `CERTBOT_EMAIL`.
- **Permessi:** rende eseguibili gli script sh.
- **Cartelle:** crea `letsencrypt_data` e `certbot-www` se non esistono.
- **Avvio:** `compose up -d --build`.
- **Attesa Nginx:** tentativi su `/.well-known/acme-challenge/ping` (best-effort).
- **Renewal:** se il file di renewal esiste ma sembra corrotto (mancano riferimenti a cert/privkey/chain/fullchain), lo sposta in `.broken.*` per permettere a Certbot di rigenerarlo.
- **Certificato:** una run `compose run --rm certbot certonly ... --keep-until-expiring` per assicurare che il cert ci sia e la config di renewal sia valida.
- **Reload:** touch del flag e `nginx -t` + `nginx -s reload` sul servizio Nginx scelto.
- **Certbot in background:** `compose up -d certbot` per il loop di rinnovo.
- **Dry-run:** `certbot renew --dry-run` per verificare che il rinnovo funzioni; in caso di errore avvisa di controllare i log.

---

Fine del documento. Per variabili d’ambiente (`POSTGRES_*`, `SERVER_NAME`, `CERTBOT_EMAIL`, `DEPLOY_PROFILE`, ecc.) fare riferimento a `.env.example` e alla documentazione del progetto.
