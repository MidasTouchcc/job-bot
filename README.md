# 🔍 Andre's Job Bot

A self-hosted job-search dashboard that pulls live postings from **8 sources** into one place, scores each one against your skill profile, and lets you track what you've saved and applied to — all running locally on your machine.

Built as a personal project to make the job hunt faster: instead of checking eight sites by hand, run one search and get a ranked, de-duplicated list filtered to remote/hybrid/local work and your minimum salary.

> **Note:** This is a job *aggregator* with a keyword-based relevance score — it does not use any LLM/AI model. It fetches from public APIs and RSS feeds.

---

## Features

- **One search, 8 sources** — RemoteOK, Jobicy, We Work Remotely, Remotive, The Muse, SoCal government feeds, Craigslist (IE / LA / OC), and USAJobs (federal).
- **Relevance scoring** — every posting is scored against a 100+ keyword skill profile and shown as a `% match`.
- **Search modes** — quick presets for **Dev/AI**, **Ops**, **Trading**, or **All**, plus a free-text keyword box.
- **Filters** — work type (remote / hybrid / on-site) with live counts, and a minimum-salary slider.
- **Smart cleanup** — salary parsing from free text, de-duplication, and sorting by work type → match score → salary.
- **Saved / Applied tracker** — save jobs and mark them applied; status persists in a local database.
- **Optional federal jobs** — add a free USAJobs API key in Settings to include federal listings.

---

## Tech stack

- **Backend:** Python 3 · Flask · SQLite
- **Frontend:** vanilla HTML / CSS / JavaScript (single-page dashboard, no framework)
- **Data:** third-party REST APIs and RSS/XML feeds (via `requests`)

---

## Getting started

**Requirements:** Python 3.9+

```bash
# 1. Clone
git clone https://github.com/MidasTouchcc/job-bot.git
cd job-bot

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. Run
python3 app.py
```

Then open **http://localhost:5001** in your browser.

Or just run the launcher, which checks Python and installs dependencies for you:

```bash
bash start.sh
```

---

## Configuration (optional)

Most sources work with no setup. To include **USAJobs** (federal) listings, add a free API key:

```bash
cp config.example.json config.json
```

Then edit `config.json` with your email and key, or paste them into the in-app **⚙️ API Keys** dialog:

```json
{
  "usajobs_email": "you@example.com",
  "usajobs_api_key": "YOUR_USAJOBS_API_KEY"
}
```

Get a free key at [developer.usajobs.gov](https://developer.usajobs.gov/apirequest/).

> `config.json` and `jobs.db` are git-ignored — your keys and saved jobs stay local.

---

## Job sources

| Source | Coverage |
|---|---|
| RemoteOK | Remote (global / US) |
| Jobicy | Remote (US) |
| We Work Remotely | Remote — back office, management & finance, support |
| Remotive | Remote — ops, finance, data, support, HR |
| The Muse | Flexible / remote at top companies |
| SoCal Government | Riverside & San Bernardino counties + Inland Empire cities |
| Craigslist | Inland Empire, Los Angeles, Orange County |
| USAJobs | Federal (requires free API key) |

---

## Project structure

```
job-bot/
├── app.py               # Flask server + REST API (/search, /save, /saved, /config)
├── searcher.py          # Job aggregation + relevance-scoring engine
├── templates/
│   └── index.html       # Single-page dashboard UI
├── requirements.txt     # flask, requests
├── config.example.json  # Copy to config.json to add a USAJobs key
├── start.sh             # One-command launcher
└── jobs.db              # Local SQLite DB (auto-created, git-ignored)
```

---

## License

Personal project — free to use and adapt.

**Author:** Andre Charles · [github.com/MidasTouchcc](https://github.com/MidasTouchcc) · [linkedin.com/in/andre-charles-727468185](https://www.linkedin.com/in/andre-charles-727468185)
