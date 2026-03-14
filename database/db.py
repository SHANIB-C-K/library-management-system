from pymongo import MongoClient
from bson.objectid import ObjectId
from config import Config
from datetime import datetime

# Connect to MongoDB
# MongoClient is lazy; we don't need server_info() to block on import
client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=5000)
db = client['library_db']

# Collections Definition
users_collection = db['users']
books_collection = db['books']
borrow_records_collection = db['borrow_records']
returns_collection = db['returns']
categories_collection = db['categories']

# ==========================================
# Database Helper Functions
# ==========================================

def insert_book(title, author, category, isbn, quantity, available=None):
    """Insert a new book into the books collection."""
    if available is None:
        available = quantity
        
    new_book = {
        'title': title,
        'author': author,
        'category': category,
        'isbn': isbn,
        'quantity': quantity,
        'available': available
    }
    result = books_collection.insert_one(new_book)
    return result.inserted_id

def get_all_books():
    """Retrieve all books."""
    return list(books_collection.find())

def borrow_book(user_id, book_id, borrow_date=None, due_date=None, status="borrowed"):
    """Create a new borrow record and decrement available copies."""
    if borrow_date is None:
        borrow_date = datetime.now()
        
    # Check if book is available
    book = books_collection.find_one({'_id': ObjectId(book_id)})
    if not book or book.get('available', 0) <= 0:
        return None
        
    # Decrement availability in the books collection
    books_collection.update_one(
        {'_id': ObjectId(book_id)},
        {'$inc': {'available': -1}}
    )
    
    # Create borrow record including the expected due_date
    record = {
        'user_id':     ObjectId(user_id),
        'book_id':     ObjectId(book_id),
        'borrow_date': borrow_date,
        'due_date':    due_date,        # Expected return date
        'return_date': None,
        'status':      status
    }
    result = borrow_records_collection.insert_one(record)
    return result.inserted_id

def return_book(borrow_id, return_date=None, fine=0.0, condition='good'):
    """Process a return, log it with condition & fine, increment book available copies."""
    if return_date is None:
        return_date = datetime.now()

    borrow_record = borrow_records_collection.find_one({'_id': ObjectId(borrow_id)})
    if not borrow_record or borrow_record['status'] == 'returned':
        return None

    # Mark the borrow record as returned
    borrow_records_collection.update_one(
        {'_id': ObjectId(borrow_id)},
        {'$set': {'status': 'returned', 'return_date': return_date}}
    )

    # Put the copy back into the books collection
    books_collection.update_one(
        {'_id': borrow_record['book_id']},
        {'$inc': {'available': 1}}
    )

    # Insert full return record (condition + fine stored for audit trail)
    return_record = {
        'borrow_id':   ObjectId(borrow_id),
        'return_date': return_date,
        'condition':   condition,
        'fine':        fine
    }
    result = returns_collection.insert_one(return_record)
    return result.inserted_id

def add_user(name, email, password, role, phone):
    """Add a new user to the system."""
    new_user = {
        'name': name,
        'email': email,
        'password': password,
        'role': role,
        'phone': phone,
        'created_at': datetime.now()
    }
    result = users_collection.insert_one(new_user)
    return result.inserted_id

def get_user_list():
    """Retrieve all users."""
    return list(users_collection.find())
