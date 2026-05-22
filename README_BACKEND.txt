Angie's Mini Mart / Angielu Hub - Backend + SQLite Version

Run the app:
  python main.py

Default admin account:
  Username: admin
  Password: admin123

Backend/database files added:
  backend.py        - SQLite backend, CRUD helpers, auth, reports, exports, backup
  angie.sqlite3    - SQLite database with seeded users, products, categories, orders, transactions, reports, settings

UI note:
  The existing UI design/layout was kept. Existing buttons and forms were wired to SQLite-backed actions.

Main backend-backed actions:
  Login / Sign up
  Add Product / Save Product / Product selection
  Category creation
  Create Order / Print Receipt
  Transaction receipt preview / reprint / PDF download
  Export CSV for orders, transactions, reports
  Generate Report
  Save Business Profile, Account, Preferences
  Backup / Restore SQLite database

Latest update:
  Product Management > + Add Product now opens a professional modal window using Poppins font.
  The window saves directly to SQLite and keeps the existing dashboard/product UI unchanged.
