"""
searcher.py — Job search engine for Andre's Job Bot
Sources: RemoteOK, Jobicy, We Work Remotely, Remotive, The Muse,
         Craigslist (IE/LA/OC), SoCal Government RSS feeds, USAJobs
"""

import requests
import json
import os
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── Andre's full capability profile ────────────────────────────────────────────
ANDRE_SKILLS = [
    # Software / AI / Automation  (PRIMARY target — Self-Taught Developer & AI Builder)
    'software', 'software engineer', 'software developer', 'software engineering',
    'developer', 'web developer', 'application developer', 'junior developer',
    'junior software engineer', 'entry level developer', 'associate developer',
    'frontend', 'front end', 'front-end', 'backend', 'back end',
    'full stack', 'full-stack', 'engineer', 'programmer', 'coding', 'scripting',
    'python', 'javascript', 'typescript', 'html', 'css', 'react', 'node', 'node.js',
    'api', 'rest api', 'git', 'github', 'flask', 'pine script',
    'linux', 'ssh', 'vps', 'cloud', 'devops',
    'ai', 'artificial intelligence', 'machine learning', 'llm', 'generative ai', 'gen ai',
    'ai engineer', 'prompt engineering', 'ai agent', 'agentic', 'chatbot',
    'automation engineer', 'rpa', 'integration', 'no-code', 'low-code', 'data engineer',

    # Operations / Logistics / Management (core FedEx background)
    'operations', 'operations manager', 'operations coordinator',
    'operations supervisor', 'operations analyst', 'operations specialist',
    'operations lead', 'operations director',
    'logistics', 'logistics manager', 'logistics coordinator', 'logistics analyst',
    'logistics supervisor', 'logistics director',
    'transportation', 'transportation manager', 'transportation coordinator',
    'transportation analyst', 'transportation supervisor', 'transportation director',
    'fleet', 'fleet manager', 'fleet coordinator', 'fleet operations', 'fleet management',
    'supply chain', 'supply chain manager', 'supply chain analyst',
    'supply chain coordinator', 'supply chain specialist',
    'distribution', 'distribution manager', 'distribution coordinator',
    'warehouse', 'warehouse manager', 'warehouse operations', 'warehouse coordinator',
    'warehouse supervisor',
    'dispatch', 'dispatch manager', 'dispatch coordinator', 'dispatcher',
    'linehaul', 'freight', 'shipping', 'receiving', 'tms',
    'transportation management system', 'transportation management',
    'facilities', 'facility manager', 'facility coordinator', 'facility operations',

    # Admin / Business Operations
    'admin', 'administrator', 'administrative manager', 'administrative coordinator',
    'office manager', 'office coordinator', 'office administrator',
    'business operations', 'business analyst', 'business coordinator',
    'coordinator', 'project coordinator', 'project manager', 'project administrator',
    'program manager', 'program coordinator', 'program administrator',
    'operations lead', 'team lead', 'supervisor', 'manager', 'director',
    'planning', 'scheduler', 'scheduling',
    'compliance', 'auditing', 'quality assurance', 'safety manager',
    'procurement', 'vendor management', 'contract management',

    # Data / Analytics / Tech
    'data analyst', 'data analysis', 'data coordinator', 'data manager',
    'reporting', 'sql', 'excel', 'google workspace', 'google sheets',
    'spreadsheet', 'database', 'sqlite', 'dashboard', 'metrics',
    'process improvement', 'workflow', 'automation', 'variance analysis',
    'inventory', 'records management', 'microsoft office', 'data entry',
    'business intelligence', 'reporting analyst',

    # Customer / Account / Support
    'customer service', 'customer success', 'customer operations',
    'customer experience', 'client relations', 'client success',
    'account manager', 'account coordinator', 'account executive',
    'client coordinator', 'customer support', 'support manager',

    # Real Estate / Property
    'property', 'real estate', 'acquisitions', 'acquisition',
    'property management', 'asset management', 'research', 'title',

    # Finance / Trading / Risk
    'trader', 'trading', 'day trader', 'financial analyst', 'fintech',
    'brokerage', 'investment', 'equities', 'futures', 'risk management',
    'risk analyst', 'technical analysis', 'market analysis', 'market analyst',
    'trading platform', 'trading operations', 'trading desk',
    'securities', 'capital markets', 'quantitative', 'portfolio',
    'wealth management', 'financial services', 'budget', 'budgeting',
    'accounting', 'financial records', 'variance', 'bookkeeping',
]

# ─── Keyword presets ─────────────────────────────────────────────────────────────
PRESETS = {
    'dev': (
        'software developer engineer python javascript html css react '
        'junior developer web developer full stack ai automation data analyst'
    ),
    'ops': (
        'operations manager logistics coordinator transportation fleet '
        'supply chain warehouse dispatcher office manager project coordinator '
        'supervisor administrator business operations'
    ),
    'trading': (
        'trader trading analyst fintech financial analyst market analyst '
        'risk management brokerage investment securities futures capital markets'
    ),
    'both': (
        'operations logistics transportation coordinator manager supervisor '
        'trader trading financial supply chain fleet dispatch administrator '
        'business operations analyst'
    ),
}


# Whole-word matcher built once from the skill list (longest phrases first so
# "software engineer" wins over "software"). \b avoids false hits like "ai" in "email".
_SKILL_RE = re.compile(
    r'\b(' + '|'.join(re.escape(s) for s in sorted(set(ANDRE_SKILLS), key=len, reverse=True)) + r')\b',
    re.IGNORECASE,
)

# Seniority signals (used to surface junior / entry-friendly roles).
_SENIOR_RE = re.compile(r'\b(senior|sr\.?|lead|principal|director|vp|vice president|head of|architect|chief|manager|mgr|supervisor|supervisory|deputy administrator)\b', re.IGNORECASE)
_JUNIOR_RE = re.compile(r'\b(junior|jr\.?|entry[\s-]?level|entry|associate|apprentice|trainee|intern|internship|graduate)\b', re.IGNORECASE)
_YEARS_RE  = re.compile(r'(\d{1,2})\s*\+?\s*(?:years|yrs)\b', re.IGNORECASE)

# Low-quality / off-market filler to drop (foreign-market gigs, data-labeling mills, monthly micro-pay).
_NOISE_COMPANIES = {'telus digital', 'workada'}
_NOISE_TITLE = re.compile(r'\b(data partner|data label|online data analyst|labeling specialist)\b', re.IGNORECASE)
_LANG_TITLE  = re.compile(r'\((?:french|spanish|arabic|german|portuguese|mandarin|hindi)\b|spanish speakers', re.IGNORECASE)
_FOREIGN_LOC = re.compile(r'\b(bogot|bangalore|india|ireland|dublin|ecuador|quito|peru|lima|brazil|brasil|colombia|cyprus|finland|ukraine|philippines|pakistan|new delhi|lisbon|portugal|romania|metropolitain)\b', re.IGNORECASE)
_MONTHLY_PAY = re.compile(r'\$\s?\d{3,4}(?:[.,]\d+)?\s?(?:[-–]\s?\$?\d{3,4})?\s?(?:usd)?\s?/\s?month', re.IGNORECASE)

# "Remote" jobs that actually require living in a specific area. Hide them unless that
# area is California / Pacific / anywhere-in-the-US (i.e. somewhere Midas could take).
_GEO_RESTRICT = re.compile(
    r'(\barea only\b|\bresidents? of\b|must (?:reside|live|be located|be based)\b|'
    r'within \d+\s*miles? of\b|candidates? (?:residing|living|located) in\b|'
    r'\bonly considering candidates\b|\blocal to\b)', re.IGNORECASE)
_LOCATION_OK = re.compile(
    r'\b(california|,\s?ca\b|\bca,|los angeles|san diego|orange county|riverside|'
    r'san bernardino|inland empire|irvine|anaheim|long beach|pasadena|socal|'
    r'southern california|west coast|pacific time|\bpst\b|\bpdt\b|'
    r'united states|u\.s\.a?\.?|\busa\b|nationwide|anywhere in the|'
    r'work from anywhere|remote \(us\)|all 50 states)\b', re.IGNORECASE)


class JobSearcher:

    def __init__(self):
        self.config = self._load_config()

    def _load_config(self):
        path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _clean_html(self, text, max_len=600):
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', ' ', str(text))
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_len]

    def _parse_salary_from_text(self, text):
        if not text:
            return 0, 0
        text = str(text).replace(',', '').replace('$', '').lower()
        matches = re.findall(r'\b(\d{2,3})k\b|\b(\d{5,6})\b', text)
        nums = []
        for k_val, full_val in matches:
            if k_val:
                nums.append(int(k_val) * 1000)
            elif full_val:
                v = int(full_val)
                if 20000 <= v <= 500000:
                    nums.append(v)
        if not nums:
            return 0, 0
        return min(nums), max(nums)

    def _score_job(self, job):
        title = job.get('title') or ''
        body  = (job.get('description') or '') + ' ' + ' '.join(job.get('tags') or [])
        title_hits = {m.lower() for m in _SKILL_RE.findall(title)}
        body_hits  = {m.lower() for m in _SKILL_RE.findall(body)} - title_hits
        # Title matches matter most; body adds supporting signal.
        raw = len(title_hits) * 14 + len(body_hits) * 4
        return max(0, min(raw, 100))

    def _seniority(self, job):
        """Classify a posting as 'entry', 'senior', or 'open' (unspecified)."""
        title = job.get('title') or ''
        if _JUNIOR_RE.search(title):
            return 'entry'
        if _SENIOR_RE.search(title):
            return 'senior'
        if (job.get('salary_min') or 0) >= 100000:   # $100k+ ≈ not an entry-level role
            return 'senior'
        yrs = [int(m) for m in _YEARS_RE.findall(job.get('description') or '')]
        if yrs and max(yrs) >= 5:
            return 'senior'
        return 'open'

    def _is_noise(self, job):
        """Filler we don't want: data-labeling gigs, foreign-market roles, monthly micro-pay."""
        if (job.get('company') or '').strip().lower() in _NOISE_COMPANIES:
            return True
        title = job.get('title') or ''
        if _NOISE_TITLE.search(title) or _LANG_TITLE.search(title):
            return True
        if _FOREIGN_LOC.search(job.get('location') or ''):
            return True
        desc = job.get('description') or ''
        if _MONTHLY_PAY.search(desc) or 'latam' in desc.lower():
            return True
        return False

    def _geo_locked_elsewhere(self, job):
        """True if a 'remote' job actually requires living somewhere that isn't CA / Pacific / US-wide."""
        text = (job.get('title') or '') + ' | ' + (job.get('location') or '') + ' | ' + (job.get('description') or '')
        if not _GEO_RESTRICT.search(text):
            return False
        return not _LOCATION_OK.search(text)

    def _fmt_salary(self, lo, hi):
        if lo and hi and lo != hi:
            return f"${lo:,} – ${hi:,}/yr"
        if lo:
            return f"${lo:,}+/yr"
        return 'Not listed'

    # ── Source: RemoteOK ─────────────────────────────────────────────────────

    def search_remoteok(self, keywords):
        jobs = []
        kw_list = keywords.lower().split()
        tags = '%2B'.join(kw_list[:3])
        try:
            r = requests.get(
                f'https://remoteok.com/api?tag={tags}',
                headers={'User-Agent': 'Mozilla/5.0 (PersonalJobBot/1.0)'},
                timeout=15
            )
            data = r.json()
            for job in data[1:]:
                if not isinstance(job, dict):
                    continue
                title = job.get('position') or ''
                desc  = job.get('description') or ''
                combined = (title + ' ' + desc).lower()
                if not any(k in combined for k in kw_list):
                    continue
                sal_min = int(job.get('salary_min') or 0)
                sal_max = int(job.get('salary_max') or 0)
                jobs.append({
                    'id': f"remoteok_{job.get('id', '')}",
                    'title': title,
                    'company': job.get('company') or '',
                    'location': 'Remote (US)',
                    'work_type': 'remote',
                    'salary_min': sal_min,
                    'salary_max': sal_max,
                    'salary_display': self._fmt_salary(sal_min, sal_max),
                    'url': job.get('url') or '',
                    'description': self._clean_html(desc),
                    'tags': list(job.get('tags') or []),
                    'source': 'RemoteOK',
                    'date': str(job.get('date') or '')
                })
        except Exception as e:
            print(f"  [RemoteOK] {e}")
        return jobs

    # ── Source: Jobicy (USA only) ────────────────────────────────────────────

    def search_jobicy(self, keywords):
        jobs = []
        kw_list = keywords.lower().split()
        tag_str = ','.join(kw_list[:4])
        try:
            r = requests.get(
                'https://jobicy.com/api/v2/remote-jobs',
                params={'count': 50, 'geo': 'usa', 'tag': tag_str},
                timeout=15
            )
            data = r.json()
            for job in data.get('jobs') or []:
                title = job.get('jobTitle') or ''
                desc  = job.get('jobDescription') or ''
                combined = (title + ' ' + desc).lower()
                if not any(k in combined for k in kw_list):
                    continue
                sal_min = int(job.get('annualSalaryMin') or 0)
                sal_max = int(job.get('annualSalaryMax') or 0)
                jobs.append({
                    'id': f"jobicy_{job.get('id', '')}",
                    'title': title,
                    'company': job.get('companyName') or '',
                    'location': 'Remote (US)',
                    'work_type': 'remote',
                    'salary_min': sal_min,
                    'salary_max': sal_max,
                    'salary_display': self._fmt_salary(sal_min, sal_max),
                    'url': job.get('url') or '',
                    'description': self._clean_html(desc),
                    'tags': list((job.get('jobIndustry') or []) + (job.get('jobType') or [])),
                    'source': 'Jobicy',
                    'date': str(job.get('pubDate') or '')
                })
        except Exception as e:
            print(f"  [Jobicy] {e}")
        return jobs

    # ── Source: We Work Remotely ─────────────────────────────────────────────

    def search_weworkremotely(self, keywords):
        """RSS feeds — US-focused, high-quality remote jobs."""
        jobs = []
        kw_list = keywords.lower().split()
        feeds = [
            ('https://weworkremotely.com/categories/remote-programming-jobs.rss',
             'Programming / Engineering'),
            ('https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss',
             'DevOps / Sysadmin'),
            ('https://weworkremotely.com/categories/remote-back-office.rss',
             'Back Office / Operations'),
            ('https://weworkremotely.com/categories/remote-management-finance.rss',
             'Management & Finance'),
            ('https://weworkremotely.com/categories/remote-customer-support-jobs.rss',
             'Customer Support / Success'),
        ]
        for feed_url, category in feeds:
            try:
                r = requests.get(
                    feed_url,
                    headers={'User-Agent': 'Mozilla/5.0 (PersonalJobBot/1.0)'},
                    timeout=15
                )
                root = ET.fromstring(r.content)
                channel = root.find('channel')
                if channel is None:
                    continue
                for item in channel.findall('item'):
                    title = (item.findtext('title') or '').replace('\n', ' ').strip()
                    link  = item.findtext('link') or ''
                    desc  = item.findtext('{http://www.w3.org/2005/Atom}summary') or \
                            item.findtext('description') or ''
                    date  = item.findtext('pubDate') or ''
                    if not title or not link:
                        continue
                    combined = (title + ' ' + self._clean_html(desc)).lower()
                    if kw_list and not any(k in combined for k in kw_list):
                        continue
                    sal_min, sal_max = self._parse_salary_from_text(combined)
                    jobs.append({
                        'id': f"wwr_{hash(link) & 0xFFFFFFFF}",
                        'title': title,
                        'company': '',
                        'location': 'Remote (US)',
                        'work_type': 'remote',
                        'salary_min': sal_min,
                        'salary_max': sal_max,
                        'salary_display': self._fmt_salary(sal_min, sal_max),
                        'url': link,
                        'description': self._clean_html(desc),
                        'tags': ['🌎 Remote', category],
                        'source': 'We Work Remotely',
                        'date': date
                    })
            except Exception as e:
                print(f"  [WeWorkRemotely - {category}] {e}")
        return jobs

    # ── Source: Remotive ─────────────────────────────────────────────────────

    def search_remotive(self, keywords):
        """Remotive.com — curated US-friendly remote jobs, no key needed."""
        jobs = []
        kw_list = keywords.lower().split()
        categories = [
            'software-dev', 'devops', 'data', 'operations', 'finance-legal',
            'business-development', 'customer-support', 'human-resources'
        ]
        seen_ids = set()
        for cat in categories:
            try:
                r = requests.get(
                    'https://remotive.com/api/remote-jobs',
                    params={'category': cat, 'limit': 20},
                    headers={'User-Agent': 'Mozilla/5.0 (PersonalJobBot/1.0)'},
                    timeout=15
                )
                if r.status_code != 200:
                    continue
                data = r.json()
                for job in data.get('jobs') or []:
                    job_id = f"remotive_{job.get('id', '')}"
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)
                    title   = job.get('title') or ''
                    desc    = job.get('description') or ''
                    company = job.get('company_name') or ''
                    combined = (title + ' ' + self._clean_html(desc) + ' ' + company).lower()
                    if kw_list and not any(k in combined for k in kw_list):
                        continue
                    sal_text = job.get('salary') or ''
                    sal_min, sal_max = self._parse_salary_from_text(sal_text)
                    jobs.append({
                        'id': job_id,
                        'title': title,
                        'company': company,
                        'location': 'Remote (US)',
                        'work_type': 'remote',
                        'salary_min': sal_min,
                        'salary_max': sal_max,
                        'salary_display': (self._fmt_salary(sal_min, sal_max)
                                           if (sal_min or sal_max) else (sal_text or 'Not listed')),
                        'url': job.get('url') or '',
                        'description': self._clean_html(desc),
                        'tags': [job.get('job_type') or 'Full-time', '🌎 Remote'],
                        'source': 'Remotive',
                        'date': str(job.get('publication_date') or '')
                    })
            except Exception as e:
                print(f"  [Remotive - {cat}] {e}")
        return jobs

    # ── Source: The Muse ─────────────────────────────────────────────────────

    def search_muse(self, keywords):
        """The Muse — top companies with great benefits, no key needed."""
        jobs = []
        kw_list = keywords.lower().split()
        searches = [
            ('Software Engineering', 'Flexible / Remote'),
            ('Data Science', 'Flexible / Remote'),
            ('Computer and IT', 'Flexible / Remote'),
            ('Data & Analytics', 'Flexible / Remote'),
            ('Operations', 'Flexible / Remote'),
            ('Business Operations', 'Flexible / Remote'),
            ('Customer Service', 'Flexible / Remote'),
            ('Finance', 'Flexible / Remote'),
        ]
        seen_ids = set()
        for cat, loc in searches:
            try:
                r = requests.get(
                    'https://www.themuse.com/api/public/jobs',
                    params={'category': cat, 'location': loc, 'page': 0},
                    headers={'User-Agent': 'Mozilla/5.0 (PersonalJobBot/1.0)'},
                    timeout=15
                )
                if r.status_code != 200:
                    continue
                data = r.json()
                for job in data.get('results') or []:
                    job_id = f"muse_{job.get('id', '')}"
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)
                    title   = job.get('name') or ''
                    company = (job.get('company') or {}).get('name') or ''
                    url     = (job.get('refs') or {}).get('landing_page') or ''
                    locs    = [l.get('name', '') for l in (job.get('locations') or [])]
                    loc_str = ', '.join(locs) if locs else 'Remote'
                    desc    = self._clean_html(job.get('contents') or '')
                    combined = (title + ' ' + desc + ' ' + company).lower()
                    if kw_list and not any(k in combined for k in kw_list):
                        continue
                    sal_min, sal_max = self._parse_salary_from_text(desc)
                    is_remote = any('remote' in l.lower() or 'flexible' in l.lower()
                                    for l in locs)
                    jobs.append({
                        'id': job_id,
                        'title': title,
                        'company': company,
                        'location': loc_str,
                        'work_type': 'remote' if is_remote else 'hybrid',
                        'salary_min': sal_min,
                        'salary_max': sal_max,
                        'salary_display': self._fmt_salary(sal_min, sal_max),
                        'url': url,
                        'description': desc,
                        'tags': ['⭐ Top Company', '💰 Great Benefits', cat],
                        'source': 'The Muse',
                        'date': str(job.get('updated_at') or '')
                    })
            except Exception as e:
                print(f"  [The Muse - {cat}] {e}")
        return jobs

    # ── Source: SoCal Government (within ~55 mi of Riverside) ────────────────

    def search_local_government(self):
        feeds = [
            # Riverside area
            ('https://www.governmentjobs.com/careers/riversideca/rss/alljobs',
             'City of Riverside', 'Riverside, CA'),
            ('https://www.governmentjobs.com/careers/countyofriverside/rss/alljobs',
             'County of Riverside', 'Riverside, CA'),
            ('https://www.governmentjobs.com/careers/rctransit/rss/alljobs',
             'Riverside Transit Agency', 'Riverside, CA'),
            ('https://www.governmentjobs.com/careers/riversideusd/rss/alljobs',
             'Riverside Unified School District', 'Riverside, CA'),
            ('https://www.governmentjobs.com/careers/rcoe/rss/alljobs',
             'Riverside County Office of Education', 'Riverside, CA'),
            # San Bernardino area
            ('https://www.governmentjobs.com/careers/sanbernardino/rss/alljobs',
             'City of San Bernardino', 'San Bernardino, CA'),
            ('https://www.governmentjobs.com/careers/sbcounty/rss/alljobs',
             'San Bernardino County', 'San Bernardino, CA'),
            # Inland Empire cities
            ('https://www.governmentjobs.com/careers/ontario/rss/alljobs',
             'City of Ontario', 'Ontario, CA'),
            ('https://www.governmentjobs.com/careers/fontana/rss/alljobs',
             'City of Fontana', 'Fontana, CA'),
            ('https://www.governmentjobs.com/careers/corona/rss/alljobs',
             'City of Corona', 'Corona, CA'),
        ]
        jobs = []
        for url, agency, loc in feeds:
            try:
                r = requests.get(
                    url,
                    headers={'User-Agent': 'Mozilla/5.0 (PersonalJobBot/1.0)'},
                    timeout=12
                )
                root = ET.fromstring(r.content)
                channel = root.find('channel')
                if channel is None:
                    continue
                for item in channel.findall('item'):
                    title = item.findtext('title') or ''
                    link  = item.findtext('link')  or ''
                    desc  = item.findtext('description') or ''
                    date  = item.findtext('pubDate') or ''
                    sal_min, sal_max = self._parse_salary_from_text(desc + ' ' + title)
                    lower = (title + desc).lower()
                    work_type = 'hybrid' if ('telework' in lower or 'remote' in lower) else 'onsite'
                    jobs.append({
                        'id': f"govjob_{hash(link) & 0xFFFFFFFF}",
                        'title': title,
                        'company': agency,
                        'location': loc,
                        'work_type': work_type,
                        'salary_min': sal_min,
                        'salary_max': sal_max,
                        'salary_display': self._fmt_salary(sal_min, sal_max),
                        'url': link,
                        'description': self._clean_html(desc),
                        'tags': ['🏛️ Government', '📍 Local', '💰 Great Benefits'],
                        'source': agency,
                        'date': date
                    })
            except Exception as e:
                print(f"  [{agency}] {e}")
        return jobs

    # ── Source: Craigslist (IE + LA + OC) ────────────────────────────────────

    def search_craigslist(self, keywords):
        jobs = []
        kw_encoded = requests.utils.quote(keywords)
        areas = [
            ('inlandempire', 'Inland Empire, CA'),
            ('losangeles',   'Los Angeles, CA'),
            ('orangecounty', 'Orange County, CA'),
        ]
        for subdomain, area_label in areas:
            url = f'https://{subdomain}.craigslist.org/search/jjj?query={kw_encoded}&format=rss'
            try:
                r = requests.get(
                    url,
                    headers={'User-Agent': 'Mozilla/5.0 (PersonalJobBot/1.0)'},
                    timeout=15
                )
                root = ET.fromstring(r.content)
                items = (
                    root.findall('{http://purl.org/rss/1.0/}item') or
                    root.findall('.//item')
                )
                for item in items[:20]:
                    def txt(tag, _item=item):
                        return (
                            _item.findtext(f'{{http://purl.org/rss/1.0/}}{tag}') or
                            _item.findtext(f'{{http://purl.org/dc/elements/1.1/}}{tag}') or
                            _item.findtext(tag) or ''
                        ).strip()
                    title = txt('title')
                    link  = txt('link')
                    desc  = txt('description') or txt('summary')
                    date  = txt('date') or txt('pubDate')
                    if not title or not link:
                        continue
                    sal_min, sal_max = self._parse_salary_from_text(title + ' ' + desc)
                    lower = (title + desc).lower()
                    work_type = ('remote' if 'remote' in lower else
                                 'hybrid' if 'hybrid' in lower else 'onsite')
                    jobs.append({
                        'id': f"cl_{hash(link) & 0xFFFFFFFF}",
                        'title': title,
                        'company': f'({area_label})',
                        'location': area_label,
                        'work_type': work_type,
                        'salary_min': sal_min,
                        'salary_max': sal_max,
                        'salary_display': self._fmt_salary(sal_min, sal_max),
                        'url': link,
                        'description': self._clean_html(desc),
                        'tags': ['📍 Local SoCal'],
                        'source': f'Craigslist {area_label.split(",")[0]}',
                        'date': date
                    })
            except Exception as e:
                print(f"  [Craigslist {area_label}] {e}")
        return jobs

    # ── Source: USAJobs (Federal — optional) ─────────────────────────────────

    def search_usajobs(self, keywords, location):
        api_key = self.config.get('usajobs_api_key') or ''
        email   = self.config.get('usajobs_email')   or ''
        if not api_key or not email:
            print("  [USAJobs] No API key — skipping. (Add in ⚙️ Settings)")
            return []
        headers = {'Authorization-Key': api_key, 'User-Agent': email, 'Host': 'data.usajobs.gov'}
        # USAJobs ANDs a long Keyword string (→ 0 results), so query a few short terms
        # separately and widen the search with a 75-mile radius around the location.
        terms = [t for t in keywords.split() if len(t) > 2][:4] or ['']
        jobs, seen = [], set()
        for term in terms:
            try:
                r = requests.get(
                    'https://data.usajobs.gov/api/Search',
                    params={'Keyword': term, 'LocationName': location, 'Radius': 75,
                            'HiringPath': 'public', 'ResultsPerPage': 25, 'Fields': 'Min'},
                    headers=headers, timeout=15
                )
                items = (r.json().get('SearchResult') or {}).get('SearchResultItems') or []
            except Exception as e:
                print(f"  [USAJobs] {e}")
                continue
            for item in items:
                pos = item.get('MatchedObjectDescriptor') or {}
                pid = pos.get('PositionID', '')
                if pid in seen:
                    continue
                seen.add(pid)
                work_type = 'onsite'
                tele = (pos.get('TeleworkSchedule') or '').lower()
                if 'full' in tele:
                    work_type = 'remote'
                elif 'situational' in tele or 'regular' in tele:
                    work_type = 'hybrid'
                for loc_obj in (pos.get('PositionLocation') or []):
                    if 'anywhere' in str(loc_obj.get('LocationName') or '').lower():
                        work_type = 'remote'
                        break
                remun   = ((pos.get('PositionRemuneration') or [{}])[0])
                sal_min = int(float(remun.get('MinimumRange') or 0))
                sal_max = int(float(remun.get('MaximumRange') or 0))
                if remun.get('RateIntervalCode') == 'PH':
                    sal_min, sal_max = sal_min * 2080, sal_max * 2080
                detail = ((pos.get('UserArea') or {}).get('Details') or {})
                jobs.append({
                    'id': f"usajobs_{pid}",
                    'title': pos.get('PositionTitle') or '',
                    'company': pos.get('OrganizationName') or pos.get('DepartmentName') or '',
                    'location': pos.get('PositionLocationDisplay') or location,
                    'work_type': work_type,
                    'salary_min': sal_min,
                    'salary_max': sal_max,
                    'salary_display': self._fmt_salary(sal_min, sal_max),
                    'url': pos.get('PositionURI') or '',
                    'description': self._clean_html(detail.get('JobSummary') or ''),
                    'tags': ['🏛️ Federal Government', '💰 Great Benefits'],
                    'source': 'USAJobs (Federal)',
                    'date': pos.get('PublicationStartDate') or ''
                })
        return jobs

    # ── Main ─────────────────────────────────────────────────────────────────

    def search_all(self, keywords, location, min_salary, work_type_filter, level='all'):
        print(f"\n🔍 '{keywords}' | {location} | ${min_salary:,}+ | {work_type_filter}\n")

        # All sources run concurrently — total time ≈ the slowest source, not the sum.
        tasks = {
            'RemoteOK':         lambda: self.search_remoteok(keywords),
            'Jobicy':           lambda: self.search_jobicy(keywords),
            'We Work Remotely': lambda: self.search_weworkremotely(keywords),
            'Remotive':         lambda: self.search_remotive(keywords),
            'The Muse':         lambda: self.search_muse(keywords),
            'SoCal Government': self.search_local_government,
            'Craigslist':       lambda: self.search_craigslist(keywords),
            'USAJobs':          lambda: self.search_usajobs(keywords, location),
        }
        all_jobs = []
        with ThreadPoolExecutor(max_workers=len(tasks)) as ex:
            futures = {ex.submit(fn): name for name, fn in tasks.items()}
            for fut in as_completed(futures):
                name = futures[fut]
                try:
                    res = fut.result()
                    print(f"  ✓ {name}: {len(res)}")
                    all_jobs.extend(res)
                except Exception as e:
                    print(f"  ✗ {name}: {e}")

        print(f"   Raw total: {len(all_jobs)}")

        allowed = set(work_type_filter.lower().split(','))
        # Domain keywords for the relevance gate — strip qualifier / stop-words like
        # "entry", "level", "remote" so they aren't mistaken for a job type to match.
        STOPWORDS = {'entry', 'entry-level', 'level', 'junior', 'jr', 'senior', 'sr',
                     'mid', 'lead', 'remote', 'hybrid', 'onsite', 'on-site', 'job',
                     'jobs', 'work', 'position', 'role', 'roles', 'any', 'all', 'and', 'the'}
        kw_terms = [k for k in keywords.lower().split() if len(k) > 2 and k not in STOPWORDS]

        # Pass 1 — work type, salary, and seniority.
        base = []
        for job in all_jobs:
            wt = job.get('work_type') or 'onsite'
            if 'all' not in allowed and wt not in allowed:
                continue
            sal = job.get('salary_min') or 0
            if sal > 0 and sal < min_salary:
                continue
            tags = job.get('tags') or []
            is_gov = any('Government' in str(t) for t in tags)
            if not is_gov and (self._is_noise(job) or self._geo_locked_elsewhere(job)):
                continue
            job['level'] = self._seniority(job)
            if level == 'entry' and job['level'] == 'senior':
                continue
            job['score'] = self._score_job(job)
            base.append(job)

        # Pass 2 — title-relevance gate: keeps an Ops search from returning dev/finance
        # roles. Government listings always pass. The gate RELAXES itself if it would
        # leave too few results, so a broad or qualifier-only search is never near-empty.
        if kw_terms:
            def _relevant(j):
                if any('Government' in str(t) for t in (j.get('tags') or [])):
                    return True
                title_l = (j.get('title') or '').lower()
                return any(k in title_l for k in kw_terms)
            gated = [j for j in base if _relevant(j)]
            filtered = gated if len(gated) >= 5 else base
        else:
            filtered = base

        # Deduplicate
        seen, unique = set(), []
        for job in filtered:
            key = ((job.get('title') or '').lower()[:40],
                   (job.get('company') or '').lower()[:25])
            if key not in seen:
                seen.add(key)
                unique.append(job)

        order = {'remote': 0, 'hybrid': 1, 'onsite': 2}
        unique.sort(key=lambda x: (
            order.get(x.get('work_type') or 'onsite', 2),
            -(x.get('score') or 0),
            -(x.get('salary_min') or 0)
        ))

        print(f"   After filter/dedupe: {len(unique)}\n")
        return unique
