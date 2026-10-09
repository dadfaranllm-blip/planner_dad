import os,tempfile
fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd); os.environ['DATABASE_URL']='sqlite:///'+path; os.environ['JWT_SECRET']='test-final'
from fastapi.testclient import TestClient
from app.main import app,Base,engine
c=TestClient(app)
def reg(email):
 r=c.post('/auth/register',json={'email':email,'name':email.split('@')[0],'password':'12345678'}); assert r.status_code==200,r.text; return {'Authorization':'Bearer '+r.json()['access_token']},r.json()['user']
def test_integrated_final_modules():
 Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
 h,u=reg('owner@example.com'); h2,u2=reg('member@example.com')
 # periodic sync default + change
 p=c.get('/sync/preferences',headers=h); assert p.status_code==200 and p.json()['interval_hours']==6
 assert c.put('/sync/preferences',headers=h,json={'interval_hours':3,'sync_on_open':True,'sync_on_change':True}).status_code==200
 # SMS rule and privacy-first suggestion -> task
 assert c.post('/sms/rules',headers=h,json={'sender_contains':'BANK','keyword':'OTP','action':'ignore'}).status_code==200
 assert c.post('/sms/analyze',headers=h,json={'sender':'MYBANK','body':'OTP 1234'}).json()['status']=='ignored'
 sug=c.post('/sms/analyze',headers=h,json={'sender':'Clinic','body':'Appointment tomorrow'}); assert sug.status_code==200
 acc=c.post('/sms/suggestions/'+sug.json()['suggestion_id']+'/accept',headers=h); assert acc.status_code==200
 # share task
 sh=c.post('/shares',headers=h,json={'entity_type':'task','entity_id':acc.json()['task_id'],'shared_with_id':u2['id'],'permission':'viewer'}); assert sh.status_code==200
 assert len(c.get('/shares/with-me',headers=h2).json())==1
 # collaborative workspace, fixed member color, revision conflict, versioning/comments
 w=c.post('/workspaces',headers=h,json={'name':'Legal Team'}).json(); assert c.post(f"/workspaces/{w['id']}/members",headers=h,json={'user_id':u2['id'],'role':'editor','color':'#16A34A'}).status_code==200
 d=c.post(f"/workspaces/{w['id']}/documents",headers=h,json={'title':'Memo','content':'v0'}); assert d.status_code==200
 did=d.json()['id']; up=c.put('/documents/'+did,headers=h2,json={'content':'v1','base_revision':0}); assert up.status_code==200 and up.json()['revision']==1
 conflict=c.put('/documents/'+did,headers=h,json={'content':'bad','base_revision':0}); assert conflict.status_code==409
 assert len(c.get('/documents/'+did+'/versions',headers=h).json())==2
 assert c.post('/documents/'+did+'/comments',headers=h2,json={'body':'@owner review','anchor':'0:2'}).status_code==200
 # messenger still integrated
 conv=c.post('/conversations',headers=h,json={'other_user_id':u2['id']}).json(); assert c.post('/conversations/'+conv['id']+'/messages',headers=h,json={'body':'Workspace updated'}).status_code==200
