from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from bson.objectid import ObjectId
from datetime import datetime
from config import Config

# Import collections from our database module
from database.db import (
    users_collection, books_collection, borrow_records_collection,
    returns_collection, categories_collection
)

app = Flask(__name__)
app.config.from_object(Config)

# ==========================================
# Dashboard Routes
# ==========================================
@app.route('/')
def dashboard():
    """Render the main dashboard with summary statistics."""
    stats = {
        'total_books': books_collection.count_documents({}),
        'total_users': users_collection.count_documents({}),
        'active_borrows': borrow_records_collection.count_documents({'status': 'borrowed'}),
        'total_categories': categories_collection.count_documents({})
    }
    
    # Get recent borrow records for the dashboard table
    recent_borrows = list(borrow_records_collection.aggregate([
        {"$sort": {"borrow_date": -1}},
        {"$limit": 5},
        {"$lookup": {
            "from": "books",
            "localField": "book_id",
            "foreignField": "_id",
            "as": "book_info"
        }},
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user_info"
        }}
    ]))
    
    return render_template('dashboard.html', stats=stats, recent_borrows=recent_borrows)

# ==========================================
# Books Routes (CRUD)
# ==========================================
@app.route('/books')
def books():
    """Display all books."""
    all_books = list(books_collection.aggregate([
        {"$lookup": {
            "from": "categories",
            "localField": "category_id",
            "foreignField": "_id",
            "as": "category_info"
        }}
    ]))
    all_categories = list(categories_collection.find())
    return render_template('books.html', books=all_books, categories=all_categories)

@app.route('/books/add', methods=['POST'])
def add_book():
    """Create a new book record."""
    title = request.form.get('title')
    author = request.form.get('author')
    isbn = request.form.get('isbn')
    category_id = request.form.get('category_id')
    copies = int(request.form.get('copies', 0))
    
    new_book = {
        'title': title,
        'author': author,
        'isbn': isbn,
        'category_id': ObjectId(category_id) if category_id else None,
        'total_copies': copies,
        'available_copies': copies,
        'created_at': datetime.now()
    }
    
    books_collection.insert_one(new_book)
    return redirect(url_for('books'))

@app.route('/books/edit/<book_id>', methods=['POST'])
def edit_book(book_id):
    """Update an existing book record."""
    title = request.form.get('title')
    author = request.form.get('author')
    isbn = request.form.get('isbn')
    category_id = request.form.get('category_id')
    added_copies = int(request.form.get('added_copies', 0))
    
    # Update book details and incrementally adjust copies
    books_collection.update_one(
        {'_id': ObjectId(book_id)},
        {
            '$set': {
                'title': title,
                'author': author,
                'isbn': isbn,
                'category_id': ObjectId(category_id) if category_id else None
            },
            '$inc': {
                'total_copies': added_copies,
                'available_copies': added_copies
            }
        }
    )
    return redirect(url_for('books'))

@app.route('/books/delete/<book_id>', methods=['POST'])
def delete_book(book_id):
    """Delete a book record."""
    # Check if book is currently borrowed before deleting (Good practice for DBMS lab)
    active_borrows = borrow_records_collection.count_documents({
        'book_id': ObjectId(book_id),
        'status': 'borrowed'
    })
    
    if active_borrows > 0:
        return jsonify({'success': False, 'message': 'Cannot delete book. Copies are currently borrowed.'}), 400
        
    books_collection.delete_one({'_id': ObjectId(book_id)})
    return jsonify({'success': True})

# ==========================================
# Categories Routes
# ==========================================
@app.route('/categories', methods=['POST'])
def add_category():
    """Create a new category."""
    name = request.form.get('name')
    description = request.form.get('description')
    
    new_category = {
        'name': name,
        'description': description
    }
    
    categories_collection.insert_one(new_category)
    return redirect(url_for('books')) # Redirecting to books since category modal might be there

# ==========================================
# Users Routes (CRUD)
# ==========================================
@app.route('/users')
def users():
    """Display all users."""
    all_users = list(users_collection.find())
    return render_template('users.html', users=all_users)

@app.route('/users/add', methods=['POST'])
def add_user():
    """Create a new user (Member/Student)."""
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    role = request.form.get('role', 'student')
    
    new_user = {
        'name': name,
        'email': email,
        'phone': phone,
        'role': role,
        'created_at': datetime.now()
    }
    
    users_collection.insert_one(new_user)
    return redirect(url_for('users'))

@app.route('/users/delete/<user_id>', methods=['POST'])
def delete_user(user_id):
    """Delete a user record."""
    users_collection.delete_one({'_id': ObjectId(user_id)})
    return jsonify({'success': True})

# ==========================================
# Borrow Routes
# ==========================================
@app.route('/borrow')
def borrow():
    """Display borrow forms and active borrow records."""
    active_borrows = list(borrow_records_collection.aggregate([
        {"$match": {"status": "borrowed"}},
        {"$lookup": {
            "from": "books",
            "localField": "book_id",
            "foreignField": "_id",
            "as": "book_info"
        }},
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user_info"
        }}
    ]))
    
    # We only want to show available books and valid users in the dropdowns
    available_books = list(books_collection.find({'available_copies': {'$gt': 0}}))
    all_users = list(users_collection.find())
    
    return render_template('borrow.html', 
                           active_borrows=active_borrows,
                           books=available_books,
                           users=all_users)

@app.route('/borrow/add', methods=['POST'])
def issue_book():
    """Issue a book to a user."""
    book_id = request.form.get('book_id')
    user_id = request.form.get('user_id')
    due_date = request.form.get('due_date')
    
    book_oid = ObjectId(book_id)
    
    # Double check availability (concurrency safety principle for DBMS)
    book = books_collection.find_one({'_id': book_oid})
    if not book or book.get('available_copies', 0) <= 0:
        return redirect(url_for('borrow'))
        
    # 1. Decrement available copies
    books_collection.update_one(
        {'_id': book_oid},
        {'$inc': {'available_copies': -1}}
    )
    
    # 2. Add borrow record
    borrow_record = {
        'book_id': book_oid,
        'user_id': ObjectId(user_id),
        'borrow_date': datetime.now(),
        'due_date': datetime.strptime(due_date, '%Y-%m-%d') if due_date else None,
        'status': 'borrowed'
    }
    borrow_records_collection.insert_one(borrow_record)
    
    return redirect(url_for('borrow'))

# ==========================================
# Return Routes
# ==========================================
@app.route('/return')
def return_books():
    """Display return forms and return history."""
    return_history = list(returns_collection.aggregate([
        {"$sort": {"return_date": -1}},
        {"$lookup": {
            "from": "borrow_records",
            "localField": "borrow_id",
            "foreignField": "_id",
            "as": "borrow_info"
        }},
        # Unwind borrow info to join book and user
        {"$unwind": "$borrow_info"},
        {"$lookup": {
            "from": "books",
            "localField": "borrow_info.book_id",
            "foreignField": "_id",
            "as": "book_info"
        }},
        {"$lookup": {
            "from": "users",
            "localField": "borrow_info.user_id",
            "foreignField": "_id",
            "as": "user_info"
        }}
    ]))
    
    # Get active borrows for the return dropdown
    active_borrows = list(borrow_records_collection.aggregate([
        {"$match": {"status": "borrowed"}},
        {"$lookup": {
            "from": "books",
            "localField": "book_id",
            "foreignField": "_id",
            "as": "book_info"
        }},
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user_info"
        }}
    ]))
    
    return render_template('return.html', returns=return_history, active_borrows=active_borrows)

@app.route('/return/add', methods=['POST'])
def process_return():
    """Process a book return."""
    borrow_id = request.form.get('borrow_id')
    condition = request.form.get('condition', 'good')
    fine = float(request.form.get('fine', 0.0))
    
    borrow_oid = ObjectId(borrow_id)
    borrow_record = borrow_records_collection.find_one({'_id': borrow_oid})
    
    if not borrow_record or borrow_record['status'] == 'returned':
        return redirect(url_for('return_books'))
        
    # 1. Update borrow record status
    borrow_records_collection.update_one(
        {'_id': borrow_oid},
        {'$set': {'status': 'returned'}}
    )
    
    # 2. Increment book available copies
    books_collection.update_one(
        {'_id': borrow_record['book_id']},
        {'$inc': {'available_copies': 1}}
    )
    
    # 3. Create a return record
    return_record = {
        'borrow_id': borrow_oid,
        'return_date': datetime.now(),
        'condition': condition,
        'fine': fine
    }
    returns_collection.insert_one(return_record)
    
    return redirect(url_for('return_books'))

if __name__ == '__main__':
    # Run the Flask app on default port 5000
    app.run(debug=True, host='0.0.0.0')
