import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

from api_scraper import (
    DATA_FILE,
    DOCS_DATA_FILE,
    CATEGORY_KEYWORDS,
    deduplicate,
    http_get,
    make_job,
)

HOST = 'google-jobs-api.p.rapidapi.com'
KEY = os.environ.get('GOOGLE_JOBS_RAPIDAPI_KEY')
MAX_REQUESTS = int(os.environ.get('GOOGLE_JOBS_MAX_REQUESTS') or '6')
STOP_STATUSES = {401, 403, 429}


def env_list(name, fallback):
    raw = os.environ.get(name, '')
    values = [v.strip() for v in raw.split(',') if v.strip()]
    return values or fallback


INCLUDES = env_list('GOOGLE_JOBS_INCLUDES', [
    'trabajo remoto español',
    'spanish speaking remote',
    'remote spanish required',
    'latam remote spanish',
    'ventas remoto español',
    'customer success spanish',
])

SPANISH_HINTS = [
    ' de ', ' del ', ' la ', ' el ', ' los ', ' las ', ' para ', ' con ', ' en ',
    ' experiencia ', ' requisitos ', ' responsabilidades ', ' buscamos ', ' equipo ',
    ' trabajo ', ' remoto ', ' salario ', ' beneficios ', ' habilidades ', ' español ',
    ' espanol ', ' ventas ', ' comercial ', ' atención ', ' atencion ', ' soporte ',
]


def pick(obj, *keys):
    for key in keys:
        value = obj.get(key)
        if value not in (None, ''):
            return value
    return ''


def extract_items(data):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ('data', 'jobs', 'items', 'results', 'job_results', 'list', 'organic_results'):
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = extract_items(value)
            if nested:
                return nested
    return []


def provider_url(item):
    providers = item.get('jobProviders') or item.get('job_providers') or item.get('providers') or item.get('related_links') or []
    if isinstance(providers, list):
        for provider in providers:
            if isinstance(provider, dict):
                url = pick(provider, 'url', 'link', 'jobUrl', 'job_url', 'applyUrl', 'apply_url')
                if url:
                    return url
    return ''


def spanish_content_score(*parts):
    text = ' ' + ' '.join(str(part or '').lower() for part in parts) + ' '
    score = sum(1 for hint in SPANISH_HINTS if hint in text)
    if any(ch in text for ch in 'áéíóúñü'):
        score += 2
    return score


def posted_at_sort_value(value):
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        timestamp = float(value)
        return timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
    text = str(value).strip()
    if not text:
        return 0
    if text.isdigit():
        timestamp = float(text)
        return timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp()
    except ValueError:
        return 0


def scrape_google_jobs():
    if not KEY:
        print('Google Jobs RapidAPI: skipped (requires GOOGLE_JOBS_RAPIDAPI_KEY)')
        return []

    headers = {
        'Content-Type': 'application/json',
        'x-rapidapi-host': HOST,
        'x-rapidapi-key': KEY,
    }
    jobs = []
    seen_urls = set()
    request_count = 0

    for include in INCLUDES:
        if request_count >= MAX_REQUESTS:
            print(f'Google Jobs RapidAPI: stopped after {MAX_REQUESTS} requests to protect quota')
            return jobs

        url = f'https://{HOST}/google-jobs/relocation?{urlencode({"include": include})}'
        status, data = http_get(url, headers=headers, timeout=30)
        request_count += 1
        if status != 200:
            print(f'Google Jobs RapidAPI {include}: HTTP {status}')
            if status in STOP_STATUSES:
                print('Google Jobs RapidAPI: stopping to protect quota/auth after quota or auth response')
                return jobs
            continue

        items = extract_items(data)
        print(f'Google Jobs RapidAPI {include}: {len(items)} jobs')
        for item in items:
            if not isinstance(item, dict):
                continue

            title = pick(item, 'title', 'job_title', 'position', 'name')
            company = pick(item, 'company', 'company_name', 'organization', 'employer')
            location = pick(item, 'location', 'job_location', 'formatted_location', 'city', 'country') or 'Remote'
            description = pick(item, 'description', 'job_description', 'summary', 'snippet')
            job_url = pick(item, 'url', 'job_url', 'link', 'apply_url', 'application_url') or provider_url(item)
            posted_at = pick(item, 'posted_at', 'posted_date', 'date_posted', 'published', 'created_at')
            job_type = pick(item, 'employment_type', 'job_type', 'type') or 'FULL_TIME'
            salary = pick(item, 'salary', 'salary_range', 'compensation')

            if not title and not description:
                continue
            if job_url in seen_urls and job_url:
                continue
            seen_urls.add(job_url)

            score = spanish_content_score(title, location, description, include)
            tags = ['Google Jobs', 'RapidAPI', include]
            if score >= 3:
                tags.append('Contenido en espanol')

            jobs.append(make_job(
                source='google_jobs_rapidapi',
                source_url=job_url,
                title=title or include,
                company=company,
                location=location,
                remote='remote' in f'{title} {location} {description}'.lower() or 'remoto' in f'{title} {location} {description}'.lower(),
                job_type=str(job_type).upper().replace(' ', '_'),
                salary=salary,
                description=description,
                posted_at=posted_at or datetime.now(timezone.utc).isoformat(),
                apply_url=job_url,
                tags=tags,
            ))
        time.sleep(2)
    return jobs


def load_existing():
    if not os.path.exists(DATA_FILE):
        return {'jobs': [], 'sources': {}, 'categories': {}, 'totalJobs': 0}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_output(existing, new_jobs):
    all_jobs = deduplicate((existing.get('jobs') or []) + new_jobs)
    all_jobs.sort(key=lambda j: posted_at_sort_value(j.get('postedAt')), reverse=True)

    cat_counts = {}
    for cat in CATEGORY_KEYWORDS:
        cat_counts[cat] = len([j for j in all_jobs if cat in j.get('categories', [])])
    cat_counts['general'] = len([j for j in all_jobs if j.get('categories') == ['general']])

    source_counts = {}
    for job in all_jobs:
        source = job.get('source', 'unknown')
        source_counts[source] = source_counts.get(source, 0) + 1

    output = {
        **existing,
        'updatedAt': datetime.now(timezone.utc).isoformat(),
        'totalJobs': len(all_jobs),
        'sources': dict(sorted(source_counts.items())),
        'categories': cat_counts,
        'jobs': all_jobs,
    }

    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(DOCS_DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    with open(DOCS_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return output


if __name__ == '__main__':
    existing = load_existing()
    new_jobs = scrape_google_jobs()
    output = write_output(existing, new_jobs)
    print(f'Google Jobs RapidAPI merged: +{len(new_jobs)} raw jobs, {output["totalJobs"]} total jobs')
