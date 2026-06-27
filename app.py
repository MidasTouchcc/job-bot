"""
app.py — Andre's Job Bot · Local Flask server
Run: python3 app.py   then open http://localhost:5001
"""

from flask import Flask, render_template, jsonify, request
import sqlite3, json, os
from datetime import datetime
from searcher import JobSearcher

app     = Flask(__name__)
BASE    = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'jobs.db')
CFG     = os.path.join(BASE, 'config.json')

def init_db():
    c = sqlite3.connect(DB_PATH)
    c.execute('''CREATE TABLE IF NOT EXISTS saved_jobs (
        id TEXT PRIMARY KEY, title TEXT, company TEXT, url TEXT,
        work_type TEXT, source TEXT,
        status TEXT DEFAULT 'saved', notes TEXT DEFAULT '',
        created_at TEXT)''')
    c.commit(); c.close()

@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/search')
def search():
    kw  = request.args.get('keywords', 'software developer python automation ai data analyst operations')
    wt  = request.args.get('work_type', 'remote,hybrid,all')
    sal = int(request.args.get('min_salary', 60000))
    jobs = JobSearcher().search_all(kw, 'Riverside, CA', sal, wt)
    return jsonify({'jobs': jobs, 'count': len(jobs)})

@app.route('/api/save', methods=['POST'])
def save_job():
    d = request.get_json() or {}
    c = sqlite3.connect(DB_PATH)
    c.execute('''INSERT OR REPLACE INTO saved_jobs
        (id,title,company,url,work_type,source,status,notes,created_at)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (d.get('id',''), d.get('title',''), d.get('company',''),
         d.get('url',''), d.get('work_type',''), d.get('source',''),
         d.get('status','saved'), d.get('notes',''), datetime.now().isoformat()))
    c.commit(); c.close()
    return jsonify({'success': True})

@app.route('/api/unsave', methods=['POST'])
def unsave():
    d = request.get_json() or {}
    c = sqlite3.connect(DB_PATH)
    c.execute('DELETE FROM saved_jobs WHERE id=?', (d.get('id',''),))
    c.commit(); c.close()
    return jsonify({'success': True})

@app.route('/api/saved')
def get_saved():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute(
        'SELECT * FROM saved_jobs ORDER BY created_at DESC').fetchall()]
    c.close()
    return jsonify({'jobs': rows})

@app.route('/api/config', methods=['GET','POST'])
def config():
    if request.method == 'POST':
        existing = {}
        if os.path.exists(CFG):
            try: existing = json.load(open(CFG))
            except: pass
        existing.update(request.get_json() or {})
        json.dump(existing, open(CFG,'w'), indent=2)
        return jsonify({'success': True})
    cfg = {}
    if os.path.exists(CFG):
        try: cfg = json.load(open(CFG))
        except: pass
    return jsonify({'usajobs_email': cfg.get('usajobs_email',''),
                    'usajobs_key_set': bool(cfg.get('usajobs_api_key',''))})

if __name__ == '__main__':
    init_db()
    print("\n" + "═"*46)
    print("   🔍  Andre's Job Bot")
    print("═"*46)
    print("   👉  http://localhost:5001")
    print("   ⛔  Ctrl+C to stop")
    print("═"*46 + "\n")
    app.run(debug=False, port=5001, host='127.0.0.1')
