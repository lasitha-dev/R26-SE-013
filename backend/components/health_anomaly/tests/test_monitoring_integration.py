"""Exercise merged monitoring with fake collections, without importing AI/DB startup."""
import ast
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from bson import ObjectId
from fastapi import APIRouter, FastAPI, Header, HTTPException, status
from fastapi.testclient import TestClient

from components.health_anomaly.schemas import DailyLogBulkItem, DailyLogResponse, TriagePredictPayload, PredictPayload, PredictResponse
from components.health_anomaly.wellness_monitoring import (
    import_daily_logs, normalize_date_str, owned_cattle, living_cattle_filter, farm_cattle_filter,
)


def matches(doc, query):
    for key, value in query.items():
        if key == '$or':
            if not any(matches(doc, sub) for sub in value): return False
        elif isinstance(value, dict):
            actual = doc.get(key)
            for op, expected in value.items():
                if op == '$in' and actual not in expected: return False
                if op == '$ne' and actual == expected: return False
                if op == '$exists' and (key in doc) != expected: return False
                if op == '$lte' and (actual is None or actual > expected): return False
        elif doc.get(key) != value: return False
    return True


class Cursor:
    def __init__(self, docs): self.docs = deepcopy(docs)
    def sort(self, *args): return self
    async def to_list(self, length): return self.docs
    def __aiter__(self): self.iterator = iter(self.docs); return self
    async def __anext__(self):
        try: return next(self.iterator)
        except StopIteration: raise StopAsyncIteration


class Collection:
    def __init__(self, docs=()): self.docs = deepcopy(list(docs)); self.writes = 0
    def find(self, query): return Cursor([doc for doc in self.docs if matches(doc, query)])
    async def find_one(self, query): return next((deepcopy(d) for d in self.docs if matches(d, query)), None)
    async def update_one(self, query, update):
        for doc in self.docs:
            if matches(doc, query): doc.update(update['$set']); self.writes += 1; break
    async def bulk_write(self, operations, ordered):
        for operation in operations:
            doc = deepcopy(operation._doc)
            current = next((d for d in self.docs if matches(d, operation._filter)), None)
            if current is None: doc['_id'] = ObjectId(); self.docs.append(doc)
            else: doc['_id'] = current['_id']; current.clear(); current.update(doc)
            self.writes += 1


def cow(email='farm-a', tag='shared', **extra):
    return dict(_id=ObjectId(), owner_email=email, identifier=tag, gender='female', breed='Jersey',
                status='Healthy', health_status='Healthy', **extra)


def row(animal=None, **extra):
    return DailyLogBulkItem(**(dict(cattle_id=str(animal['_id']) if animal else None,
                                    date='2026-10-15', milk_yield=10, weight=400) | extra))


def inference(cow, latest, history, custom_milk, custom_weight):
    return dict(is_anomaly=latest['milk_yield'] < 8, new_status='Alert' if latest['milk_yield'] < 8 else 'Healthy',
                date=latest['date'], milk_yield=latest['milk_yield'], weight=latest['weight'])


async def run(rows, animals, logs=None, evaluate=inference):
    cattle = Collection(animals); stored = Collection(logs or [])
    result = await import_daily_logs(rows, 'farm-a', cattle, stored, Collection(), evaluate)
    return result, cattle, stored


@pytest.mark.parametrize('raw,expected', [('10/9/26', '2026-10-09'), ('2026.10.9', '2026-10-09'),
                                        ('2024-02-29', '2024-02-29'), ('10-15-2026', '2026-10-15')])
def test_date_contract(raw, expected): assert normalize_date_str(raw) == expected


@pytest.mark.parametrize('raw', ['', '2026-02-29', '2026-04-31', '15/10/2026', 'nonsense', '2026-13-01'])
def test_invalid_dates_do_not_roll_over(raw):
    with pytest.raises(HTTPException) as err: normalize_date_str(raw)
    assert err.value.status_code == 400


@pytest.mark.asyncio
async def test_automatic_replacement_preserves_record_id_and_other_farms():
    a, b = cow(), cow('farm-b')
    original = dict(_id=ObjectId(), cattle_id=str(a['_id']), date='2026-10-15', milk_yield=20, weight=500)
    foreign = dict(original, _id=ObjectId(), cattle_id=str(b['_id']))
    result, cattle, stored = await run([row(identifier='SHARED', milk_yield=6)], [a, b], [original, foreign])
    assert result['count'] == result['inserted_count'] == 1 and result['alerts_triggered'] == 1
    assert stored.docs[0]['_id'] == original['_id'] and stored.docs[0]['milk_yield'] == 6
    assert stored.docs[1] == foreign and cattle.docs[1] == b


@pytest.mark.asyncio
async def test_same_csv_key_last_row_wins_and_retries_do_not_duplicate():
    a = cow(); cattle, stored, settings = Collection([a]), Collection(), Collection()
    rows = [row(a, milk_yield=8), row(a, milk_yield=9)]
    for _ in range(2):
        result = await import_daily_logs(rows, 'farm-a', cattle, stored, settings, inference)
        assert result['inserted_count'] == 1
    assert len(stored.docs) == 1 and stored.docs[0]['milk_yield'] == 9


@pytest.mark.asyncio
async def test_foreign_id_never_falls_back_to_own_tag():
    a, b = cow(), cow('farm-b'); cattle, logs = Collection([a, b]), Collection()
    with pytest.raises(HTTPException) as err:
        await import_daily_logs([row(b, identifier='shared')], 'farm-a', cattle, logs, Collection(), inference)
    assert err.value.status_code == 404 and logs.writes == 0


@pytest.mark.asyncio
async def test_unknown_row_rejects_entire_batch_before_writing():
    a = cow(); cattle, logs = Collection([a]), Collection()
    with pytest.raises(HTTPException):
        await import_daily_logs([row(a), row(identifier='missing')], 'farm-a', cattle, logs, Collection(), inference)
    assert logs.writes == cattle.writes == 0


@pytest.mark.asyncio
async def test_inference_failure_leaves_existing_records_untouched():
    a = cow(); original = dict(_id=ObjectId(), cattle_id=str(a['_id']), date='2026-10-15', milk_yield=20, weight=500)
    cattle, logs = Collection([a]), Collection([original])
    with pytest.raises(RuntimeError):
        await import_daily_logs([row(a)], 'farm-a', cattle, logs, Collection(), Mock(side_effect=RuntimeError('missing model')))
    assert logs.docs == [original] and logs.writes == cattle.writes == 0


@pytest.mark.asyncio
async def test_deceased_and_male_rows_are_skipped_without_inference():
    a, b = cow(), cow(tag='male'); a['status'] = 'Deceased'; b['gender'] = 'Male'
    result, cattle, logs = await run([row(a), row(b)], [a, b], evaluate=Mock(side_effect=AssertionError('must not infer')))
    assert result['skipped_count'] == 2 and result['count'] == 0 and logs.writes == cattle.writes == 0


@pytest.mark.asyncio
async def test_backfill_uses_latest_stored_day_for_status_weight_and_monitor_date():
    a = cow(); latest = dict(_id=ObjectId(), cattle_id=str(a['_id']), date='2026-10-16', milk_yield=15, weight=450)
    result, cattle, logs = await run([row(a, milk_yield=2)], [a], [latest])
    assert result['results'][0]['date'] == '2026-10-16'
    assert cattle.docs[0]['weight'] == 450 and cattle.docs[0]['status'] == 'Healthy'
    assert cattle.docs[0]['last_monitored_date'] == '2026-10-16'


@pytest.mark.asyncio
async def test_normalized_existing_dates_replace_in_place_and_sensors_survive_response():
    a = cow(); original = dict(_id=ObjectId(), cattle_id=str(a['_id']), date='10/15/26', milk_yield=20, weight=500)
    result, _, logs = await run([row(a, water_intake=48, feed_intake=14, body_temp=38.5)], [a], [original])
    assert len(logs.docs) == 1 and logs.docs[0]['_id'] == original['_id']
    response = DailyLogResponse(id=str(original['_id']), **{k:v for k,v in logs.docs[0].items() if k != '_id'})
    assert response.water_intake == 48 and response.body_temp == 38.5


@pytest.fixture
def routes():
    a, b = cow(), cow('farm-b')
    cattle, logs = Collection([a, b]), Collection()
    async def authenticate(header):
        if header != 'Bearer farm-a': raise HTTPException(401, 'Invalid token')
        return 'farm-a'
    ns = dict(APIRouter=APIRouter, HTTPException=HTTPException, Header=Header, status=status, Optional=Optional,
              DailyLogBulkItem=DailyLogBulkItem, DailyLogResponse=DailyLogResponse, TriagePredictPayload=TriagePredictPayload,
              PredictPayload=PredictPayload, PredictResponse=PredictResponse, ObjectId=ObjectId, datetime=datetime, timedelta=timedelta, np=np, pd=pd,
              cattles_collection=cattle, daily_logs_collection=logs, breed_settings_collection=Collection(),
              get_current_user_email=authenticate, import_daily_logs=import_daily_logs, farm_cattle_filter=farm_cattle_filter,
              living_cattle_filter=living_cattle_filter, owned_cattle=owned_cattle, normalize_date_str=normalize_date_str,
              evaluate_cow_persistent_monitoring=inference, router=APIRouter())
    path = Path(__file__).resolve().parents[1] / 'router.py'
    names = {'create_daily_logs_bulk', 'list_daily_logs', 'predict_7day', 'predict_health_anomaly'}
    nodes = [n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
    app = FastAPI(); app.include_router(ns['router'], prefix='/api')
    return SimpleNamespace(client=TestClient(app), ns=ns, a=a, b=b, cattle=cattle, logs=logs)


@pytest.mark.parametrize('header', [None, 'Bearer invalid'])
def test_bulk_route_missing_or_invalid_auth_is_401_without_writes(routes, header):
    response = routes.client.post('/api/daily-logs/bulk', json=[row(routes.a).model_dump()], headers={'Authorization': header} if header else {})
    assert response.status_code == 401 and routes.logs.writes == 0


def test_daily_log_list_requires_auth_and_never_falls_back_to_all_farms(routes):
    routes.logs.docs = [dict(_id=ObjectId(), cattle_id=str(routes.b['_id']), date='2026-10-15', milk_yield=10, weight=400)]
    assert routes.client.get('/api/daily-logs').status_code == 401
    assert routes.client.get('/api/daily-logs', headers={'Authorization': 'Bearer farm-a'}).json() == []


def test_bulk_route_preserves_validation_status_and_legacy_count(routes):
    headers = {'Authorization': 'Bearer farm-a'}
    response = routes.client.post('/api/daily-logs/bulk', headers=headers, json=[row(routes.a).model_dump()])
    assert response.status_code == 201 and response.json()['count'] == 1
    response = routes.client.post('/api/daily-logs/bulk', headers=headers, json=[row(routes.a, date='2026-02-30').model_dump()])
    assert response.status_code == 400


def triage_payload(animal=None, **extra):
    return dict(cattle_id=str(animal['_id']) if animal else None, bcs_score=3, age_months=36, days_in_milk=100,
                breed='Jersey', genetic_group='A', lactation_stage='Early', ambient_temp=[30]*7, humidity=[75]*7,
                thi=[80]*7, body_temp=[38.5]*7, milk_yield=[10]*7, water_intake=[48]*7, feed_intake=[14]*7, weight=[400]*7) | extra


def test_triage_rejects_unauthorized_foreign_and_deceased_status_writes(routes):
    path = '/api/monitor/predict-7day'; headers = {'Authorization': 'Bearer farm-a'}
    assert routes.client.post(path, json=triage_payload(routes.a)).status_code == 401
    assert routes.client.post(path, json=triage_payload(routes.b), headers=headers).status_code == 404
    routes.cattle.docs[0]['health_status'] = 'Deceased'
    assert routes.client.post(path, json=triage_payload(routes.a), headers=headers).status_code == 400
    assert routes.cattle.writes == 0


def test_triage_scaler_schema_tensor_shapes_and_status_persistence(routes):
    columns = [f'{name}_Day_{day}' for day in range(1, 8) for name in
               ['Ambient_Temp', 'Humidity', 'THI', 'Body_Temp', 'Milk_Yield', 'Water_Intake', 'Feed_Intake', 'Weight']]
    static = ['Age_Months', 'Days_in_Milk'] + [f'Unused_{i}' for i in range(42)] + ['Breed_Jersey']
    def scaler(expected):
        def transform(df):
            assert list(df.columns) == expected
            return df.to_numpy(dtype=float)
        return SimpleNamespace(transform=transform)
    def predict(inputs, verbose):
        assert [x.shape for x in inputs] == [(1, 7, 8), (1, 45), (1, 1)]
        assert inputs[0][0, 0].tolist() == [30, 75, 80, 38.5, 10, 48, 14, 400]
        return np.array([[0.1, 0.8, 0.1]])
    routes.ns.update(late_fusion_model=SimpleNamespace(predict=predict), late_fusion_scalers=dict(
        scaler_ts=scaler(columns), scaler_static=scaler(static), scaler_visual=scaler(['Day_7_BCS']),
        ts_cols=columns, dummy_columns=static))
    response = routes.client.post('/api/monitor/predict-7day', json=triage_payload(routes.a), headers={'Authorization': 'Bearer farm-a'})
    assert response.status_code == 200 and response.json()['status'] == 'Heat Stress'
    assert routes.cattle.docs[0]['health_status'] == 'Heat Stress' and routes.cattle.docs[1] == routes.b
    bad = routes.client.post('/api/monitor/predict-7day', json=triage_payload(ambient_temp=[30]))
    assert bad.status_code == 400
