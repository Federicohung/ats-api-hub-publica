const PROVIDERS = [
  ['GITHUB_ACTIONS_TOKEN', 'Backend Sync Token'],
  ['JSEARCH_RAPIDAPI_KEY', 'JSearch RapidAPI'],
  ['LINKEDIN_RAPIDAPI_KEY', 'LinkedIn Job Search API RapidAPI'],
  ['LINKEDIN_API2_RAPIDAPI_KEY', 'LinkedIn Jobs API RapidAPI'],
  ['INDEED12_RAPIDAPI_KEY', 'Indeed RapidAPI'],
  ['RSS_RAPIDAPI_KEY', 'RSS Jobs API RapidAPI'],
  ['JOBS_API14_RAPIDAPI_KEY', 'Jobs API RapidAPI'],
  ['JOBS_SEARCH_RAPIDAPI_KEY', 'Jobs Search API RapidAPI'],
  ['ADZUNA_APP_ID', 'Adzuna App ID'],
  ['ADZUNA_APP_KEY', 'Adzuna App Key'],
  ['JOOBLE_API_KEY', 'Jooble'],
  ['SMARTRECRUITERS_API_KEY', 'SmartRecruiters'],
  ['WORKABLE_API_KEY', 'Workable'],
  ['TEAMTAILOR_API_KEY', 'Teamtailor'],
  ['BREEZY_API_KEY', 'Breezy HR']
];

module.exports = function handler(_req, res) {
  res.status(200).json({
    ok: true,
    providers: PROVIDERS.map(([key, label]) => ({
      key,
      label,
      configured: Boolean(process.env[key])
    })),
    healthEndpoint: '/api/provider-health',
    message: 'Solo se expone el estado de configuracion, nunca el valor de los secretos.'
  });
};
