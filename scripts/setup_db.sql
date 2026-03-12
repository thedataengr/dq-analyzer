-- DQ Analyzer Sample Database Setup
-- Run this script to create the sample database used by dq-analyzer

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INT,
    status VARCHAR(50),
    amount DECIMAL(10,2),
    created_at TIMESTAMP
);

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(150),
    country VARCHAR(50),
    created_at TIMESTAMP
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    price DECIMAL(10,2),
    category VARCHAR(50),
    stock_count INT
);

-- Insert orders with quality issues (nulls, negatives)
INSERT INTO orders (customer_id, status, amount, created_at) VALUES
(1, 'completed', 150.00, NOW()),
(2, 'pending', NULL, NOW()),
(NULL, 'completed', 200.00, NOW()),
(3, 'completed', -50.00, NOW()),
(4, NULL, 300.00, NOW()),
(5, 'completed', 175.00, NOW()),
(NULL, NULL, NULL, NOW()),
(6, 'pending', 90.00, NOW()),
(7, 'completed', 110.00, NOW()),
(8, 'completed', NULL, NOW());

-- Insert customers with quality issues (duplicate emails, nulls)
INSERT INTO customers (name, email, country, created_at) VALUES
('Alice Smith', 'alice@example.com', 'US', NOW()),
('Bob Jones', NULL, 'UK', NOW()),
('Carol White', 'carol@example.com', NULL, NOW()),
('Dave Brown', 'alice@example.com', 'US', NOW()),
('Eve Davis', 'eve@example.com', 'IN', NOW()),
('Frank Miller', NULL, 'AU', NOW()),
('Grace Wilson', 'grace@example.com', 'US', NOW()),
(NULL, 'noname@example.com', 'CA', NOW());

-- Insert products with quality issues (negative prices, nulls)
INSERT INTO products (name, price, category, stock_count) VALUES
('Laptop', 999.99, 'Electronics', 50),
('Mouse', NULL, 'Electronics', 200),
('Keyboard', 49.99, NULL, 150),
('Monitor', -199.99, 'Electronics', 30),
('Desk', 299.99, 'Furniture', NULL),
('Chair', 199.99, 'Furniture', 75),
(NULL, 29.99, 'Accessories', 500),
('Headphones', 79.99, 'Electronics', 100);
