import json
import os
import re
import unicodedata
from datetime import datetime, timezone

FILES = ['docs/jobs.json', 'scraper/data/jobs.json']
MIN_SPANISH_CONTENT_SCORE = int(os.environ.get('MIN_SPANISH_CONTENT_SCORE') or '3')

SPANISH_EXPLICIT_TERMS = [
    'spanish', 'spanish speaking', 'spanish required', 'spanish speaker',
    'bilingual spanish', 'espanol', 'español', 'castellano', 'idioma español',
]

SPANISH_CONTENT_TERMS = [
    ' de ', ' del ', ' la ', ' el ', ' los ', ' las ', ' una ', ' un ', ' para ', ' con ', ' en ',
    ' experiencia ', ' requisitos ', ' responsabilidades ', ' buscamos ', ' buscamos a ',
    ' candidato ', ' candidata ', ' equipo ', ' trabajo ', ' remoto ', ' presencial ',
    ' jornada ', ' salario ', ' beneficios ', ' conocimientos ', ' habilidades ',
    ' funciones ', ' puesto ', ' vacante ', ' empresa ', ' cliente ', ' proyectos ',
    ' ventas ', ' comercial ', ' atención ', ' atencion ', ' soporte ', ' marketing ',
    ' desarrollador ', ' desarrolladora ', ' ingeniero ', ' ingeniera ', ' analista ',
    ' administración ', ' administracion ', ' finanzas ', ' recursos humanos ',
    ' nivel ', ' modalidad ', ' contrato ', ' postular ', ' oportunidad ',
]


def norm(value):
    text = unicodedata.normalize('NFKD', str(value or '').lower())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def plain_text(job):
    return ' '.join(str(part or '') for part in [
        job.get('title'),
        job.get('company'),
        job.get('location'),
        job.get('description'),
        ' '.join(job.get('tags') or []),
        ' '.join((job.get('market') or {}).get('matches') or []),
    ])


def spanish_content_score(job):
    text = ' ' + plain_text(job).lower() + ' '
    normalized = ' ' + norm(plain_text(job)) + ' '
    score = 0
    for term in SPANISH_CONTENT_TERMS:
        if term in text or norm(term) in normalized:
            score += 1
    if re.search(r'[áéíóúñüÁÉÍÓÚÑÜ]', plain_text(job)):
        score += 2
    return score


def explicit_spanish(job):
    text = norm(plain_text(job))
    return any(re.search(r'(?<![a-z0-9])' + re.escape(norm(term)) + r'(?![a-z0-9])', text) for term in SPANISH_EXPLICIT_TERMS)


def sort_key(job):
    market = job.get('market') or {}
    score = int(market.get('spanishContentScore') or 0)
    posted = str(job.get('postedAt') or job.get('foundAt') or '')
    return (score, posted)


for path in FILES:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    before = len(data.get('jobs') or [])
    kept = []
    for job in data.get('jobs') or []:
        score = spanish_content_score(job)
        is_explicit = explicit_spanish(job)
        market = job.get('market') or {}
        market['spanishContentScore'] = score
        market['spanishContent'] = score >= MIN_SPANISH_CONTENT_SCORE
        market['explicitSpanishRequirement'] = is_explicit
        job['market'] = market

        if score >= MIN_SPANISH_CONTENT_SCORE or is_explicit:
            kept.append(job)

    kept.sort(key=sort_key, reverse=True)

    source_counts = {}
    cat_counts = {k: 0 for k in (data.get('categories') or {})}
    for job in kept:
        source = job.get('source', 'unknown')
        source_counts[source] = source_counts.get(source, 0) + 1
        for cat in job.get('categories') or ['general']:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

    data['updatedAt'] = datetime.now(timezone.utc).isoformat()
    data['totalJobs'] = len(kept)
    data['sources'] = dict(sorted(source_counts.items()))
    data['categories'] = cat_counts
    data['jobs'] = kept

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'{path}: kept {len(kept)} of {before} jobs with Spanish content or explicit Spanish requirement')
