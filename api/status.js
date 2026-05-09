const PROVIDERS = [
  ['GITHUB_ACTIONS_TOKEN', 'Backend Sync Token'],
  ['RAPIDAPI_KEY', 'JSearch'],
  ['LINKEDIN_RAPIDAPI_KEY', 'LinkedIn RapidAPI', 'RAPIDAPI_KEY'],
  ['LINKEDIN_API2_RAPIDAPI_KEY', 'LinkedIn API2 RapidAPI', 'RAPIDAPI_KEY'],
  ['INDEED12_RAPIDAPI_KEY', 'Indeed12 RapidAPI', 'RAPIDAPI_KEY'],
  ['RSS_RAPIDAPI_KEY', 'RSS Jobs RapidAPI', 'RAPIDAPI_KEY'],
  ['JOBS_API14_RAPIDAPI_KEY', 'Jobs API14 Salary', 'RAPIDAPI_KEY'],
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
    providers: PROVIDERS.map(([key, label, fallbackKey]) => ({
      key,
      label,
      configured: Boolean(process.env[key] || (fallbackKey && process.env[fallbackKey]))
    })),
    message: 'Solo se expone el estado de configuracion, nunca el valor de los secretos.'
  });
};
