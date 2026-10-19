"""Exercise the real case route functions with isolated repository fakes.

The legacy router eagerly loads models and connects collections at import time.
Compile only these route definitions to test authorization without that lifecycle.
"""
import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from copy import deepcopy
import pytest
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Header, status
from fastapi.testclient import TestClient
from components.health_anomaly.schemas import DiagnosticCaseCreate, DiagnosticCaseResponse, DiagnosticCaseVerifyRequest, VetNotificationResponse


def matches(doc, query):
    for key, expected in query.items():
        if key == '$or':
            if not any(matches(doc, item) for item in expected): return False
        elif key == '$and':
            if not all(matches(doc, item) for item in expected): return False
        elif isinstance(expected, dict) and '$in' in expected:
            value = doc.get(key)
            if isinstance(value, list):
                if not any(item in expected['$in'] for item in value): return False
            elif value not in expected['$in']: return False
        elif isinstance(doc.get(key), list):
            if expected not in doc[key]: return False
        elif doc.get(key) != expected: return False
    return True


class Cursor:
    def __init__(self, docs): self.docs = docs
    def sort(self, *args): return self
    def limit(self, size): self.docs = self.docs[:size]; return self
    def __aiter__(self): self.iterator = iter(self.docs); return self
    async def __anext__(self):
        try: return deepcopy(next(self.iterator))
        except StopIteration: raise StopAsyncIteration


class Collection:
    def __init__(self, docs=()): self.docs = deepcopy(list(docs))
    def find(self, query): return Cursor([doc for doc in self.docs if matches(doc, query)])
    async def find_one(self, query): return next((deepcopy(doc) for doc in self.docs if matches(doc, query)), None)
    async def insert_one(self, doc):
        doc = deepcopy(doc); doc.setdefault('_id', ObjectId()); self.docs.append(doc)
        return SimpleNamespace(inserted_id=doc['_id'])
    async def update_one(self, query, update):
        for doc in self.docs:
            if matches(doc, query): doc.update(update['$set']); break
        return SimpleNamespace(modified_count=1)
    async def delete_one(self, query):
        for doc in self.docs:
            if matches(doc, query): self.docs.remove(doc); return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


@pytest.fixture
def cases():
    farm_a = dict(_id=ObjectId(),email='farm-a',owner_name='Same name',assigned_vet_emails=['vet-a'])
    farm_b = dict(_id=ObjectId(),email='farm-b',owner_name='Same name',assigned_vet_emails=['vet-b'])
    animal_a = dict(_id=ObjectId(),owner_email='farm-a',identifier='A',breed='Breed')
    animal_b = dict(_id=ObjectId(),owner_email='farm-b',identifier='B',breed='Breed')
    db = dict(farms_collection=Collection([farm_a,farm_b]),
        vets_collection=Collection([dict(_id=ObjectId(),email='vet-a'),dict(_id=ObjectId(),email='vet-b')]),
        cattles_collection=Collection([animal_a,animal_b]), diagnostic_cases_collection=Collection(), vet_notifications_collection=Collection())
    async def authenticate(header):
        if header not in ['Bearer '+name for name in ('farm-a','farm-b','vet-a','vet-b')]: raise HTTPException(401,'Invalid token')
        return header[7:]
    namespace = dict(db, APIRouter=APIRouter, HTTPException=HTTPException, Header=Header, status=status,
        Optional=Optional, DiagnosticCaseCreate=DiagnosticCaseCreate, DiagnosticCaseResponse=DiagnosticCaseResponse,
        DiagnosticCaseVerifyRequest=DiagnosticCaseVerifyRequest, VetNotificationResponse=VetNotificationResponse, datetime=datetime, ObjectId=ObjectId,
        get_current_user_email=authenticate, _invalidate_forecast_cache=lambda:None,
        __name__='components.health_anomaly._isolated_case_routes', __package__='components.health_anomaly')
    namespace['router'] = APIRouter()
    source = Path(__file__).resolve().parents[2] / 'health_anomaly/router.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    names = {'_diagnostic_access','report_diagnostic_case','list_diagnostic_cases','verify_diagnostic_case','delete_diagnostic_case', 'list_vet_notifications', 'mark_notification_read'}
    selected = [node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names]
    exec(compile(ast.Module(body=selected,type_ignores=[]), str(source), 'exec'), namespace)
    app=FastAPI();app.include_router(namespace['router'],prefix='/api')
    return SimpleNamespace(client=TestClient(app), db=db, a=animal_a,b=animal_b,fa=farm_a,fb=farm_b)


def header(name): return {'Authorization':'Bearer '+name}
def payload(animal=None, **extra):
    return dict(disease_name='Mastitis',confidence=91, cattle_id=str(animal['_id']) if animal else None,
                severity='Unassessable') | extra


@pytest.mark.parametrize('method,path,body', [('get','/api/vet/cases',None),
    ('post','/api/vet/cases',payload()),('put','/api/vet/cases/'+str(ObjectId())+'/verify',{}),
    ('delete','/api/vet/cases/'+str(ObjectId()),None)])
def test_missing_auth_never_reads_or_writes(cases,method,path,body):
    response = cases.client.request(method,path,**({'json':body} if body is not None else {}))
    assert response.status_code == 401
    assert not cases.db['diagnostic_cases_collection'].docs


def test_farmer_identity_and_pending_status_are_server_derived(cases):
    response=cases.client.post('/api/vet/cases',headers=header('farm-a'),json=payload(cases.a,
        verified=True,reporter_email='vet-a',reported_by='vet',assigned_vet_id='forged',animal_identifier='spoofed'))
    assert response.status_code == 201
    case=response.json()
    assert not case['verified'] and case['reporter_email']=='farm-a' and case['reported_by']=='farmer'
    assert case['animal_identifier']=='A' and case['farm_id']==str(cases.fa['_id'])
    assert case['stage'] is None and case['prognosis'] is None
    assert cases.client.put('/api/vet/cases/'+case['id']+'/verify',headers=header('farm-a'),json={}).status_code==403


def test_foreign_cattle_farm_spoof_and_unassigned_vet_are_rejected(cases):
    for actor, body in [('farm-a',payload(cases.b)),('vet-b',payload(cases.a)),
                        ('farm-a',payload(cases.a,farm_id=str(cases.fb['_id'])))]:
        assert cases.client.post('/api/vet/cases',headers=header(actor),json=body).status_code==403
    assert not cases.db['diagnostic_cases_collection'].docs


def test_case_scope_protects_lists_verification_and_deletion(cases):
    own=cases.client.post('/api/vet/cases',headers=header('farm-a'),json=payload(cases.a)).json()
    other=cases.client.post('/api/vet/cases',headers=header('farm-b'),json=payload(cases.b)).json()
    for actor in ['farm-a','vet-a']:
        listed=cases.client.get('/api/vet/cases',headers=header(actor)).json()
        assert [case['id'] for case in listed]==[own['id']], actor
    assert cases.client.put('/api/vet/cases/'+other['id']+'/verify',headers=header('vet-a'),json={}).status_code==403
    assert cases.client.delete('/api/vet/cases/'+other['id'],headers=header('vet-a')).status_code==403
    assert cases.client.put('/api/vet/cases/'+own['id']+'/verify',headers=header('vet-a'),json={}).status_code==200
    assert cases.client.delete('/api/vet/cases/'+own['id'],headers=header('vet-a')).status_code==200
    assert len(cases.db['diagnostic_cases_collection'].docs)==1


def test_unassigned_vet_demo_case_is_private_to_its_reporter(cases):
    response=cases.client.post('/api/vet/cases',headers=header('vet-a'),json=payload(verified=True))
    assert response.status_code==201
    assert cases.client.get('/api/vet/cases',headers=header('vet-b')).json()==[]
    assert cases.client.get('/api/vet/cases',headers=header('vet-a')).json()[0]['id']==response.json()['id']


def test_case_notifications_are_private_and_read_actions_require_auth(cases):
    cases.client.post('/api/vet/cases',headers=header('farm-a'),json=payload(cases.a))
    own=cases.client.get('/api/vet/notifications',headers=header('vet-a')).json()
    assert len(own)==1
    assert cases.client.get('/api/vet/notifications',headers=header('vet-b')).json()==[]
    path='/api/vet/notifications/'+own[0]['id']+'/read'
    assert cases.client.put(path).status_code==401
    assert cases.client.put(path,headers=header('vet-b')).status_code==403
    assert cases.client.put(path,headers=header('vet-a')).status_code==200
