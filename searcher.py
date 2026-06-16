"""
searcher.py — Job search engine for Andre's Job Bot
Sources: RemoteOK, Jobicy, Arbeitnow, Craigslist IE, Riverside Gov, USAJobs
"""

import requests
import json
import os
import re
import xml.etree.ElementTree as ET

# ─── Andre's full skill profile (operations + trading) ─────────────────────────
ANDRE_SKILLS = [
    # Operations / Admin / Logistics
    'operations', 'logistics', 'data analyst', 'data analysis', 'admin',
    'coordinator', 'management', 'sql', 'excel', 'google workspace',
    'google sheets', 'spreadsheet', 'database', 'supply chain', 'warehouse',
    'transportation', 'property', 'real estate', 'process improvement',
    'workflow', 'automation', 'reporting', 'variance', 'inventory',
    'project management', 'microsoft office', 'customer service', 'accounting',
    'budget', 'financial records', 'records management', 'data entry',
    'acquisition', 'research', 'sqlite', 'e-commerce', 'tms',
    'transportation management', 'linehaul', 'dispatch', 'auditing',

    # Trading / Finance
    'trader', 'trading', 'day trader', 'day trading', 'prop trader',
    'proprietary trading', 'technical analysis', 'technical analyst',
    'support resistance', 'chart analysis', 'charting', 'tradingview',
    'market analysis', 'market analyst', 'financial analyst', 'fintech',
    'brokerage', 'investment', 'equities', 'futures', 'forex', 'options',
    'risk management', 'risk analyst', 'trading psychology', 'trading education',
    'trading coach', 'trading mentor', 'trading operations', 'trading desk',
    'securities', 'stock market', 'capital markets', 'hedge fund',
    'algo trading', 'algorithmic trading', 'quantitative', 'portfolio',
    'wealth management', 'financial services', 'trading platform',
    'trading software', 'market maker', 'order flow'
]

# ─── Keyword presets for quick search ──────────────────────────────────────────
PRESETS = {
    'ops':     'operations data analyst admin coordinator logistics',
    'trading': 'trader trading analyst fintech financial analyst market analyst risk',
    'both':    'operations trader data analyst financial admin coordinator trading'
}


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
        text = (
            (job.get('title') or '') + ' ' +
            (job.get('description') or '') + ' ' +
            ' '.join(job.get('tags') or [])
        ).lower()
        hits = sum(1 for s in ANDRE_SKILLS if s in text)
        return min(int(hits / len(ANDRE_SKILLS) * 220), 100)

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
                    'location': 'Remote',
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

    # ── Source: Jobicy ───────────────────────────────────────────────────────

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
                    'location': 'Remote',
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

    # ── Source: Arbeitnow ────────────────────────────────────────────────────

    def search_arbeitnow(self, keywords):
        jobs = []
        kw_list = keywords.lower().split()
        try:
            r = requests.get('https://www.arbeitnow.com/api/job-board-api', timeout=15)
            data = r.json()
            for job in data.get('data') or []:
                title = job.get('title') or ''
                desc  = job.get('description') or ''
                combined = (title + ' ' + desc).lower()
                if not any(k in combined for k in kw_list):
                    continue
                is_remote = bool(job.get('remote'))
                jobs.append({
                    'id': f"arbeitnow_{job.get('slug', '')}",
                    'title': title,
                    'company': job.get('company_name') or '',
                    'location': 'Remote' if is_remote else (job.get('location') or ''),
                    'work_type': 'remote' if is_remote else 'onsite',
                    'salary_min': 0,
                    'salary_max': 0,
                    'salary_display': 'Not listed',
                    'url': job.get('url') or '',
                    'description': self._clean_html(desc),
                    'tags': list(job.get('tags') or []),
                    'source': 'Arbeitnow',
                    'date': str(job.get('created_at') or '')
                })
        except Exception as e:
            print(f"  [Arbeitnow] {e}")
        return jobs

    # ── Source: Local Government (Riverside) ─────────────────────────────────

    def search_local_government(self):
        feeds = [
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
                        'tags': ['🏛️ Local Government'],
                        'source': agency,
                        'date': date
                    })
            except Exception as e:
                print(f"  [{agency}] {e}")
        return jobs

    # ── Source: Craigslist Inland Empire ─────────────────────────────────────

    def search_craigslist(self, keywords):
        jobs = []
        kw_encoded = requests.utils.quote(keywords)
        url = f'https://inlandempire.craigslist.org/search/jjj?query={kw_encoded}&format=rss'
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
            for item in items[:25]:
                def txt(tag):
                    return (
                        item.findtext(f'{{http://purl.org/rss/1.0/}}{tag}') or
                        item.findtext(f'{{http://purl.org/dc/elements/1.1/}}{tag}') or
                        item.findtext(tag) or ''
                    ).strip()
                title = txt('title')
                link  = txt('link')
                desc  = txt('description') or txt('summary')
                date  = txt('date') or txt('pubDate')
                if not title or not link:
                    continue
                sal_min, sal_max = self._parse_salary_from_text(title + ' ' + desc)
                lower = (title + desc).lower()
                work_type = 'remote' if 'remote' in lower else ('hybrid' if 'hybrid' in lower else 'onsite')
                jobs.append({
                    'id': f"cl_{hash(link) & 0xFFFFFFFF}",
                    'title': title,
                    'company': 'Local Business (Craigslist)',
                    'location': 'Inland Empire, CA',
                    'work_type': work_type,
                    'salary_min': sal_min,
                    'salary_max': sal_max,
                    'salary_display': self._fmt_salary(sal_min, sal_max),
                    'url': link,
                    'description': self._clean_html(desc),
                    'tags': ['📍 Local', '🏢 Small Business'],
                    'source': 'Craigslist IE',
                    'date': date
                })
        except Exception as e:
            print(f"  [Craigslist IE] {e}")
        return jobs

    # ── Source: USAJobs (Federal — optional) ─────────────────────────────────

    def search_usajobs(self, keywords, location):
        api_key = self.config.get('usajobs_api_key') or ''
        email   = self.config.get('usajobs_email')   or ''
        if not api_key or not email:
            print("  [USAJobs] No API key — skipping. (Add in ⚙️ Settings)")
            return []
        jobs = []
        try:
            r = requests.get(
                'https://data.usajobs.gov/api/Search',
                params={'Keyword': keywords, 'LocationName': location,
                        'ResultsPerPage': 25, 'Fields': 'Min'},
                headers={'Authorization-Key': api_key, 'User-Agent': email,
                         'Host': 'data.usajobs.gov'},
                timeout=15
            )
            data = r.json()
            items = (data.get('SearchResult') or {}).get('SearchResultItems') or []
            for item in items:
                pos = item.get('MatchedObjectDescriptor') or {}
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
                    'id': f"usajobs_{pos.get('PositionID', '')}",
                    'title': pos.get('PositionTitle') or '',
                    'company': pos.get('OrganizationName') or pos.get('DepartmentName') or '',
                    'location': pos.get('PositionLocationDisplay') or location,
                    'work_type': work_type,
                    'salary_min': sal_min,
                    'salary_max': sal_max,
                    'salary_display': self._fmt_salary(sal_min, sal_max),
                    'url': pos.get('PositionURI') or '',
                    'description': self._clean_html(detail.get('JobSummary') or ''),
                    'tags': ['🏛️ Federal Government'],
                    'source': 'USAJobs (Federal)',
                    'date': pos.get('PublicationStartDate') or ''
                })
        except Exception as e:
            print(f"  [USAJobs] {e}")
        return jobs

    # ── Main ─────────────────────────────────────────────────────────────────

    def search_all(self, keywords, location, min_salary, work_type_filter):
        print(f"\n🔍 '{keywords}' | {location} | ${min_salary:,}+ | {work_type_filter}\n")

        all_jobs = []
        print("  ↳ RemoteOK...")
        all_jobs.extend(self.search_remoteok(keywords))
        print("  ↳ Jobicy...")
        all_jobs.extend(self.search_jobicy(keywords))
        print("  ↳ Arbeitnow...")
        all_jobs.extend(self.search_arbeitnow(keywords))
        print("  ↳ Riverside Gov...")
        all_jobs.extend(self.search_local_government())
        print("  ↳ Craigslist IE...")
        all_jobs.extend(self.search_craigslist(keywords))
        print("  ↳ USAJobs...")
        all_jobs.extend(self.search_usajobs(keywords, location))

        print(f"   Raw total: {len(all_jobs)}")

        allowed = set(work_type_filter.lower().split(','))
        filtered = []
        for job in all_jobs:
            wt = job.get('work_type') or 'onsite'
            if 'all' not in allowed and wt not in allowed:
                continue
            sal = job.get('salary_min') or 0
            if sal > 0 and sal < min_salary:
                continue
            job['score'] = self._score_job(job)
            filtered.append(job)

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
