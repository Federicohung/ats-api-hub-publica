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

### 🧩 ATS / Careers boards
| Fuente | Tipo | Configuración |
|---|---|---|
| Greenhouse | Public job board API | `GREENHOUSE_BOARDS` opcional |
| Lever | Public postings API | `LEVER_SITES` opcional |
| Ashby | Public postings API | `ASHBY_BOARDS` opcional |
| SmartRecruiters | Posting API oficial | `SMARTRECRUITERS_API_KEY` + `SMARTRECRUITERS_COMPANIES` |
| Workable | SPI jobs API oficial | `WORKABLE_API_KEY` + `WORKABLE_ACCOUNTS` |
| Recruitee | Careers endpoint público | `RECRUITEE_COMPANIES` opcional |
| Teamtailor | API oficial | `TEAMTAILOR_API_KEY` + `TEAMTAILOR_COMPANIES` |
| Breezy HR | API oficial | `BREEZY_API_KEY` + `BREEZY_COMPANIES` |

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

### 2b. Deploy en Vercel

Conecta el repo `Federicohung/job-hub-api` en Vercel.

Vercel queda configurado por `vercel.json`:

- Build command: `npm run build`
- Output directory: `docs`

GitHub Actions sigue actualizando `docs/jobs.json`; cada commit nuevo dispara un redeploy automático en Vercel.

### 3. Configurar GitHub Secrets (opcional, para APIs freemium)

Settings → Secrets and variables → Actions → New repository secret:

- `RAPIDAPI_KEY` — JSearch API key
- `ADZUNA_APP_ID` — Adzuna App ID
- `ADZUNA_APP_KEY` — Adzuna App Key
- `JOOBLE_API_KEY` — Jooble API key
- `SMARTRECRUITERS_API_KEY` — opcional para SmartRecruiters
- `WORKABLE_API_KEY` — opcional para Workable
- `TEAMTAILOR_API_KEY` — opcional para Teamtailor
- `BREEZY_API_KEY` — opcional para Breezy HR

Variables opcionales del repo para elegir empresas/boards ATS:

- `GREENHOUSE_BOARDS`
- `LEVER_SITES`
- `ASHBY_BOARDS`
- `SMARTRECRUITERS_COMPANIES`
- `WORKABLE_ACCOUNTS`
- `RECRUITEE_COMPANIES`
- `TEAMTAILOR_COMPANIES`
- `BREEZY_COMPANIES`

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
