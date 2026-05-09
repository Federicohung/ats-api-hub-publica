const PROVIDERS = {
  RAPIDAPI_KEY: 'JSearch',
  LINKEDIN_RAPIDAPI_KEY: 'LinkedIn RapidAPI',
  ADZUNA_APP_ID: 'Adzuna App ID',
  ADZUNA_APP_KEY: 'Adzuna App Key',
  JOOBLE_API_KEY: 'Jooble',
  SMARTRECRUITERS_API_KEY: 'SmartRecruiters',
  WORKABLE_API_KEY: 'Workable',
  TEAMTAILOR_API_KEY: 'Teamtailor',
  BREEZY_API_KEY: 'Breezy HR',
  GITHUB_ACTIONS_TOKEN: 'Backend Sync Token',
};

module.exports = function handler(req, res) {
  const providers = Object.entries(PROVIDERS).map(([key, label]) => ({
    key,
    label,
    configured: Boolean(process.env[key]),
  }));

  res.status(200).json({
    ok: true,
    providers,
    message: 'Este endpoint solo muestra si una variable existe; nunca devuelve secretos.',
  });
};
