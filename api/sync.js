const REPO = 'Federicohung/ats-api-hub-publica';
const WORKFLOW = 'scrape.yml';

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') {
    return res.status(405).json({ ok: false, message: 'Use POST para iniciar sync.' });
  }

  const token = process.env.GITHUB_ACTIONS_TOKEN || process.env.GH_WORKFLOW_TOKEN;
  if (!token) {
    return res.status(501).json({
      ok: false,
      code: 'MISSING_SERVER_TOKEN',
      message: 'Falta GITHUB_ACTIONS_TOKEN en Vercel Environment Variables. No uses tokens en el navegador.',
      setupUrl: 'https://vercel.com/dashboard',
    });
  }

  try {
    const dispatch = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github+json',
        'Content-Type': 'application/json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'ats-api-hub-sync',
      },
      body: JSON.stringify({ ref: 'master' }),
    });

    if (dispatch.status !== 204) {
      const detail = await dispatch.text();
      return res.status(dispatch.status).json({
        ok: false,
        message: 'GitHub no pudo iniciar el workflow.',
        detail,
      });
    }

    return res.status(202).json({
      ok: true,
      message: 'Sync iniciado en GitHub Actions.',
      actionsUrl: `https://github.com/${REPO}/actions/workflows/${WORKFLOW}`,
    });
  } catch (error) {
    return res.status(500).json({ ok: false, message: 'Error iniciando sync.', detail: error.message });
  }
};
