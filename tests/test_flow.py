import json, os, subprocess, tempfile, time, unittest, urllib.request, urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Flow(unittest.TestCase):
 def test_session_flow(self):
  with tempfile.TemporaryDirectory() as d:
   env={**os.environ,'STUDY_DB':d+'/test.db','PORT':'18765'};env.pop('OPENAI_API_KEY',None)
   p=subprocess.Popen(['python3','app.py'],cwd=ROOT,env=env,stdout=subprocess.PIPE)
   try:
    time.sleep(.3)
    def post(path,data):
     req=urllib.request.Request('http://127.0.0.1:18765'+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
     with urllib.request.urlopen(req) as r:return json.load(r)
    s=post('/api/session',{});sid=s['session_id'];self.assertEqual(s['mode'],'demo')
    self.assertIn('hello',post('/api/chat',{'session_id':sid,'message':'hello'})['answer'])
    code=post('/api/finish',{'session_id':sid})['completion_code'];self.assertTrue(11111<=code<=22222)
    self.assertEqual(code,post('/api/finish',{'session_id':sid})['completion_code'])
    restored=post('/api/session',{'session_id':sid});self.assertEqual(restored['completion_code'],code);self.assertEqual(len(restored['messages']),2)
    with self.assertRaises(urllib.error.HTTPError):post('/api/chat',{'session_id':sid,'message':'again'})
    subprocess.run(['python3','export.py',d+'/exports'],cwd=ROOT,env=env,check=True,capture_output=True)
    self.assertIn(str(code),Path(d+'/exports/summary.csv').read_text())
   finally:
    p.terminate();p.wait();p.stdout.close()
if __name__=='__main__':unittest.main()
