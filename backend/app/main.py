import os, uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from fastapi import FastAPI, Depends, HTTPException, Header, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import hashlib, hmac, secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, String, DateTime, ForeignKey, Text, Boolean, Integer, select, or_, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

DB=os.getenv('DATABASE_URL','sqlite:///./planner.db'); SECRET=os.getenv('JWT_SECRET','dev-secret')
engine=create_engine(DB,pool_pre_ping=True,connect_args={'check_same_thread':False} if DB.startswith('sqlite') else {})
class Base(DeclarativeBase): pass
def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)

class User(Base):
    __tablename__='users'; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); email:Mapped[str]=mapped_column(String(255),unique=True,index=True); name:Mapped[str]=mapped_column(String(120)); password_hash:Mapped[str]=mapped_column(String(255)); color:Mapped[str]=mapped_column(String(16),default='#2563EB'); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class AuthSession(Base):
    __tablename__='auth_sessions'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    refresh_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True)
    device_name:Mapped[Optional[str]]=mapped_column(String(160),nullable=True)
    platform:Mapped[Optional[str]]=mapped_column(String(40),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    last_used_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    revoked_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)

class Calendar(Base):
    __tablename__='calendars'; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True); name:Mapped[str]=mapped_column(String(120),default='My Calendar'); source:Mapped[str]=mapped_column(String(30),default='app'); color:Mapped[str]=mapped_column(String(16),default='#2563EB')
class Task(Base):
    __tablename__='tasks'; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True); title:Mapped[str]=mapped_column(String(255)); notes:Mapped[Optional[str]]=mapped_column(Text,nullable=True); due_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True); status:Mapped[str]=mapped_column(String(20),default='open'); completed_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True); reminder_previous_day_17:Mapped[bool]=mapped_column(Boolean,default=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Event(Base):
    __tablename__='events'; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True); calendar_id:Mapped[Optional[str]]=mapped_column(ForeignKey('calendars.id'),nullable=True); title:Mapped[str]=mapped_column(String(255)); starts_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); ends_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True); status:Mapped[str]=mapped_column(String(20),default='open'); source:Mapped[str]=mapped_column(String(30),default='app'); external_id:Mapped[Optional[str]]=mapped_column(String(255),nullable=True); completed_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Reminder(Base):
    __tablename__='reminders'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    entity_type:Mapped[str]=mapped_column(String(20),index=True)
    entity_id:Mapped[str]=mapped_column(String(36),index=True)
    remind_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    status:Mapped[str]=mapped_column(String(20),default='pending',index=True)
    channel:Mapped[str]=mapped_column(String(20),default='local')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    sent_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
class UserSetting(Base):
    __tablename__='user_settings'
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),primary_key=True)
    timezone:Mapped[str]=mapped_column(String(80),default='Asia/Tehran')
    default_reminder_enabled:Mapped[bool]=mapped_column(Boolean,default=True)
    default_reminder_hour:Mapped[int]=mapped_column(Integer,default=17)
    default_reminder_minute:Mapped[int]=mapped_column(Integer,default=0)
    default_reminder_days_before:Mapped[int]=mapped_column(Integer,default=1)
class Workspace(Base):
    __tablename__='workspaces'; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True); name:Mapped[str]=mapped_column(String(160)); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class WorkspaceMember(Base):
    __tablename__='workspace_members'; __table_args__=(UniqueConstraint('workspace_id','user_id'),); id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); workspace_id:Mapped[str]=mapped_column(ForeignKey('workspaces.id'),index=True); user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True); role:Mapped[str]=mapped_column(String(20),default='editor'); color:Mapped[str]=mapped_column(String(16),default='#2563EB')
class Conversation(Base):
    __tablename__='conversations'; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); user1_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True); user2_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Message(Base):
    __tablename__='messages'; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); conversation_id:Mapped[str]=mapped_column(ForeignKey('conversations.id'),index=True); sender_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True); body:Mapped[str]=mapped_column(Text); sent_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); seen_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
class Activity(Base):
    __tablename__='activities'; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True); action:Mapped[str]=mapped_column(String(80)); entity_type:Mapped[str]=mapped_column(String(40)); entity_id:Mapped[str]=mapped_column(String(36)); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
Base.metadata.create_all(engine)
app=FastAPI(title='Planner Suite API',version='1.0.0')
_origins=[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:3000,http://127.0.0.1:3000').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=_origins,allow_credentials=True,allow_methods=['GET','POST','PUT','PATCH','DELETE','OPTIONS'],allow_headers=['Authorization','Content-Type'])
bearer=HTTPBearer()
_password_hasher=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2,hash_len=32,salt_len=16)
def hash_password(password):
    return _password_hasher.hash(password)
def verify_password(password,stored):
    try:
        if stored.startswith('$argon2'):
            return _password_hasher.verify(stored,password)
        # Backward-compatible verification for existing installs; successful login rehashes below.
        _,salt,digest=stored.split('$',2); actual=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),200000).hex(); return hmac.compare_digest(actual,digest)
    except Exception: return False
def db():
    with Session(engine) as s: yield s
def token(user_id):
    return jwt.encode({'sub':user_id,'typ':'access','exp':now()+timedelta(minutes=int(os.getenv('ACCESS_TOKEN_MINUTES','60')))},SECRET,algorithm='HS256')
def _refresh_hash(raw:str): return hashlib.sha256(raw.encode()).hexdigest()
def issue_session(s:Session,u:User,device_name:Optional[str]=None,platform:Optional[str]=None):
    raw=secrets.token_urlsafe(48)
    row=AuthSession(user_id=u.id,refresh_hash=_refresh_hash(raw),device_name=device_name,platform=platform,expires_at=now()+timedelta(days=int(os.getenv('REFRESH_TOKEN_DAYS','180'))))
    s.add(row); s.commit(); s.refresh(row)
    return {'access_token':token(u.id),'refresh_token':raw,'session_id':row.id,'token_type':'bearer','user':{'id':u.id,'email':u.email,'name':u.name,'color':u.color}}
def me(c:HTTPAuthorizationCredentials=Depends(bearer),s:Session=Depends(db)):
    try: user_id=jwt.decode(c.credentials,SECRET,algorithms=['HS256'])['sub']
    except Exception: raise HTTPException(401,'Invalid token')
    u=s.get(User,user_id)
    if not u: raise HTTPException(401,'User not found')
    return u
def log(s,u,action,kind,eid): s.add(Activity(user_id=u.id,action=action,entity_type=kind,entity_id=eid))
def stable_color(key:str):
    palette=['#2563EB','#16A34A','#DC2626','#9333EA','#EA580C','#0891B2','#DB2777','#4F46E5','#65A30D','#B45309','#0F766E','#7C3AED']
    return palette[int(hashlib.sha256(key.encode()).hexdigest()[:8],16)%len(palette)]
def next_day_8(dt:Optional[datetime]):
    base=dt or now(); d=(base+timedelta(days=1)).date(); return datetime(d.year,d.month,d.day,8,0,tzinfo=base.tzinfo or timezone.utc)
def ensure_settings(s,user_id):
    x=s.get(UserSetting,user_id)
    if not x: x=UserSetting(user_id=user_id); s.add(x); s.flush()
    return x
def default_remind_at(target,setting):
    if not target or not setting.default_reminder_enabled: return None
    d=(target-timedelta(days=setting.default_reminder_days_before)).date()
    return datetime(d.year,d.month,d.day,setting.default_reminder_hour,setting.default_reminder_minute,tzinfo=target.tzinfo or timezone.utc)
def add_default_reminder(s,u,kind,eid,target):
    st=ensure_settings(s,u.id); at=default_remind_at(target,st)
    if at: s.add(Reminder(owner_id=u.id,entity_type=kind,entity_id=eid,remind_at=at))
def cancel_reminders(s,u,kind,eid):
    for r in s.scalars(select(Reminder).where(Reminder.owner_id==u.id,Reminder.entity_type==kind,Reminder.entity_id==eid,Reminder.status=='pending')): r.status='cancelled'
def reschedule_default(s,u,kind,eid,target):
    cancel_reminders(s,u,kind,eid); add_default_reminder(s,u,kind,eid,target)
class Register(BaseModel): email:EmailStr; name:str=Field(min_length=1,max_length=120); password:str=Field(min_length=8)
class Login(BaseModel): email:EmailStr; password:str; device_name:Optional[str]=None; platform:Optional[str]=None
class RefreshIn(BaseModel): refresh_token:str; device_name:Optional[str]=None
class LogoutIn(BaseModel): refresh_token:Optional[str]=None
class CalendarIn(BaseModel): name:str; color:str='#2563EB'
class TaskIn(BaseModel): title:str=Field(min_length=1,max_length=255); notes:Optional[str]=None; due_at:Optional[datetime]=None
class TaskPatch(BaseModel): title:Optional[str]=Field(default=None,min_length=1,max_length=255); notes:Optional[str]=None; due_at:Optional[datetime]=None
class ContinueIn(BaseModel): due_at:Optional[datetime]=None
class EventIn(BaseModel): title:str=Field(min_length=1,max_length=255); starts_at:datetime; ends_at:Optional[datetime]=None; calendar_id:Optional[str]=None
class EventPatch(BaseModel): title:Optional[str]=Field(default=None,min_length=1,max_length=255); starts_at:Optional[datetime]=None; ends_at:Optional[datetime]=None; calendar_id:Optional[str]=None
class WorkspaceIn(BaseModel): name:str
class MemberIn(BaseModel): user_id:str; role:str='editor'; color:str='#16A34A'
class ConversationIn(BaseModel): other_user_id:str
class MessageIn(BaseModel): body:str=Field(min_length=1)
class ReminderIn(BaseModel): entity_type:str; entity_id:str; remind_at:datetime; channel:str='local'
class SnoozeIn(BaseModel): minutes:int=Field(default=10,ge=1,le=10080)
class SettingsIn(BaseModel):
    timezone:str='Asia/Tehran'; default_reminder_enabled:bool=True; default_reminder_days_before:int=Field(default=1,ge=0,le=365); default_reminder_hour:int=Field(default=17,ge=0,le=23); default_reminder_minute:int=Field(default=0,ge=0,le=59)
@app.get('/health')
def health(): return {'ok':True,'version':'1.0.0'}
@app.post('/auth/register')
def register(x:Register,s:Session=Depends(db)):
    if s.scalar(select(User).where(User.email==x.email)): raise HTTPException(409,'Email exists')
    u=User(email=x.email,name=x.name,password_hash=hash_password(x.password)); s.add(u); s.flush(); c=Calendar(owner_id=u.id,name='My Calendar',color=u.color); s.add(c); s.add(UserSetting(user_id=u.id)); s.commit(); return issue_session(s,u)
@app.post('/auth/login')
def login(x:Login,s:Session=Depends(db)):
    u=s.scalar(select(User).where(User.email==x.email));
    if not u or not verify_password(x.password,u.password_hash): raise HTTPException(401,'Invalid credentials')
    if not u.password_hash.startswith('$argon2'):
        u.password_hash=hash_password(x.password); s.commit()
    return issue_session(s,u,x.device_name,x.platform)
@app.post('/auth/refresh')
def refresh_auth(x:RefreshIn,s:Session=Depends(db)):
    row=s.scalar(select(AuthSession).where(AuthSession.refresh_hash==_refresh_hash(x.refresh_token)))
    expires=row.expires_at.replace(tzinfo=timezone.utc) if row and row.expires_at and row.expires_at.tzinfo is None else (row.expires_at if row else None)
    if not row or row.revoked_at is not None or not expires or expires<=now(): raise HTTPException(401,'Refresh session expired')
    u=s.get(User,row.user_id)
    if not u: raise HTTPException(401,'User not found')
    # rotate refresh token on every use
    raw=secrets.token_urlsafe(48); row.refresh_hash=_refresh_hash(raw); row.last_used_at=now(); s.commit()
    return {'access_token':token(u.id),'refresh_token':raw,'session_id':row.id,'token_type':'bearer','user':{'id':u.id,'email':u.email,'name':u.name,'color':u.color}}
@app.post('/auth/logout')
def logout_auth(x:LogoutIn,s:Session=Depends(db)):
    if x.refresh_token:
        row=s.scalar(select(AuthSession).where(AuthSession.refresh_hash==_refresh_hash(x.refresh_token)))
        if row: row.revoked_at=now(); s.commit()
    return {'ok':True}
@app.get('/me')
def get_me(u:User=Depends(me)): return {'id':u.id,'email':u.email,'name':u.name,'color':u.color}
@app.get('/calendars')
def calendars(u:User=Depends(me),s:Session=Depends(db)): return s.scalars(select(Calendar).where(Calendar.owner_id==u.id)).all()
@app.post('/calendars')
def create_calendar(x:CalendarIn,u:User=Depends(me),s:Session=Depends(db)):
    c=Calendar(owner_id=u.id,**x.model_dump()); s.add(c); s.flush(); log(s,u,'created','calendar',c.id); s.commit(); s.refresh(c); return c
def _share_people(s:Session,kind:str,eid:str):
    rows=s.scalars(select(Share).where(Share.entity_type==kind,Share.entity_id==eid)).all() if 'Share' in globals() else []
    out=[]
    for sh in rows:
        person=s.get(User,sh.shared_with_id)
        if person: out.append({'user_id':person.id,'name':person.name,'email':person.email,'color':person.color,'permission':sh.permission})
    return out

def _item_dict(obj,kind,s):
    fields=['id','title','status','created_at','completed_at']
    if kind=='task': fields += ['notes','due_at','reminder_previous_day_17']
    else: fields += ['starts_at','ends_at','calendar_id','source','external_id']
    d={k:getattr(obj,k,None) for k in fields}
    d['shared_with']=_share_people(s,kind,obj.id)
    return d

@app.get('/tasks')
def tasks(u:User=Depends(me),s:Session=Depends(db)):
    rows=s.scalars(select(Task).where(Task.owner_id==u.id).order_by(Task.created_at.desc())).all(); return [_item_dict(x,'task',s) for x in rows]
@app.post('/tasks')
def create_task(x:TaskIn,u:User=Depends(me),s:Session=Depends(db)):
    t=Task(owner_id=u.id,**x.model_dump()); s.add(t); s.flush(); add_default_reminder(s,u,'task',t.id,t.due_at); log(s,u,'created','task',t.id); s.commit(); s.refresh(t); return t
@app.patch('/tasks/{task_id}')
def update_task(task_id:str,x:TaskPatch,u:User=Depends(me),s:Session=Depends(db)):
    t=s.get(Task,task_id)
    if not t or t.owner_id!=u.id: raise HTTPException(404,'Task not found')
    data=x.model_dump(exclude_unset=True)
    for k,v in data.items(): setattr(t,k,v)
    if 'due_at' in data: reschedule_default(s,u,'task',t.id,t.due_at)
    log(s,u,'updated','task',t.id); s.commit(); s.refresh(t); return _item_dict(t,'task',s)
@app.delete('/tasks/{task_id}')
def delete_task(task_id:str,u:User=Depends(me),s:Session=Depends(db)):
    t=s.get(Task,task_id)
    if not t or t.owner_id!=u.id: raise HTTPException(404,'Task not found')
    cancel_reminders(s,u,'task',t.id); log(s,u,'deleted','task',t.id); s.delete(t); s.commit(); return {'ok':True}
@app.post('/tasks/{task_id}/complete')
def complete_task(task_id:str,u:User=Depends(me),s:Session=Depends(db)):
    t=s.get(Task,task_id)
    if not t or t.owner_id!=u.id: raise HTTPException(404,'Task not found')
    t.status='completed'; t.completed_at=now(); cancel_reminders(s,u,'task',t.id); log(s,u,'completed','task',t.id); s.commit(); return {'ok':True,'completed_at':t.completed_at}
@app.post('/tasks/{task_id}/continue')
def continue_task(task_id:str,x:ContinueIn,u:User=Depends(me),s:Session=Depends(db)):
    t=s.get(Task,task_id)
    if not t or t.owner_id!=u.id: raise HTTPException(404,'Task not found')
    t.due_at=x.due_at or next_day_8(t.due_at); t.status='open'; t.completed_at=None; reschedule_default(s,u,'task',t.id,t.due_at); log(s,u,'continued','task',t.id); s.commit(); return {'ok':True,'due_at':t.due_at}
@app.get('/events')
def events(u:User=Depends(me),s:Session=Depends(db)):
    rows=s.scalars(select(Event).where(Event.owner_id==u.id).order_by(Event.created_at.desc())).all(); return [_item_dict(x,'event',s) for x in rows]
@app.post('/events')
def create_event(x:EventIn,u:User=Depends(me),s:Session=Depends(db)):
    if x.ends_at and x.ends_at<x.starts_at: raise HTTPException(422,'ends_at must be after starts_at')
    if x.calendar_id:
        c=s.get(Calendar,x.calendar_id)
        if not c or c.owner_id!=u.id: raise HTTPException(404,'Calendar not found')
    e=Event(owner_id=u.id,**x.model_dump()); s.add(e); s.flush(); add_default_reminder(s,u,'event',e.id,e.starts_at); log(s,u,'created','event',e.id); s.commit(); s.refresh(e); return e
@app.patch('/events/{eid}')
def update_event(eid:str,x:EventPatch,u:User=Depends(me),s:Session=Depends(db)):
    e=s.get(Event,eid)
    if not e or e.owner_id!=u.id: raise HTTPException(404,'Event not found')
    data=x.model_dump(exclude_unset=True)
    for k,v in data.items(): setattr(e,k,v)
    if e.ends_at and e.starts_at and e.ends_at<e.starts_at: raise HTTPException(422,'ends_at must be after starts_at')
    if 'starts_at' in data: reschedule_default(s,u,'event',e.id,e.starts_at)
    log(s,u,'updated','event',e.id); s.commit(); s.refresh(e); return _item_dict(e,'event',s)
@app.delete('/events/{eid}')
def delete_event(eid:str,u:User=Depends(me),s:Session=Depends(db)):
    e=s.get(Event,eid)
    if not e or e.owner_id!=u.id: raise HTTPException(404,'Event not found')
    cancel_reminders(s,u,'event',e.id); log(s,u,'deleted','event',e.id); s.delete(e); s.commit(); return {'ok':True}
@app.post('/events/{eid}/complete')
def complete_event(eid:str,u:User=Depends(me),s:Session=Depends(db)):
    e=s.get(Event,eid)
    if not e or e.owner_id!=u.id: raise HTTPException(404,'Event not found')
    e.status='completed'; e.completed_at=now(); cancel_reminders(s,u,'event',e.id); log(s,u,'completed','event',e.id); s.commit(); return {'ok':True}
@app.post('/events/{eid}/continue')
def continue_event(eid:str,x:ContinueIn,u:User=Depends(me),s:Session=Depends(db)):
    e=s.get(Event,eid)
    if not e or e.owner_id!=u.id: raise HTTPException(404,'Event not found')
    duration=(e.ends_at-e.starts_at) if e.ends_at else None; e.starts_at=x.due_at or next_day_8(e.starts_at); e.ends_at=e.starts_at+duration if duration else None; e.status='open'; e.completed_at=None; reschedule_default(s,u,'event',e.id,e.starts_at); log(s,u,'continued','event',e.id); s.commit(); return {'ok':True,'starts_at':e.starts_at,'ends_at':e.ends_at}
@app.get('/workspaces')
def workspaces(u:User=Depends(me),s:Session=Depends(db)):
    ids=select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id==u.id); return s.scalars(select(Workspace).where(Workspace.id.in_(ids))).all()
@app.get('/workspaces/summary')
def workspace_summary(u:User=Depends(me),s:Session=Depends(db)):
    ids=list(s.scalars(select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id==u.id)).all())
    out=[]
    for wid in ids:
        w=s.get(Workspace,wid)
        members=[]
        for m in s.scalars(select(WorkspaceMember).where(WorkspaceMember.workspace_id==wid)).all():
            person=s.get(User,m.user_id)
            if person: members.append({'user_id':person.id,'name':person.name,'email':person.email,'role':m.role,'color':m.color})
        docs=[]
        if 'WorkspaceDocument' in globals():
            for d in s.scalars(select(WorkspaceDocument).where(WorkspaceDocument.workspace_id==wid)).all():
                last=s.scalar(select(DocumentVersion).where(DocumentVersion.document_id==d.id).order_by(DocumentVersion.revision.desc()))
                author=s.get(User,last.author_id) if last else None
                am=membership(s,wid,last.author_id) if last else None
                docs.append({'id':d.id,'title':d.title,'revision':d.revision,'updated_at':d.updated_at,'last_editor':({'id':author.id,'name':author.name,'color':am.color if am else author.color} if author else None)})
        out.append({'id':w.id,'name':w.name,'members':members,'documents':docs})
    return out

@app.post('/workspaces')
def create_workspace(x:WorkspaceIn,u:User=Depends(me),s:Session=Depends(db)):
    w=Workspace(owner_id=u.id,name=x.name); s.add(w); s.flush(); s.add(WorkspaceMember(workspace_id=w.id,user_id=u.id,role='owner',color=u.color)); log(s,u,'created','workspace',w.id); s.commit(); return {'id':w.id,'name':w.name}
@app.post('/workspaces/{wid}/members')
def add_member(wid:str,x:MemberIn,u:User=Depends(me),s:Session=Depends(db)):
    w=s.get(Workspace,wid)
    if not w or w.owner_id!=u.id: raise HTTPException(404,'Workspace not found')
    if not s.get(User,x.user_id): raise HTTPException(404,'User not found')
    if s.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id==wid,WorkspaceMember.user_id==x.user_id)): raise HTTPException(409,'Already member')
    m=WorkspaceMember(workspace_id=wid,**x.model_dump()); s.add(m); log(s,u,'member_added','workspace',wid); s.commit(); return {'ok':True}
@app.get('/conversations')
def conversations(u:User=Depends(me),s:Session=Depends(db)):
    rows=s.scalars(select(Conversation).where(or_(Conversation.user1_id==u.id,Conversation.user2_id==u.id))).all(); out=[]
    for c in rows:
        oid=c.user2_id if c.user1_id==u.id else c.user1_id; other=s.get(User,oid)
        out.append({'id':c.id,'other':({'id':other.id,'name':other.name,'email':other.email,'color':other.color} if other else None),'created_at':c.created_at})
    return out
@app.post('/conversations')
def create_conversation(x:ConversationIn,u:User=Depends(me),s:Session=Depends(db)):
    if x.other_user_id==u.id: raise HTTPException(422,'Cannot message yourself')
    if not s.get(User,x.other_user_id): raise HTTPException(404,'User not found')
    c=s.scalar(select(Conversation).where(or_((Conversation.user1_id==u.id)&(Conversation.user2_id==x.other_user_id),(Conversation.user1_id==x.other_user_id)&(Conversation.user2_id==u.id))))
    if not c: c=Conversation(user1_id=u.id,user2_id=x.other_user_id); s.add(c); s.commit(); s.refresh(c)
    return {'id':c.id}
@app.get('/conversations/{cid}/messages')
def messages(cid:str,u:User=Depends(me),s:Session=Depends(db)):
    c=s.get(Conversation,cid)
    if not c or u.id not in (c.user1_id,c.user2_id): raise HTTPException(404,'Conversation not found')
    return s.scalars(select(Message).where(Message.conversation_id==cid).order_by(Message.sent_at)).all()
@app.post('/conversations/{cid}/messages')
def send_message(cid:str,x:MessageIn,u:User=Depends(me),s:Session=Depends(db)):
    c=s.get(Conversation,cid)
    if not c or u.id not in (c.user1_id,c.user2_id): raise HTTPException(404,'Conversation not found')
    m=Message(conversation_id=cid,sender_id=u.id,body=x.body); s.add(m); s.flush()
    recipient_id=c.user2_id if c.user1_id==u.id else c.user1_id
    emit_notification(s,recipient_id,'message','پیام جدید',f'{u.name}: {x.body[:120]}','conversation',cid,{'conversation_id':cid,'message_id':m.id})
    s.commit(); s.refresh(m); return m
@app.get('/activity')
def activity(u:User=Depends(me),s:Session=Depends(db)): return s.scalars(select(Activity).where(Activity.user_id==u.id).order_by(Activity.created_at.desc()).limit(100)).all()

@app.get('/settings')
def get_settings(u:User=Depends(me),s:Session=Depends(db)):
    return ensure_settings(s,u.id)
@app.put('/settings')
def put_settings(x:SettingsIn,u:User=Depends(me),s:Session=Depends(db)):
    st=ensure_settings(s,u.id)
    for k,v in x.model_dump().items(): setattr(st,k,v)
    log(s,u,'updated','settings',u.id); s.commit(); s.refresh(st); return st
@app.get('/reminders')
def reminders(status:Optional[str]=None,u:User=Depends(me),s:Session=Depends(db)):
    q=select(Reminder).where(Reminder.owner_id==u.id)
    if status: q=q.where(Reminder.status==status)
    return s.scalars(q.order_by(Reminder.remind_at)).all()
@app.post('/reminders')
def create_reminder(x:ReminderIn,u:User=Depends(me),s:Session=Depends(db)):
    if x.entity_type not in ('task','event'): raise HTTPException(422,'entity_type must be task or event')
    obj=s.get(Task if x.entity_type=='task' else Event,x.entity_id)
    if not obj or obj.owner_id!=u.id: raise HTTPException(404,'Item not found')
    r=Reminder(owner_id=u.id,**x.model_dump()); s.add(r); s.flush(); log(s,u,'created','reminder',r.id); s.commit(); s.refresh(r); return r
@app.post('/reminders/{rid}/snooze')
def snooze(rid:str,x:SnoozeIn,u:User=Depends(me),s:Session=Depends(db)):
    r=s.get(Reminder,rid)
    if not r or r.owner_id!=u.id: raise HTTPException(404,'Reminder not found')
    r.remind_at=now()+timedelta(minutes=x.minutes); r.status='pending'; r.sent_at=None; log(s,u,'snoozed','reminder',r.id); s.commit(); return {'ok':True,'remind_at':r.remind_at}
@app.post('/reminders/{rid}/cancel')
def cancel_reminder(rid:str,u:User=Depends(me),s:Session=Depends(db)):
    r=s.get(Reminder,rid)
    if not r or r.owner_id!=u.id: raise HTTPException(404,'Reminder not found')
    r.status='cancelled'; log(s,u,'cancelled','reminder',r.id); s.commit(); return {'ok':True}
@app.post('/reminders/dispatch-due')
def dispatch_due(u:User=Depends(me),s:Session=Depends(db)):
    due=s.scalars(select(Reminder).where(Reminder.owner_id==u.id,Reminder.status=='pending',Reminder.remind_at<=now())).all()
    out=[]
    for r in due:
        obj=s.get(Task if r.entity_type=='task' else Event,r.entity_id)
        title=getattr(obj,'title','موعد برنامه') if obj else 'موعد برنامه'
        emit_notification(s,u.id,'reminder','یادآوری موعد',title,r.entity_type,r.entity_id,{'reminder_id':r.id})
        r.status='sent'; r.sent_at=now(); out.append({'id':r.id,'entity_type':r.entity_type,'entity_id':r.entity_id,'channel':'push+local'})
    s.commit(); return {'count':len(out),'notifications':out}

# ---- Phase 4: Google Calendar + external/device sync foundation ----
import json
from urllib.parse import urlencode
import httpx

class SyncAccount(Base):
    __tablename__='sync_accounts'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    provider:Mapped[str]=mapped_column(String(30),index=True)
    provider_account_id:Mapped[Optional[str]]=mapped_column(String(255),nullable=True)
    email:Mapped[Optional[str]]=mapped_column(String(255),nullable=True)
    access_token:Mapped[Optional[str]]=mapped_column(Text,nullable=True)
    refresh_token:Mapped[Optional[str]]=mapped_column(Text,nullable=True)
    token_expires_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    sync_enabled:Mapped[bool]=mapped_column(Boolean,default=True)
    last_synced_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ExternalEventMap(Base):
    __tablename__='external_event_maps'
    __table_args__=(UniqueConstraint('account_id','external_calendar_id','external_event_id'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    account_id:Mapped[str]=mapped_column(ForeignKey('sync_accounts.id'),index=True)
    event_id:Mapped[str]=mapped_column(ForeignKey('events.id'),index=True)
    external_calendar_id:Mapped[str]=mapped_column(String(255))
    external_event_id:Mapped[str]=mapped_column(String(255))
    etag:Mapped[Optional[str]]=mapped_column(String(255),nullable=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
Base.metadata.create_all(engine)

class DeviceSyncEventIn(BaseModel):
    device_calendar_id:str
    device_event_id:str
    title:str
    starts_at:datetime
    ends_at:Optional[datetime]=None
    updated_at:Optional[datetime]=None

@app.get('/sync/accounts')
def sync_accounts(u:User=Depends(me),s:Session=Depends(db)):
    rows=s.scalars(select(SyncAccount).where(SyncAccount.owner_id==u.id)).all()
    return [{'id':x.id,'provider':x.provider,'email':x.email,'sync_enabled':x.sync_enabled,'last_synced_at':x.last_synced_at,'connected':bool(x.refresh_token or x.access_token)} for x in rows]

def google_cfg():
    cid=os.getenv('GOOGLE_CLIENT_ID'); secret=os.getenv('GOOGLE_CLIENT_SECRET'); redirect=os.getenv('GOOGLE_REDIRECT_URI')
    if not cid or not secret or not redirect: raise HTTPException(503,'Google Calendar is not configured on this server')
    return cid,secret,redirect

@app.get('/sync/google/connect')
def google_connect(u:User=Depends(me)):
    cid,_,redirect=google_cfg()
    state=jwt.encode({'sub':u.id,'purpose':'google_oauth','exp':now()+timedelta(minutes=10)},SECRET,algorithm='HS256')
    q=urlencode({'client_id':cid,'redirect_uri':redirect,'response_type':'code','scope':'openid email https://www.googleapis.com/auth/calendar','access_type':'offline','prompt':'consent','state':state})
    return {'authorization_url':'https://accounts.google.com/o/oauth2/v2/auth?'+q}

@app.get('/sync/google/callback')
def google_callback(code:str,state:str,s:Session=Depends(db)):
    cid,secret,redirect=google_cfg()
    try:
        p=jwt.decode(state,SECRET,algorithms=['HS256']); assert p.get('purpose')=='google_oauth'; user_id=p['sub']
    except Exception: raise HTTPException(400,'Invalid OAuth state')
    with httpx.Client(timeout=20) as h:
        tr=h.post('https://oauth2.googleapis.com/token',data={'code':code,'client_id':cid,'client_secret':secret,'redirect_uri':redirect,'grant_type':'authorization_code'})
        if tr.status_code>=400: raise HTTPException(400,'Google token exchange failed')
        tok=tr.json(); info=h.get('https://www.googleapis.com/oauth2/v2/userinfo',headers={'Authorization':'Bearer '+tok['access_token']}).json()
    a=s.scalar(select(SyncAccount).where(SyncAccount.owner_id==user_id,SyncAccount.provider=='google'))
    if not a: a=SyncAccount(owner_id=user_id,provider='google'); s.add(a)
    a.provider_account_id=info.get('id'); a.email=info.get('email'); a.access_token=tok.get('access_token'); a.refresh_token=tok.get('refresh_token') or a.refresh_token; a.token_expires_at=now()+timedelta(seconds=tok.get('expires_in',3600)); a.sync_enabled=True
    s.commit(); return {'ok':True,'email':a.email,'message':'Google Calendar connected. You may close this window.'}

def google_access(a:SyncAccount,s:Session):
    if a.access_token and (not a.token_expires_at or a.token_expires_at>now()+timedelta(minutes=2)): return a.access_token
    cid,secret,_=google_cfg()
    if not a.refresh_token: raise HTTPException(401,'Google account needs reconnect')
    r=httpx.post('https://oauth2.googleapis.com/token',data={'client_id':cid,'client_secret':secret,'refresh_token':a.refresh_token,'grant_type':'refresh_token'},timeout=20)
    if r.status_code>=400: raise HTTPException(502,'Google token refresh failed')
    d=r.json(); a.access_token=d['access_token']; a.token_expires_at=now()+timedelta(seconds=d.get('expires_in',3600)); s.commit(); return a.access_token

@app.delete('/sync/google')
def google_disconnect(u:User=Depends(me),s:Session=Depends(db)):
    a=s.scalar(select(SyncAccount).where(SyncAccount.owner_id==u.id,SyncAccount.provider=='google'))
    if a: s.delete(a); log(s,u,'disconnected','sync',a.id); s.commit()
    return {'ok':True}

@app.post('/sync/google/run')
def google_sync(u:User=Depends(me),s:Session=Depends(db)):
    a=s.scalar(select(SyncAccount).where(SyncAccount.owner_id==u.id,SyncAccount.provider=='google',SyncAccount.sync_enabled==True))
    if not a: raise HTTPException(404,'Google Calendar is not connected')
    access=google_access(a,s); headers={'Authorization':'Bearer '+access}
    imported=updated=0
    with httpx.Client(timeout=30,headers=headers) as h:
        cr=h.get('https://www.googleapis.com/calendar/v3/users/me/calendarList')
        if cr.status_code>=400: raise HTTPException(502,'Google Calendar request failed')
        for gc in cr.json().get('items',[]):
            gid=gc['id']; cal=s.scalar(select(Calendar).where(Calendar.owner_id==u.id,Calendar.source=='google',Calendar.name==gc.get('summary','Google Calendar')))
            if not cal: cal=Calendar(owner_id=u.id,name=gc.get('summary','Google Calendar'),source='google',color=gc.get('backgroundColor','#4285F4')); s.add(cal); s.flush()
            er=h.get('https://www.googleapis.com/calendar/v3/calendars/'+httpx.URL('').copy_with(path=gid).path+'/events',params={'singleEvents':'true','maxResults':250,'timeMin':(now()-timedelta(days=90)).isoformat().replace('+00:00','Z')})
            if er.status_code>=400: continue
            for ge in er.json().get('items',[]):
                if ge.get('status')=='cancelled': continue
                start=ge.get('start',{}).get('dateTime') or ge.get('start',{}).get('date'); end=ge.get('end',{}).get('dateTime') or ge.get('end',{}).get('date')
                if not start: continue
                def pdt(v):
                    if len(v)==10: return datetime.fromisoformat(v+'T00:00:00+00:00')
                    return datetime.fromisoformat(v.replace('Z','+00:00'))
                m=s.scalar(select(ExternalEventMap).where(ExternalEventMap.account_id==a.id,ExternalEventMap.external_calendar_id==gid,ExternalEventMap.external_event_id==ge['id']))
                if m:
                    ev=s.get(Event,m.event_id); ev.title=ge.get('summary','(بدون عنوان)'); ev.starts_at=pdt(start); ev.ends_at=pdt(end) if end else None; m.etag=ge.get('etag'); m.updated_at=now(); updated+=1
                else:
                    ev=Event(owner_id=u.id,calendar_id=cal.id,title=ge.get('summary','(بدون عنوان)'),starts_at=pdt(start),ends_at=pdt(end) if end else None,source='google',external_id=ge['id']); s.add(ev); s.flush(); s.add(ExternalEventMap(account_id=a.id,event_id=ev.id,external_calendar_id=gid,external_event_id=ge['id'],etag=ge.get('etag'))); imported+=1
    a.last_synced_at=now(); log(s,u,'synced','google_calendar',a.id); s.commit(); return {'ok':True,'imported':imported,'updated':updated,'last_synced_at':a.last_synced_at}

@app.post('/sync/device/events')
def device_event_upsert(x:DeviceSyncEventIn,u:User=Depends(me),s:Session=Depends(db)):
    # Mobile/Windows native clients use this idempotent endpoint; repeated device events never duplicate.
    account=s.scalar(select(SyncAccount).where(SyncAccount.owner_id==u.id,SyncAccount.provider=='device'))
    if not account: account=SyncAccount(owner_id=u.id,provider='device',provider_account_id='local-device'); s.add(account); s.flush()
    m=s.scalar(select(ExternalEventMap).where(ExternalEventMap.account_id==account.id,ExternalEventMap.external_calendar_id==x.device_calendar_id,ExternalEventMap.external_event_id==x.device_event_id))
    if m:
        e=s.get(Event,m.event_id); e.title=x.title; e.starts_at=x.starts_at; e.ends_at=x.ends_at; m.updated_at=now(); created=False
    else:
        cal=s.scalar(select(Calendar).where(Calendar.owner_id==u.id,Calendar.source=='device'))
        if not cal: cal=Calendar(owner_id=u.id,name='تقویم دستگاه',source='device',color='#64748B'); s.add(cal); s.flush()
        e=Event(owner_id=u.id,calendar_id=cal.id,title=x.title,starts_at=x.starts_at,ends_at=x.ends_at,source='device',external_id=x.device_event_id); s.add(e); s.flush(); s.add(ExternalEventMap(account_id=account.id,event_id=e.id,external_calendar_id=x.device_calendar_id,external_event_id=x.device_event_id)); created=True
    account.last_synced_at=now(); s.commit(); return {'ok':True,'event_id':e.id,'created':created}

# ---- Final integrated modules: SMS automation, periodic sync, sharing, collaborative workspace ----
from sqlalchemy import JSON
class SmsRule(Base):
    __tablename__='sms_rules'; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True); sender_contains:Mapped[Optional[str]]=mapped_column(String(120),nullable=True); keyword:Mapped[Optional[str]]=mapped_column(String(120),nullable=True); action:Mapped[str]=mapped_column(String(20),default='suggest'); enabled:Mapped[bool]=mapped_column(Boolean,default=True)
class SmsSuggestion(Base):
    __tablename__='sms_suggestions'; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True); sender:Mapped[str]=mapped_column(String(120)); body:Mapped[str]=mapped_column(Text); suggested_type:Mapped[str]=mapped_column(String(20),default='task'); title:Mapped[str]=mapped_column(String(255)); due_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True); status:Mapped[str]=mapped_column(String(20),default='suggested'); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Share(Base):
    __tablename__='shares'; __table_args__=(UniqueConstraint('entity_type','entity_id','shared_with_id'),); id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True); entity_type:Mapped[str]=mapped_column(String(30)); entity_id:Mapped[str]=mapped_column(String(36)); shared_with_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True); permission:Mapped[str]=mapped_column(String(20),default='viewer'); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class WorkspaceDocument(Base):
    __tablename__='workspace_documents'; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); workspace_id:Mapped[str]=mapped_column(ForeignKey('workspaces.id'),index=True); creator_id:Mapped[str]=mapped_column(ForeignKey('users.id')); title:Mapped[str]=mapped_column(String(255)); content:Mapped[str]=mapped_column(Text,default=''); revision:Mapped[int]=mapped_column(Integer,default=0); updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class DocumentVersion(Base):
    __tablename__='document_versions'; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); document_id:Mapped[str]=mapped_column(ForeignKey('workspace_documents.id'),index=True); author_id:Mapped[str]=mapped_column(ForeignKey('users.id')); revision:Mapped[int]=mapped_column(Integer); content:Mapped[str]=mapped_column(Text); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class DocumentComment(Base):
    __tablename__='document_comments'; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); document_id:Mapped[str]=mapped_column(ForeignKey('workspace_documents.id'),index=True); author_id:Mapped[str]=mapped_column(ForeignKey('users.id')); body:Mapped[str]=mapped_column(Text); anchor:Mapped[Optional[str]]=mapped_column(String(255),nullable=True); resolved:Mapped[bool]=mapped_column(Boolean,default=False); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class SyncPreference(Base):
    __tablename__='sync_preferences'; user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),primary_key=True); interval_hours:Mapped[int]=mapped_column(Integer,default=6); sync_on_open:Mapped[bool]=mapped_column(Boolean,default=True); sync_on_change:Mapped[bool]=mapped_column(Boolean,default=True); last_scheduler_run:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
Base.metadata.create_all(engine)

class SmsRuleIn(BaseModel): sender_contains:Optional[str]=None; keyword:Optional[str]=None; action:str='suggest'; enabled:bool=True
class SmsIn(BaseModel): sender:str; body:str; received_at:Optional[datetime]=None
class ShareIn(BaseModel): entity_type:str; entity_id:str; shared_with_id:str; permission:str='viewer'
class DocIn(BaseModel): title:str=Field(min_length=1,max_length=255); content:str=''
class DocUpdate(BaseModel): content:str; base_revision:int
class CommentIn(BaseModel): body:str=Field(min_length=1); anchor:Optional[str]=None
class SyncPrefIn(BaseModel): interval_hours:int=Field(default=6,ge=0,le=24); sync_on_open:bool=True; sync_on_change:bool=True

def membership(s,wid,uid_): return s.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id==wid,WorkspaceMember.user_id==uid_))
def doc_access(s,did,uid_):
    d=s.get(WorkspaceDocument,did)
    if not d or not membership(s,d.workspace_id,uid_): raise HTTPException(404,'Document not found')
    return d

@app.get('/sms/rules')
def sms_rules(u:User=Depends(me),s:Session=Depends(db)): return s.scalars(select(SmsRule).where(SmsRule.owner_id==u.id)).all()
@app.post('/sms/rules')
def sms_rule_create(x:SmsRuleIn,u:User=Depends(me),s:Session=Depends(db)):
    r=SmsRule(owner_id=u.id,**x.model_dump()); s.add(r); s.commit(); s.refresh(r); return r
@app.post('/sms/analyze')
def sms_analyze(x:SmsIn,u:User=Depends(me),s:Session=Depends(db)):
    rules=s.scalars(select(SmsRule).where(SmsRule.owner_id==u.id,SmsRule.enabled==True)).all(); matched=None
    for r in rules:
        if (not r.sender_contains or r.sender_contains.lower() in x.sender.lower()) and (not r.keyword or r.keyword.lower() in x.body.lower()): matched=r; break
    if matched and matched.action=='ignore': return {'status':'ignored'}
    # privacy-first deterministic extraction; an external AI provider can be added only after opt-in.
    title=x.body.strip().replace('\n',' ')[:255] or 'SMS'; sug=SmsSuggestion(owner_id=u.id,sender=x.sender,body=x.body,title=title,suggested_type='task'); s.add(sug); s.commit(); s.refresh(sug); return {'status':'suggested','suggestion_id':sug.id,'title':sug.title,'type':sug.suggested_type}
@app.post('/sms/suggestions/{sid}/accept')
def sms_accept(sid:str,u:User=Depends(me),s:Session=Depends(db)):
    x=s.get(SmsSuggestion,sid)
    if not x or x.owner_id!=u.id: raise HTTPException(404,'Suggestion not found')
    t=Task(owner_id=u.id,title=x.title,due_at=x.due_at); s.add(t); s.flush(); x.status='accepted'; log(s,u,'accepted','sms_suggestion',x.id); s.commit(); return {'ok':True,'task_id':t.id}

@app.post('/shares')
def share_create(x:ShareIn,u:User=Depends(me),s:Session=Depends(db)):
    if x.permission not in ('viewer','editor'): raise HTTPException(422,'Invalid permission')
    model={'task':Task,'event':Event,'calendar':Calendar}.get(x.entity_type)
    obj=s.get(model,x.entity_id) if model else None
    if not obj or obj.owner_id!=u.id: raise HTTPException(404,'Item not found')
    if not s.get(User,x.shared_with_id): raise HTTPException(404,'User not found')
    existing=s.scalar(select(Share).where(Share.entity_type==x.entity_type,Share.entity_id==x.entity_id,Share.shared_with_id==x.shared_with_id))
    if existing:
        existing.permission=x.permission; sh=existing
    else:
        sh=Share(owner_id=u.id,**x.model_dump()); s.add(sh)
    s.flush(); emit_notification(s,x.shared_with_id,'share','مورد جدید با شما به اشتراک گذاشته شد',f'{u.name} یک {x.entity_type} را با شما به اشتراک گذاشت.','share',sh.id,{'entity_type':x.entity_type,'entity_id':x.entity_id,'permission':x.permission})
    s.commit(); s.refresh(sh); return sh
@app.get('/shares/with-me')
def shared_with_me(u:User=Depends(me),s:Session=Depends(db)): return s.scalars(select(Share).where(Share.shared_with_id==u.id)).all()

@app.post('/workspaces/{wid}/documents')
def doc_create(wid:str,x:DocIn,u:User=Depends(me),s:Session=Depends(db)):
    m=membership(s,wid,u.id)
    if not m or m.role=='viewer': raise HTTPException(403,'Editor access required')
    d=WorkspaceDocument(workspace_id=wid,creator_id=u.id,title=x.title,content=x.content); s.add(d); s.flush(); s.add(DocumentVersion(document_id=d.id,author_id=u.id,revision=0,content=x.content)); log(s,u,'created','document',d.id); s.commit(); return {'id':d.id,'title':d.title,'content':d.content,'revision':d.revision}
@app.get('/workspaces/{wid}/documents')
def doc_list(wid:str,u:User=Depends(me),s:Session=Depends(db)):
    if not membership(s,wid,u.id): raise HTTPException(404,'Workspace not found')
    return s.scalars(select(WorkspaceDocument).where(WorkspaceDocument.workspace_id==wid)).all()
@app.put('/documents/{did}')
def doc_update(did:str,x:DocUpdate,u:User=Depends(me),s:Session=Depends(db)):
    d=doc_access(s,did,u.id); m=membership(s,d.workspace_id,u.id)
    if m.role=='viewer': raise HTTPException(403,'Editor access required')
    if x.base_revision!=d.revision: raise HTTPException(409,detail={'message':'revision conflict','current_revision':d.revision,'content':d.content})
    d.revision+=1; d.content=x.content; d.updated_at=now(); s.add(DocumentVersion(document_id=d.id,author_id=u.id,revision=d.revision,content=d.content)); log(s,u,'updated','document',d.id)
    for wm in s.scalars(select(WorkspaceMember).where(WorkspaceMember.workspace_id==d.workspace_id,WorkspaceMember.user_id!=u.id)).all():
        emit_notification(s,wm.user_id,'workspace','فضای کار به‌روزرسانی شد',f'{u.name} سند «{d.title}» را ویرایش کرد.','document',d.id,{'workspace_id':d.workspace_id,'document_id':d.id,'revision':d.revision,'actor_color':m.color})
    s.commit(); return {'ok':True,'revision':d.revision,'author_id':u.id,'author_name':u.name,'author_color':m.color}
@app.get('/documents/{did}/versions')
def doc_versions(did:str,u:User=Depends(me),s:Session=Depends(db)):
    doc_access(s,did,u.id); return s.scalars(select(DocumentVersion).where(DocumentVersion.document_id==did).order_by(DocumentVersion.revision.desc())).all()
@app.post('/documents/{did}/comments')
def comment_create(did:str,x:CommentIn,u:User=Depends(me),s:Session=Depends(db)):
    d=doc_access(s,did,u.id); c=DocumentComment(document_id=did,author_id=u.id,**x.model_dump()); s.add(c); s.flush(); m=membership(s,d.workspace_id,u.id)
    for wm in s.scalars(select(WorkspaceMember).where(WorkspaceMember.workspace_id==d.workspace_id,WorkspaceMember.user_id!=u.id)).all():
        emit_notification(s,wm.user_id,'workspace_comment','نظر جدید در فضای کار',f'{u.name}: {x.body[:120]}','document',did,{'workspace_id':d.workspace_id,'document_id':did,'comment_id':c.id,'actor_color':m.color})
    s.commit(); s.refresh(c); return {'id':c.id,'document_id':did,'author_id':u.id,'author_name':u.name,'author_color':m.color,'body':c.body,'anchor':c.anchor,'resolved':c.resolved,'created_at':c.created_at}

@app.get('/sync/preferences')
def sync_pref(u:User=Depends(me),s:Session=Depends(db)):
    p=s.get(SyncPreference,u.id)
    if not p: p=SyncPreference(user_id=u.id); s.add(p); s.commit(); s.refresh(p)
    return p
@app.put('/sync/preferences')
def sync_pref_put(x:SyncPrefIn,u:User=Depends(me),s:Session=Depends(db)):
    p=s.get(SyncPreference,u.id) or SyncPreference(user_id=u.id); p.interval_hours=x.interval_hours; p.sync_on_open=x.sync_on_open; p.sync_on_change=x.sync_on_change; s.add(p); s.commit(); s.refresh(p); return p
@app.post('/internal/scheduler/tick')
def scheduler_tick(x_internal_key:Optional[str]=Header(default=None),s:Session=Depends(db)):
    key=os.getenv('SCHEDULER_KEY','')
    if not key or not hmac.compare_digest(x_internal_key or '',key): raise HTTPException(403,'Invalid internal key')
    due=0
    for p in s.scalars(select(SyncPreference).where(SyncPreference.interval_hours>0)).all():
        if not p.last_scheduler_run or p.last_scheduler_run<=now()-timedelta(hours=p.interval_hours): p.last_scheduler_run=now(); due+=1
    s.commit(); return {'ok':True,'accounts_due':due}


# ---- Unified collaboration visibility, notifications and voice calls ----
from sqlalchemy import JSON

class DeviceToken(Base):
    __tablename__='device_tokens'; __table_args__=(UniqueConstraint('owner_id','token'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    token:Mapped[str]=mapped_column(Text)
    platform:Mapped[str]=mapped_column(String(20),default='android')
    device_name:Mapped[Optional[str]]=mapped_column(String(120),nullable=True)
    enabled:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    last_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Notification(Base):
    __tablename__='notifications'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    kind:Mapped[str]=mapped_column(String(40),index=True)
    title:Mapped[str]=mapped_column(String(180))
    body:Mapped[str]=mapped_column(Text)
    entity_type:Mapped[Optional[str]]=mapped_column(String(40),nullable=True)
    entity_id:Mapped[Optional[str]]=mapped_column(String(36),nullable=True)
    data_json:Mapped[Optional[str]]=mapped_column(Text,nullable=True)
    status:Mapped[str]=mapped_column(String(20),default='queued',index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    pushed_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    read_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)

class VoiceCall(Base):
    __tablename__='voice_calls'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    conversation_id:Mapped[str]=mapped_column(ForeignKey('conversations.id'),index=True)
    caller_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    callee_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    status:Mapped[str]=mapped_column(String(20),default='ringing',index=True)
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    answered_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    ended_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)

class CallSignal(Base):
    __tablename__='call_signals'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    call_id:Mapped[str]=mapped_column(ForeignKey('voice_calls.id'),index=True)
    sender_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    kind:Mapped[str]=mapped_column(String(20))
    payload:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

Base.metadata.create_all(engine)

class DeviceTokenIn(BaseModel):
    token:str=Field(min_length=8)
    platform:str='android'
    device_name:Optional[str]=None
class CallSignalIn(BaseModel):
    kind:str
    payload:str

def emit_notification(s:Session,user_id:str,kind:str,title:str,body:str,entity_type:Optional[str]=None,entity_id:Optional[str]=None,data:Optional[dict]=None):
    n=Notification(owner_id=user_id,kind=kind,title=title,body=body,entity_type=entity_type,entity_id=entity_id,data_json=json.dumps(data or {},ensure_ascii=False))
    s.add(n); return n

def conversation_for(s:Session,cid:str,uid_:str):
    c=s.get(Conversation,cid)
    if not c or uid_ not in (c.user1_id,c.user2_id): raise HTTPException(404,'Conversation not found')
    return c

def call_for(s:Session,call_id:str,uid_:str):
    call=s.get(VoiceCall,call_id)
    if not call or uid_ not in (call.caller_id,call.callee_id): raise HTTPException(404,'Call not found')
    return call

@app.get('/workspaces/{wid}/members/detail')
def workspace_members_detail(wid:str,u:User=Depends(me),s:Session=Depends(db)):
    if not membership(s,wid,u.id): raise HTTPException(404,'Workspace not found')
    rows=s.execute(select(WorkspaceMember,User).join(User,User.id==WorkspaceMember.user_id).where(WorkspaceMember.workspace_id==wid)).all()
    return [{'user_id':m.user_id,'name':usr.name,'email':usr.email,'role':m.role,'color':m.color} for m,usr in rows]

@app.get('/documents/{did}/versions/detail')
def doc_versions_detail(did:str,u:User=Depends(me),s:Session=Depends(db)):
    d=doc_access(s,did,u.id)
    rows=s.execute(select(DocumentVersion,User,WorkspaceMember).join(User,User.id==DocumentVersion.author_id).join(WorkspaceMember,(WorkspaceMember.user_id==DocumentVersion.author_id)&(WorkspaceMember.workspace_id==d.workspace_id)).where(DocumentVersion.document_id==did).order_by(DocumentVersion.revision.desc())).all()
    return [{'id':v.id,'revision':v.revision,'content':v.content,'created_at':v.created_at,'author':{'id':usr.id,'name':usr.name,'color':wm.color}} for v,usr,wm in rows]

@app.get('/documents/{did}/comments/detail')
def doc_comments_detail(did:str,u:User=Depends(me),s:Session=Depends(db)):
    d=doc_access(s,did,u.id)
    rows=s.execute(select(DocumentComment,User,WorkspaceMember).join(User,User.id==DocumentComment.author_id).join(WorkspaceMember,(WorkspaceMember.user_id==DocumentComment.author_id)&(WorkspaceMember.workspace_id==d.workspace_id)).where(DocumentComment.document_id==did).order_by(DocumentComment.created_at)).all()
    return [{'id':c.id,'body':c.body,'anchor':c.anchor,'resolved':c.resolved,'created_at':c.created_at,'author':{'id':usr.id,'name':usr.name,'color':wm.color}} for c,usr,wm in rows]

@app.get('/conversations/{cid}/messages/detail')
def message_detail(cid:str,u:User=Depends(me),s:Session=Depends(db)):
    conversation_for(s,cid,u.id)
    rows=s.execute(select(Message,User).join(User,User.id==Message.sender_id).where(Message.conversation_id==cid).order_by(Message.sent_at)).all()
    return [{'id':m.id,'body':m.body,'sent_at':m.sent_at,'seen_at':m.seen_at,'sender':{'id':usr.id,'name':usr.name,'color':usr.color}} for m,usr in rows]

@app.get('/shares/entity/{entity_type}/{entity_id}')
def shares_for_entity(entity_type:str,entity_id:str,u:User=Depends(me),s:Session=Depends(db)):
    model={'task':Task,'event':Event,'calendar':Calendar}.get(entity_type)
    obj=s.get(model,entity_id) if model else None
    if not obj or obj.owner_id!=u.id: raise HTTPException(404,'Item not found')
    rows=s.execute(select(Share,User).join(User,User.id==Share.shared_with_id).where(Share.owner_id==u.id,Share.entity_type==entity_type,Share.entity_id==entity_id)).all()
    return [{'share_id':sh.id,'permission':sh.permission,'shared_at':sh.created_at,'user':{'id':usr.id,'name':usr.name,'email':usr.email,'color':usr.color}} for sh,usr in rows]

@app.delete('/shares/{share_id}')
def share_delete(share_id:str,u:User=Depends(me),s:Session=Depends(db)):
    sh=s.get(Share,share_id)
    if not sh or sh.owner_id!=u.id: raise HTTPException(404,'Share not found')
    s.delete(sh); s.commit(); return {'ok':True}

@app.post('/devices/push-token')
def register_push_token(x:DeviceTokenIn,u:User=Depends(me),s:Session=Depends(db)):
    d=s.scalar(select(DeviceToken).where(DeviceToken.owner_id==u.id,DeviceToken.token==x.token))
    if not d: d=DeviceToken(owner_id=u.id,token=x.token,platform=x.platform,device_name=x.device_name); s.add(d)
    d.enabled=True; d.platform=x.platform; d.device_name=x.device_name; d.last_seen_at=now(); s.commit(); s.refresh(d); return {'ok':True,'device_id':d.id}

@app.delete('/devices/push-token/{device_id}')
def unregister_push_token(device_id:str,u:User=Depends(me),s:Session=Depends(db)):
    d=s.get(DeviceToken,device_id)
    if not d or d.owner_id!=u.id: raise HTTPException(404,'Device not found')
    d.enabled=False; s.commit(); return {'ok':True}

@app.get('/notifications')
def notification_list(unread_only:bool=False,u:User=Depends(me),s:Session=Depends(db)):
    q=select(Notification).where(Notification.owner_id==u.id)
    if unread_only: q=q.where(Notification.read_at==None)
    rows=s.scalars(q.order_by(Notification.created_at.desc()).limit(200)).all()
    return [{'id':n.id,'kind':n.kind,'title':n.title,'body':n.body,'entity_type':n.entity_type,'entity_id':n.entity_id,'data':json.loads(n.data_json or '{}'),'status':n.status,'created_at':n.created_at,'read_at':n.read_at} for n in rows]

@app.post('/notifications/{nid}/read')
def notification_read(nid:str,u:User=Depends(me),s:Session=Depends(db)):
    n=s.get(Notification,nid)
    if not n or n.owner_id!=u.id: raise HTTPException(404,'Notification not found')
    n.read_at=now(); s.commit(); return {'ok':True}

@app.post('/conversations/{cid}/calls')
def call_start(cid:str,u:User=Depends(me),s:Session=Depends(db)):
    c=conversation_for(s,cid,u.id); other=c.user2_id if c.user1_id==u.id else c.user1_id
    call=VoiceCall(conversation_id=cid,caller_id=u.id,callee_id=other); s.add(call); s.flush()
    emit_notification(s,other,'incoming_call','تماس صوتی ورودی',f'{u.name} با شما تماس می‌گیرد.','voice_call',call.id,{'conversation_id':cid,'call_id':call.id})
    s.commit(); s.refresh(call); return {'id':call.id,'status':call.status,'caller_id':call.caller_id,'callee_id':call.callee_id}

@app.post('/calls/{call_id}/answer')
def call_answer(call_id:str,u:User=Depends(me),s:Session=Depends(db)):
    call=call_for(s,call_id,u.id)
    if u.id!=call.callee_id: raise HTTPException(403,'Only callee can answer')
    if call.status!='ringing': raise HTTPException(409,'Call is not ringing')
    call.status='active'; call.answered_at=now(); emit_notification(s,call.caller_id,'call_answered','تماس پاسخ داده شد',u.name,'voice_call',call.id,{'call_id':call.id}); s.commit(); return {'ok':True,'status':call.status}

@app.post('/calls/{call_id}/end')
def call_end(call_id:str,u:User=Depends(me),s:Session=Depends(db)):
    call=call_for(s,call_id,u.id); call.status='ended'; call.ended_at=now(); other=call.callee_id if u.id==call.caller_id else call.caller_id
    emit_notification(s,other,'call_ended','تماس پایان یافت',u.name,'voice_call',call.id,{'call_id':call.id}); s.commit(); return {'ok':True,'status':'ended'}

@app.post('/calls/{call_id}/signals')
def call_signal(call_id:str,x:CallSignalIn,u:User=Depends(me),s:Session=Depends(db)):
    call_for(s,call_id,u.id)
    if x.kind not in ('offer','answer','ice'): raise HTTPException(422,'Invalid signal kind')
    sig=CallSignal(call_id=call_id,sender_id=u.id,kind=x.kind,payload=x.payload); s.add(sig); s.commit(); s.refresh(sig); return {'id':sig.id,'kind':sig.kind}

@app.get('/calls/{call_id}/signals')
def call_signals(call_id:str,after:Optional[datetime]=None,u:User=Depends(me),s:Session=Depends(db)):
    call_for(s,call_id,u.id); q=select(CallSignal).where(CallSignal.call_id==call_id,CallSignal.sender_id!=u.id)
    if after: q=q.where(CallSignal.created_at>after)
    return s.scalars(q.order_by(CallSignal.created_at)).all()

@app.post('/internal/push/dispatch')
def push_dispatch(x_internal_key:Optional[str]=Header(default=None),s:Session=Depends(db)):
    key=os.getenv('SCHEDULER_KEY','')
    if not key or not hmac.compare_digest(x_internal_key or '',key): raise HTTPException(403,'Invalid internal key')
    # Firebase HTTP v1 is optional at runtime. Notifications remain queued when credentials are absent.
    credential_json=os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
    project_id=os.getenv('FIREBASE_PROJECT_ID')
    queued=s.scalars(select(Notification).where(Notification.status=='queued').order_by(Notification.created_at).limit(100)).all()
    if not credential_json or not project_id:
        return {'ok':False,'configured':False,'queued':len(queued),'message':'Firebase credentials are not configured'}
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        info=json.loads(credential_json)
        creds=service_account.Credentials.from_service_account_info(info,scopes=['https://www.googleapis.com/auth/firebase.messaging'])
        session=AuthorizedSession(creds); sent=failed=0
        for n in queued:
            devices=s.scalars(select(DeviceToken).where(DeviceToken.owner_id==n.owner_id,DeviceToken.enabled==True)).all()
            if not devices: continue
            all_ok=True
            for d in devices:
                payload={'message':{'token':d.token,'notification':{'title':n.title,'body':n.body},'data':{'notification_id':n.id,'kind':n.kind,'entity_type':n.entity_type or '','entity_id':n.entity_id or ''}}}
                r=session.post(f'https://fcm.googleapis.com/v1/projects/{project_id}/messages:send',json=payload,timeout=15)
                all_ok=all_ok and r.status_code<300
            if all_ok: n.status='pushed'; n.pushed_at=now(); sent+=1
            else: failed+=1
        s.commit(); return {'ok':True,'configured':True,'sent':sent,'failed':failed}
    except Exception as e:
        return {'ok':False,'configured':True,'error':str(e)[:240]}


@app.get('/calls/config')
def call_config(u:User=Depends(me)):
    servers=[{'urls':['stun:stun.l.google.com:19302']}]
    turn=os.getenv('TURN_URL')
    if turn:
        servers.append({'urls':[turn],'username':os.getenv('TURN_USERNAME',''),'credential':os.getenv('TURN_CREDENTIAL','')})
    return {'iceServers':servers}

# ---- Google / Apple login identities: same central Planner user ----
class ExternalIdentity(Base):
    __tablename__='external_identities'; __table_args__=(UniqueConstraint('provider','subject'),UniqueConstraint('user_id','provider'))
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    provider:Mapped[str]=mapped_column(String(20),index=True)
    subject:Mapped[str]=mapped_column(String(255),index=True)
    email:Mapped[Optional[str]]=mapped_column(String(255),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
Base.metadata.create_all(engine)

def social_state(provider:str):
    return jwt.encode({'purpose':'social_login','provider':provider,'nonce':secrets.token_urlsafe(18),'exp':now()+timedelta(minutes=10)},SECRET,algorithm='HS256')
def verify_social_state(state:str,provider:str):
    try:
        p=jwt.decode(state,SECRET,algorithms=['HS256'])
        if p.get('purpose')!='social_login' or p.get('provider')!=provider: raise ValueError()
        return p
    except Exception: raise HTTPException(400,'Invalid OAuth state')
def social_user(s:Session,provider:str,subject:str,email:Optional[str],name:Optional[str],email_verified:bool=True):
    ident=s.scalar(select(ExternalIdentity).where(ExternalIdentity.provider==provider,ExternalIdentity.subject==subject))
    if ident:
        u=s.get(User,ident.user_id); return u
    u=None
    if email and email_verified: u=s.scalar(select(User).where(User.email==email.lower()))
    if not u:
        if not email: email=f'{provider}-{subject[:24]}@local.invalid'
        u=User(email=email.lower(),name=(name or email.split('@')[0])[:120],password_hash=hash_password(secrets.token_urlsafe(48)))
        s.add(u); s.flush(); s.add(Calendar(owner_id=u.id,name='My Calendar')); ensure_settings(s,u.id)
    s.add(ExternalIdentity(user_id=u.id,provider=provider,subject=subject,email=email)); s.commit(); s.refresh(u); return u

@app.get('/auth/google/start')
def auth_google_start():
    cid=os.getenv('GOOGLE_CLIENT_ID'); redirect=os.getenv('GOOGLE_LOGIN_REDIRECT_URI') or os.getenv('GOOGLE_REDIRECT_URI')
    if not cid or not redirect: raise HTTPException(503,'Google login is not configured')
    state=social_state('google')
    q=urlencode({'client_id':cid,'redirect_uri':redirect,'response_type':'code','scope':'openid email profile','state':state,'prompt':'select_account'})
    return {'authorization_url':'https://accounts.google.com/o/oauth2/v2/auth?'+q,'state':state}

@app.get('/auth/google/callback')
def auth_google_callback(code:str,state:str,s:Session=Depends(db)):
    verify_social_state(state,'google')
    cid=os.getenv('GOOGLE_CLIENT_ID'); secret=os.getenv('GOOGLE_CLIENT_SECRET'); redirect=os.getenv('GOOGLE_LOGIN_REDIRECT_URI') or os.getenv('GOOGLE_REDIRECT_URI')
    if not cid or not secret or not redirect: raise HTTPException(503,'Google login is not configured')
    with httpx.Client(timeout=20) as h:
        tr=h.post('https://oauth2.googleapis.com/token',data={'code':code,'client_id':cid,'client_secret':secret,'redirect_uri':redirect,'grant_type':'authorization_code'})
        if tr.status_code>=400: raise HTTPException(400,'Google token exchange failed')
        data=tr.json(); idt=data.get('id_token')
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        claims=google_id_token.verify_oauth2_token(idt,google_requests.Request(),cid)
    except Exception: raise HTTPException(400,'Invalid Google identity token')
    if not claims.get('sub'): raise HTTPException(400,'Google subject missing')
    u=social_user(s,'google',claims['sub'],claims.get('email'),claims.get('name'),bool(claims.get('email_verified')))
    return issue_session(s,u,platform='oauth')

def apple_client_secret():
    team=os.getenv('APPLE_TEAM_ID'); client=os.getenv('APPLE_CLIENT_ID'); kid=os.getenv('APPLE_KEY_ID'); key=os.getenv('APPLE_PRIVATE_KEY')
    if not all((team,client,kid,key)): raise HTTPException(503,'Apple login is not configured')
    key=key.replace('\\n','\n')
    return jwt.encode({'iss':team,'iat':int(now().timestamp()),'exp':int((now()+timedelta(minutes=10)).timestamp()),'aud':'https://appleid.apple.com','sub':client},key,algorithm='ES256',headers={'kid':kid})

@app.get('/auth/apple/start')
def auth_apple_start():
    client=os.getenv('APPLE_CLIENT_ID'); redirect=os.getenv('APPLE_REDIRECT_URI')
    if not client or not redirect: raise HTTPException(503,'Apple login is not configured')
    state=social_state('apple')
    q=urlencode({'client_id':client,'redirect_uri':redirect,'response_type':'code id_token','response_mode':'form_post','scope':'name email','state':state})
    return {'authorization_url':'https://appleid.apple.com/auth/authorize?'+q,'state':state}

@app.post('/auth/apple/callback')
def auth_apple_callback(code:str=Form(...),state:str=Form(...),id_token_value:Optional[str]=Form(default=None,alias='id_token'),user:Optional[str]=Form(default=None),s:Session=Depends(db)):
    verify_social_state(state,'apple'); client=os.getenv('APPLE_CLIENT_ID'); redirect=os.getenv('APPLE_REDIRECT_URI')
    secret=apple_client_secret()
    with httpx.Client(timeout=20) as h:
        tr=h.post('https://appleid.apple.com/auth/token',data={'client_id':client,'client_secret':secret,'code':code,'grant_type':'authorization_code','redirect_uri':redirect})
        if tr.status_code>=400: raise HTTPException(400,'Apple token exchange failed')
        tok=tr.json(); raw=id_token_value or tok.get('id_token')
    try:
        jwk=jwt.PyJWKClient('https://appleid.apple.com/auth/keys').get_signing_key_from_jwt(raw)
        claims=jwt.decode(raw,jwk.key,algorithms=['RS256'],audience=client,issuer='https://appleid.apple.com')
    except Exception: raise HTTPException(400,'Invalid Apple identity token')
    name=None
    if user:
        try:
            ud=json.loads(user); n=ud.get('name') or {}; name=(' '.join([n.get('firstName',''),n.get('lastName','')])).strip() or None
        except Exception: pass
    u=social_user(s,'apple',claims['sub'],claims.get('email'),name,bool(claims.get('email_verified',True)))
    return issue_session(s,u,platform='oauth')


class GoogleMobileLoginIn(BaseModel): id_token:str; device_name:Optional[str]='android'; platform:Optional[str]='android'
class AppleMobileLoginIn(BaseModel): identity_token:str; first_name:Optional[str]=None; last_name:Optional[str]=None; device_name:Optional[str]='android'; platform:Optional[str]='android'

@app.post('/auth/google/mobile')
def auth_google_mobile(x:GoogleMobileLoginIn,s:Session=Depends(db)):
    cid=os.getenv('GOOGLE_CLIENT_ID') or os.getenv('GOOGLE_LOGIN_CLIENT_ID')
    if not cid: raise HTTPException(503,'Google login is not configured')
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        claims=google_id_token.verify_oauth2_token(x.id_token,google_requests.Request(),cid)
    except Exception: raise HTTPException(400,'Invalid Google identity token')
    if not claims.get('sub'): raise HTTPException(400,'Google subject missing')
    u=social_user(s,'google',claims['sub'],claims.get('email'),claims.get('name'),bool(claims.get('email_verified')))
    return issue_session(s,u,x.device_name,x.platform)

@app.post('/auth/apple/mobile')
def auth_apple_mobile(x:AppleMobileLoginIn,s:Session=Depends(db)):
    client=os.getenv('APPLE_CLIENT_ID')
    if not client: raise HTTPException(503,'Apple login is not configured')
    try:
        jwk=jwt.PyJWKClient('https://appleid.apple.com/auth/keys').get_signing_key_from_jwt(x.identity_token)
        claims=jwt.decode(x.identity_token,jwk.key,algorithms=['RS256'],audience=client,issuer='https://appleid.apple.com')
    except Exception: raise HTTPException(400,'Invalid Apple identity token')
    name=(' '.join([x.first_name or '',x.last_name or ''])).strip() or None
    u=social_user(s,'apple',claims['sub'],claims.get('email'),name,bool(claims.get('email_verified',True)))
    return issue_session(s,u,x.device_name,x.platform)
