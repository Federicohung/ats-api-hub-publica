# Job Hub API 🦞

Dashboard de empleos vía APIs confiables (gratuitas + freemium).

## Fuentes

### 🆓 Gratuitas (funcionan sin configuración)
| Fuente | Tipo | Cobertura |
|---|---|---|
| Remotive | API | Remote jobs worldwide |
| Arbeitnow | API | Global remote |
| RemoteOK | API | Remote jobs worldwide |
| Torre | API | LATAM tech |

### 🔑 Freemium (requieren API key)
| Fuente | Free tier | Registro |
|---|---|---|
| JSearch (RapidAPI) | 100 req/mes | [rapidapi.com](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) |
| Adzuna | 1000 req/mes | [developer.adzuna.com](https://developer.adzuna.com/) |
| Jooble | Generoso | [jooble.org/api](https://jooble.org/api/about) |

## Setup

### 1. Crear repo y hacer deploy

```bash
# Crear el repo en GitHub (nombre: job-hub-api)
# Subir los archivos
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/Federicohung/job-hub-api.git
git push -u origin master
```

### 2. Configurar GitHub Pages

Settings → Pages → Source: `docs/` folder

### 3. Configurar GitHub Secrets (opcional, para APIs freemium)

Settings → Secrets and variables → Actions → New repository secret:

- `RAPIDAPI_KEY` — JSearch API key
- `ADZUNA_APP_ID` — Adzuna App ID
- `ADZUNA_APP_KEY` — Adzuna App Key
- `JOOBLE_API_KEY` — Jooble API key

### 4. Activar workflow

Actions → Enable workflows → Run workflow

## Sync

El scraper corre automáticamente cada 12 horas (08:00 y 20:00 UTC) y se puede disparar manualmente desde el dashboard con el botón 🔄 Sync.

## Categorías

El sistema auto-categoriza cada puesto en una de estas áreas:

💻 Tecnología · 💼 Ventas · 📢 Marketing · ⚙️ Operaciones · 🤝 Customer Success · 💰 Finanzas · 👥 RRHH · 🎨 Diseño · 📊 Datos · ⚖️ Legal · 📚 Educación · 🏥 Salud · 📋 Administración · 🔧 Ingeniería · 🎯 Gerencia

## Estructura

```
├── index.html              # Dashboard
├── scraper/
│   ├── api_scraper.py      # Agregador de APIs
│   └── data/jobs.json      # Datos scrapeados
├── docs/                   # GitHub Pages output
│   ├── index.html
│   └── jobs.json
└── .github/workflows/
    └── scrape.yml          # CI/CD pipeline
```
