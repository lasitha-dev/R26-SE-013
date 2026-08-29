import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment variables
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://127.0.0.1:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "adrs_core")

# Initialize MongoDB client
client = AsyncIOMotorClient(MONGODB_URL, serverSelectionTimeoutMS=2000)

# Database instance
db = client[MONGODB_DB_NAME]

# Collections
farms_collection = db.farms
cattles_collection = db.cattle
vets_collection = db.vets