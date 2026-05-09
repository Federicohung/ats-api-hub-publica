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

STOP_STATUSES = {401, 403, 429}


def env_list(name, fallback):
    raw = os.environ.get(name, '')
    values = [v.strip() for v in raw.split(',') if v.strip()]
    return values or fallback


TITLES = env_list('LINKEDIN_SEARCH_TITLES', [
    'Spanish',
    'Spanish Speaking',
    'Latam Remote',
    'Remote Spanish',
    'Account Manager Spanish',
    'Customer Success Spanish',
    'Data Spanish',
])

LOCATIONS = env_list('LINKEDIN_SEARCH_LOCATIONS', [
    'Latin America OR Spain OR Mexico OR Colombia OR Chile OR Argentina',
    'Remote OR LATAM OR Spain',
])


def linkedin_providers():
    providers = []
    key = os.environ.get('LINKEDIN_RAPIDAPI_KEY')
    host = (os.environ.get('LINKEDIN_RAPIDAPI_HOST') or 'linkedin-job-search-api.p.rapidapi.com').strip()
    path = (os.environ.get('LINKEDIN_RAPIDAPI_PATH') or 'active-jb-1h').strip('/')
    if key and host and path:
        providers.append({
            'source': 'linkedin_rapidapi',
            'host': host,
            'path': path,
            'key': key,
            'max_requests': int(os.environ.get('LINKEDIN_RAPIDAPI_MAX_REQUESTS') or '4'),
        })

    key2 = os.environ.get('LINKEDIN_API2_RAPIDAPI_KEY')
    host2 = (os.environ.get('LINKEDIN_API2_RAPIDAPI_HOST') or 'linkedin-jobs-api2.p.rapidapi.com').strip()
    path2 = (os.environ.get('LINKEDIN_API2_RAPIDAPI_PATH') or 'active-jb-1h').strip('/')
    if key2 and host2 and path2:
        providers.append({
            'source': 'linkedin_api2',
            'host': host2,
            'path': path2,
            'key': key2,
            'max_requests': int(os.environ.get('LINKEDIN_API2_MAX_REQUESTS') or '4'),
        })

    return providers


def pick(obj, *keys):
    for key in keys:
        value = obj.get(key)
        if value not in (None, ''):
            return value
    return ''


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


def extract_items(data):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ('data', 'jobs', 'items', 'results', 'job_results'):
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = extract_items(value)
            if nested:
                return nested
    return []


def scrape_provider(provider):
    headers = {
        'Content-Type': 'application/json',
        'x-rapidapi-host': provider['host'],
        'x-rapidapi-key': provider['key'],
    }
    jobs = []
    seen_urls = set()
    request_count = 0

    for title_filter in TITLES:
        for location_filter in LOCATIONS:
            if request_count >= provider['max_requests']:
                print(f"{provider['source']}: stopped after {provider['max_requests']} requests to protect quota")
                return jobs

            query = urlencode({
                'offset': 0,
                'title_filter': title_filter,
                'location_filter': location_filter,
                'description_type': 'text',
            })
            url = f"https://{provider['host']}/{provider['path']}?{query}"
            status, data = http_get(url, headers=headers, timeout=25)
            request_count += 1
            if status != 200:
                print(f"{provider['source']} {title_filter}/{location_filter}: HTTP {status}")
                if status in STOP_STATUSES:
                    print(f"{provider['source']}: stopping to protect quota/auth after quota or auth response")
                    return jobs
                continue

            items = extract_items(data)
            print(f"{provider['source']} {title_filter}/{location_filter}: {len(items)} jobs")
            for item in items:
                if not isinstance(item, dict):
                    continue

                title = pick(item, 'title', 'job_title', 'position', 'name')
                company = pick(item, 'company', 'company_name', 'organization', 'employer')
                location = pick(item, 'location', 'job_location', 'formatted_location', 'workplace') or location_filter
                description = pick(item, 'description', 'job_description', 'summary', 'snippet')
                job_url = pick(item, 'url', 'job_url', 'linkedin_url', 'linkedin_job_url', 'apply_url', 'application_url')
                posted_at = pick(item, 'posted_at', 'posted_date', 'date_posted', 'created_at', 'listed_at')
                job_type = pick(item, 'employment_type', 'job_type', 'type') or 'FULL_TIME'

                if not title and not description:
                    continue
                if job_url in seen_urls and job_url:
                    continue
                seen_urls.add(job_url)

                tags = [title_filter, location_filter, 'LinkedIn', 'RapidAPI']
                jobs.append(make_job(
                    source=provider['source'],
                    source_url=job_url,
                    title=title or title_filter,
                    company=company,
                    location=location,
                    remote='remote' in f'{title} {location} {description}'.lower(),
                    job_type=str(job_type).upper().replace(' ', '_'),
                    salary=pick(item, 'salary', 'salary_range', 'compensation'),
                    description=description,
                    posted_at=posted_at or datetime.now(timezone.utc).isoformat(),
                    apply_url=job_url,
                    tags=tags,
                ))
            time.sleep(1)
    return jobs


def scrape_linkedin_rapidapi():
    providers = linkedin_providers()
    if not providers:
        print('LinkedIn RapidAPI: skipped (requires LINKEDIN_RAPIDAPI_KEY and/or LINKEDIN_API2_RAPIDAPI_KEY)')
        return []

    jobs = []
    for provider in providers:
        jobs.extend(scrape_provider(provider))
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
    new_jobs = scrape_linkedin_rapidapi()
    output = write_output(existing, new_jobs)
    print(f'LinkedIn RapidAPI merged: +{len(new_jobs)} raw jobs, {output["totalJobs"]} total jobs')
