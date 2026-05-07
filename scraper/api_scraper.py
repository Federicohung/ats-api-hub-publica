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
DATA_FILE = os.path.join(_SCRIPT_DIR, 'data', 'jobs.json')
SYNC_LOG = os.path.join(_SCRIPT_DIR, 'data', 'sync_log.json')
HISTORY_FILE = os.path.join(_SCRIPT_DIR, 'data', 'sync_history.json')

MAX_AGE_DAYS = 30
BATCH_SIZE = 500

# ─── API Keys (from environment or defaults) ───
JSEARCH_KEY = os.environ.get('RAPIDAPI_KEY', '')
ADZUNA_ID = os.environ.get('ADZUNA_APP_ID', '')
ADZUNA_KEY = os.environ.get('ADZUNA_APP_KEY', '')
JOOBLE_KEY = os.environ.get('JOOBLE_API_KEY', '')

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
                has_spanish = any(w in combined for w in [
                    'spanish', 'español', 'espanol', 'bilingual', 'latam',
                    'latin america', 'hispanic', 'chile', 'colombia', 'mexico',
                    'argentina', 'peru', 'spain', 'españa', 'madrid', 'barcelona',
                    'bogota', 'lima', 'buenos aires', 'santiago', 'monterrey',
                    'medellin', 'guadalajara', 'valencia', 'sevilla',
                    'worldwide', 'americas', 'europe', 'anywhere', 'global',
                    'africa', 'asia pacific', 'us canada',
                ])
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
                has_spanish = any(w in combined for w in [
                    'spanish', 'español', 'bilingual', 'latam', 'hispanic',
                    'chile', 'colombia', 'mexico', 'argentina', 'peru',
                    'spain', 'españa', 'worldwide', 'anywhere', 'remote',
                    'americas', 'europe', 'africa', 'asia',
                ])
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
    queries = ['remote', 'spanish', 'latam', 'sales', 'operations', 'marketing', 'finance', 'engineer', 'design', 'data', 'manager']
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
            has_relevance = any(w in combined for w in [
                'spanish', 'español', 'bilingual', 'latam', 'hispanic',
                'chile', 'colombia', 'mexico', 'argentina', 'peru', 'spain',
                'worldwide', 'anywhere', 'americas', 'europe', 'global',
                'africa', 'asia', 'international', 'multinational',
            ])
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
    queries = [
        'remote spanish speaking', 'remote latam', 'remote spain',
        'spanish required', 'bilingual spanish english',
        'operations manager remote', 'sales manager remote',
        'customer success remote', 'marketing manager remote',
        'software engineer remote', 'data analyst remote',
        'project manager remote', 'HR manager remote',
        'finance manager remote', 'design remote',
    ]
    headers = {
        'X-RapidAPI-Key': JSEARCH_KEY,
        'X-RapidAPI-Host': 'jsearch.p.rapidapi.com',
    }
    for q in queries:
        try:
            status, data = http_get(
                'https://jsearch.p.rapidapi.com/search',
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
    ]
    queries = [
        'remoto', 'teletrabajo', 'gerente', 'ventas', 'operaciones',
        'marketing', 'desarrollador', 'ingeniero', 'datos', 'diseño',
        'administrativo', 'recursos humanos', 'contable', 'abogado',
    ]
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
    locations = ['Madrid', 'Barcelona', 'Mexico', 'Bogota', 'Buenos Aires', 'Santiago', 'Lima', 'Remote']
    queries = ['remote', 'gerente', 'ventas', 'marketing', 'desarrollador', 'ingeniero']
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

def deduplicate(jobs):
    seen = {}
    for job in jobs:
        key = re.sub(r'[\s\-,\.]+', ' ', f"{job['company'].lower()}:{job['title'].lower()}").strip()
        if key not in seen or job.get('applyUrl'):
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

    log.info(f'=== DONE: {len(all_jobs)} jobs from {len(source_counts)} sources ===')
    return output


if __name__ == '__main__':
    run_pipeline()
