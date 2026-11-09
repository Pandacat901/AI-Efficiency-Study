"""Export private study data locally; never commit exports to Git."""
import csv, json, sys
from pathlib import Path
from datetime import datetime
from app import db, init

if len(sys.argv) != 2: raise SystemExit('Usage: python export.py OUTPUT_DIRECTORY')
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); init()
with db() as c:
    for table in ('sessions','messages','events'):
        rows = c.execute('SELECT * FROM '+table).fetchall()
        with (out / (table+'.csv')).open('w',newline='',encoding='utf-8') as f:
            columns = [x[1] for x in c.execute('PRAGMA table_info('+table+')')]; w=csv.DictWriter(f,fieldnames=columns); w.writeheader(); w.writerows(map(dict,rows))
    sessions = c.execute('SELECT * FROM sessions').fetchall()
    with (out/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        cols=['session_id','completion_code','started_at','completed_at','elapsed_seconds','status','mode','model','user_messages','assistant_messages','follow_up_count','input_tokens','output_tokens','chat_errors']
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader()
        for s in sessions:
            messages=c.execute('SELECT * FROM messages WHERE session_id=?',(s['id'],)).fetchall(); users=sum(m['role']=='user' for m in messages); assistants=sum(m['role']=='assistant' for m in messages)
            tokens=[m for m in messages if m['role']=='assistant']; known=bool(tokens) and all(m['input_tokens'] is not None and m['output_tokens'] is not None for m in tokens)
            elapsed=(datetime.fromisoformat(s['completed_at'])-datetime.fromisoformat(s['started_at'])).total_seconds() if s['completed_at'] else ''
            errors=c.execute("SELECT COUNT(*) FROM events WHERE session_id=? AND type='chat_error'",(s['id'],)).fetchone()[0]
            w.writerow(dict(session_id=s['id'],completion_code=s['completion_code'],started_at=s['started_at'],completed_at=s['completed_at'],elapsed_seconds=elapsed,status='completed' if s['completed_at'] else 'incomplete',mode=s['mode'],model=s['model'],user_messages=users,assistant_messages=assistants,follow_up_count=max(0,users-1),input_tokens=sum(m['input_tokens'] for m in tokens) if known else '',output_tokens=sum(m['output_tokens'] for m in tokens) if known else '',chat_errors=errors))
print('Exported to',out)
