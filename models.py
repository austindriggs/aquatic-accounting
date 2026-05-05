"""
==============================================================================
AQUATIC PANDAS - Database Models (SQLAlchemy ORM)
CS440 Project - Budget Management System
==============================================================================

This file defines all database models using SQLAlchemy ORM.
Models are mapped to the database tables defined in init.sql.
"""

from extensions import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

# ==============================================================================
# USER MODEL
# ==============================================================================

class User(UserMixin, db.Model):
    """User account model with authentication and profile relationships."""
    __tablename__ = 'User'
    
    # Attributes
    user_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    accounts = db.relationship('Account', back_populates='user', cascade='all, delete-orphan')
    categories = db.relationship('Category', back_populates='user', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set user password"""
        # Enforce a minimal password length before hashing.
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters long")
        # Store only the hash, never the plaintext password.
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password against stored hash"""
        # Compare candidate password against the persisted hash.
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        """Return serialized user data (excludes password_hash)"""
        # API-safe representation of a user record.
        return {
            'user_id': self.user_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def get_total_budget(self):
        """Calculate total budget across all categories"""
        # Aggregate current budget values from related categories.
        return sum(category.budget for category in self.categories)
    
    def get_accounts(self):
        """Return all user accounts"""
        # Relationship-backed list of linked accounts.
        return self.accounts

    def get_id(self):
        """Return the user identifier expected by Flask-Login."""
        return str(self.user_id)


# ==============================================================================
# INSTITUTION MODEL
# ==============================================================================

class Institution(db.Model):
    """Financial institution model linked to user accounts."""
    __tablename__ = 'Institution'
    
    # Attributes
    institution_id = db.Column(db.Integer, primary_key=True)
    institution_name = db.Column(db.String(255), unique=True, nullable=False)
    website = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    accounts = db.relationship('Account', back_populates='institution')
    
    def to_dict(self):
        """Return serialized institution data"""
        # Normalize Institution object to JSON-friendly data.
        return {
            'institution_id': self.institution_id,
            'institution_name': self.institution_name,
            'website': self.website,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def get_accounts(self):
        """Return all accounts at this institution"""
        # Return accounts linked through foreign key relationship.
        return self.accounts


# ==============================================================================
# ACCOUNT MODEL
# ==============================================================================

class Account(db.Model):
    """Bank account model with balance and transaction helpers."""
    __tablename__ = 'Account'
    
    # Attributes
    account_id = db.Column(db.Integer, primary_key=True)
    account_name = db.Column(db.String(255), nullable=False)
    account_type = db.Column(db.String(50), nullable=False)
    starting_balance = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    user_id = db.Column(db.Integer, db.ForeignKey('User.user_id'), nullable=False)
    institution_id = db.Column(db.Integer, db.ForeignKey('Institution.institution_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='accounts')
    institution = db.relationship('Institution', back_populates='accounts')
    transactions = db.relationship('Transaction', back_populates='account', cascade='all, delete-orphan')
    
    def to_dict(self):
        """Return serialized account data"""
        # Include computed balance for frontend/API consumers.
        return {
            'account_id': self.account_id,
            'account_name': self.account_name,
            'account_type': self.account_type,
            'starting_balance': float(self.starting_balance),
            'user_id': self.user_id,
            'institution_id': self.institution_id,
            'balance': float(self.get_balance()),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def get_balance(self):
        """Calculate account balance (sum of inflows - sum of outflows)"""
        # Sum incoming funds and subtract outgoing funds from the starting balance.
        starting_balance = float(self.starting_balance or 0)
        total_inflow = sum(float(t.inflow) for t in self.transactions)
        total_outflow = sum(float(t.outflow) for t in self.transactions)
        return starting_balance + total_inflow - total_outflow
    
    def get_transactions(self, start_date=None, end_date=None):
        """Get transactions within date range"""
        # Start from all transactions for this account.
        query = Transaction.query.filter_by(account_id=self.account_id)
        # Optionally apply a lower date bound.
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        # Optionally apply an upper date bound.
        if end_date:
            query = query.filter(Transaction.date <= end_date)
        return query.all()

    @classmethod
    def get_user_summary(cls, user_id):
        """Call the get_account_summary stored procedure for a user.

        Returns a list of RowMapping objects with keys:
          account_id, account_name, account_type, starting_balance,
          total_inflow, total_outflow, current_balance
        """
        result = db.session.execute(
            text('CALL get_account_summary(:user_id)'),
            {'user_id': user_id}
        )
        return result.mappings().fetchall()


# ==============================================================================
# CATEGORY MODEL
# ==============================================================================

class Category(db.Model):
    """Budget category model with spending and remaining-budget helpers."""
    __tablename__ = 'Category'
    
    # Attributes
    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(255), nullable=False)
    budget = db.Column(db.Numeric(10, 2), default=0.00)
    user_id = db.Column(db.Integer, db.ForeignKey('User.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint on category_name and user_id
    __table_args__ = (db.UniqueConstraint('category_name', 'user_id', name='unique_category_per_user'),)
    
    # Relationships
    user = db.relationship('User', back_populates='categories')
    transactions = db.relationship('Transaction', back_populates='category', cascade='all, delete-orphan')
    
    def to_dict(self):
        """Return serialized category data"""
        # Include computed spending metrics for budget views.
        return {
            'category_id': self.category_id,
            'category_name': self.category_name,
            'budget': float(self.budget),
            'spent_amount': float(self.get_spent_amount()),
            'remaining_budget': float(self.get_remaining_budget()),
            'is_over_budget': self.is_over_budget(),
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def get_spent_amount(self):
        """Calculate total spent in category"""
        # Expenses are tracked in the outflow field.
        return sum(float(t.outflow) for t in self.transactions)
    
    def get_remaining_budget(self):
        """Calculate remaining budget"""
        # Remaining = configured budget - current spending.
        return float(self.budget) - self.get_spent_amount()
    
    def is_over_budget(self):
        """Check if category is over budget"""
        # True when spending exceeds allocated budget.
        return self.get_spent_amount() > float(self.budget)


# ==============================================================================
# TRANSACTION MODEL
# ==============================================================================

class Transaction(db.Model):
    """Transaction model for inflow/outflow records on an account."""
    __tablename__ = 'Transaction'
    
    # Attributes
    transaction_id = db.Column(db.Integer, primary_key=True)
    memo = db.Column(db.String(255))
    date = db.Column(db.Date, nullable=False)
    outflow = db.Column(db.Numeric(10, 2), default=0.00)
    payee = db.Column(db.String(255))
    inflow = db.Column(db.Numeric(10, 2), default=0.00)
    category_id = db.Column(db.Integer, db.ForeignKey('Category.category_id'))
    account_id = db.Column(db.Integer, db.ForeignKey('Account.account_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    category = db.relationship('Category', back_populates='transactions')
    account = db.relationship('Account', back_populates='transactions')
    
    def to_dict(self):
        """Return serialized transaction data"""
        # Standard serialized shape used by API responses.
        return {
            'transaction_id': self.transaction_id,
            'memo': self.memo,
            'date': self.date.isoformat() if self.date else None,
            'outflow': float(self.outflow),
            'payee': self.payee,
            'inflow': float(self.inflow),
            'category_id': self.category_id,
            'account_id': self.account_id,
            'amount': float(self.get_amount()),
            'type': self.get_type(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def get_amount(self):
        """Get transaction amount (absolute value)"""
        # Use outflow for expense rows, otherwise use inflow.
        return float(self.outflow) if float(self.outflow) > 0 else float(self.inflow)
    
    def get_type(self):
        """Get transaction type (income/expense)"""
        # Classify transaction based on which monetary field is populated.
        return "Expense" if float(self.outflow) > 0 else "Income"
