import os
os.environ.setdefault('JWT_SECRET','test-secret-at-least-32-bytes-long-12345')
from fastapi.testclient import TestClient
from app.main import app

c=TestClient(app)
def test_refresh_rotation_and_logout():
    email='persist-session@example.com'
    c.post('/auth/register',json={'email':email,'name':'Persist','password':'long-password-123'})
    r=c.post('/auth/login',json={'email':email,'password':'long-password-123','device_name':'phone','platform':'android'})
    assert r.status_code==200
    first=r.json(); assert first.get('refresh_token') and first.get('access_token')
    rr=c.post('/auth/refresh',json={'refresh_token':first['refresh_token'],'device_name':'phone'})
    assert rr.status_code==200
    second=rr.json(); assert second['refresh_token']!=first['refresh_token']
    # Rotation invalidates old refresh token.
    assert c.post('/auth/refresh',json={'refresh_token':first['refresh_token']}).status_code==401
    assert c.post('/auth/logout',json={'refresh_token':second['refresh_token']}).status_code==200
    assert c.post('/auth/refresh',json={'refresh_token':second['refresh_token']}).status_code==401
