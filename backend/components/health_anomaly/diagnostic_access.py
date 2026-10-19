"""Diagnostic-case scope checks. Collection dependencies are supplied by the router."""
from bson import ObjectId
from fastapi import HTTPException


def assigned(vet, farm):
    return bool(vet and farm and (
        str(farm['_id']) in {str(value) for value in vet.get('assigned_farm_ids', [])}
        or farm.get('email') in vet.get('assigned_farms', [])
        or str(vet['_id']) in {str(value) for value in farm.get('assigned_vet_ids', [])}
        or vet.get('email') in farm.get('assigned_vet_emails', [])))


class DiagnosticAccess:
    def __init__(self, farms, vets, cattle, authenticate):
        self.farms, self.vets, self.cattle, self.authenticate = farms, vets, cattle, authenticate

    async def actor(self, authorization, vet_only=False):
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(401, 'Authentication is required.')
        email = await self.authenticate(authorization)
        vet = await self.vets.find_one({'email': email})
        farm = await self.farms.find_one({'email': email}) if not vet else None
        if not vet and (vet_only or not farm):
            raise HTTPException(403, 'An authorized veterinary account is required.' if vet_only else 'Account not registered.')
        return dict(email=email, vet=vet, farm=farm)

    async def farm(self, identifier):
        query = {'_id': ObjectId(identifier)} if ObjectId.is_valid(str(identifier)) else {'email': identifier}
        result = await self.farms.find_one(query)
        if not result:
            raise HTTPException(404, 'Farm not found.')
        return result

    def authorize(self, actor, farm):
        permitted = (assigned(actor['vet'], farm) if actor['vet'] else
                     bool(farm and str(farm['_id']) == str(actor['farm']['_id'])))
        if not permitted:
            raise HTTPException(403, 'The case is outside your assigned farm scope.')

    async def creation(self, actor, cattle_id, farm_id):
        animal = None
        farm = await self.farm(farm_id) if farm_id else actor['farm']
        if cattle_id:
            if not ObjectId.is_valid(cattle_id):
                raise HTTPException(400, 'Invalid cattle ID.')
            animal = await self.cattle.find_one({'_id': ObjectId(cattle_id)})
            if not animal:
                raise HTTPException(404, 'Cattle not found.')
            owner = animal.get('owner_email')
            if not owner:
                raise HTTPException(403, 'Cattle ownership cannot be established.')
            animal_farm = await self.farm(owner)
            if farm and str(farm['_id']) != str(animal_farm['_id']):
                raise HTTPException(403, 'Cattle and farm do not match.')
            farm = animal_farm
        if farm:
            self.authorize(actor, farm)
        elif not actor['vet']:
            raise HTTPException(403, 'A farm is required for farmer reports.')
        return animal, farm

    async def case(self, actor, case):
        if case.get('cattle_id'):
            await self.creation(actor, case['cattle_id'], case.get('farm_id'))
        elif case.get('farm_id'):
            self.authorize(actor, await self.farm(case['farm_id']))
        elif case.get('reporter_email') != actor['email'] or not actor['vet'] or case.get('reported_by') != 'vet':
            raise HTTPException(403, 'Unassigned case ownership cannot be established.')

    async def list_scope(self, actor):
        if actor['farm']:
            farms = [actor['farm']]
        else:
            vet = actor['vet']
            ids = [ObjectId(str(value)) for value in vet.get('assigned_farm_ids', []) if ObjectId.is_valid(str(value))]
            query = {'$or': [{'_id': {'$in': ids}}, {'email': {'$in': vet.get('assigned_farms', [])}},
                              {'assigned_vet_ids': {'$in': [str(vet['_id']), vet['_id']]}}, {'assigned_vet_emails': vet['email']}]}
            farms = [farm async for farm in self.farms.find(query)]
        aliases = [value for farm in farms for value in (str(farm['_id']), farm.get('email')) if value]
        clauses = [{'farm_id': {'$in': aliases}}]
        if actor['vet']:
            clauses.append({'farm_id': None, 'reporter_email': actor['email'], 'reported_by': 'vet'})
        return {'$or': clauses}
