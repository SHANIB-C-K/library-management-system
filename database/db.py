from pymongo import MongoClient
from config import Config

try:
    # Establish connection to MongoDB using the URI from Config
    client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[Config.MONGO_DBNAME]
    
    # Check if connection is successful (raises exception if not)
    client.server_info()
    print("Successfully connected to MongoDB.")
    
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")

# Define the 5 collections required for the CRUD operations
users_collection = db['users']
books_collection = db['books']
borrow_records_collection = db['borrow_records']
returns_collection = db['returns']
categories_collection = db['categories']
