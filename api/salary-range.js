const HOST = 'jobs-api14.p.rapidapi.com';

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 'no-store, max-age=0');

  const key = process.env.JOBS_API14_RAPIDAPI_KEY;
  if (!key) {
    return res.status(501).json({
      ok: false,
      code: 'MISSING_JOBS_API14_KEY',
      message: 'Falta JOBS_API14_RAPIDAPI_KEY en Vercel Environment Variables.',
    });
  }

  const query = String(req.query.query || 'developer').slice(0, 80);
  const countryCode = String(req.query.countryCode || 'es').slice(0, 2).toLowerCase();
  const url = new URL(`https://${HOST}/v2/salary/range`);
  url.searchParams.set('query', query);
  url.searchParams.set('countryCode', countryCode);

  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        'x-rapidapi-host': HOST,
        'x-rapidapi-key': key,
      },
      cache: 'no-store',
    });

    const text = await response.text();
    let body;
    try {
      body = text ? JSON.parse(text) : {};
    } catch (_error) {
      body = { raw: text };
    }

    return res.status(response.status).json({
      ok: response.ok,
      provider: 'jobs_api14_salary',
      query,
      countryCode,
      data: body,
    });
  } catch (error) {
    return res.status(500).json({
      ok: false,
      message: 'No pude consultar Jobs API14 Salary.',
      detail: error.message,
    });
  }
};
