import os, tempfile
fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd); os.environ['DATABASE_URL']='sqlite:///'+path; os.environ['JWT_SECRET']='test'
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
def auth(email='a@example.com'):
 r=c.post('/auth/register',json={'email':email,'name':'A','password':'12345678'}); assert r.status_code==200,r.text; return {'Authorization':'Bearer '+r.json()['access_token']},r.json()['user']
def test_core_flow():
 h,u=auth(); assert c.get('/me',headers=h).status_code==200
 cal=c.get('/calendars',headers=h).json()[0]
 t=c.post('/tasks',headers=h,json={'title':'Call','due_at':'2026-09-30T10:00:00Z'}); assert t.status_code==200
 tid=t.json()['id']; r=c.post(f'/tasks/{tid}/continue',headers=h,json={}); assert r.status_code==200 and 'T08:00:00' in r.json()['due_at']
 assert c.post(f'/tasks/{tid}/complete',headers=h).status_code==200
 e=c.post('/events',headers=h,json={'title':'Meeting','starts_at':'2026-09-30T11:00:00Z','ends_at':'2026-09-30T12:00:00Z','calendar_id':cal['id']}); assert e.status_code==200
 eid=e.json()['id']; assert c.post(f'/events/{eid}/continue',headers=h,json={}).status_code==200; assert c.post(f'/events/{eid}/complete',headers=h).status_code==200
 w=c.post('/workspaces',headers=h,json={'name':'Team'}); assert w.status_code==200
 h2,u2=auth('b@example.com'); assert c.post(f"/workspaces/{w.json()['id']}/members",headers=h,json={'user_id':u2['id'],'role':'editor','color':'#16A34A'}).status_code==200
 conv=c.post('/conversations',headers=h,json={'other_user_id':u2['id']}); assert conv.status_code==200
 cid=conv.json()['id']; assert c.post(f'/conversations/{cid}/messages',headers=h,json={'body':'hello'}).status_code==200; assert len(c.get(f'/conversations/{cid}/messages',headers=h2).json())==1
 assert len(c.get('/activity',headers=h).json())>=5

def test_phase3_reminders_and_settings():
 from fastapi.testclient import TestClient
 from app.main import app, Base, engine
 Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
 c=TestClient(app)
 r=c.post('/auth/register',json={'email':'rem@example.com','name':'Rem','password':'12345678'}); assert r.status_code==200
 h={'Authorization':'Bearer '+r.json()['access_token']}
 st=c.get('/settings',headers=h); assert st.status_code==200 and st.json()['default_reminder_hour']==17
 st=c.put('/settings',headers=h,json={'timezone':'Asia/Tehran','default_reminder_enabled':True,'default_reminder_days_before':1,'default_reminder_hour':17,'default_reminder_minute':0}); assert st.status_code==200
 t=c.post('/tasks',headers=h,json={'title':'Deadline','due_at':'2026-10-05T10:00:00Z'}); assert t.status_code==200
 tid=t.json()['id']; rs=c.get('/reminders?status=pending',headers=h).json(); assert len(rs)==1 and rs[0]['entity_id']==tid and rs[0]['remind_at'].startswith('2026-10-04T17:00:00')
 custom=c.post('/reminders',headers=h,json={'entity_type':'task','entity_id':tid,'remind_at':'2026-10-05T09:00:00Z','channel':'local'}); assert custom.status_code==200
 rid=custom.json()['id']; assert c.post(f'/reminders/{rid}/snooze',headers=h,json={'minutes':30}).status_code==200
 cont=c.post(f'/tasks/{tid}/continue',headers=h,json={'due_at':'2026-10-07T12:00:00Z'}); assert cont.status_code==200
 pending=c.get('/reminders?status=pending',headers=h).json(); assert len(pending)==1 and pending[0]['remind_at'].startswith('2026-10-06T17:00:00')
 assert c.post(f'/tasks/{tid}/complete',headers=h).status_code==200
 assert len(c.get('/reminders?status=pending',headers=h).json())==0

def test_phase4_device_sync_idempotent_and_google_status():
 from app.main import Base, engine
 Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
 c=TestClient(app)
 r=c.post('/auth/register',json={'email':'sync@example.com','name':'Sync','password':'12345678'}); assert r.status_code==200
 h={'Authorization':'Bearer '+r.json()['access_token']}
 payload={'device_calendar_id':'phone-main','device_event_id':'evt-42','title':'Device meeting','starts_at':'2026-10-10T10:00:00Z','ends_at':'2026-10-10T11:00:00Z'}
 a=c.post('/sync/device/events',headers=h,json=payload); assert a.status_code==200 and a.json()['created'] is True
 payload['title']='Device meeting updated'
 b=c.post('/sync/device/events',headers=h,json=payload); assert b.status_code==200 and b.json()['created'] is False and b.json()['event_id']==a.json()['event_id']
 ev=c.get('/events',headers=h).json(); assert len(ev)==1 and ev[0]['title']=='Device meeting updated' and ev[0]['source']=='device'
 accounts=c.get('/sync/accounts',headers=h); assert accounts.status_code==200 and accounts.json()[0]['provider']=='device'
 g=c.get('/sync/google/connect',headers=h); assert g.status_code==503
