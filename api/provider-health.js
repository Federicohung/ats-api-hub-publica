const CHECKS = [
  {
    id: 'google_jobs_rapidapi',
    label: 'Google Jobs API',
    key: 'GOOGLE_JOBS_RAPIDAPI_KEY',
    host: 'google-jobs-api.p.rapidapi.com',
    url: 'https://google-jobs-api.p.rapidapi.com/google-jobs/relocation?include=senior%20engineer',
  },
  {
    id: 'jsearch',
    label: 'JSearch',
    key: 'JSEARCH_RAPIDAPI_KEY',
    host: 'jsearch.p.rapidapi.com',
    url: 'https://jsearch.p.rapidapi.com/search?query=remote%20spanish&page=1&num_pages=1',
  },
  {
    id: 'linkedin_job_search',
    label: 'LinkedIn Job Search API',
    key: 'LINKEDIN_RAPIDAPI_KEY',
    host: 'linkedin-job-search-api.p.rapidapi.com',
    url: 'https://linkedin-job-search-api.p.rapidapi.com/active-jb-1h?offset=0&title_filter=Data%20Engineer&location_filter=Spain&description_type=text',
  },
  {
    id: 'linkedin_jobs_api',
    label: 'LinkedIn Jobs API',
    key: 'LINKEDIN_API2_RAPIDAPI_KEY',
    host: 'linkedin-jobs-api2.p.rapidapi.com',
    url: 'https://linkedin-jobs-api2.p.rapidapi.com/active-jb-1h',
  },
  {
    id: 'indeed12',
    label: 'Indeed',
    key: 'INDEED12_RAPIDAPI_KEY',
    host: 'indeed12.p.rapidapi.com',
    url: 'https://indeed12.p.rapidapi.com/company/Ubisoft/jobs?locality=us&start=1',
  },
  {
    id: 'rss_jobs',
    label: 'RSS Jobs API',
    key: 'RSS_RAPIDAPI_KEY',
    host: 'job-postings-rss-feed.p.rapidapi.com',
    url: 'https://job-postings-rss-feed.p.rapidapi.com/api/rss/v1/jobs_full?page=1&countryCode=us&hasSalary=true',
  },
  {
    id: 'jobs_api14_list',
    label: 'Jobs API /v2/list',
    key: 'JOBS_API14_RAPIDAPI_KEY',
    host: 'jobs-api14.p.rapidapi.com',
    url: 'https://jobs-api14.p.rapidapi.com/v2/list?query=developer&location=Spain',
  },
  {
    id: 'jobs_api14_salary',
    label: 'Jobs API salary range',
    key: 'JOBS_API14_RAPIDAPI_KEY',
    host: 'jobs-api14.p.rapidapi.com',
    url: 'https://jobs-api14.p.rapidapi.com/v2/salary/range?query=developer&countryCode=es',
  },
];

function extractItems(data) {
  if (Array.isArray(data)) return data;
  if (!data || typeof data !== 'object') return [];
  for (const key of ['data', 'jobs', 'items', 'results', 'job_results', 'list']) {
    const value = data[key];
    if (Array.isArray(value)) return value;
    const nested = extractItems(value);
    if (nested.length) return nested;
  }
  if (Array.isArray(data.aggregated_response)) {
    const jobs = data.aggregated_response.flatMap((item) => Array.isArray(item?.jobs) ? item.jobs : []);
    if (jobs.length) return jobs;
  }
  return [];
}

async function fetchWithTimeout(url, options, timeoutMs = 12000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal, cache: 'no-store' });
  } finally {
    clearTimeout(timer);
  }
}

module.exports = async function handler(_req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 'no-store, max-age=0');

  const results = [];
  for (const check of CHECKS) {
    const apiKey = process.env[check.key];
    if (!apiKey) {
      results.push({
        id: check.id,
        label: check.label,
        key: check.key,
        host: check.host,
        configured: false,
        ok: false,
        status: null,
        sampleCount: 0,
        hint: 'Falta esta variable en Vercel Environment.',
      });
      continue;
    }

    try {
      const response = await fetchWithTimeout(check.url, {
        headers: {
          'Content-Type': 'application/json',
          'x-rapidapi-host': check.host,
          'x-rapidapi-key': apiKey,
        },
      });
      const text = await response.text();
      let body = {};
      try { body = text ? JSON.parse(text) : {}; } catch (_error) { body = { raw: text.slice(0, 200) }; }
      const sampleCount = extractItems(body).length;
      results.push({
        id: check.id,
        label: check.label,
        key: check.key,
        host: check.host,
        configured: true,
        ok: response.ok,
        status: response.status,
        sampleCount,
        hint: response.ok
          ? 'El proveedor responde. Si sampleCount es 0, la ruta funciona pero esa consulta no trajo ofertas.'
          : 'La key existe, pero RapidAPI rechazo este host/ruta. Revisa que el secreto corresponda a esta API y que el endpoint sea el de la pagina Go to API.',
      });
    } catch (error) {
      results.push({
        id: check.id,
        label: check.label,
        key: check.key,
        host: check.host,
        configured: true,
        ok: false,
        status: 0,
        sampleCount: 0,
        hint: error.name === 'AbortError' ? 'Timeout consultando proveedor.' : error.message,
      });
    }
  }

  res.status(200).json({
    ok: true,
    warning: 'Este endpoint hace una consulta real por proveedor y puede consumir una pequena parte de la cuota.',
    checkedAt: new Date().toISOString(),
    results,
  });
};
