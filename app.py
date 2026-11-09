import csv, io, json, os, secrets, sqlite3, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent
DB = os.environ.get('STUDY_DB', str(ROOT / 'study.db'))
MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
MIN_CODE = int(os.environ.get('CODE_MIN', '11111'))
MAX_CODE = int(os.environ.get('CODE_MAX', '22222'))

def now(): return datetime.now(timezone.utc).isoformat()
def db():
    c = sqlite3.connect(DB, timeout=30); c.row_factory = sqlite3.Row
    return c

def init():
    with db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, started_at TEXT NOT NULL, completed_at TEXT, completion_code INTEGER UNIQUE, model TEXT NOT NULL, mode TEXT NOT NULL); CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, timestamp TEXT NOT NULL, input_tokens INTEGER, output_tokens INTEGER, model TEXT); CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, type TEXT NOT NULL, timestamp TEXT NOT NULL, detail TEXT);''')

def generate_reply(messages):
    key = os.environ.get('OPENAI_API_KEY')
    if not key: return ('Demo response: Connect an OpenAI API key to enable real AI responses. You wrote: ' + messages[-1]['content'], None, None, 'demo')
    data = json.dumps({'model': MODEL, 'messages': messages}).encode()
    req = urllib.request.Request('https://api.openai.com/v1/chat/completions', data=data, headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=90) as response: result = json.load(response)
    usage = result.get('usage', {})
    return result['choices'][0]['message']['content'], usage.get('prompt_tokens'), usage.get('completion_tokens'), result.get('model', MODEL)

class Handler(BaseHTTPRequestHandler):
    def respond(self, status, payload):
        content = json.dumps(payload).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(content))); self.end_headers(); self.wfile.write(content)
    def do_GET(self):
        if self.path in ('/', '/style.css', '/app.js'):
            path = ROOT / 'static' / ('index.html' if self.path == '/' else self.path[1:]); data = path.read_bytes()
            self.send_response(200); self.send_header('Content-Type', {'html':'text/html; charset=utf-8','css':'text/css; charset=utf-8','js':'text/javascript; charset=utf-8'}[path.suffix[1:]]); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
        else: self.respond(404, {'error':'Not found'})
    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length','0'))
            if length > 50000: return self.respond(413, {'error':'Request too large'})
            data = json.loads(self.rfile.read(length) or b'{}')
            if self.path == '/api/session':
                sid = data.get('session_id')
                with db() as c:
                    session = c.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone() if isinstance(sid,str) else None
                    if not session:
                        sid = secrets.token_urlsafe(32); mode = 'openai' if os.environ.get('OPENAI_API_KEY') else 'demo'
                        c.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?)',(sid,now(),None,None,MODEL,mode)); c.execute('INSERT INTO events (session_id,type,timestamp) VALUES (?,?,?)',(sid,'session_started',now()))
                        session = c.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
                    messages = [dict(x) for x in c.execute('SELECT role,content,timestamp FROM messages WHERE session_id=? ORDER BY id',(sid,))]
                return self.respond(200, {'session_id':sid,'started_at':session['started_at'],'completion_code':session['completion_code'],'mode':session['mode'],'messages':messages})
            sid = data.get('session_id')
            with db() as c:
                s = c.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone() if isinstance(sid,str) else None
                if not s: return self.respond(404, {'error':'Session not found'})
                if self.path == '/api/finish':
                    if not s['completed_at']:
                        available = set(range(MIN_CODE,MAX_CODE+1)) - {r[0] for r in c.execute('SELECT completion_code FROM sessions WHERE completion_code IS NOT NULL')}
                        if not available: return self.respond(503, {'error':'No completion codes available. Contact the researcher.'})
                        code = secrets.choice(tuple(available)); c.execute('UPDATE sessions SET completed_at=?,completion_code=? WHERE id=? AND completed_at IS NULL',(now(),code,sid)); c.execute('INSERT INTO events (session_id,type,timestamp) VALUES (?,?,?)',(sid,'completed',now()))
                    return self.respond(200, {'completion_code': c.execute('SELECT completion_code FROM sessions WHERE id=?',(sid,)).fetchone()[0]})
                if s['completed_at']: return self.respond(409, {'error':'Session already completed'})
                if self.path == '/api/event':
                    kind = data.get('type')
                    if kind not in ('visible','hidden','inactive','active','page_exit'): return self.respond(400, {'error':'Invalid event'})
                    c.execute('INSERT INTO events (session_id,type,timestamp,detail) VALUES (?,?,?,?)',(sid,kind,now(),None)); return self.respond(200, {'ok':True})
                if self.path == '/api/chat':
                    message = data.get('message','')
                    if not isinstance(message,str) or not message.strip() or len(message)>12000: return self.respond(400, {'error':'Message must be between 1 and 12,000 characters'})
                    c.execute('INSERT INTO messages (session_id,role,content,timestamp) VALUES (?,?,?,?)',(sid,'user',message.strip(),now())); c.commit()
                    history = [dict(x) for x in c.execute('SELECT role,content FROM messages WHERE session_id=? ORDER BY id',(sid,))]
                    try: answer, inp, out, model = generate_reply(history)
                    except Exception:
                        c.execute('INSERT INTO events (session_id,type,timestamp,detail) VALUES (?,?,?,?)',(sid,'chat_error',now(),'AI request failed')); return self.respond(502, {'error':'The response could not be generated. Your message was saved; please try again.'})
                    c.execute('INSERT INTO messages (session_id,role,content,timestamp,input_tokens,output_tokens,model) VALUES (?,?,?,?,?,?,?)',(sid,'assistant',answer,now(),inp,out,model)); return self.respond(200, {'answer':answer})
            self.respond(404, {'error':'Not found'})
        except (ValueError, TypeError, json.JSONDecodeError): self.respond(400, {'error':'Invalid request'})
    def log_message(self, fmt, *args): pass

if __name__ == '__main__':
    init(); port=int(os.environ.get('PORT','8000')); print(f'Running at http://localhost:{port}', flush=True); ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
