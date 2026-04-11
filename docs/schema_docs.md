# Database Schema Documentation

## Table: orders
**Description:** Records all customer purchase transactions. This is the primary revenue table.
**Business Rules:**
- Records are never deleted. Use status='cancelled' for cancellations.
- Negative amount values indicate refunds or chargebacks.
- customer_id can be null for guest checkout orders — these cannot be attributed to a CRM record.
- amount represents the final charged amount in USD after discounts.

**Columns:**
- id: Primary key. Auto-incremented.
- customer_id: FK to customers.id. Nullable for guest checkouts.
- status: Lifecycle state. Values: pending, completed, cancelled.
- amount: Final transaction value in USD. Negative = refund.
- created_at: UTC timestamp of order creation.

**Known Issues:**
- As of Q1 2026, approximately 20-30% of rows have null customer_id due to a guest checkout bug introduced in v2.3 of the payment service.
- The ETL job that populates this table runs at 2am UTC. Data from the previous day may be incomplete before this time.

## Table: customers
**Description:** Stores CRM records for registered customers which includes primary identity and demographic information of customers. 

**Business Rules:**
- Email Uniqueness: The email column should technically be unique; however, historical data may contain duplicates where the same email is tied to multiple IDs.
- Geography: The country column uses ISO 3166-1 alpha-2 or full country names. This is used for tax and shipping calculations.
- Identity: Records where name is NULL represent customers who signed up via social login but haven't completed their profile setup.

**Columns:**
- id: Primary key. Unique identifier for the customer.
- name: Full name of the customer. May be NULL for incomplete profiles.
- email: Primary contact address. Used for account login and notifications.
- country: Residential country of the customer. Critical for regional reporting.
- created_at: UTC timestamp when the customer account was first created.

**Known Issues:**
- Duplicate Emails: Approximately 5-10% of records share an email address with another ID (e.g., Alice and Dave sharing alice@example.com).
- Null Contact Data: Some of the imported legacy records may lack email addresses entirely.

## Table: products
**Description:** The master catalog for all physical items available for sale. Used for inventory management and pricing.

**Business Rules:**
- Pricing: The price column represents the standard MSRP.
- Stock Management: A stock_count of 0 indicates an "Out of Stock" status on the storefront.
- Validation: Prices should always be positive. Negative prices are considered data entry errors and should be excluded from stock value calculations.

**Columns:**
- id: Primary key. Unique product SKU or identifier.
- name: The display name of the product.
- price: Unit price in USD.
- category: Product classification (e.g., Electronics, Furniture). Used for front-end navigation.
- stock_count: Current quantity available in the warehouse.

**Known Issues:**
- Negative Pricing: A bug in the inventory upload tool occasionally records negative values for items marked for clearance (e.g., Monitor at -199.99).
- Categorization: Items added via the "Quick-Add" option often have NULL categories and require manual cleanup by the Merchandising team.
- Missing Stock Data: Furniture items sourced from third-party vendors frequently show NULL stock counts due to an API sync lag.
