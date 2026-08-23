import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment variables
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb+srv://user4:user123@cluster0.8e4nq9e.mongodb.net/?appName=Cluster0")

# Initialize MongoDB client
client = AsyncIOMotorClient(MONGODB_URL)

# Database instance
db = client.adrs_core

# Collections
farms_collection = db.farms
cattles_collection = db.cattle

