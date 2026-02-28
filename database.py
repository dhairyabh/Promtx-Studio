import os
from pymongo import MongoClient
from dotenv import load_dotenv

def get_db():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(dotenv_path=env_path, override=True)
    
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("Warning: MONGODB_URI not found in .env file.")
        return None
        
    try:
        client = MongoClient(uri)
        # Verify connection
        client.admin.command('ping')
        return client.promtx_studio
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None
