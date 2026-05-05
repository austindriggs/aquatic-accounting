"""
==============================================================================
AQUATIC PANDAS - API Routes
CS440 Project - Budget Management System
==============================================================================

This file defines all Flask routes/API endpoints for the application.
Routes are organized by resource type:
- Authentication (login, register, logout)
- Users (profile management)
- Accounts (account management)
- Categories (budget categories)
- Transactions (financial records)
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User, Account, Institution, Category, Transaction
from datetime import datetime
import re

# Create Blueprints for organizing routes
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
api_bp = Blueprint('api', __name__, url_prefix='/api')
main_bp = Blueprint('main', __name__)

# ==============================================================================
# AUTHENTICATION ROUTES
# ==============================================================================

def validate_email(email):
    """Validate email format"""
    # Basic email-format guard for registration.
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Register a new user account
    
    REQUEST BODY: {
        first_name: str (required),
        last_name: str (required),
        email: str (required, unique),
        password: str (required, min 6 chars),
        phone: str (optional),
        address: str (optional)
    }
    
    RESPONSE: 
        201 Created: {status: 'success', user_id: int, message: 'User created'}
        400 Bad Request: {status: 'error', message: 'error details'}
        409 Conflict: {status: 'error', message: 'Email already exists'}
    """
    try:
        # Serve the registration HTML template for GET requests
        if request.method == 'GET':
            return render_template('register.html')
            
        # Parse JSON payload or Form data from request body.
        data = request.get_json(silent=True) or request.form
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email', 'password']
        if not all(field in data for field in required_fields):
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
        
        # Validate email format
        if not validate_email(data['email']):
            return jsonify({'status': 'error', 'message': 'Invalid email format'}), 400
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return jsonify({'status': 'error', 'message': 'Email already registered'}), 409
        
        # Build model object from request payload.
        new_user = User(
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data['email'],
            phone=data.get('phone', ''),
            address=data.get('address', '')
        )
        
        # Set password (will be hashed)
        new_user.set_password(data['password'])
        
        # Persist the new user row.
        db.session.add(new_user)
        db.session.commit()
        
        # If this was a form submission, log the user in and redirect to home
        if not request.is_json:
            login_user(new_user)
            return redirect(url_for('main.index'))

        return jsonify({
            'status': 'success',
            'message': 'User registered successfully',
            'user_id': new_user.user_id
        }), 201

    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login user with email and password
    
    REQUEST BODY: {
        email: str (required),
        password: str (required)
    }
    
    RESPONSE:
        200 OK: {
            status: 'success',
            message: 'Login successful',
            user: {user_data},
            user_id: int
        }
        401 Unauthorized: {status: 'error', message: 'Invalid credentials'}
        400 Bad Request: {status: 'error', message: 'Missing fields'}
    """
    try:
        # Serve the login HTML template for GET requests
        if request.method == 'GET':
            return render_template('login.html')
            
        # Parse login payload (JSON or Form).
        data = request.get_json(silent=True) or request.form
        
        # Validate required fields
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({'status': 'error', 'message': 'Missing email or password'}), 400
        
        # Find user by email
        user = User.query.filter_by(email=data['email']).first()
        
        # Check if user exists and password is correct
        if not user or not user.check_password(data['password']):
            return jsonify({'status': 'error', 'message': 'Invalid email or password'}), 401
        
        # Create authenticated session for this user.
        login_user(user, remember=True)
        
        # If this was a form submission, redirect to the home page
        if not request.is_json:
            return redirect(url_for('main.index'))

        return jsonify({
            'status': 'success',
            'message': 'Login successful',
            'user': user.to_dict(),
            'user_id': user.user_id
        }), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """
    Logout current user
    
    RESPONSE:
        200 OK: {status: 'success', message: 'Logout successful'}
        401 Unauthorized: {status: 'error', message: 'Not logged in'}
    """
    try:
        # Clear current login session.
        logout_user()
        return jsonify({'status': 'success', 'message': 'Logout successful'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@auth_bp.route('/current-user', methods=['GET'])
@login_required
def get_current_user():
    """
    Get current logged-in user information
    
    RESPONSE:
        200 OK: {status: 'success', user: {user_data}}
        401 Unauthorized: {status: 'error', message: 'Not logged in'}
    """
    # current_user is injected by Flask-Login after authentication.
    return jsonify({
        'status': 'success',
        'user': current_user.to_dict()
    }), 200


# ==============================================================================
# VIEW ROUTES (Pages)
# ==============================================================================

@main_bp.route('/')
def index():
    """Root route: Redirect to login if not authenticated, otherwise show dashboard"""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    # Use stored procedure to calculate account balances in a single SQL call
    account_summaries = Account.get_user_summary(current_user.user_id)
    balance_by_id = {row['account_id']: float(row['current_balance']) for row in account_summaries}
    total_balance = sum(balance_by_id.values())
    
    # Get all categories with calculated metrics
    categories = current_user.categories
    total_budget = sum(float(cat.budget) for cat in categories)
    total_spent = sum(float(cat.get_spent_amount()) for cat in categories)
    total_remaining = total_budget - total_spent

    dashboard_categories = []
    for category in categories:
        budget_value = float(category.budget)
        spent_value = float(category.get_spent_amount())
        remaining_value = budget_value - spent_value
        percentage = (spent_value / budget_value * 100) if budget_value > 0 else 0
        dashboard_categories.append({
            'category_name': category.category_name,
            'budget': budget_value,
            'spent_amount': spent_value,
            'remaining_budget': remaining_value,
            'percentage': percentage,
            'is_over_budget': spent_value > budget_value,
        })
    
    # Get recent transactions (last 10) from all accounts, sorted by date
    all_transactions = []
    for account in current_user.accounts:
        all_transactions.extend(account.transactions)
    all_transactions.sort(key=lambda x: x.date, reverse=True)
    recent_transactions = all_transactions[:10]
    
    # Prepare accounts with balance info using stored procedure results
    accounts_with_balance = [
        {
            'id': account.account_id,
            'name': account.account_name,
            'type': account.account_type,
            'institution': account.institution.institution_name,
            'balance': balance_by_id.get(account.account_id, float(account.get_balance())),
            'website': account.institution.website
        }
        for account in current_user.accounts
    ]
    
    return render_template(
        'index.html',
        total_balance=total_balance,
        total_budget=total_budget,
        total_spent=total_spent,
        total_remaining=total_remaining,
        categories=dashboard_categories,
        recent_transactions=recent_transactions,
        accounts=accounts_with_balance
    )

@main_bp.route('/budget')
@login_required
def budget_page():
    """Display budget categories and spending"""
    # Load categories for the current user and compute totals used by the template
    categories = current_user.categories
    total_budgeted = sum(float(cat.budget) for cat in categories)
    total_spent = sum(float(cat.get_spent_amount()) for cat in categories)
    total_remaining = total_budgeted - total_spent

    return render_template(
        'budget.html',
        categories=categories,
        user_id=current_user.user_id,
        total_budgeted=total_budgeted,
        total_spent=total_spent,
        total_remaining=total_remaining
    )


@main_bp.route('/users/<int:user_id>/categories', methods=['POST'])
@login_required
def create_category_form(user_id):
    """Create a new Category from the HTML form and redirect back to budget."""
    # Authorization: users may only create categories for themselves
    if current_user.user_id != user_id:
        return jsonify({'status': 'error', 'message': 'Cannot create category for this user'}), 403

    # Read and normalize form values
    name = (request.form.get('name') or '').strip()
    budget_val = (request.form.get('budgeted_amount') or '').strip()

    if not name:
        return redirect(url_for('main.budget_page'))

    try:
        budget_num = float(budget_val.replace(',', '')) if budget_val else 0.0
    except ValueError:
        budget_num = 0.0

    # Create or update Category for this user
    try:
        existing_category = Category.query.filter_by(category_name=name, user_id=user_id).first()

        if existing_category:
            existing_category.budget = budget_num
        else:
            new_category = Category(category_name=name, budget=budget_num, user_id=user_id)
            db.session.add(new_category)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # The prevent_negative_budget DB trigger raises this error on invalid input
        if 'Budget cannot be negative' in str(e):
            return redirect(url_for('main.budget_page'))

    return redirect(url_for('main.budget_page'))


@main_bp.route('/categories/<int:category_id>/delete', methods=['GET'])
@login_required
def delete_category_page(category_id):
    """Delete a category from the HTML budget page and redirect back."""
    category = Category.query.get(category_id)
    if not category:
        return redirect(url_for('main.budget_page'))

    if current_user.user_id != category.user_id:
        return redirect(url_for('main.budget_page'))

    try:
        db.session.delete(category)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return redirect(url_for('main.budget_page'))

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', current_user.first_name)
        current_user.last_name = request.form.get('last_name', current_user.last_name)
        current_user.phone = request.form.get('phone', current_user.phone)
        current_user.address = request.form.get('address', current_user.address)
        new_email = request.form.get('email', '').strip()
        if new_email and new_email != current_user.email:
            existing = User.query.filter_by(email=new_email).first()
            if not existing:
                current_user.email = new_email
        db.session.commit()
        return redirect(url_for('main.profile'))
    return render_template('profile.html', user=current_user)

@main_bp.route('/transactions')
@login_required

def transactions_page():
    """Display all transactions for the current user"""
    # Gather transactions from all of the user's accounts
    all_transactions = []
    for account in current_user.accounts:
        all_transactions.extend(account.transactions)
    # Sort by date descending
    all_transactions.sort(key=lambda x: x.date, reverse=True)

    return render_template(
        'transactions.html',
        transactions=all_transactions,
        accounts=current_user.accounts,
        categories=current_user.categories,
        user_id=current_user.user_id
    )


@main_bp.route('/transactions/create', methods=['POST'])
@login_required
def create_transaction_form():
    """Create a transaction from the HTML form and redirect back to transactions."""
    date_value = (request.form.get('date') or '').strip()
    payee = (request.form.get('payee') or '').strip()
    memo = (request.form.get('memo') or '').strip()
    inflow_value = (request.form.get('inflow') or '').strip()
    outflow_value = (request.form.get('outflow') or '').strip()
    account_id = request.form.get('account_id')
    category_id = request.form.get('category_id')

    if not date_value or not payee or not account_id:
        return redirect(url_for('main.transactions_page'))

    account = Account.query.get(account_id)
    if not account or account.user_id != current_user.user_id:
        return redirect(url_for('main.transactions_page'))

    try:
        transaction_date = datetime.strptime(date_value, '%Y-%m-%d').date()
        inflow_num = float(inflow_value.replace(',', '')) if inflow_value else 0.0
        outflow_num = float(outflow_value.replace(',', '')) if outflow_value else 0.0
        category_id_num = int(category_id) if category_id else None

        if category_id_num:
            category = Category.query.get(category_id_num)
            if not category or category.user_id != current_user.user_id:
                category_id_num = None

        new_transaction = Transaction(
            date=transaction_date,
            payee=payee,
            memo=memo,
            inflow=inflow_num,
            outflow=outflow_num,
            account_id=account.account_id,
            category_id=category_id_num
        )
        db.session.add(new_transaction)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return redirect(url_for('main.transactions_page'))


@main_bp.route('/transactions/<int:transaction_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_transaction_page(transaction_id):
    """Edit a transaction from a simple HTML form."""
    transaction = Transaction.query.get(transaction_id)
    if not transaction or transaction.account.user_id != current_user.user_id:
        return redirect(url_for('main.transactions_page'))

    if request.method == 'GET':
        accounts = current_user.accounts
        categories = current_user.categories
        return render_template(
            'edit_transaction.html',
            transaction=transaction,
            accounts=accounts,
            categories=categories
        )

    date_value = (request.form.get('date') or '').strip()
    payee = (request.form.get('payee') or '').strip()
    memo = (request.form.get('memo') or '').strip()
    inflow_value = (request.form.get('inflow') or '').strip()
    outflow_value = (request.form.get('outflow') or '').strip()
    account_id = request.form.get('account_id')
    category_id = request.form.get('category_id')

    if not date_value or not payee or not account_id:
        return redirect(url_for('main.edit_transaction_page', transaction_id=transaction_id))

    selected_account = Account.query.get(account_id)
    if not selected_account or selected_account.user_id != current_user.user_id:
        return redirect(url_for('main.edit_transaction_page', transaction_id=transaction_id))

    try:
        transaction.date = datetime.strptime(date_value, '%Y-%m-%d').date()
        transaction.payee = payee
        transaction.memo = memo
        transaction.inflow = float(inflow_value.replace(',', '')) if inflow_value else 0.0
        transaction.outflow = float(outflow_value.replace(',', '')) if outflow_value else 0.0
        transaction.account_id = selected_account.account_id

        if category_id:
            category = Category.query.get(category_id)
            transaction.category_id = category.category_id if category and category.user_id == current_user.user_id else None
        else:
            transaction.category_id = None

        db.session.commit()
    except Exception:
        db.session.rollback()

    return redirect(url_for('main.transactions_page'))


@main_bp.route('/transactions/<int:transaction_id>/delete', methods=['GET'])
@login_required
def delete_transaction_page(transaction_id):
    """Delete a transaction from the HTML page and redirect back to transactions."""
    transaction = Transaction.query.get(transaction_id)
    if not transaction or transaction.account.user_id != current_user.user_id:
        return redirect(url_for('main.transactions_page'))

    try:
        db.session.delete(transaction)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return redirect(url_for('main.transactions_page'))

@main_bp.route('/accounts')
@login_required
def accounts_page():
    """Display list of user accounts"""
    accounts = [
        {
            'id': account.account_id,
            'name': account.account_name,
            'type': account.account_type,
            'institution': account.institution.institution_name,
            'starting_balance': float(account.starting_balance or 0),
            'website': account.institution.website or ''
        }
        for account in current_user.accounts
    ]

    return render_template('accounts.html', accounts=accounts)


@main_bp.route('/accounts/create', methods=['POST'])
@login_required
def create_account_form():
    """Create a bank account from the HTML form and redirect back to accounts."""
    account_name = (request.form.get('name') or '').strip()
    account_type = (request.form.get('type') or '').strip()
    institution_name = (request.form.get('institution') or '').strip()
    website = (request.form.get('website') or '').strip()
    starting_amount_value = (request.form.get('starting_amount') or '').strip()

    if not account_name or not account_type or not institution_name:
        return redirect(url_for('main.accounts_page'))

    try:
        starting_amount = float(starting_amount_value.replace(',', '')) if starting_amount_value else 0.0
    except ValueError:
        starting_amount = 0.0

    try:
        institution = Institution.query.filter_by(institution_name=institution_name).first()
        if institution:
            if website:
                institution.website = website
        else:
            institution = Institution(institution_name=institution_name, website=website)
            db.session.add(institution)
            db.session.flush()

        new_account = Account(
            account_name=account_name,
            account_type=account_type,
            starting_balance=starting_amount,
            user_id=current_user.user_id,
            institution_id=institution.institution_id
        )
        db.session.add(new_account)

        db.session.commit()
    except Exception:
        db.session.rollback()

    return redirect(url_for('main.accounts_page'))


@main_bp.route('/accounts/<int:account_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_account_page(account_id):
    """Edit an account's details from a simple HTML form."""
    account = Account.query.get(account_id)
    if not account or account.user_id != current_user.user_id:
        return redirect(url_for('main.accounts_page'))

    if request.method == 'GET':
        return render_template('edit_account.html', account=account)

    account_name = (request.form.get('name') or '').strip()
    account_type = (request.form.get('type') or '').strip()
    institution_name = (request.form.get('institution') or '').strip()
    website = (request.form.get('website') or '').strip()
    starting_amount_value = (request.form.get('starting_amount') or '').strip()

    if not account_name or not account_type or not institution_name:
        return redirect(url_for('main.edit_account_page', account_id=account_id))

    try:
        starting_balance = float(starting_amount_value.replace(',', '')) if starting_amount_value else 0.0
    except ValueError:
        starting_balance = 0.0

    try:
        institution = Institution.query.filter_by(institution_name=institution_name).first()
        if institution:
            if website:
                institution.website = website
        else:
            institution = Institution(institution_name=institution_name, website=website)
            db.session.add(institution)
            db.session.flush()

        account.account_name = account_name
        account.account_type = account_type
        account.starting_balance = starting_balance
        account.institution_id = institution.institution_id

        db.session.commit()
    except Exception:
        db.session.rollback()

    return redirect(url_for('main.accounts_page'))


@main_bp.route('/accounts/<int:account_id>/delete', methods=['GET'])
@login_required
def delete_account_page(account_id):
    """Delete an account from the HTML page and redirect back to accounts."""
    account = Account.query.get(account_id)
    if not account or account.user_id != current_user.user_id:
        return redirect(url_for('main.accounts_page'))

    try:
        db.session.delete(account)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return redirect(url_for('main.accounts_page'))




# Convenience routes: expose common auth pages at top-level paths
# so templates or external links that point to `/login` or `/register`
# work without requiring the `/auth` prefix.
@main_bp.route('/login', methods=['GET'])
def login_view():
    """Redirect to the auth blueprint login handler (serves login page)."""
    return redirect(url_for('auth.login'))


@main_bp.route('/register', methods=['GET'])
def register_view():
    """Redirect to the auth blueprint register handler (serves register page)."""
    return redirect(url_for('auth.register'))


@main_bp.route('/logout', methods=['GET'])
@login_required
def logout_view():
    """Convenience GET logout which ends the session and redirects to login.

    Note: the API logout endpoint remains POST /auth/logout for scripted calls.
    """
    logout_user()
    return redirect(url_for('auth.login'))


# ==============================================================================
# ERROR HANDLERS
# ==============================================================================

@main_bp.app_errorhandler(404)
def not_found(error):
    """Return JSON error payloads for common HTTP failures."""
    return {'error': 'Resource not found'}, 404

@main_bp.app_errorhandler(500)
def internal_error(error):
    """Global error handler for server-side exceptions."""
    db.session.rollback()
    return {'error': 'Internal server error'}, 500

@main_bp.app_errorhandler(400)
def bad_request(error):
    """Handler for malformed requests."""
    return {'error': 'Bad request'}, 400


# ==============================================================================
# USER ROUTES
# ==============================================================================

@api_bp.route('/users/<int:user_id>', methods=['GET'])
@login_required
def get_user(user_id):
    """
    Get user profile
    Users can only view their own profile unless they're admin
    
    RESPONSE:
        200 OK: {status: 'success', user: {user_data}}
        404 Not Found: {status: 'error', message: 'User not found'}
        403 Forbidden: {status: 'error', message: 'Cannot view this user'}
    """
    try:
        # Check authorization
        if current_user.user_id != user_id:
            return jsonify({'status': 'error', 'message': 'Cannot view this user'}), 403
        
        # Load target user record.
        user = User.query.get(user_id)
        if not user:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404
        
        return jsonify({
            'status': 'success',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/users/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    """
    Update user profile information
    Users can only update their own profile
    
    REQUEST BODY: {
        first_name: str (optional),
        last_name: str (optional),
        phone: str (optional),
        address: str (optional)
    }
    
    RESPONSE:
        200 OK: {status: 'success', user: {updated_user_data}}
        404 Not Found: {status: 'error', message: 'User not found'}
        403 Forbidden: {status: 'error', message: 'Cannot update this user'}
    """
    try:
        # Check authorization
        if current_user.user_id != user_id:
            return jsonify({'status': 'error', 'message': 'Cannot update this user'}), 403
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404
        
        # Apply partial updates from request body.
        data = request.get_json()
        
        # Update allowed fields
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'phone' in data:
            user.phone = data['phone']
        if 'address' in data:
            user.address = data['address']
        
        # Persist profile changes.
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """
    Delete user account (cascades to all related data)
    Users can only delete their own account
    
    RESPONSE:
        200 OK: {status: 'success', message: 'User deleted'}
        404 Not Found: {status: 'error', message: 'User not found'}
        403 Forbidden: {status: 'error', message: 'Cannot delete this user'}
    """
    try:
        # Check authorization
        if current_user.user_id != user_id:
            return jsonify({'status': 'error', 'message': 'Cannot delete this user'}), 403
        
        # Load then delete user; cascades remove linked data by schema rules.
        user = User.query.get(user_id)
        if not user:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404
        
        db.session.delete(user)
        db.session.commit()
        
        # Logout the user
        logout_user()
        
        return jsonify({
            'status': 'success',
            'message': 'User deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


# ==============================================================================
# ACCOUNT ROUTES
# ==============================================================================

@api_bp.route('/users/<int:user_id>/accounts', methods=['POST'])
@login_required
def create_account(user_id):
    """
    Create new account for user
    Users can only create accounts for themselves
    
    REQUEST BODY: {
        account_name: str (required),
        account_type: str (required, e.g., 'Checking', 'Savings'),
        institution_id: int (required)
    }
    
    RESPONSE:
        201 Created: {status: 'success', account: {account_data}}
        400 Bad Request: {status: 'error', message: 'Missing fields'}
        403 Forbidden: {status: 'error', message: 'Cannot create account'}
        404 Not Found: {status: 'error', message: 'Institution not found'}
    """
    try:
        # Check authorization
        if current_user.user_id != user_id:
            return jsonify({'status': 'error', 'message': 'Cannot create account for this user'}), 403
        
        # Parse and validate account creation payload.
        data = request.get_json()
        
        # Validate required fields
        if not data or not data.get('account_name') or not data.get('account_type') or not data.get('institution_id'):
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
        
        # Check if institution exists
        institution = Institution.query.get(data['institution_id'])
        if not institution:
            return jsonify({'status': 'error', 'message': 'Institution not found'}), 404
        
        # Create new account
        new_account = Account(
            account_name=data['account_name'],
            account_type=data['account_type'],
            user_id=user_id,
            institution_id=data['institution_id']
        )
        
        # Persist the new account record.
        db.session.add(new_account)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'account': new_account.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/users/<int:user_id>/accounts', methods=['GET'])
@login_required
def get_user_accounts(user_id):
    """
    Get all accounts for user with balances
    Users can only view their own accounts
    
    RESPONSE:
        200 OK: {status: 'success', accounts: [{account_data}]}
        403 Forbidden: {status: 'error', message: 'Cannot view accounts'}
    """
    try:
        # Check authorization
        if current_user.user_id != user_id:
            return jsonify({'status': 'error', 'message': 'Cannot view these accounts'}), 403
        
        accounts = Account.query.filter_by(user_id=user_id).all()

        # Use stored procedure for balance calculations
        summaries = Account.get_user_summary(user_id)
        balance_by_id = {row['account_id']: float(row['current_balance']) for row in summaries}

        account_list = []
        for account in accounts:
            account_data = account.to_dict()
            if account.account_id in balance_by_id:
                account_data['balance'] = balance_by_id[account.account_id]
            account_list.append(account_data)

        return jsonify({
            'status': 'success',
            'accounts': account_list
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/accounts/<int:account_id>', methods=['GET'])
@login_required
def get_account(account_id):
    """
    Get account details with balance
    
    RESPONSE:
        200 OK: {status: 'success', account: {account_data}}
        404 Not Found: {status: 'error', message: 'Account not found'}
        403 Forbidden: {status: 'error', message: 'Cannot view this account'}
    """
    try:
        account = Account.query.get(account_id)
        if not account:
            return jsonify({'status': 'error', 'message': 'Account not found'}), 404
        
        # Check authorization
        if current_user.user_id != account.user_id:
            return jsonify({'status': 'error', 'message': 'Cannot view this account'}), 403
        
        return jsonify({
            'status': 'success',
            'account': account.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/accounts/<int:account_id>', methods=['PUT'])
@login_required
def update_account(account_id):
    """
    Update account details
    
    REQUEST BODY: {
        account_name: str (optional),
        account_type: str (optional),
        institution_id: int (optional)
    }
    
    RESPONSE:
        200 OK: {status: 'success', account: {updated_account_data}}
        404 Not Found: {status: 'error', message: 'Account not found'}
        403 Forbidden: {status: 'error', message: 'Cannot update this account'}
    """
    try:
        account = Account.query.get(account_id)
        if not account:
            return jsonify({'status': 'error', 'message': 'Account not found'}), 404
        
        # Check authorization
        if current_user.user_id != account.user_id:
            return jsonify({'status': 'error', 'message': 'Cannot update this account'}), 403
        
        # Apply optional field updates.
        data = request.get_json()
        
        # Update allowed fields
        if 'account_name' in data:
            account.account_name = data['account_name']
        if 'account_type' in data:
            account.account_type = data['account_type']
        if 'institution_id' in data:
            # Verify institution exists
            institution = Institution.query.get(data['institution_id'])
            if not institution:
                return jsonify({'status': 'error', 'message': 'Institution not found'}), 404
            account.institution_id = data['institution_id']
        
        # Persist account updates.
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'account': account.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/accounts/<int:account_id>', methods=['DELETE'])
@login_required
def delete_account(account_id):
    """
    Delete account and all associated transactions
    
    RESPONSE:
        200 OK: {status: 'success', message: 'Account deleted'}
        404 Not Found: {status: 'error', message: 'Account not found'}
        403 Forbidden: {status: 'error', message: 'Cannot delete this account'}
    """
    try:
        account = Account.query.get(account_id)
        if not account:
            return jsonify({'status': 'error', 'message': 'Account not found'}), 404
        
        # Check authorization
        if current_user.user_id != account.user_id:
            return jsonify({'status': 'error', 'message': 'Cannot delete this account'}), 403
        
        db.session.delete(account)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Account deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


# ==============================================================================
# CATEGORY ROUTES
# ==============================================================================

@api_bp.route('/users/<int:user_id>/categories', methods=['POST'])
@login_required
def create_category(user_id):
    """
    Create budget category for user
    Users can only create categories for themselves
    
    REQUEST BODY: {
        category_name: str (required),
        budget: float (required, >= 0)
    }
    
    RESPONSE:
        201 Created: {status: 'success', category: {category_data}}
        400 Bad Request: {status: 'error', message: 'Missing fields or invalid data'}
        403 Forbidden: {status: 'error', message: 'Cannot create category'}
        409 Conflict: {status: 'error', message: 'Category already exists'}
    """
    try:
        # Check authorization
        if current_user.user_id != user_id:
            return jsonify({'status': 'error', 'message': 'Cannot create category for this user'}), 403
        
        # Parse and validate category payload.
        data = request.get_json()
        
        # Validate required fields
        if not data or not data.get('category_name') or 'budget' not in data:
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
        
        # Check if category already exists for this user
        existing_category = Category.query.filter_by(
            category_name=data['category_name'],
            user_id=user_id
        ).first()
        
        if existing_category:
            return jsonify({'status': 'error', 'message': 'Category already exists for this user'}), 409
        
        # Create new category
        new_category = Category(
            category_name=data['category_name'],
            budget=float(data['budget']),
            user_id=user_id
        )
        
        # Persist the new budget category.
        db.session.add(new_category)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'category': new_category.to_dict()
        }), 201
        
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid budget value'}), 400
    except Exception as e:
        db.session.rollback()
        # Catch the error raised by the prevent_negative_budget DB trigger
        if 'Budget cannot be negative' in str(e):
            return jsonify({'status': 'error', 'message': 'Budget cannot be negative'}), 400
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/users/<int:user_id>/categories', methods=['GET'])
@login_required
def get_user_categories(user_id):
    """
    Get all budget categories for user
    Users can only view their own categories
    
    RESPONSE:
        200 OK: {status: 'success', categories: [{category_data}]}
        403 Forbidden: {status: 'error', message: 'Cannot view categories'}
    """
    try:
        # Check authorization
        if current_user.user_id != user_id:
            return jsonify({'status': 'error', 'message': 'Cannot view these categories'}), 403
        
        categories = Category.query.filter_by(user_id=user_id).all()
        
        return jsonify({
            'status': 'success',
            'categories': [category.to_dict() for category in categories]
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/categories/<int:category_id>', methods=['GET'])
@login_required
def get_category(category_id):
    """
    Get category details with spending information
    
    RESPONSE:
        200 OK: {status: 'success', category: {category_data}}
        404 Not Found: {status: 'error', message: 'Category not found'}
        403 Forbidden: {status: 'error', message: 'Cannot view this category'}
    """
    try:
        category = Category.query.get(category_id)
        if not category:
            return jsonify({'status': 'error', 'message': 'Category not found'}), 404
        
        # Check authorization
        if current_user.user_id != category.user_id:
            return jsonify({'status': 'error', 'message': 'Cannot view this category'}), 403
        
        return jsonify({
            'status': 'success',
            'category': category.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/categories/<int:category_id>', methods=['PUT'])
@login_required
def update_category(category_id):
    """
    Update category budget
    
    REQUEST BODY: {
        category_name: str (optional),
        budget: float (optional, >= 0)
    }
    
    RESPONSE:
        200 OK: {status: 'success', category: {updated_category_data}}
        404 Not Found: {status: 'error', message: 'Category not found'}
        403 Forbidden: {status: 'error', message: 'Cannot update this category'}
    """
    try:
        category = Category.query.get(category_id)
        if not category:
            return jsonify({'status': 'error', 'message': 'Category not found'}), 404
        
        # Check authorization
        if current_user.user_id != category.user_id:
            return jsonify({'status': 'error', 'message': 'Cannot update this category'}), 403
        
        # Apply category name/budget updates.
        data = request.get_json()
        
        # Update allowed fields
        if 'category_name' in data:
            category.category_name = data['category_name']
        if 'budget' in data:
            category.budget = float(data['budget'])
        
        # Persist category updates.
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'category': category.to_dict()
        }), 200
        
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid budget value'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@login_required
def delete_category(category_id):
    """
    Delete category (cascades to associated transactions)
    
    RESPONSE:
        200 OK: {status: 'success', message: 'Category deleted'}
        404 Not Found: {status: 'error', message: 'Category not found'}
        403 Forbidden: {status: 'error', message: 'Cannot delete this category'}
    """
    try:
        category = Category.query.get(category_id)
        if not category:
            return jsonify({'status': 'error', 'message': 'Category not found'}), 404
        
        # Check authorization
        if current_user.user_id != category.user_id:
            return jsonify({'status': 'error', 'message': 'Cannot delete this category'}), 403
        
        db.session.delete(category)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Category deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


# ==============================================================================
# TRANSACTION ROUTES
# ==============================================================================

@api_bp.route('/accounts/<int:account_id>/transactions', methods=['POST'])
@login_required
def create_transaction(account_id):
    """
    Create new transaction for account
    Users can only create transactions for their own accounts
    
    REQUEST BODY: {
        date: str (required, YYYY-MM-DD format),
        payee: str (required),
        memo: str (optional),
        outflow: float (optional, >= 0),
        inflow: float (optional, >= 0),
        category_id: int (optional)
    }
    
    RESPONSE:
        201 Created: {status: 'success', transaction: {transaction_data}}
        400 Bad Request: {status: 'error', message: 'Invalid data'}
        404 Not Found: {status: 'error', message: 'Account not found'}
        403 Forbidden: {status: 'error', message: 'Cannot create transaction'}
    """
    try:
        account = Account.query.get(account_id)
        if not account:
            return jsonify({'status': 'error', 'message': 'Account not found'}), 404
        
        # Check authorization
        if current_user.user_id != account.user_id:
            return jsonify({'status': 'error', 'message': 'Cannot create transaction for this account'}), 403
        
        # Parse transaction payload.
        data = request.get_json()
        
        # Validate required fields
        if not data or not data.get('date') or not data.get('payee'):
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
        
        # Parse date
        try:
            transaction_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid date format (use YYYY-MM-DD)'}), 400
        
        # Create a transaction row linked to the account.
        new_transaction = Transaction(
            date=transaction_date,
            payee=data['payee'],
            memo=data.get('memo', ''),
            outflow=float(data.get('outflow', 0)),
            inflow=float(data.get('inflow', 0)),
            account_id=account_id,
            category_id=data.get('category_id')
        )
        
        # Persist transaction.
        db.session.add(new_transaction)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'transaction': new_transaction.to_dict()
        }), 201
        
    except ValueError as e:
        return jsonify({'status': 'error', 'message': 'Invalid value: ' + str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/accounts/<int:account_id>/transactions', methods=['GET'])
@login_required
def get_account_transactions(account_id):
    """
    Get all transactions for account
    Users can only view transactions for their own accounts
    
    Query parameters:
        start_date: str (optional, YYYY-MM-DD)
        end_date: str (optional, YYYY-MM-DD)
    
    RESPONSE:
        200 OK: {status: 'success', transactions: [{transaction_data}]}
        404 Not Found: {status: 'error', message: 'Account not found'}
        403 Forbidden: {status: 'error', message: 'Cannot view transactions'}
    """
    try:
        account = Account.query.get(account_id)
        if not account:
            return jsonify({'status': 'error', 'message': 'Account not found'}), 404
        
        # Check authorization
        if current_user.user_id != account.user_id:
            return jsonify({'status': 'error', 'message': 'Cannot view these transactions'}), 403
        
        # Optional filtering window for transaction listing.
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        transactions = account.get_transactions(start_date, end_date)
        
        return jsonify({
            'status': 'success',
            'transactions': [transaction.to_dict() for transaction in transactions]
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/transactions/<int:transaction_id>', methods=['GET'])
@login_required
def get_transaction(transaction_id):
    """
    Get transaction details
    
    RESPONSE:
        200 OK: {status: 'success', transaction: {transaction_data}}
        404 Not Found: {status: 'error', message: 'Transaction not found'}
        403 Forbidden: {status: 'error', message: 'Cannot view this transaction'}
    """
    try:
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            return jsonify({'status': 'error', 'message': 'Transaction not found'}), 404
        
        # Check authorization
        if current_user.user_id != transaction.account.user_id:
            return jsonify({'status': 'error', 'message': 'Cannot view this transaction'}), 403
        
        return jsonify({
            'status': 'success',
            'transaction': transaction.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/transactions/<int:transaction_id>', methods=['PUT'])
@login_required
def update_transaction(transaction_id):
    """
    Update transaction details
    
    REQUEST BODY: {
        date: str (optional, YYYY-MM-DD),
        payee: str (optional),
        memo: str (optional),
        outflow: float (optional),
        inflow: float (optional),
        category_id: int (optional)
    }
    
    RESPONSE:
        200 OK: {status: 'success', transaction: {updated_transaction_data}}
        404 Not Found: {status: 'error', message: 'Transaction not found'}
        403 Forbidden: {status: 'error', message: 'Cannot update this transaction'}
    """
    try:
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            return jsonify({'status': 'error', 'message': 'Transaction not found'}), 404
        
        # Check authorization
        if current_user.user_id != transaction.account.user_id:
            return jsonify({'status': 'error', 'message': 'Cannot update this transaction'}), 403
        
        # Apply partial transaction updates.
        data = request.get_json()
        
        # Update allowed fields
        if 'date' in data:
            try:
                transaction.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Invalid date format (use YYYY-MM-DD)'}), 400
        
        if 'payee' in data:
            transaction.payee = data['payee']
        if 'memo' in data:
            transaction.memo = data['memo']
        if 'outflow' in data:
            transaction.outflow = float(data['outflow'])
        if 'inflow' in data:
            transaction.inflow = float(data['inflow'])
        if 'category_id' in data:
            transaction.category_id = data['category_id']
        
        # Persist updated transaction values.
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'transaction': transaction.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500


@api_bp.route('/transactions/<int:transaction_id>', methods=['DELETE'])
@login_required
def delete_transaction(transaction_id):
    """
    Delete transaction
    
    RESPONSE:
        200 OK: {status: 'success', message: 'Transaction deleted'}
        404 Not Found: {status: 'error', message: 'Transaction not found'}
        403 Forbidden: {status: 'error', message: 'Cannot delete this transaction'}
    """
    try:
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            return jsonify({'status': 'error', 'message': 'Transaction not found'}), 404
        
        # Check authorization
        if current_user.user_id != transaction.account.user_id:
            return jsonify({'status': 'error', 'message': 'Cannot delete this transaction'}), 403
        
        db.session.delete(transaction)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Transaction deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Server error: ' + str(e)}), 500
