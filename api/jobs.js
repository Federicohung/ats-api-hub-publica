const fs = require('fs');
const path = require('path');

const DATA_URL = 'https://api.github.com/repos/Federicohung/ats-api-hub-publica/contents/docs/jobs.json?ref=master';

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 'no-store, max-age=0');

  try {
    const headers = {
      Accept: 'application/vnd.github.raw',
      'User-Agent': 'ats-api-hub-jobs',
    };
    if (process.env.GITHUB_ACTIONS_TOKEN) {
      headers.Authorization = `Bearer ${process.env.GITHUB_ACTIONS_TOKEN}`;
    }

    const response = await fetch(DATA_URL, { headers, cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`GitHub jobs fetch failed: ${response.status}`);
    }

    const data = await response.text();
    JSON.parse(data);
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    return res.status(200).send(data);
  } catch (error) {
    try {
      const fallback = fs.readFileSync(path.join(process.cwd(), 'docs', 'jobs.json'), 'utf8');
      JSON.parse(fallback);
      res.setHeader('Content-Type', 'application/json; charset=utf-8');
      res.setHeader('X-ATS-Data-Fallback', 'local');
      return res.status(200).send(fallback);
    } catch (fallbackError) {
      return res.status(500).json({
        ok: false,
        message: 'No pude cargar jobs.json desde GitHub ni desde el fallback local.',
        detail: error.message,
      });
    }
  }
};
