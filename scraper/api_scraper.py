# Job Hub API — Multi-source Job Aggregator
# Uses free + freemium APIs with auto-categorization
# Sources: Remotive, Arbeitnow, Torre, RemoteOK (free) + JSearch, Adzuna, Jooble (optional keys)

import json, os, time, logging, re, html, hashlib
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('job-hub-api')

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_SCRIPT_DIR)
DATA_FILE = os.path.join(_SCRIPT_DIR, 'data', 'jobs.json')
DOCS_DATA_FILE = os.path.join(_ROOT_DIR, 'docs', 'jobs.json')
SYNC_LOG = os.path.join(_SCRIPT_DIR, 'data', 'sync_log.json')
HISTORY_FILE = os.path.join(_SCRIPT_DIR, 'data', 'sync_history.json')

MAX_AGE_DAYS = 30
BATCH_SIZE = 500

# ─── API Keys (from environment or defaults) ───
JSEARCH_KEY = os.environ.get('RAPIDAPI_KEY', '')
ADZUNA_ID = os.environ.get('ADZUNA_APP_ID', '')
ADZUNA_KEY = os.environ.get('ADZUNA_APP_KEY', '')
JOOBLE_KEY = os.environ.get('JOOBLE_API_KEY', '')
SMARTRECRUITERS_KEY = os.environ.get('SMARTRECRUITERS_API_KEY', '')
WORKABLE_KEY = os.environ.get('WORKABLE_API_KEY', '')
TEAMTAILOR_KEY = os.environ.get('TEAMTAILOR_API_KEY', '')
BREEZY_KEY = os.environ.get('BREEZY_API_KEY', '')


def env_list(name, fallback):
    raw = os.environ.get(name, '')
    values = [v.strip() for v in raw.split(',') if v.strip()]
    return values or fallback


# Public ATS/careers-board targets. Add/override via comma-separated env vars.
GREENHOUSE_BOARDS = env_list('GREENHOUSE_BOARDS', [
    'airbnb', 'stripe', 'datadog', 'cloudflare', 'figma', 'notion', 'gitlab'
])
LEVER_SITES = env_list('LEVER_SITES', [
    'netflix', 'spotify', 'scaleai', 'benchling', 'postman', 'anduril'
])
ASHBY_BOARDS = env_list('ASHBY_BOARDS', [
    'openai', 'anthropic', 'perplexity', 'cursor', 'ashby', 'ramp'
])
SMARTRECRUITERS_COMPANIES = env_list('SMARTRECRUITERS_COMPANIES', [
    'Visa', 'BoschGroup', 'Square', 'NielsenIQ', 'Wolt', 'Avaloq'
])
WORKABLE_ACCOUNTS = env_list('WORKABLE_ACCOUNTS', [
    'workable', 'bending-spoons', 'canonical', 'superside', 'hostinger'
])
RECRUITEE_COMPANIES = env_list('RECRUITEE_COMPANIES', [
    'recruitee', 'mollie', 'weaviate', 'typeform', 'hotjar'
])
TEAMTAILOR_COMPANIES = env_list('TEAMTAILOR_COMPANIES', [])
BREEZY_COMPANIES = env_list('BREEZY_COMPANIES', [])

SPANISH_MARKET_TERMS = [
    'spanish', 'spanish speaking', 'spanish required', 'spanish speaker',
    'bilingual spanish', 'español', 'espanol', 'idioma español', 'castellano',
    'remoto', 'teletrabajo', 'trabajo remoto', 'latam', 'latin america',
    'latinoamerica', 'latinoamérica', 'hispanic', 'americas', 'worldwide',
    'anywhere', 'global', 'remote', 'remote anywhere', 'remote-first',
    'spain', 'españa', 'madrid', 'barcelona', 'valencia', 'sevilla',
    'mexico', 'méxico', 'ciudad de mexico', 'cdmx', 'monterrey',
    'guadalajara', 'chile', 'santiago', 'colombia', 'bogota', 'bogotá',
    'medellin', 'medellín', 'argentina', 'buenos aires', 'peru', 'perú',
    'lima', 'uruguay', 'montevideo', 'ecuador', 'quito', 'guayaquil',
    'costa rica', 'panama', 'panamá', 'dominican republic', 'república dominicana',
    'puerto rico', 'guatemala', 'el salvador', 'bolivia', 'paraguay',
]

SPANISH_SEARCH_QUERIES = env_list('SPANISH_SEARCH_QUERIES', [
    'remote spanish speaking',
    'remote spanish required',
    'spanish required remote',
    'bilingual spanish english remote',
    'latam remote',
    'latin america remote',
    'remote spain',
    'trabajo remoto español',
    'teletrabajo español',
    'remoto latam',
    'remoto españa',
    'ventas remoto español',
    'marketing remoto español',
    'customer success spanish remote',
    'soporte español remoto',
    'operaciones remoto español',
    'project manager spanish remote',
    'product manager spanish remote',
    'software engineer latam remote',
    'frontend developer latam remote',
    'backend developer latam remote',
    'data analyst spanish remote',
    'finance spanish remote',
    'recruiter spanish remote',
    'legal spanish remote',
])

SPANISH_JOB_QUERIES = env_list('SPANISH_JOB_QUERIES', [
    'remoto', 'teletrabajo', 'español', 'spanish', 'bilingüe',
    'latam', 'latin america', 'españa', 'méxico', 'chile', 'colombia',
    'argentina', 'perú', 'uruguay', 'ventas', 'marketing', 'soporte',
    'customer success', 'operaciones', 'desarrollador', 'developer',
    'ingeniero', 'software engineer', 'datos', 'data analyst', 'diseño',
    'recursos humanos', 'finanzas', 'contable', 'legal', 'abogado',
    'project manager', 'product manager',
])

LATAM_SPAIN_LOCATIONS = env_list('LATAM_SPAIN_LOCATIONS', [
    'Remote', 'Latam', 'Latin America', 'Spain', 'España', 'Madrid',
    'Barcelona', 'Mexico', 'México', 'Chile', 'Santiago', 'Colombia',
    'Bogota', 'Bogotá', 'Argentina', 'Buenos Aires', 'Peru', 'Perú',
    'Lima', 'Uruguay', 'Montevideo',
])


def spanish_market_matches(*parts):
    text = ' '.join(str(part or '') for part in parts).lower()
    return [term for term in SPANISH_MARKET_TERMS if term in text]


def is_spanish_market_relevant(*parts):
    return bool(spanish_market_matches(*parts))

# ─── Auto-categorization ───
CATEGORY_KEYWORDS = {
    'tecnologia': [
        'developer', 'engineer', 'software', 'devops', 'frontend', 'backend',
        'full stack', 'fullstack', 'programador', 'desarrollador', 'IT',
        'QA', 'testing', 'architect', 'tech lead', 'sre', 'cloud',
        'aws', 'azure', 'gcp', 'linux', 'sysadmin', 'mobile', 'ios',
        'android', 'react', 'node', 'python', 'java', 'ruby', 'php',
        'data engineer', 'machine learning', 'artificial intelligence',
        'cybersecurity', 'devsecops', 'product manager', 'tech',
    ],
    'ventas': [
        'sales', 'account manager', 'commercial', 'business development',
        'comercial', 'ventas', 'KAM', 'key account', 'BDR', 'SDR',
        'closing', 'revenue', 'seller', 'salesforce', 'lead generation',
        'business rep', 'territory manager', 'account executive',
    ],
    'marketing': [
        'marketing', 'SEO', 'SEM', 'content', 'social media',
        'digital marketing', 'growth', 'brand', 'copywriter',
        'email marketing', 'performance', 'PPC', 'ads', 'publicidad',
        'community manager', 'communications', 'PR', 'brand manager',
        'inbound', 'outbound', 'demand generation', 'product marketing',
    ],
    'operaciones': [
        'operations', 'project manager', 'supply chain', 'logistics',
        'operations manager', 'COO', 'procesos', 'PMO', 'scrum',
        'agile', 'coordinator', 'procurement', 'warehouse',
        'production', 'manufacturing', 'plant manager', 'facilities',
        'quality', 'lean', 'six sigma', 'continuous improvement',
    ],
    'customer-success': [
        'customer success', 'customer service', 'support', 'CSM',
        'help desk', 'call center', 'atención', 'soporte', 'client success',
        'CX', 'customer experience', 'retention', 'churn',
        'technical support', 'service desk', 'helpdesk',
    ],
    'finanzas': [
        'finance', 'accounting', 'financial', 'contable', 'auditor',
        'FP&A', 'treasury', 'analista financiero', 'CFO',
        'bookkeeping', 'tax', 'controllership', 'risk',
        'investment', 'banking', 'insurance', 'real estate',
    ],
    'rrhh': [
        'HR', 'human resources', 'recruiter', 'talent', 'people ops',
        'RRHH', 'reclutamiento', 'headhunter', 'CHRO', 'people',
        'onboarding', 'payroll', 'compensation', 'benefits',
        'training', 'development', 'organizational', 'culture',
    ],
    'diseño': [
        'design', 'UX', 'UI', 'graphic', 'product design', 'diseñador',
        'Figma', 'creative', 'art director', 'visual', 'web design',
        'interaction', 'user research', 'prototyping', 'wireframe',
        'illustration', 'motion', 'video', 'photography',
    ],
    'datos': [
        'data science', 'data analyst', 'BI', 'analytics',
        'machine learning', 'AI', 'SQL', 'tableau', 'power BI',
        'estadístico', 'statistician', 'ETL', 'data warehouse',
        'big data', 'visualization', 'insights', 'reporting',
        'python data', 'R ', 'pandas', 'spark', 'hadoop',
    ],
    'legal': [
        'legal', 'lawyer', 'compliance', 'paralegal', 'abogado',
        'jurídico', 'contract', 'regulatory', 'corporate',
        'litigation', 'intellectual property', 'IP', 'patent',
        'notary', 'mediator', 'counsel',
    ],
    'educación': [
        'teacher', 'profesor', 'trainer', 'instructor', 'education',
        'e-learning', 'tutor', 'academic', 'curriculum', 'pedagogy',
        'professor', 'lecturer', 'research', 'university',
        'school', 'learning', 'teaching', 'instructional designer',
    ],
    'salud': [
        'healthcare', 'medical', 'nurse', 'doctor', 'pharma',
        'clinical', 'salud', 'enfermería', 'médico', 'therapist',
        'psychologist', 'pharmacist', 'biotech', 'hospital',
        'health', 'wellness', 'nutrition', 'dental', 'veterinary',
    ],
    'administración': [
        'admin', 'assistant', 'office manager', 'receptionist',
        'secretary', 'coordinator', 'administrativo', 'clerk',
        'scheduler', 'data entry', 'back office', 'front desk',
        'virtual assistant', 'executive assistant', 'personal assistant',
    ],
    'ingeniería': [
        'civil engineer', 'mechanical', 'industrial', 'electrical',
        'ingeniero', 'manufacturing', 'producción', 'maintenance',
        'automation', 'robotics', 'chemical', 'aerospace',
        'structural', 'environmental', 'petroleum', 'mining',
    ],
    'gerencia': [
        'manager', 'director', 'VP', 'head', 'chief', 'leader',
        'gerente', 'director', 'supervisor', 'presidente',
        'superintendente', 'jefe', 'líder', 'c-level',
        'general manager', 'regional manager', 'country manager',
    ],
}

CATEGORY_LABELS = {
    'tecnologia': '💻 Tecnología',
    'ventas': '💼 Ventas',
    'marketing': '📢 Marketing',
    'operaciones': '⚙️ Operaciones',
    'customer-success': '🤝 Customer Success',
    'finanzas': '💰 Finanzas',
    'rrhh': '👥 RRHH',
    'diseño': '🎨 Diseño',
    'datos': '📊 Datos',
    'legal': '⚖️ Legal',
    'educación': '📚 Educación',
    'salud': '🏥 Salud',
    'administración': '📋 Administración',
    'ingeniería': '🔧 Ingeniería',
    'gerencia': '🎯 Gerencia',
}


def auto_categorize(title, description='', tags=None):
    """Auto-categorize a job into max 2 categories (most specific match)."""
    text = f"{title} {' '.join(tags or [])} {description}".lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[cat] = score
    # Sort by score descending, take top 2 (but minimum score of 1)
    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    cats = [c for c, s in sorted_cats[:2]] if sorted_cats else ['general']
    return cats


# ─── HTTP helpers ───

def http_get(url, headers=None, timeout=15):
    hdrs = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 JobHub-API/1.0',
            'Accept': 'application/json'}
    if headers:
        hdrs.update(headers)
    req = Request(url, headers=hdrs)
    try:
        resp = urlopen(req, timeout=timeout)
        body = resp.read().decode('utf-8', errors='replace')
        return resp.status, json.loads(body) if body else {}
    except HTTPError as e:
        body = e.read().decode('utf-8', errors='replace') if e.fp else ''
        return e.code, {}
    except (URLError, Exception) as e:
        log.error(f'HTTP GET failed: {url} -> {e}')
        return 0, {}


def http_post(url, payload, headers=None, timeout=15):
    data = json.dumps(payload).encode('utf-8')
    hdrs = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 JobHub-API/1.0',
            'Content-Type': 'application/json', 'Accept': 'application/json'}
    if headers:
        hdrs.update(headers)
    req = Request(url, data=data, headers=hdrs)
    try:
        resp = urlopen(req, timeout=timeout)
        body = resp.read().decode('utf-8', errors='replace')
        return resp.status, json.loads(body) if body else {}
    except HTTPError as e:
        return e.code, {}
    except (URLError, Exception) as e:
        log.error(f'HTTP POST failed: {url} -> {e}')
        return 0, {}


def strip_html(text):
    if not text: return ''
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def make_id(source, source_id):
    return hashlib.md5(f"{source}:{source_id}".encode()).hexdigest()[:12]


def make_job(source, source_url, title, company, location, remote, job_type, salary,
             description, posted_at, apply_url=None, tags=None):
    """Create a normalized job dict."""
    cats = auto_categorize(title, description, tags)
    market_terms = spanish_market_matches(title, company, location, description, ' '.join(tags or []))
    loc_lower = (location or '').lower()
    is_remote = remote or any(w in loc_lower for w in ['remote', 'remoto', 'work from home', 'wfh', 'teletrabajo'])
    return {
        'id': make_id(source, source_url or title),
        'source': source,
        'sourceUrl': source_url,
        'applyUrl': apply_url or source_url,  # Direct apply link
        'title': title,
        'company': company or 'No especificada',
        'location': location,
        'remote': is_remote,
        'type': job_type or 'FULL_TIME',
        'salary': salary or 'No publicado',
        'description': strip_html(description or '')[:500],
        'postedAt': posted_at,
        'foundAt': datetime.now(timezone.utc).isoformat(),
        'categories': cats,
        'tags': (tags or [])[:8],
        'market': {
            'spanishLatamSpain': bool(market_terms),
            'matches': market_terms[:8],
        },
        'urlValid': True,
    }


# ═══════════════════════════════════════════════════════════════
# SOURCE: Remotive API (FREE — no key needed)
# ═══════════════════════════════════════════════════════════════

def scrape_remotive():
    jobs = []
    seen_ids = set()
    # Remotive API returns latest jobs — paginate for variety
    for page in range(1, 4):
        try:
            status, data = http_get(f'https://remotive.com/api/remote-jobs?limit=100&page={page}')
            if status != 200:
                continue
            for j in data.get('jobs', []):
                jid = j.get('id', '')
                if jid in seen_ids:
                    continue
                seen_ids.add(jid)
                title = j.get('title', '')
                desc = strip_html(j.get('description', ''))
                loc = j.get('candidate_required_location', '')
                # Broaden filter: remote + worldwide/americas/europe = relevant
                combined = f"{title} {desc} {loc}".lower()
                has_spanish = is_spanish_market_relevant(combined)
                if not has_spanish:
                    continue
                jobs.append(make_job(
                    source='remotive',
                    source_url=j.get('url', ''),
                    title=title,
                    company=j.get('company_name', ''),
                    location=loc,
                    remote=True,
                    job_type=(j.get('job_type') or 'full_time').upper(),
                    salary=j.get('salary', ''),
                    description=desc,
                    posted_at=j.get('publication_date', ''),
                    tags=j.get('tags', []),
                ))
            log.info(f'Remotive page {page}: {len(data.get("jobs", []))} jobs')
            time.sleep(3)
        except Exception as e:
            log.error(f'Remotive page {page}: {e}')
            break
    return jobs


# ═══════════════════════════════════════════════════════════════
# SOURCE: Arbeitnow API (FREE — no key needed)
# ═══════════════════════════════════════════════════════════════

def scrape_arbeitnow():
    jobs = []
    seen = set()
    for page in range(1, 6):
        try:
            status, data = http_get(f'https://www.arbeitnow.com/api/job-board-api?page={page}')
            if status != 200:
                break
            items = data.get('data', [])
            if not items:
                break
            for j in items:
                slug = j.get('slug', '')
                if slug in seen:
                    continue
                seen.add(slug)
                combined = f"{j.get('title','')} {j.get('company_name','')} {j.get('location','')} {strip_html(j.get('description',''))}".lower()
                has_spanish = is_spanish_market_relevant(combined)
                if not has_spanish:
                    continue
                jobs.append(make_job(
                    source='arbeitnow',
                    source_url=j.get('url', ''),
                    title=j.get('title', ''),
                    company=j.get('company_name', ''),
                    location=j.get('location', ''),
                    remote=j.get('remote', False),
                    job_type=(j.get('job_types', ['full_time'])[0] if j.get('job_types') else 'full_time').upper(),
                    salary='',
                    description=j.get('description', ''),
                    posted_at=str(j.get('created_at', '')),
                    tags=j.get('tags', []),
                ))
            log.info(f'Arbeitnow page {page}: {len(items)} items')
            time.sleep(2)
        except Exception as e:
            log.error(f'Arbeitnow: {e}')
            break
    return jobs


# ═══════════════════════════════════════════════════════════════
# SOURCE: Torre API (FREE — no key needed)
# ═══════════════════════════════════════════════════════════════

def scrape_torre():
    jobs = []
    queries = SPANISH_JOB_QUERIES
    for q in queries:
        try:
            status, data = http_get(f'https://api.torre.co/opportunities/_search/?keyword={q}&remote=true&size=25&offset=0')
            if status != 200:
                continue
            results = data.get('results', [])
            if not results:
                results = data if isinstance(data, list) else []
            for opp in results:
                obj = opp.get('objective', '') or ''
                if not obj:
                    continue
                orgs = opp.get('organizations', [])
                org = orgs[0].get('name', '') if orgs else ''
                oid = opp.get('id', obj[:20])
                locs = opp.get('locations', [])
                loc = ', '.join(l.get('name', '') for l in locs) if locs else 'Remote'
                skills = [s.get('name', '') for s in opp.get('skills', []) if s.get('name')]
                url = opp.get('url', f'https://torre.co/opportunities/{oid}')
                jobs.append(make_job(
                    source='torre',
                    source_url=url,
                    title=obj,
                    company=org,
                    location=loc,
                    remote=True,
                    job_type='FULL_TIME',
                    salary=opp.get('compensation', ''),
                    description=opp.get('description', ''),
                    posted_at=opp.get('created', ''),
                    tags=skills,
                ))
            log.info(f'Torre "{q}": {len(results)} results')
            time.sleep(2)
        except Exception as e:
            log.error(f'Torre "{q}": {e}')
    return jobs


# ═══════════════════════════════════════════════════════════════
# SOURCE: RemoteOK API (FREE — no key needed)
# ═══════════════════════════════════════════════════════════════

def scrape_remoteok():
    jobs = []
    try:
        status, data = http_get('https://remoteok.com/api')
        if status != 200 or not isinstance(data, list):
            log.warning(f'RemoteOK: API returned {status}')
            return jobs
        for j in data:
            if not isinstance(j, dict) or j.get('slug') is None:
                continue
            title = j.get('title', '')
            desc = strip_html(j.get('description', ''))
            loc = j.get('location', '')
            combined = f"{title} {desc} {loc} {' '.join(j.get('tags', []))}".lower()
            # RemoteOK is all-remote — filter for Spanish/LATAM/global relevance
            has_relevance = is_spanish_market_relevant(combined)
            if not has_relevance:
                continue
            jobs.append(make_job(
                source='remoteok',
                source_url=j.get('url', ''),
                title=title,
                company=j.get('company', ''),
                location=loc or 'Worldwide',
                remote=True,
                job_type='FULL_TIME',
                salary=j.get('salary', ''),
                description=desc,
                posted_at=datetime.fromtimestamp(int(j.get('epoch', 0)), tz=timezone.utc).isoformat() if str(j.get('epoch', '')).isdigit() else '',
                tags=j.get('tags', []),
            ))
        log.info(f'RemoteOK: {len(jobs)} jobs collected')
    except Exception as e:
        log.error(f'RemoteOK: {e}')
    return jobs


# ═══════════════════════════════════════════════════════════════
# SOURCE: JSearch API (Freemium — RapidAPI key needed)
# ═══════════════════════════════════════════════════════════════

def scrape_jsearch():
    if not JSEARCH_KEY:
        log.info('JSearch: skipped (no RAPIDAPI_KEY)')
        return []
    jobs = []
    queries = SPANISH_SEARCH_QUERIES
    headers = {
        'X-RapidAPI-Key': JSEARCH_KEY,
        'X-RapidAPI-Host': 'jsearch.p.rapidapi.com',
    }
    for q in queries:
        try:
            status, data = http_get(
                f'https://jsearch.p.rapidapi.com/search?query={q.replace(" ", "%20")}&page=1&num_pages=1',
                headers=headers,
                timeout=20,
            )
            if status != 200:
                log.warning(f'JSearch "{q}": HTTP {status}')
                continue
            for j in data.get('data', []):
                jobs.append(make_job(
                    source='jsearch',
                    source_url=j.get('job_google_link', ''),
                    title=j.get('job_title', ''),
                    company=j.get('employer_name', ''),
                    location=f"{j.get('job_city', '')}, {j.get('job_country', '')}".strip(', '),
                    remote=j.get('job_is_remote', False),
                    job_type=j.get('job_employment_type', 'FULL_TIME'),
                    salary=_format_salary(j),
                    description=j.get('job_description', ''),
                    posted_at=j.get('job_posted_at_datetime_utc', ''),
                    apply_url=j.get('job_apply_link', ''),  # Direct apply!
                    tags=[],
                ))
            log.info(f'JSearch "{q}": {len(data.get("data", []))} jobs')
            time.sleep(3)
        except Exception as e:
            log.error(f'JSearch "{q}": {e}')
    return jobs


def _format_salary(j):
    parts = []
    if j.get('job_min_salary'):
        parts.append(str(j.get('job_min_salary')))
    if j.get('job_max_salary'):
        parts.append(str(j.get('job_max_salary')))
    if parts:
        return f"{j.get('job_salary_currency', '')} {'-'.join(parts)}"
    return 'No publicado'


# ═══════════════════════════════════════════════════════════════
# SOURCE: Adzuna API (Free — registration needed)
# ═══════════════════════════════════════════════════════════════

def scrape_adzuna():
    if not ADZUNA_ID or not ADZUNA_KEY:
        log.info('Adzuna: skipped (no ADZUNA_APP_ID / ADZUNA_APP_KEY)')
        return []
    jobs = []
    countries = [
        ('es', 'España'),
        ('mx', 'México'),
        ('cl', 'Chile'),
        ('co', 'Colombia'),
        ('ar', 'Argentina'),
        ('pe', 'Perú'),
        ('br', 'Brasil'),
    ]
    queries = SPANISH_JOB_QUERIES
    for country, name in countries:
        for q in queries:
            try:
                status, data = http_get(
                    f'https://api.adzuna.com/v1/api/jobs/{country}/search/1',
                    timeout=20,
                )
                # Adzuna needs params in URL — construct manually
                params = f"app_id={ADZUNA_ID}&app_key={ADZUNA_KEY}&what={q}&results_per_page=20&content-type=application/json"
                url = f'https://api.adzuna.com/v1/api/jobs/{country}/search/1?{params}'
                status, data = http_get(url, timeout=20)
                if status != 200:
                    log.warning(f'Adzuna {country}/{q}: HTTP {status}')
                    continue
                for j in data.get('results', []):
                    jobs.append(make_job(
                        source='adzuna',
                        source_url=j.get('redirect_url', ''),
                        title=j.get('title', ''),
                        company=j.get('company', {}).get('display_name', ''),
                        location=j.get('location', {}).get('display_name', ''),
                        remote='remote' in q or 'remoto' in q or 'teletrabajo' in q,
                        job_type=(j.get('contract_time', 'full_time') or 'full_time').upper().replace('-', '_'),
                        salary=_adzuna_salary(j),
                        description=j.get('description', ''),
                        posted_at=j.get('created', ''),
                        apply_url=j.get('redirect_url', ''),
                        tags=[j.get('category', {}).get('label', '')],
                    ))
                log.info(f'Adzuna {country}/{q}: {len(data.get("results", []))} jobs')
                time.sleep(2)
            except Exception as e:
                log.error(f'Adzuna {country}/{q}: {e}')
    return jobs


def _adzuna_salary(j):
    parts = []
    if j.get('salary_min'):
        parts.append(str(j.get('salary_min')))
    if j.get('salary_max'):
        parts.append(str(j.get('salary_max')))
    if parts:
        return f"{'-'.join(parts)} {j.get('salary_currency', '')}"
    return 'No publicado'


# ═══════════════════════════════════════════════════════════════
# SOURCE: Jooble API (Free — registration needed)
# ═══════════════════════════════════════════════════════════════

def scrape_jooble():
    if not JOOBLE_KEY:
        log.info('Jooble: skipped (no JOOBLE_API_KEY)')
        return []
    jobs = []
    locations = LATAM_SPAIN_LOCATIONS
    queries = SPANISH_JOB_QUERIES
    for loc in locations:
        for q in queries:
            try:
                status, data = http_post(
                    f'https://jooble.org/api/{JOOBLE_KEY}',
                    {'keywords': q, 'location': loc, 'page': 1},
                    timeout=20,
                )
                if status != 200:
                    continue
                for j in data.get('jobs', []):
                    jobs.append(make_job(
                        source='jooble',
                        source_url=j.get('link', ''),
                        title=j.get('title', ''),
                        company=j.get('company', ''),
                        location=j.get('location', loc),
                        remote='remote' in loc.lower() or 'remote' in q.lower(),
                        job_type=(j.get('type', 'full_time') or 'full_time').upper(),
                        salary=j.get('salary', ''),
                        description=j.get('description', ''),
                        posted_at=j.get('updated', ''),
                        apply_url=j.get('link', ''),
                        tags=[],
                    ))
                log.info(f'Jooble {loc}/{q}: {len(data.get("jobs", []))} jobs')
                time.sleep(2)
            except Exception as e:
                log.error(f'Jooble {loc}/{q}: {e}')
    return jobs


# ═══════════════════════════════════════════════════════════════
# DEDUPLICATION & PIPELINE
# ═══════════════════════════════════════════════════════════════

def _location_from_greenhouse(job):
    offices = job.get('offices') or []
    if offices:
        locations = [o.get('location') or o.get('name') for o in offices if o.get('location') or o.get('name')]
        if locations:
            return ', '.join(dict.fromkeys(locations))
    return job.get('location', {}).get('name', '') if isinstance(job.get('location'), dict) else ''


def scrape_greenhouse():
    """Greenhouse Job Board API. Public GET endpoints, no API key required."""
    jobs = []
    for board in GREENHOUSE_BOARDS:
        try:
            status, data = http_get(f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true', timeout=20)
            if status != 200:
                log.warning(f'Greenhouse {board}: HTTP {status}')
                continue
            items = data.get('jobs', [])
            for j in items:
                departments = [d.get('name', '') for d in j.get('departments', []) if d.get('name')]
                title = j.get('title', '')
                location = _location_from_greenhouse(j) or 'Not specified'
                if not is_spanish_market_relevant(title, board, location, j.get('content', ''), ' '.join(departments)):
                    continue
                url = j.get('absolute_url') or f'https://boards.greenhouse.io/{board}/jobs/{j.get("id", "")}'
                jobs.append(make_job(
                    source='greenhouse',
                    source_url=url,
                    title=title,
                    company=board,
                    location=location,
                    remote='remote' in f'{title} {location}'.lower(),
                    job_type='FULL_TIME',
                    salary='No publicado',
                    description=j.get('content', ''),
                    posted_at=j.get('updated_at', ''),
                    apply_url=url,
                    tags=departments,
                ))
            log.info(f'Greenhouse {board}: {len(items)} jobs')
            time.sleep(1)
        except Exception as e:
            log.error(f'Greenhouse {board}: {e}')
    return jobs


def scrape_lever():
    """Lever Postings API. Public postings endpoint, no API key required for reads."""
    jobs = []
    for site in LEVER_SITES:
        try:
            status, data = http_get(f'https://api.lever.co/v0/postings/{site}?mode=json', timeout=20)
            if status != 200 or not isinstance(data, list):
                log.warning(f'Lever {site}: HTTP {status}')
                continue
            for j in data:
                cats = j.get('categories') or {}
                location = cats.get('location') or ', '.join(cats.get('allLocations') or []) or 'Not specified'
                title = j.get('text', '')
                if not is_spanish_market_relevant(title, site, location, j.get('descriptionPlain') or j.get('description', ''), cats.get('team', ''), cats.get('department', '')):
                    continue
                apply_url = j.get('hostedUrl') or j.get('applyUrl') or f'https://jobs.lever.co/{site}/{j.get("id", "")}'
                jobs.append(make_job(
                    source='lever',
                    source_url=apply_url,
                    title=title,
                    company=site,
                    location=location,
                    remote='remote' in f'{title} {location}'.lower(),
                    job_type=(cats.get('commitment') or 'FULL_TIME').upper().replace(' ', '_'),
                    salary='No publicado',
                    description=j.get('descriptionPlain') or j.get('description', ''),
                    posted_at=j.get('createdAt', ''),
                    apply_url=apply_url,
                    tags=[cats.get('team', ''), cats.get('department', '')],
                ))
            log.info(f'Lever {site}: {len(data)} jobs')
            time.sleep(1)
        except Exception as e:
            log.error(f'Lever {site}: {e}')
    return jobs


def _ashby_salary(job):
    comp = job.get('compensation') or {}
    if not isinstance(comp, dict):
        return 'No publicado'
    parts = []
    if comp.get('compensationTierSummary'):
        parts.append(comp.get('compensationTierSummary'))
    if comp.get('summaryComponents'):
        parts.extend(str(v) for v in comp.get('summaryComponents') if v)
    return ' · '.join(parts) if parts else 'No publicado'


def scrape_ashby():
    """Ashby public Job Postings API."""
    jobs = []
    for board in ASHBY_BOARDS:
        try:
            status, data = http_get(f'https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true', timeout=20)
            if status != 200:
                log.warning(f'Ashby {board}: HTTP {status}')
                continue
            items = data.get('jobs', [])
            for j in items:
                title = j.get('title', '')
                location = j.get('location') or 'Not specified'
                if not is_spanish_market_relevant(title, board, location, j.get('descriptionHtml') or j.get('descriptionPlain') or '', j.get('department', ''), j.get('team', '')):
                    continue
                url = j.get('jobUrl') or j.get('applyUrl') or f'https://jobs.ashbyhq.com/{board}/{j.get("id", "")}'
                jobs.append(make_job(
                    source='ashby',
                    source_url=url,
                    title=title,
                    company=board,
                    location=location,
                    remote='remote' in f'{title} {location}'.lower(),
                    job_type='FULL_TIME',
                    salary=_ashby_salary(j),
                    description=j.get('descriptionHtml') or j.get('descriptionPlain') or '',
                    posted_at=j.get('publishedDate') or j.get('updatedAt') or '',
                    apply_url=url,
                    tags=[j.get('department', ''), j.get('team', '')],
                ))
            log.info(f'Ashby {board}: {len(items)} jobs')
            time.sleep(1)
        except Exception as e:
            log.error(f'Ashby {board}: {e}')
    return jobs


def scrape_smartrecruiters():
    """SmartRecruiters Posting API. Requires SMARTRECRUITERS_API_KEY."""
    if not SMARTRECRUITERS_KEY:
        log.info('SmartRecruiters: skipped (requires SMARTRECRUITERS_API_KEY)')
        return []
    jobs = []
    headers = {'X-SmartToken': SMARTRECRUITERS_KEY}
    for company in SMARTRECRUITERS_COMPANIES:
        try:
            status, data = http_get(f'https://api.smartrecruiters.com/v1/companies/{company}/postings?limit=100', headers=headers, timeout=20)
            if status != 200:
                log.warning(f'SmartRecruiters {company}: HTTP {status}')
                continue
            items = data.get('content') or data.get('jobs') or []
            for j in items:
                title = j.get('name') or j.get('title') or ''
                loc = j.get('location') or {}
                location = loc.get('fullLocation') or loc.get('city') or loc.get('country') or 'Not specified'
                if not is_spanish_market_relevant(title, company, location):
                    continue
                url = f'https://jobs.smartrecruiters.com/{company}/{j.get("id")}' if j.get('id') else j.get('ref', '')
                jobs.append(make_job(
                    source='smartrecruiters',
                    source_url=url,
                    title=title,
                    company=company,
                    location=location,
                    remote='remote' in f'{title} {location}'.lower(),
                    job_type=(j.get('typeOfEmployment', {}).get('label') if isinstance(j.get('typeOfEmployment'), dict) else 'FULL_TIME'),
                    salary='No publicado',
                    description='',
                    posted_at=j.get('releasedDate', ''),
                    apply_url=url,
                    tags=[j.get('department', {}).get('label', '')] if isinstance(j.get('department'), dict) else [],
                ))
            log.info(f'SmartRecruiters {company}: {len(items)} jobs')
            time.sleep(1)
        except Exception as e:
            log.error(f'SmartRecruiters {company}: {e}')
    return jobs


def scrape_workable():
    """Workable SPI jobs endpoint. Requires WORKABLE_API_KEY."""
    if not WORKABLE_KEY:
        log.info('Workable: skipped (requires WORKABLE_API_KEY)')
        return []
    jobs = []
    headers = {'Authorization': f'Bearer {WORKABLE_KEY}'}
    for account in WORKABLE_ACCOUNTS:
        try:
            status, data = http_get(f'https://{account}.workable.com/spi/v3/jobs?state=published', headers=headers, timeout=20)
            if status != 200:
                log.warning(f'Workable {account}: HTTP {status}')
                continue
            items = data.get('jobs') or []
            for j in items:
                title = j.get('title', '')
                loc = j.get('location') or {}
                if isinstance(loc, dict):
                    location = ', '.join(filter(None, [loc.get('city'), loc.get('country'), loc.get('country_name')]))
                else:
                    location = loc or 'Not specified'
                if not is_spanish_market_relevant(title, account, location, j.get('description') or j.get('full_description') or '', j.get('department', '')):
                    continue
                url = j.get('url') or j.get('application_url') or f'https://apply.workable.com/{account}/j/{j.get("shortcode", "")}'
                jobs.append(make_job(
                    source='workable',
                    source_url=url,
                    title=title,
                    company=account,
                    location=location,
                    remote='remote' in f'{title} {location} {j.get("workplace", "")}'.lower(),
                    job_type=(j.get('employment_type') or j.get('type') or 'FULL_TIME').upper(),
                    salary=j.get('salary') or 'No publicado',
                    description=j.get('description') or j.get('full_description') or '',
                    posted_at=j.get('created_at') or j.get('published') or j.get('published_on') or '',
                    apply_url=url,
                    tags=[j.get('department', '')],
                ))
            log.info(f'Workable {account}: {len(items)} jobs')
            time.sleep(1)
        except Exception as e:
            log.error(f'Workable {account}: {e}')
    return jobs


def scrape_recruitee():
    """Recruitee Careers Site API. Public careers offers endpoint."""
    jobs = []
    for company in RECRUITEE_COMPANIES:
        try:
            status, data = http_get(f'https://{company}.recruitee.com/api/offers', timeout=20)
            if status != 200:
                log.warning(f'Recruitee {company}: HTTP {status}')
                continue
            items = data.get('offers') or []
            for j in items:
                title = j.get('title', '')
                location = j.get('location') or j.get('city') or 'Not specified'
                if not is_spanish_market_relevant(title, company, location, j.get('description') or j.get('requirements') or '', j.get('department', '')):
                    continue
                url = j.get('careers_apply_url') or j.get('careers_url') or f'https://{company}.recruitee.com/o/{j.get("slug", j.get("id", ""))}'
                jobs.append(make_job(
                    source='recruitee',
                    source_url=url,
                    title=title,
                    company=company,
                    location=location,
                    remote='remote' in f'{title} {location}'.lower(),
                    job_type=(j.get('employment_type') or 'FULL_TIME').upper(),
                    salary='No publicado',
                    description=j.get('description') or j.get('requirements') or '',
                    posted_at=j.get('published_at') or j.get('created_at') or '',
                    apply_url=url,
                    tags=[j.get('department', '')],
                ))
            log.info(f'Recruitee {company}: {len(items)} jobs')
            time.sleep(1)
        except Exception as e:
            log.error(f'Recruitee {company}: {e}')
    return jobs


def scrape_teamtailor():
    """Teamtailor official API requires TEAMTAILOR_API_KEY and TEAMTAILOR_COMPANIES."""
    if not TEAMTAILOR_KEY or not TEAMTAILOR_COMPANIES:
        log.info('Teamtailor: skipped (requires TEAMTAILOR_API_KEY and TEAMTAILOR_COMPANIES)')
        return []
    jobs = []
    headers = {'Authorization': f'Token token={TEAMTAILOR_KEY}', 'X-Api-Version': '20240404'}
    for company in TEAMTAILOR_COMPANIES:
        try:
            status, data = http_get(f'https://api.teamtailor.com/v1/jobs?filter%5Bcompany%5D={company}', headers=headers, timeout=20)
            if status != 200:
                log.warning(f'Teamtailor {company}: HTTP {status}')
                continue
            items = data.get('data') or []
            for j in items:
                attrs = j.get('attributes') or {}
                title = attrs.get('title') or ''
                url = attrs.get('careersite-job-url') or attrs.get('apply-url') or ''
                location = attrs.get('location') or 'Not specified'
                if not is_spanish_market_relevant(title, company, location, attrs.get('body') or ''):
                    continue
                jobs.append(make_job(
                    source='teamtailor',
                    source_url=url,
                    title=title,
                    company=company,
                    location=location,
                    remote='remote' in f'{title} {location}'.lower(),
                    job_type=(attrs.get('employment-type') or 'FULL_TIME').upper(),
                    salary='No publicado',
                    description=attrs.get('body') or '',
                    posted_at=attrs.get('published-at') or attrs.get('created-at') or '',
                    apply_url=url,
                    tags=[],
                ))
            log.info(f'Teamtailor {company}: {len(items)} jobs')
            time.sleep(1)
        except Exception as e:
            log.error(f'Teamtailor {company}: {e}')
    return jobs


def scrape_breezy():
    """Breezy official API requires BREEZY_API_KEY and BREEZY_COMPANIES IDs."""
    if not BREEZY_KEY or not BREEZY_COMPANIES:
        log.info('Breezy: skipped (requires BREEZY_API_KEY and BREEZY_COMPANIES)')
        return []
    jobs = []
    headers = {'Authorization': BREEZY_KEY}
    for company_id in BREEZY_COMPANIES:
        try:
            status, data = http_get(f'https://api.breezy.hr/v3/company/{company_id}/positions?state=published', headers=headers, timeout=20)
            if status != 200 or not isinstance(data, list):
                log.warning(f'Breezy {company_id}: HTTP {status}')
                continue
            for j in data:
                title = j.get('name') or ''
                location = j.get('location', {}).get('name') if isinstance(j.get('location'), dict) else j.get('location', '')
                url = j.get('friendly_url') or j.get('url') or ''
                if not is_spanish_market_relevant(title, company_id, location, j.get('description') or '', j.get('department', ''), j.get('category', '')):
                    continue
                jobs.append(make_job(
                    source='breezy',
                    source_url=url,
                    title=title,
                    company=company_id,
                    location=location or 'Not specified',
                    remote='remote' in f'{title} {location}'.lower(),
                    job_type=(j.get('type') or 'FULL_TIME').upper(),
                    salary='No publicado',
                    description=j.get('description') or '',
                    posted_at=j.get('creation_date') or j.get('updated_date') or '',
                    apply_url=url,
                    tags=[j.get('department', ''), j.get('category', '')],
                ))
            log.info(f'Breezy {company_id}: {len(data)} jobs')
            time.sleep(1)
        except Exception as e:
            log.error(f'Breezy {company_id}: {e}')
    return jobs


def deduplicate(jobs):
    source_priority = {
        'greenhouse': 100,
        'lever': 100,
        'ashby': 100,
        'smartrecruiters': 95,
        'workable': 95,
        'recruitee': 95,
        'teamtailor': 90,
        'breezy': 90,
        'jsearch': 70,
        'adzuna': 65,
        'jooble': 65,
        'remotive': 60,
        'remoteok': 60,
        'arbeitnow': 55,
        'torre': 55,
    }

    def quality(job):
        score = source_priority.get(job.get('source'), 10)
        if job.get('applyUrl') and job.get('applyUrl') != job.get('sourceUrl'):
            score += 20
        if job.get('description'):
            score += 5
        if job.get('salary') and job.get('salary') != 'No publicado':
            score += 5
        return score

    seen = {}
    for job in jobs:
        key = re.sub(r'[\s\-,\.]+', ' ', f"{job['company'].lower()}:{job['title'].lower()}").strip()
        if key not in seen or quality(job) > quality(seen[key]):
            seen[key] = job
    return list(seen.values())


def run_pipeline():
    log.info('=== Job Hub API Pipeline START ===')
    all_jobs = []

    # Free sources (no key needed)
    free_sources = [
        ('Remotive', scrape_remotive),
        ('Arbeitnow', scrape_arbeitnow),
        ('Torre', scrape_torre),
        ('RemoteOK', scrape_remoteok),
    ]

    for name, fn in free_sources:
        log.info(f'[FREE] {name}...')
        try:
            results = fn()
            all_jobs.extend(results)
            log.info(f'[FREE] {name}: {len(results)} jobs')
        except Exception as e:
            log.error(f'[FREE] {name} FAILED: {e}')

    # Key-based sources (optional)
    key_sources = [
        ('JSearch', scrape_jsearch),
        ('Adzuna', scrape_adzuna),
        ('Jooble', scrape_jooble),
    ]

    for name, fn in key_sources:
        log.info(f'[API] {name}...')
        try:
            results = fn()
            all_jobs.extend(results)
            log.info(f'[API] {name}: {len(results)} jobs')
        except Exception as e:
            log.error(f'[API] {name} FAILED: {e}')

    # ATS / careers board sources
    ats_sources = [
        ('Greenhouse', scrape_greenhouse),
        ('Lever', scrape_lever),
        ('Ashby', scrape_ashby),
        ('SmartRecruiters', scrape_smartrecruiters),
        ('Workable', scrape_workable),
        ('Recruitee', scrape_recruitee),
        ('Teamtailor', scrape_teamtailor),
        ('Breezy', scrape_breezy),
    ]

    for name, fn in ats_sources:
        log.info(f'[ATS] {name}...')
        try:
            results = fn()
            all_jobs.extend(results)
            log.info(f'[ATS] {name}: {len(results)} jobs')
        except Exception as e:
            log.error(f'[ATS] {name} FAILED: {e}')

    # Dedup
    before = len(all_jobs)
    all_jobs = deduplicate(all_jobs)
    log.info(f'Dedup: {before} → {len(all_jobs)}')

    # Sort by posted date (newest first)
    all_jobs.sort(key=lambda j: j.get('postedAt', ''), reverse=True)

    # Build output with category breakdown
    cat_counts = {}
    for cat in CATEGORY_KEYWORDS:
        cat_counts[cat] = len([j for j in all_jobs if cat in j.get('categories', [])])
    cat_counts['general'] = len([j for j in all_jobs if j.get('categories') == ['general']])

    source_counts = {}
    for j in all_jobs:
        s = j['source']
        source_counts[s] = source_counts.get(s, 0) + 1

    output = {
        'version': '1.0',
        'schema': 'api-aggregator',
        'updatedAt': datetime.now(timezone.utc).isoformat(),
        'totalJobs': len(all_jobs),
        'sources': dict(sorted(source_counts.items())),
        'categories': cat_counts,
        'jobs': all_jobs,
    }

    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(DOCS_DATA_FILE), exist_ok=True)
    with open(DOCS_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info(f'=== DONE: {len(all_jobs)} jobs from {len(source_counts)} sources ===')
    return output


if __name__ == '__main__':
    run_pipeline()
