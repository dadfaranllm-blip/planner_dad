import os,tempfile
fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd)
os.environ['DATABASE_URL']='sqlite:///'+path
os.environ['JWT_SECRET']='0123456789abcdef0123456789abcdef'
from fastapi.testclient import TestClient
from app.main import app,Base,engine
c=TestClient(app)

def reg(email,name):
    r=c.post('/auth/register',json={'email':email,'name':name,'password':'12345678'})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['access_token']},r.json()['user']

def test_collab_visibility_notifications_and_calls():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    h1,u1=reg('a@example.com','Ali'); h2,u2=reg('b@example.com','Sara')
    # workspace member color + versions/comments preserve author identity/color
    w=c.post('/workspaces',headers=h1,json={'name':'Team'}).json()
    assert c.post(f"/workspaces/{w['id']}/members",headers=h1,json={'user_id':u2['id'],'role':'editor','color':'#E11D48'}).status_code==200
    members=c.get(f"/workspaces/{w['id']}/members/detail",headers=h1).json()
    sara=next(x for x in members if x['user_id']==u2['id']); assert sara['color']=='#E11D48'
    d=c.post(f"/workspaces/{w['id']}/documents",headers=h1,json={'title':'Draft','content':'v0'}).json()
    assert c.put('/documents/'+d['id'],headers=h2,json={'content':'v1','base_revision':0}).status_code==200
    versions=c.get('/documents/'+d['id']+'/versions/detail',headers=h1).json()
    assert versions[0]['author']['name']=='Sara' and versions[0]['author']['color']=='#E11D48'
    assert c.get('/notifications?unread_only=true',headers=h1).json()[0]['kind']=='workspace'
    # explicit share list on each task/event
    t=c.post('/tasks',headers=h1,json={'title':'Shared task'}).json()
    assert c.post('/shares',headers=h1,json={'entity_type':'task','entity_id':t['id'],'shared_with_id':u2['id'],'permission':'editor'}).status_code==200
    sh=c.get(f"/shares/entity/task/{t['id']}",headers=h1).json()
    assert sh[0]['user']['name']=='Sara' and sh[0]['permission']=='editor'
    # message author identity + notification
    conv=c.post('/conversations',headers=h1,json={'other_user_id':u2['id']}).json()
    m=c.post('/conversations/'+conv['id']+'/messages',headers=h1,json={'body':'hello'}); assert m.status_code==200
    md=c.get('/conversations/'+conv['id']+'/messages/detail',headers=h2).json(); assert md[-1]['sender']['name']=='Ali'
    assert any(n['kind']=='message' for n in c.get('/notifications',headers=h2).json())
    # voice-call lifecycle + signaling
    call=c.post('/conversations/'+conv['id']+'/calls',headers=h1).json(); assert call['status']=='ringing'
    assert c.post('/calls/'+call['id']+'/answer',headers=h2).json()['status']=='active'
    assert c.post('/calls/'+call['id']+'/signals',headers=h1,json={'kind':'offer','payload':'sdp'}).status_code==200
    sigs=c.get('/calls/'+call['id']+'/signals',headers=h2).json(); assert sigs and sigs[0]['kind']=='offer'
    assert c.post('/calls/'+call['id']+'/end',headers=h1).json()['status']=='ended'
