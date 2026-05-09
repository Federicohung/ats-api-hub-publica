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

HOST = 'jobs-api14.p.rapidapi.com'
KEY = os.environ.get('JOBS_API14_RAPIDAPI_KEY')
MAX_REQUESTS = int(os.environ.get('JOBS_API14_MAX_REQUESTS') or '8')
STOP_STATUSES = {401, 403, 429}


def env_list(name, fallback):
    raw = os.environ.get(name, '')
    values = [v.strip() for v in raw.split(',') if v.strip()]
    return values or fallback


QUERIES = env_list('JOBS_API14_QUERIES', [
    'spanish remote',
    'spanish speaking remote',
    'latam remote',
    'remote spanish required',
    'customer success spanish',
    'account manager spanish',
    'data analyst spanish',
    'developer latam remote',
])

LOCATIONS = env_list('JOBS_API14_LOCATIONS', [
    'Spain',
    'Mexico',
    'Colombia',
    'Chile',
    'Argentina',
    'Peru',
    'Latin America',
    'Remote',
])


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

    aggregated = data.get('aggregated_response')
    if isinstance(aggregated, list):
        jobs = []
        for item in aggregated:
            if isinstance(item, dict) and isinstance(item.get('jobs'), list):
                jobs.extend(item.get('jobs'))
        if jobs:
            return jobs

    for key in ('data', 'jobs', 'items', 'results', 'job_results', 'list'):
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = extract_items(value)
            if nested:
                return nested
    return []


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
        normalized = text.replace('Z', '+00:00')
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return 0


def provider_url(item):
    providers = item.get('jobProviders') or item.get('job_providers') or item.get('providers') or []
    if isinstance(providers, list):
        for provider in providers:
            if isinstance(provider, dict):
                url = pick(provider, 'url', 'jobUrl', 'job_url', 'applyUrl', 'apply_url')
                if url:
                    return url
    return ''


def scrape_jobs_api14():
    if not KEY:
        print('Jobs API14: skipped (requires JOBS_API14_RAPIDAPI_KEY)')
        return []

    headers = {
        'Content-Type': 'application/json',
        'x-rapidapi-host': HOST,
        'x-rapidapi-key': KEY,
    }
    jobs = []
    seen_urls = set()
    request_count = 0

    for query in QUERIES:
        for location in LOCATIONS:
            if request_count >= MAX_REQUESTS:
                print(f'Jobs API14: stopped after {MAX_REQUESTS} requests to protect quota')
                return jobs

            params = urlencode({'query': query, 'location': location})
            url = f'https://{HOST}/v2/list?{params}'
            status, data = http_get(url, headers=headers, timeout=25)
            request_count += 1
            if status != 200:
                print(f'Jobs API14 {query}/{location}: HTTP {status}')
                if status in STOP_STATUSES:
                    print('Jobs API14: stopping to protect quota/auth after quota or auth response')
                    return jobs
                continue

            items = extract_items(data)
            print(f'Jobs API14 {query}/{location}: {len(items)} jobs')
            for item in items:
                if not isinstance(item, dict):
                    continue

                title = pick(item, 'title', 'job_title', 'position', 'name')
                company = pick(item, 'company', 'company_name', 'organization', 'employer')
                job_location = pick(item, 'location', 'job_location', 'formatted_location', 'city', 'country') or location
                description = pick(item, 'description', 'job_description', 'summary', 'snippet')
                job_url = pick(item, 'url', 'job_url', 'link', 'apply_url', 'application_url') or provider_url(item)
                posted_at = pick(item, 'posted_at', 'posted_date', 'datePosted', 'date_posted', 'created_at')
                job_type = pick(item, 'employmentType', 'employment_type', 'job_type', 'type') or 'FULL_TIME'
                salary = pick(item, 'salary', 'salary_range', 'compensation')

                if not title and not description:
                    continue
                if job_url in seen_urls and job_url:
                    continue
                seen_urls.add(job_url)

                tags = ['Jobs API14', 'RapidAPI', query, location]
                jobs.append(make_job(
                    source='jobs_api14',
                    source_url=job_url,
                    title=title or query,
                    company=company,
                    location=job_location,
                    remote='remote' in f'{title} {job_location} {description}'.lower() or 'remoto' in f'{title} {job_location} {description}'.lower(),
                    job_type=str(job_type).upper().replace(' ', '_'),
                    salary=salary,
                    description=description,
                    posted_at=posted_at or datetime.now(timezone.utc).isoformat(),
                    apply_url=job_url,
                    tags=tags,
                ))
            time.sleep(1)
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
    new_jobs = scrape_jobs_api14()
    output = write_output(existing, new_jobs)
    print(f'Jobs API14 merged: +{len(new_jobs)} raw jobs, {output["totalJobs"]} total jobs')
