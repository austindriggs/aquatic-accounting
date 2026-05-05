-- ==============================================================================
-- AQUATIC PANDAS - Database Schema Initialization
-- CS440 Project - Database Design
-- ==============================================================================

-- Drop existing triggers, procedures, and tables if they exist (for clean development)
DROP TRIGGER IF EXISTS prevent_negative_budget;
DROP TRIGGER IF EXISTS update_transaction_timestamp;
DROP PROCEDURE IF EXISTS get_account_summary;
DROP TABLE IF EXISTS Transaction;
DROP TABLE IF EXISTS Category;
DROP TABLE IF EXISTS Account;
DROP TABLE IF EXISTS Institution;
DROP TABLE IF EXISTS User;

-- ==============================================================================
-- USER TABLE
-- ==============================================================================
-- Purpose: Stores user account information
-- Primary Key: user_id (auto-incremented)
-- Constraints: email must be unique
CREATE TABLE User (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    address VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==============================================================================
-- INSTITUTION TABLE
-- ==============================================================================
-- Purpose: Stores banking/financial institution information
-- Primary Key: institution_id (auto-incremented)
-- Constraints: institution_name must be unique
CREATE TABLE Institution (
    institution_id INT AUTO_INCREMENT PRIMARY KEY,
    institution_name VARCHAR(255) UNIQUE NOT NULL,
    website VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==============================================================================
-- ACCOUNT TABLE
-- ==============================================================================
-- Purpose: Stores user's accounts at various institutions
-- Primary Key: account_id (auto-incremented)
-- Foreign Keys: user_id (references User), institution_id (references Institution)
CREATE TABLE Account (
    account_id INT AUTO_INCREMENT PRIMARY KEY,
    account_name VARCHAR(255) NOT NULL,
    account_type VARCHAR(50) NOT NULL,
    starting_balance DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    user_id INT NOT NULL,
    institution_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES User(user_id) ON DELETE CASCADE,
    FOREIGN KEY (institution_id) REFERENCES Institution(institution_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==============================================================================
-- CATEGORY TABLE
-- ==============================================================================
-- Purpose: Stores budget categories for a user
-- Primary Key: category_id (auto-incremented)
-- Foreign Key: user_id (references User)
-- Constraints: category_name and user_id must be unique together
CREATE TABLE Category (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(255) NOT NULL,
    budget DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES User(user_id) ON DELETE CASCADE,
    UNIQUE KEY unique_category_per_user (category_name, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==============================================================================
-- TRANSACTION TABLE
-- ==============================================================================
-- Purpose: Records financial transactions (income/expenses)
-- Primary Key: transaction_id (auto-incremented)
-- Foreign Keys: category_id (references Category), account_id (references Account)
-- Note: outflow = money leaving the account (expense)
--       inflow = money entering the account (income)
CREATE TABLE Transaction (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    memo VARCHAR(255),
    date DATE NOT NULL,
    outflow DECIMAL(10, 2) DEFAULT 0.00,
    payee VARCHAR(255),
    category_id INT,
    account_id INT NOT NULL,
    inflow DECIMAL(10, 2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES Category(category_id) ON DELETE SET NULL,
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==============================================================================
-- INDEXES
-- ==============================================================================
-- Performance optimization indexes
CREATE INDEX idx_account_user_id ON Account(user_id);
CREATE INDEX idx_account_institution_id ON Account(institution_id);
CREATE INDEX idx_category_user_id ON Category(user_id);
CREATE INDEX idx_transaction_account_id ON Transaction(account_id);
CREATE INDEX idx_transaction_category_id ON Transaction(category_id);
CREATE INDEX idx_transaction_date ON Transaction(date);

-- Composite indexes for common multi-column filters
CREATE INDEX idx_transaction_account_date ON Transaction(account_id, date);
CREATE INDEX idx_transaction_category_date ON Transaction(category_id, date);

-- ==============================================================================
-- STORED PROCEDURE: get_account_summary
-- ==============================================================================
-- Purpose: Returns a balance summary for every account belonging to a user.
--          Calculates current balance as starting_balance + total inflows - total outflows.
-- Usage:   CALL get_account_summary(<user_id>);
DELIMITER $$
CREATE PROCEDURE get_account_summary(IN p_user_id INT)
BEGIN
    SELECT
        a.account_id,
        a.account_name,
        a.account_type,
        a.starting_balance,
        COALESCE(SUM(t.inflow),  0) AS total_inflow,
        COALESCE(SUM(t.outflow), 0) AS total_outflow,
        a.starting_balance
            + COALESCE(SUM(t.inflow),  0)
            - COALESCE(SUM(t.outflow), 0) AS current_balance
    FROM Account a
    LEFT JOIN Transaction t ON a.account_id = t.account_id
    WHERE a.user_id = p_user_id
    GROUP BY a.account_id, a.account_name, a.account_type, a.starting_balance;
END$$
DELIMITER ;

-- ==============================================================================
-- TRIGGER: prevent_negative_budget
-- ==============================================================================
-- Purpose: Enforces a database-level rule that a Category budget cannot be set
--          to a negative value on INSERT.
DELIMITER $$
CREATE TRIGGER prevent_negative_budget
BEFORE INSERT ON Category
FOR EACH ROW
BEGIN
    IF NEW.budget < 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Budget cannot be negative';
    END IF;
END$$
DELIMITER ;

-- ==============================================================================
-- TRIGGER: update_transaction_timestamp
-- ==============================================================================
-- Purpose: Automatically refreshes the updated_at timestamp on every UPDATE to
--          a Transaction row, ensuring the audit column is always accurate.
DELIMITER $$
CREATE TRIGGER update_transaction_timestamp
BEFORE UPDATE ON Transaction
FOR EACH ROW
BEGIN
    SET NEW.updated_at = NOW();
END$$
DELIMITER ;
