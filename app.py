from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from functools import wraps
from bson.objectid import ObjectId
from datetime import datetime
from config import Config

# Import collections and helpers from our database module
from database.db import (
    users_collection, books_collection, borrow_records_collection,
    returns_collection, categories_collection,
    insert_book, get_all_books, borrow_book, return_book, add_user, get_user_list
)

app = Flask(__name__)
app.config.from_object(Config)

# ==========================================
# Authentication Helpers & Routes
# ==========================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle the mock login logic for the DBMS lab miniproject."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Simple hardcoded admin credentials for the scope of the project
        if username == 'admin' and password == 'password':
            session['admin_logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials. Please use admin / password", "error")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Clear the session and log the user out."""
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# Dashboard Routes
# ==========================================
@app.route('/')
@login_required
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
@login_required
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
@login_required
def add_new_book():
    """Create a new book record."""
    title = request.form.get('title')
    author = request.form.get('author')
    isbn = request.form.get('isbn')
    category_id = request.form.get('category_id')
    
    category = categories_collection.find_one({'_id': ObjectId(category_id)}) if category_id else None
    cat_name = category['name'] if category else 'Uncategorized'
    
    copies = int(request.form.get('copies', 0))
    
    # Using the helper function
    insert_book(title, author, cat_name, isbn, copies, available=copies)
    
    return redirect(url_for('books'))

@app.route('/books/edit/<book_id>', methods=['POST'])
@login_required
def edit_book(book_id):
    """Update an existing book record."""
    title = request.form.get('title')
    author = request.form.get('author')
    isbn = request.form.get('isbn')
    category_id = request.form.get('category_id')
    added_copies = int(request.form.get('added_copies', 0))
    
    category = categories_collection.find_one({'_id': ObjectId(category_id)}) if category_id else None
    cat_name = category['name'] if category else 'Uncategorized'
    
    # Update book details and incrementally adjust copies
    books_collection.update_one(
        {'_id': ObjectId(book_id)},
        {
            '$set': {
                'title': title,
                'author': author,
                'isbn': isbn,
                'category': cat_name
            },
            '$inc': {
                'quantity': added_copies,
                'available': added_copies
            }
        }
    )
    return redirect(url_for('books'))

@app.route('/books/delete/<book_id>', methods=['POST'])
@login_required
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
@login_required
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
@login_required
def users():
    """Display all users."""
    all_users = get_user_list()
    return render_template('users.html', users=all_users)

@app.route('/users/add', methods=['POST'])
@login_required
def add_new_user():
    """Create a new user (Member/Student)."""
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    role = request.form.get('role', 'student')
    
    # Using helper function (generating a mock password for now)
    add_user(name, email, f"{name.lower()}123", role, phone)
    
    return redirect(url_for('users'))

@app.route('/users/delete/<user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """Delete a user record."""
    users_collection.delete_one({'_id': ObjectId(user_id)})
    return jsonify({'success': True})

# ==========================================
# Borrow Routes
# ==========================================
@app.route('/borrow')
@login_required
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
    available_books = list(books_collection.find({'available': {'$gt': 0}}))
    all_users = get_user_list()
    
    return render_template('borrow.html', 
                           active_borrows=active_borrows,
                           books=available_books,
                           users=all_users)

@app.route('/borrow/add', methods=['POST'])
@login_required
def issue_book():
    """Issue a book to a user."""
    book_id = request.form.get('book_id')
    user_id = request.form.get('user_id')
    due_date = request.form.get('due_date')
    
    borrow_date = datetime.now()
    
    # Call the helper method from the database
    res = borrow_book(user_id, book_id, borrow_date=borrow_date)
    
    # Note: If res is None, book was not available.
    # In a full app, you would flash an error. 
    return redirect(url_for('borrow'))

# ==========================================
# Return Routes
# ==========================================
@app.route('/return')
@login_required
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
@login_required
def process_return():
    """Process a book return."""
    borrow_id = request.form.get('borrow_id')
    condition = request.form.get('condition', 'good')
    fine = float(request.form.get('fine', 0.0))
    
    # Process return using the db helper
    return_book(borrow_id, return_date=datetime.now(), fine=fine)
    
    return redirect(url_for('return_books'))

if __name__ == '__main__':
    # Run the Flask app on default port 5000
    app.run(debug=True, host='0.0.0.0')
