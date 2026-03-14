from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from functools import wraps
from bson.objectid import ObjectId
from datetime import datetime
from config import Config

# Import collections and helpers from our database module
from database.db import (
    users_collection, books_collection, borrow_records_collection,
    returns_collection, categories_collection,
    insert_book, get_all_books, borrow_book, return_book as db_return_book, add_user, get_user_list
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
    """Render the main dashboard with summary stats and chart data."""
    from datetime import timedelta
    import calendar

    # ── Core stats ──────────────────────────────────────────────────────
    total_books      = books_collection.count_documents({})
    total_users      = users_collection.count_documents({})
    active_borrows   = borrow_records_collection.count_documents({'status': 'borrowed'})
    returned_books   = borrow_records_collection.count_documents({'status': 'returned'})
    total_categories = categories_collection.count_documents({})

    stats = {
        'total_books':      total_books,
        'total_users':      total_users,
        'active_borrows':   active_borrows,
        'returned_books':   returned_books,
        'total_categories': total_categories,
    }

    # ── Borrow trend: last 6 months ──────────────────────────────────────
    today = datetime.now()
    months_labels = []
    months_borrows = []
    months_returns = []

    for i in range(5, -1, -1):
        # First day of the month i months ago
        target = (today.replace(day=1) - timedelta(days=1)) if i == 0 else today
        # Go back i months
        month_offset = (today.month - i - 1) % 12 + 1
        year_offset  = today.year - ((i - today.month + 1) // 12 + (1 if (today.month - i) <= 0 else 0))
        first_day = datetime(year_offset, month_offset, 1)
        last_day  = datetime(year_offset, month_offset,
                             calendar.monthrange(year_offset, month_offset)[1], 23, 59, 59)

        borrows = borrow_records_collection.count_documents({
            'borrow_date': {'$gte': first_day, '$lte': last_day}
        })
        returns = borrow_records_collection.count_documents({
            'return_date': {'$gte': first_day, '$lte': last_day},
            'status': 'returned'
        })
        months_labels.append(first_day.strftime('%b %Y'))
        months_borrows.append(borrows)
        months_returns.append(returns)

    # ── Category distribution ─────────────────────────────────────────────
    category_pipeline = [
        {'$group': {'_id': '$category', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 8}
    ]
    cat_data   = list(books_collection.aggregate(category_pipeline))
    cat_labels = [d['_id'] if d['_id'] else 'Uncategorized' for d in cat_data]
    cat_counts = [d['count'] for d in cat_data]

    # ── Recent borrow activity (last 6 records) ───────────────────────────
    recent_borrows = list(borrow_records_collection.aggregate([
        {'$sort': {'borrow_date': -1}},
        {'$limit': 6},
        {'$lookup': {'from': 'books',  'localField': 'book_id',  'foreignField': '_id', 'as': 'book_info'}},
        {'$lookup': {'from': 'users',  'localField': 'user_id',  'foreignField': '_id', 'as': 'user_info'}},
    ]))

    return render_template(
        'dashboard.html',
        stats          = stats,
        recent_borrows = recent_borrows,
        months_labels  = months_labels,
        months_borrows = months_borrows,
        months_returns = months_returns,
        cat_labels     = cat_labels,
        cat_counts     = cat_counts,
    )

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

@app.route('/add_book', methods=['POST'])
@login_required
def add_book():
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

@app.route('/edit_book/<book_id>', methods=['POST'])
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

@app.route('/delete_book/<book_id>', methods=['POST'])
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
    name  = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    role  = request.form.get('role', 'student')
    add_user(name, email, f"{name.lower()}123", role, phone)
    return redirect(url_for('users'))

@app.route('/users/edit/<user_id>', methods=['POST'])
@login_required
def edit_user(user_id):
    """Update an existing user record."""
    users_collection.update_one(
        {'_id': ObjectId(user_id)},
        {'$set': {
            'name':  request.form.get('name'),
            'email': request.form.get('email'),
            'phone': request.form.get('phone'),
            'role':  request.form.get('role', 'student'),
        }}
    )
    return redirect(url_for('users'))

@app.route('/users/delete/<user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """Delete a user record."""
    users_collection.delete_one({'_id': ObjectId(user_id)})
    return jsonify({'success': True})

# ==========================================
# Borrow History Route
# ==========================================
@app.route('/borrow/history')
@login_required
def borrow_history():
    """Show full borrow history for all records."""
    all_borrows = list(borrow_records_collection.aggregate([
        {'$sort': {'borrow_date': -1}},
        {'$lookup': {'from': 'books', 'localField': 'book_id', 'foreignField': '_id', 'as': 'book_info'}},
        {'$lookup': {'from': 'users', 'localField': 'user_id', 'foreignField': '_id', 'as': 'user_info'}},
    ]))
    return render_template('borrow_history.html', borrows=all_borrows, now_date=datetime.now())

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
    """Issue a book to a user, storing borrow_date and due_date."""
    book_id   = request.form.get('book_id')
    user_id   = request.form.get('user_id')
    borrow_date_str = request.form.get('borrow_date')
    due_date_str    = request.form.get('due_date')

    # Parse the dates submitted from the form
    try:
        borrow_date = datetime.strptime(borrow_date_str, '%Y-%m-%d') if borrow_date_str else datetime.now()
        due_date    = datetime.strptime(due_date_str,    '%Y-%m-%d') if due_date_str    else None
    except ValueError:
        borrow_date = datetime.now()
        due_date    = None

    # Call the database helper; it returns None if the book is unavailable
    res = borrow_book(user_id, book_id, borrow_date=borrow_date, due_date=due_date)

    if res:
        # Redirect back to the borrow page with a success flag so SweetAlert2 fires
        return redirect(url_for('borrow', success=1))
    else:
        # Book is no longer available (race condition or bad request)
        return redirect(url_for('borrow', error='unavailable'))

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
    
    return render_template('return.html', returns=return_history, active_borrows=active_borrows, now_date=datetime.now())

@app.route('/return_book', methods=['POST'])
@login_required
def return_book_route():
    """
    Process a book return with automatic overdue fine calculation.
    Fine rules:
      - Late return: ₹5 per overdue day
      - Damaged condition: ₹100 extra
      - Lost: ₹500 extra
    """
    borrow_id = request.form.get('borrow_id')
    condition  = request.form.get('condition', 'good')

    if not borrow_id:
        return redirect(url_for('return_books'))

    # Fetch the borrow record to inspect due_date
    borrow_record = borrow_records_collection.find_one({'_id': ObjectId(borrow_id)})
    if not borrow_record:
        return redirect(url_for('return_books'))

    today       = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return_date = datetime.now()
    fine        = 0.0

    # ── Late return fine ────────────────────────────────────────────────
    due_date = borrow_record.get('due_date')
    if due_date:
        due_date_clean = due_date.replace(hour=0, minute=0, second=0, microsecond=0)
        if today > due_date_clean:
            overdue_days = (today - due_date_clean).days
            fine += overdue_days * 5.0   # ₹5 per day

    # ── Condition-based fine ────────────────────────────────────────────
    if condition == 'damaged':
        fine += 100.0
    elif condition == 'lost':
        fine += 500.0

    # Call the updated db helper
    res = db_return_book(borrow_id, return_date=return_date, fine=round(fine, 2), condition=condition)

    if res:
        return redirect(url_for('return_books', success=1, fine=round(fine, 2), condition=condition))
    else:
        return redirect(url_for('return_books', error='already_returned'))

@app.route('/return/add', methods=['POST'])
@login_required
def process_return():
    """Legacy redirect — kept for backwards compatibility."""
    return redirect(url_for('return_books'))

if __name__ == '__main__':
    # Run the Flask app on default port 5000
    app.run(debug=True, host='0.0.0.0')
