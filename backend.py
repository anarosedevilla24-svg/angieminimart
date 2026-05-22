import csv
import hashlib
import os
import secrets
import shutil
import sqlite3
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "angie.sqlite3")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def display_datetime(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return value


def display_date(value: str) -> str:
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%b %d, %Y")
    except Exception:
        return value


def money(value: Any) -> str:
    try:
        return f"₱{float(value):,.2f}"
    except Exception:
        return "₱0.00"


def parse_money(value: Any) -> float:
    if value is None:
        return 0.0
    cleaned = str(value).replace("₱", "").replace(",", "").strip()
    if not cleaned:
        return 0.0
    return float(cleaned)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).replace("pcs", "").replace("packs", "").replace("reams", "").strip()))
    except Exception:
        return default


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, _digest = stored_hash.split("$", 1)
        return secrets.compare_digest(hash_password(password, salt), stored_hash)
    except Exception:
        return False


class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'Administrator',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    icon TEXT NOT NULL DEFAULT '🔹',
                    color TEXT NOT NULL DEFAULT '#3b82f6',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    sku TEXT NOT NULL UNIQUE,
                    category_id INTEGER,
                    description TEXT NOT NULL DEFAULT '',
                    price REAL NOT NULL DEFAULT 0,
                    stock INTEGER NOT NULL DEFAULT 0,
                    unit TEXT NOT NULL DEFAULT 'pcs',
                    status TEXT NOT NULL DEFAULT 'Active',
                    icon TEXT NOT NULL DEFAULT '📦',
                    reorder_level INTEGER NOT NULL DEFAULT 20,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    address TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_no TEXT NOT NULL UNIQUE,
                    customer_id INTEGER,
                    order_type TEXT NOT NULL DEFAULT 'Walk-in',
                    subtotal REAL NOT NULL DEFAULT 0,
                    delivery_fee REAL NOT NULL DEFAULT 0,
                    discount REAL NOT NULL DEFAULT 0,
                    tax REAL NOT NULL DEFAULT 0,
                    total REAL NOT NULL DEFAULT 0,
                    payment_method TEXT NOT NULL DEFAULT 'Cash',
                    payment_status TEXT NOT NULL DEFAULT 'Paid',
                    status TEXT NOT NULL DEFAULT 'Pending',
                    fulfillment_status TEXT NOT NULL DEFAULT 'In Store',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    product_id INTEGER,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    unit_price REAL NOT NULL DEFAULT 0,
                    line_total REAL NOT NULL DEFAULT 0,
                    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_no TEXT NOT NULL UNIQUE,
                    order_id INTEGER,
                    customer_id INTEGER,
                    items_count INTEGER NOT NULL DEFAULT 0,
                    payment_method TEXT NOT NULL DEFAULT 'Cash',
                    paid_for TEXT NOT NULL DEFAULT '',
                    amount REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'Completed',
                    reference_no TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
                    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    date_range TEXT NOT NULL,
                    generated_by TEXT NOT NULL DEFAULT 'Admin User',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'Completed'
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            columns = [row["name"] for row in conn.execute("PRAGMA table_info(transactions)").fetchall()]
            if "paid_for" not in columns:
                conn.execute("ALTER TABLE transactions ADD COLUMN paid_for TEXT NOT NULL DEFAULT ''")
        self.seed_data()

    def seed_data(self) -> None:
        with self.connect() as conn:
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if user_count == 0:
                conn.execute(
                    "INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                    ("admin", "admin@angieluhub.com", hash_password("admin123"), "Administrator", now_text()),
                )

            cat_count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            if cat_count == 0:
                conn.executemany(
                    "INSERT INTO categories (name, icon, color, created_at) VALUES (?, ?, ?, ?)",
                    [
                        ("School Supplies", "📗", "#22a660", now_text()),
                        ("Snacks", "🍪", "#ff7f7f", now_text()),
                        ("Banana Chips", "🍌", "#f59e0b", now_text()),
                        ("Printing Supplies", "🖨️", "#9b5de5", now_text()),
                        ("Drinks", "🥤", "#3b82f6", now_text()),
                        ("Others", "🔹", "#3b82f6", now_text()),
                    ],
                )

            product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            if product_count == 0:
                category_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM categories")}
                products = [
                    ("Notebook", "NBK-SML-001", "School Supplies", "80 leaves, ruled paper", 15.00, 120, "pcs", "Active", "📘", 40),
                    ("Ballpen", "BLPN-BLK-001", "School Supplies", "Smooth write, 0.7mm", 12.00, 250, "pcs", "Active", "🖊️", 50),
                    ("Pencil", "PNCL-HB-001", "School Supplies", "High quality HB pencil", 8.00, 180, "pcs", "Active", "✏️", 40),
                    ("Ruler", "RULR-30-001", "School Supplies", "Transparent plastic ruler", 20.00, 90, "pcs", "Active", "📏", 100),
                    ("Correction Tape", "CORR-TP-001", "School Supplies", "5mm x 6m, easy glide", 25.00, 60, "pcs", "Active", "🧴", 70),
                    ("Banana Chips", "BCHP-100G-001", "Banana Chips", "Crispy & naturally sweet", 45.00, 75, "packs", "Active", "🍌", 25),
                    ("Chicharon", "CHCH-100G-001", "Snacks", "Crunchy snack pack", 35.00, 15, "packs", "Active", "🍪", 20),
                    ("Piattos", "PIAT-85G-001", "Snacks", "Cheese flavored chips", 20.00, 0, "pcs", "Active", "🍟", 15),
                    ("Nature's Spring", "WTR-500ML-001", "Drinks", "500ml bottled water", 12.00, 200, "pcs", "Active", "🥤", 60),
                    ("Printing Paper A4", "PP-A4-001", "Printing Supplies", "70gsm, 500 sheets", 210.00, 30, "reams", "Active", "📄", 40),
                ]
                conn.executemany(
                    """
                    INSERT INTO products
                    (name, sku, category_id, description, price, stock, unit, status, icon, reorder_level, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (name, sku, category_ids.get(category), desc, price, stock, unit, status, icon, reorder, now_text())
                        for name, sku, category, desc, price, stock, unit, status, icon, reorder in products
                    ],
                )

            customer_count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
            if customer_count == 0:
                conn.executemany(
                    "INSERT INTO customers (name, phone, email, address, created_at) VALUES (?, ?, ?, ?, ?)",
                    [
                        ("Maria Santos", "0917 111 2222", "maria.santos@email.com", "Davao City", now_text()),
                        ("John Dela Cruz", "0918 765 4321", "john.delacruz@email.com", "Davao City", now_text()),
                        ("Ana Reyes", "0919 333 4444", "ana.reyes@email.com", "Davao City", now_text()),
                        ("Kevin Lim", "0920 555 6666", "kevin.lim@email.com", "Davao City", now_text()),
                        ("Peter Co", "0921 777 8888", "peter.co@email.com", "Davao City", now_text()),
                        ("Rachel Tan", "0922 999 0000", "rachel.tan@email.com", "Davao City", now_text()),
                        ("Liza Mendoza", "0923 123 4567", "liza.mendoza@email.com", "Davao City", now_text()),
                        ("Daniel Aquino", "0924 234 5678", "daniel.aquino@email.com", "Davao City", now_text()),
                        ("Mark Joseph", "0925 345 6789", "mark.joseph@email.com", "Davao City", now_text()),
                    ],
                )

            order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            if order_count == 0:
                self._seed_orders(conn)

            report_count = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
            if report_count == 0:
                conn.executemany(
                    "INSERT INTO reports (name, report_type, date_range, generated_by, created_at, status) VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        ("Daily Sales Report - May 26", "Daily Report", "May 26, 2025", "Admin User", "2025-05-26 10:15:00", "Completed"),
                        ("Daily Inventory Report", "Daily Report", "May 26, 2025", "Admin User", "2025-05-26 09:45:00", "Completed"),
                        ("Daily Printing Report", "Daily Report", "May 26, 2025", "Admin User", "2025-05-26 09:30:00", "Completed"),
                        ("Weekly Sales Report", "Weekly Report", "May 20 - May 26", "Admin User", "2025-05-26 08:00:00", "Completed"),
                        ("Monthly Sales Report", "Monthly Report", "May 2025", "Admin User", "2025-05-25 19:15:00", "Completed"),
                        ("Inventory Summary Report", "Inventory Report", "May 2025", "Admin User", "2025-05-25 18:40:00", "Completed"),
                        ("Printing Performance Report", "Printing Report", "May 2025", "Admin User", "2025-05-25 18:20:00", "Completed"),
                        ("Sales by Category Report", "Sales Report", "May 2025", "Admin User", "2025-05-25 17:50:00", "Completed"),
                    ],
                )

            defaults = {
                "business_name": "Angielu Hub",
                "owner_name": "Admin User",
                "contact_number": "0918 765 4321",
                "email_address": "admin@angieluhub.com",
                "store_address": "Barangay 10, Davao City",
                "currency": "Philippine Peso (₱)",
                "date_format": "Month Day, Year",
                "receipt_size": "80mm Thermal Receipt",
                "low_stock_alert_level": "10 items",
                "theme": "Soft Pink / Cream",
                "last_backup": "Never",
            }
            for key, value in defaults.items():
                conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

    def _seed_orders(self, conn: sqlite3.Connection) -> None:
        customers = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM customers")}
        products = {r["name"]: r for r in conn.execute("SELECT id, name, price FROM products")}
        sample_orders = [
            ("ORD-2025-0526-001", "Maria Santos", "Walk-in", "Paid", "Pending", "In Store", "Cash", "2025-05-26 10:50:00", [("Notebook", 3), ("Ballpen", 5), ("Pencil", 15)]),
            ("ORD-2025-0526-002", "John Dela Cruz", "Delivery", "Paid", "Processing", "Out for Delivery", "GCash", "2025-05-26 10:42:00", [("Notebook", 2), ("Ballpen", 10), ("Banana Chips", 2), ("Printing Paper A4", 2), ("Correction Tape", 1)]),
            ("ORD-2025-0526-003", "Ana Reyes", "Online", "Paid", "Completed", "Delivered", "Cash", "2025-05-26 10:28:00", [("Banana Chips", 4), ("Ruler", 1)]),
            ("ORD-2025-0525-015", "Kevin Lim", "Printing Job", "Partial", "Ready for Pickup", "Ready for Pickup", "Card", "2025-05-25 15:10:00", [("Printing Paper A4", 3)]),
            ("ORD-2025-0525-014", "Peter Co", "Pickup", "Paid", "Completed", "Picked Up", "Maya", "2025-05-25 13:25:00", [("Notebook", 4), ("Ballpen", 8)]),
            ("ORD-2025-0524-021", "Rachel Tan", "Online", "Paid", "Completed", "Delivered", "Cash", "2025-05-24 17:18:00", [("Chicharon", 2), ("Piattos", 3)]),
            ("ORD-2025-0524-020", "Liza Mendoza", "Delivery", "Unpaid", "Pending", "In Store", "GCash", "2025-05-24 14:05:00", [("Printing Paper A4", 1), ("Notebook", 2)]),
            ("ORD-2025-0523-018", "Mark Joseph", "Printing Job", "Paid", "Completed", "Picked Up", "Card", "2025-05-23 12:30:00", [("Printing Paper A4", 1), ("Correction Tape", 2)]),
            ("ORD-2025-0523-017", "Daniel Aquino", "Snacks", "Paid", "Cancelled", "Cancelled", "Cash", "2025-05-23 09:40:00", [("Banana Chips", 2), ("Piattos", 4)]),
        ]
        for idx, (order_no, customer, order_type, payment_status, status, fulfillment, method, created_at, items) in enumerate(sample_orders, 1):
            subtotal = 0.0
            resolved_items = []
            for product_name, qty in items:
                product = products[product_name]
                unit_price = float(product["price"])
                line_total = unit_price * qty
                subtotal += line_total
                resolved_items.append((product["id"], product_name, qty, unit_price, line_total))
            delivery_fee = 75.0 if order_type == "Delivery" else 0.0
            discount = 0.0
            tax = round(subtotal * 0.12, 2) if status != "Cancelled" else 0.0
            total = subtotal + delivery_fee - discount + tax
            cur = conn.execute(
                """
                INSERT INTO orders
                (order_no, customer_id, order_type, subtotal, delivery_fee, discount, tax, total, payment_method,
                 payment_status, status, fulfillment_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (order_no, customers.get(customer), order_type, subtotal, delivery_fee, discount, tax, total, method,
                 payment_status, status, fulfillment, created_at),
            )
            order_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price, line_total) VALUES (?, ?, ?, ?, ?, ?)",
                [(order_id, *item) for item in resolved_items],
            )
            trx_status = "Refunded" if status == "Cancelled" else "Completed" if payment_status == "Paid" else "Pending"
            trx_no = f"TRX-2025-0526-{idx:03d}"
            prefix = {"Cash": "CS", "GCash": "GC", "Maya": "MY", "Card": "CR"}.get(method, "RF")
            conn.execute(
                """
                INSERT INTO transactions
                (transaction_no, order_id, customer_id, items_count, payment_method, amount, status, reference_no, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (trx_no, order_id, customers.get(customer), sum(q for _, _, q, _, _ in resolved_items), method, total,
                 trx_status, f"{prefix}-SM26-{idx:03d}", created_at),
            )

    # ---------- generic ----------
    def log(self, action: str, details: str = "") -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO audit_logs (action, details, created_at) VALUES (?, ?, ?)", (action, details, now_text()))

    def table_rows(self, query: str, params: Iterable[Any] = ()) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute(query, tuple(params)))

    # ---------- auth ----------
    def create_user(self, username: str, email: str, password: str, role: str = "Administrator") -> Tuple[bool, str]:
        username = username.strip()
        email = email.strip()
        if not username or not email or not password:
            return False, "Please complete all fields."
        if len(password) < 6:
            return False, "Password must be at least 6 characters."
        try:
            with self.connect() as conn:
                conn.execute(
                    "INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                    (username, email, hash_password(password), role, now_text()),
                )
            self.log("Create User", f"Created user: {username}")
            return True, "Account created successfully."
        except sqlite3.IntegrityError as exc:
            msg = str(exc).lower()
            if "username" in msg:
                return False, "Username already exists."
            if "email" in msg:
                return False, "Email already exists."
            return False, "Account already exists."

    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        username = username.strip()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username)).fetchone()
        if row and verify_password(password, row["password_hash"]):
            self.log("Login", f"User logged in: {row['username']}")
            return dict(row)
        return None

    # ---------- categories/products ----------
    def list_categories(self) -> List[sqlite3.Row]:
        return self.table_rows(
            """
            SELECT c.*, COUNT(p.id) AS product_count
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.id AND p.status != 'Archived'
            GROUP BY c.id
            ORDER BY c.name
            """
        )

    def add_category(self, name: str, icon: str = "🔹", color: str = "#3b82f6") -> Tuple[bool, str]:
        name = name.strip()
        if not name:
            return False, "Category name is required."
        try:
            with self.connect() as conn:
                conn.execute("INSERT INTO categories (name, icon, color, created_at) VALUES (?, ?, ?, ?)", (name, icon, color, now_text()))
            self.log("Add Category", name)
            return True, "Category added."
        except sqlite3.IntegrityError:
            return False, "Category already exists."

    def list_products(self, include_archived: bool = False) -> List[sqlite3.Row]:
        where = "" if include_archived else "WHERE p.status != 'Archived'"
        return self.table_rows(
            f"""
            SELECT p.*, COALESCE(c.name, 'Others') AS category_name, COALESCE(c.icon, p.icon) AS category_icon
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            {where}
            ORDER BY p.updated_at DESC, p.id DESC
            """
        )

    def get_product_by_id(self, product_id: int) -> Optional[sqlite3.Row]:
        rows = self.table_rows(
            """
            SELECT p.*, COALESCE(c.name, 'Others') AS category_name
            FROM products p LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.id = ?
            """,
            (product_id,),
        )
        return rows[0] if rows else None

    def find_product_by_sku(self, sku: str) -> Optional[sqlite3.Row]:
        rows = self.table_rows("SELECT * FROM products WHERE sku = ?", (sku.strip(),))
        return rows[0] if rows else None

    def category_id(self, name: str) -> Optional[int]:
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
            if row:
                return row["id"]
            cur = conn.execute("INSERT INTO categories (name, icon, color, created_at) VALUES (?, ?, ?, ?)", (name, "🔹", "#3b82f6", now_text()))
            return cur.lastrowid

    def add_product(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        name = str(data.get("name", "")).strip()
        sku = str(data.get("sku", "")).strip()
        category = str(data.get("category", "Others")).strip() or "Others"
        if not name or not sku:
            return False, "Product name and SKU are required."
        try:
            with self.connect() as conn:
                cat_id = self.category_id(category)
                conn.execute(
                    """
                    INSERT INTO products
                    (name, sku, category_id, description, price, stock, unit, status, icon, reorder_level, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        sku,
                        cat_id,
                        str(data.get("description", "")),
                        float(data.get("price", 0) or 0),
                        int(data.get("stock", 0) or 0),
                        str(data.get("unit", "pcs") or "pcs"),
                        str(data.get("status", "Active") or "Active"),
                        str(data.get("icon", "📦") or "📦"),
                        int(data.get("reorder_level", 20) or 20),
                        now_text(),
                    ),
                )
            self.log("Add Product", f"{name} ({sku})")
            return True, "Product added successfully."
        except sqlite3.IntegrityError:
            return False, "SKU already exists."
        except ValueError:
            return False, "Price and stock must be valid numbers."

    def update_product(self, product_id: int, data: Dict[str, Any]) -> Tuple[bool, str]:
        product = self.get_product_by_id(product_id)
        if not product:
            return False, "Product not found."
        name = str(data.get("name", "")).strip()
        sku = str(data.get("sku", "")).strip()
        category = str(data.get("category", "Others")).strip() or "Others"
        if not name or not sku:
            return False, "Product name and SKU are required."
        try:
            with self.connect() as conn:
                cat_id = self.category_id(category)
                conn.execute(
                    """
                    UPDATE products
                    SET name = ?, sku = ?, category_id = ?, description = ?, price = ?, stock = ?, unit = ?,
                        status = ?, icon = ?, reorder_level = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        sku,
                        cat_id,
                        str(data.get("description", "")),
                        float(data.get("price", 0) or 0),
                        int(data.get("stock", 0) or 0),
                        str(data.get("unit", "pcs") or "pcs"),
                        str(data.get("status", "Active") or "Active"),
                        str(data.get("icon", product["icon"] or "📦")),
                        int(data.get("reorder_level", product["reorder_level"] or 20)),
                        now_text(),
                        product_id,
                    ),
                )
            self.log("Update Product", f"{name} ({sku})")
            return True, "Product updated successfully."
        except sqlite3.IntegrityError:
            return False, "SKU already exists."
        except ValueError:
            return False, "Price and stock must be valid numbers."

    def archive_product(self, product_id: int) -> Tuple[bool, str]:
        with self.connect() as conn:
            conn.execute("UPDATE products SET status = 'Archived', updated_at = ? WHERE id = ?", (now_text(), product_id))
        self.log("Archive Product", f"ID {product_id}")
        return True, "Product archived."

    # ---------- orders/transactions ----------
    def next_number(self, prefix: str, table: str, column: str) -> str:
        date_part = datetime.now().strftime("%Y-%m-%d").replace("-", "")
        short = datetime.now().strftime("%Y-%m-%d")
        with self.connect() as conn:
            count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE ?", (f"{prefix}-{short.replace('-', '')}%",)).fetchone()[0]
        return f"{prefix}-{date_part}-{count + 1:03d}"

    def create_order_from_product(self, product_id: int, customer_name: str = "Walk-in Customer", quantity: int = 1) -> Tuple[bool, str]:
        product = self.get_product_by_id(product_id)
        if not product:
            return False, "Product not found."
        if product["stock"] < quantity:
            return False, "Not enough stock."
        with self.connect() as conn:
            customer = conn.execute("SELECT id FROM customers WHERE name = ?", (customer_name,)).fetchone()
            if customer:
                customer_id = customer["id"]
            else:
                cur = conn.execute("INSERT INTO customers (name, created_at) VALUES (?, ?)", (customer_name, now_text()))
                customer_id = cur.lastrowid
            today = datetime.now().strftime("%Y-%m-%d")
            daily_count = conn.execute("SELECT COUNT(*) FROM orders WHERE created_at LIKE ?", (today + "%",)).fetchone()[0]
            order_no = f"ORD-{today}-{daily_count + 1:03d}"
            unit_price = float(product["price"])
            subtotal = unit_price * quantity
            tax = round(subtotal * 0.12, 2)
            total = subtotal + tax
            cur = conn.execute(
                """
                INSERT INTO orders
                (order_no, customer_id, order_type, subtotal, delivery_fee, discount, tax, total, payment_method,
                 payment_status, status, fulfillment_status, created_at)
                VALUES (?, ?, 'Walk-in', ?, 0, 0, ?, ?, 'Cash', 'Paid', 'Completed', 'In Store', ?)
                """,
                (order_no, customer_id, subtotal, tax, total, now_text()),
            )
            order_id = cur.lastrowid
            conn.execute(
                "INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price, line_total) VALUES (?, ?, ?, ?, ?, ?)",
                (order_id, product_id, product["name"], quantity, unit_price, subtotal),
            )
            conn.execute("UPDATE products SET stock = stock - ?, updated_at = ? WHERE id = ?", (quantity, now_text(), product_id))
            trx_count = conn.execute("SELECT COUNT(*) FROM transactions WHERE created_at LIKE ?", (today + "%",)).fetchone()[0]
            trx_no = f"TRX-{today}-{trx_count + 1:03d}"
            conn.execute(
                """
                INSERT INTO transactions
                (transaction_no, order_id, customer_id, items_count, payment_method, amount, status, reference_no, created_at)
                VALUES (?, ?, ?, ?, 'Cash', ?, 'Completed', ?, ?)
                """,
                (trx_no, order_id, customer_id, quantity, total, f"CS-{datetime.now().strftime('%m%d')}-{trx_count + 1:03d}", now_text()),
            )
        self.log("Create Order", order_no)
        return True, f"Order created: {order_no}"

    def list_orders(self) -> List[sqlite3.Row]:
        return self.table_rows(
            """
            SELECT o.*, COALESCE(c.name, 'Walk-in Customer') AS customer_name,
                   COUNT(oi.id) AS item_lines, COALESCE(SUM(oi.quantity), 0) AS qty_count
            FROM orders o
            LEFT JOIN customers c ON c.id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.id
            GROUP BY o.id
            ORDER BY o.created_at DESC, o.id DESC
            """
        )

    def get_order(self, order_id: int) -> Optional[sqlite3.Row]:
        rows = self.table_rows(
            """
            SELECT o.*, COALESCE(c.name, 'Walk-in Customer') AS customer_name, c.phone, c.email, c.address
            FROM orders o LEFT JOIN customers c ON c.id = o.customer_id
            WHERE o.id = ?
            """,
            (order_id,),
        )
        return rows[0] if rows else None

    def order_items(self, order_id: int) -> List[sqlite3.Row]:
        return self.table_rows("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,))

    def update_order_status(self, order_id: int, status: str, fulfillment_status: Optional[str] = None) -> Tuple[bool, str]:
        order = self.get_order(order_id)
        if not order:
            return False, "Order not found."
        fulfillment_status = fulfillment_status or order["fulfillment_status"]
        with self.connect() as conn:
            conn.execute("UPDATE orders SET status = ?, fulfillment_status = ? WHERE id = ?", (status, fulfillment_status, order_id))
        self.log("Update Order Status", f"{order['order_no']} -> {status}")
        return True, "Order status updated."

    def list_transactions(self) -> List[sqlite3.Row]:
        return self.table_rows(
            """
            SELECT t.*, COALESCE(c.name, 'Walk-in Customer') AS customer_name
            FROM transactions t
            LEFT JOIN customers c ON c.id = t.customer_id
            ORDER BY t.created_at DESC, t.id DESC
            """
        )

    def create_manual_payment(
        self,
        customer_name: str = "Walk-in Customer",
        amount: float = 0,
        payment_method: str = "Cash",
        paid_for: str = "",
        quantity: int = 1,
        reference_no: str = "",
        status: str = "Completed",
    ) -> Tuple[bool, str]:
        customer_name = customer_name.strip() or "Walk-in Customer"
        payment_method = payment_method.strip() or ("Pending" if status == "Pending" else "Cash")
        paid_for = paid_for.strip()
        reference_no = reference_no.strip()
        status = "Pending" if status == "Pending" else "Completed"
        quantity = max(1, int(quantity or 1))

        if amount <= 0:
            return False, "Please enter a valid payment amount."
        if not paid_for:
            return False, "Please enter the name of the bill/payment."

        with self.connect() as conn:
            customer = conn.execute("SELECT id FROM customers WHERE name = ?", (customer_name,)).fetchone()
            if customer:
                customer_id = customer["id"]
            else:
                cur = conn.execute("INSERT INTO customers (name, created_at) VALUES (?, ?)", (customer_name, now_text()))
                customer_id = cur.lastrowid

            today = datetime.now().strftime("%Y-%m-%d")
            trx_count = conn.execute("SELECT COUNT(*) FROM transactions WHERE created_at LIKE ?", (today + "%",)).fetchone()[0]
            trx_no = f"TRX-{today}-{trx_count + 1:03d}"
            if not reference_no:
                prefix = "BILL" if status == "Pending" else "PAY"
                reference_no = f"{prefix}-{datetime.now().strftime('%m%d')}-{trx_count + 1:03d}"

            conn.execute(
                """
                INSERT INTO transactions
                (transaction_no, order_id, customer_id, items_count, payment_method, paid_for, amount, status, reference_no, created_at)
                VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (trx_no, customer_id, quantity, payment_method, paid_for, amount, status, reference_no, now_text()),
            )

        self.log("Create Payment", f"{trx_no} - {paid_for} - {status}")
        return True, f"{'Pending bill added' if status == 'Pending' else 'Payment saved'}: {trx_no}"

    def get_transaction(self, transaction_id: int) -> Optional[sqlite3.Row]:
        rows = self.table_rows(
            """
            SELECT t.*, COALESCE(c.name, 'Walk-in Customer') AS customer_name, c.phone, c.email, c.address,
                   o.subtotal, o.delivery_fee, o.discount, o.tax, o.total AS order_total, o.order_no
            FROM transactions t
            LEFT JOIN customers c ON c.id = t.customer_id
            LEFT JOIN orders o ON o.id = t.order_id
            WHERE t.id = ?
            """,
            (transaction_id,),
        )
        return rows[0] if rows else None

    def transaction_items(self, transaction_id: int) -> List[sqlite3.Row]:
        trx = self.get_transaction(transaction_id)
        if not trx or not trx["order_id"]:
            return []
        return self.order_items(int(trx["order_id"]))

    # ---------- reports/settings/export ----------
    def list_reports(self) -> List[sqlite3.Row]:
        return self.table_rows("SELECT * FROM reports ORDER BY created_at DESC, id DESC")

    def generate_report(self, report_type: str = "Sales Report") -> Tuple[bool, str]:
        today = datetime.now().strftime("%b %d, %Y")
        name = f"{report_type} - {today}"
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO reports (name, report_type, date_range, generated_by, created_at, status) VALUES (?, ?, ?, ?, ?, 'Completed')",
                (name, report_type, today, "Admin User", now_text()),
            )
        self.log("Generate Report", name)
        return True, f"Report generated: {name}"

    def get_settings(self) -> Dict[str, str]:
        return {row["key"]: row["value"] for row in self.table_rows("SELECT key, value FROM settings")}

    def set_setting(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))

    def save_business_profile(self, data: Dict[str, str]) -> Tuple[bool, str]:
        for key, value in data.items():
            self.set_setting(key, value)
        self.log("Save Business Profile", ", ".join(data.keys()))
        return True, "Business profile saved."

    def update_account(self, username: str, role: str, password: str = "") -> Tuple[bool, str]:
        with self.connect() as conn:
            admin = conn.execute("SELECT * FROM users ORDER BY id LIMIT 1").fetchone()
            if not admin:
                return False, "No account found."
            if password and password != "••••••••":
                conn.execute("UPDATE users SET username = ?, role = ?, password_hash = ? WHERE id = ?", (username, role, hash_password(password), admin["id"]))
            else:
                conn.execute("UPDATE users SET username = ?, role = ? WHERE id = ?", (username, role, admin["id"]))
        self.log("Update Account", username)
        return True, "Account updated."

    def save_preferences(self, data: Dict[str, str]) -> Tuple[bool, str]:
        for key, value in data.items():
            self.set_setting(key, value)
        self.log("Save Preferences", ", ".join(data.keys()))
        return True, "Preferences saved."

    def backup_database(self) -> Tuple[bool, str]:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        filename = f"angie_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
        destination = os.path.join(BACKUP_DIR, filename)
        shutil.copy2(self.db_path, destination)
        self.set_setting("last_backup", display_datetime(now_text()))
        self.log("Backup Database", destination)
        return True, destination

    def export_table_csv(self, table_name: str, filepath: str) -> Tuple[bool, str]:
        allowed = {
            "products": "SELECT p.name, p.sku, COALESCE(c.name, 'Others') AS category, p.price, p.stock, p.unit, p.status, p.updated_at FROM products p LEFT JOIN categories c ON c.id=p.category_id ORDER BY p.updated_at DESC",
            "orders": "SELECT o.order_no, COALESCE(c.name, 'Walk-in Customer') AS customer, o.order_type, o.total, o.payment_status, o.status, o.fulfillment_status, o.created_at FROM orders o LEFT JOIN customers c ON c.id=o.customer_id ORDER BY o.created_at DESC",
            "transactions": "SELECT t.transaction_no, t.created_at, COALESCE(c.name, 'Walk-in Customer') AS customer, t.payment_method, t.amount, t.status, t.reference_no FROM transactions t LEFT JOIN customers c ON c.id=t.customer_id ORDER BY t.created_at DESC",
            "reports": "SELECT name, report_type, date_range, generated_by, created_at, status FROM reports ORDER BY created_at DESC",
        }
        if table_name not in allowed:
            return False, "Unsupported export."
        rows = self.table_rows(allowed[table_name])
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if rows:
                writer.writerow(rows[0].keys())
                writer.writerows([list(row) for row in rows])
        self.log("Export CSV", f"{table_name} -> {filepath}")
        return True, filepath

    def clear_cache(self) -> Tuple[bool, str]:
        self.log("Clear Cache", "Application cache cleared")
        return True, "Cache cleared. Database records were not deleted."

    # ---------- formatted rows for UI ----------
    def product_table_rows(self) -> List[List[str]]:
        rows = []
        for p in self.list_products():
            status = "Out of Stock" if p["stock"] <= 0 else "Low Stock" if p["stock"] <= p["reorder_level"] else "In Stock"
            rows.append([
                p["name"], p["sku"], p["category_name"], money(p["price"]), f"{p['stock']} {p['unit']}", status,
                display_date(p["updated_at"]), "✎  ⧉  🗑"
            ])
        return rows

    def featured_products(self, limit: int = 6) -> List[sqlite3.Row]:
        return self.list_products()[:limit]

    def category_rows(self) -> List[sqlite3.Row]:
        return self.list_categories()

    def order_table_rows(self) -> List[List[str]]:
        rows = []
        for o in self.list_orders():
            rows.append([
                o["order_no"], o["customer_name"], f"{o['qty_count']} items", o["order_type"], money(o["total"]),
                o["payment_status"], o["status"], o["fulfillment_status"]
            ])
        return rows

    def transaction_table_rows(self) -> List[List[str]]:
        rows = []
        for t in self.list_transactions():
            rows.append([
                t["transaction_no"], display_datetime(t["created_at"]), t["customer_name"], f"{t['items_count']} items",
                t["payment_method"], money(t["amount"]), t["status"], t["reference_no"]
            ])
        return rows

    def report_table_rows(self) -> List[List[str]]:
        return [
            [r["name"], r["report_type"], r["date_range"], r["generated_by"], display_datetime(r["created_at"]).split(", ")[-1], r["status"], "👁  ⬇  🖨"]
            for r in self.list_reports()
        ]

    def dashboard_stats(self) -> Dict[str, Any]:
        with self.connect() as conn:
            total_sales = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE status IN ('Completed', 'Partial')").fetchone()[0]
            total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            total_products = conn.execute("SELECT COUNT(*) FROM products WHERE status != 'Archived'").fetchone()[0]
            low_stock = conn.execute("SELECT COUNT(*) FROM products WHERE stock <= reorder_level AND status != 'Archived'").fetchone()[0]
            completed = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'Completed'").fetchone()[0]
            printing_revenue = conn.execute("SELECT COALESCE(SUM(total), 0) FROM orders WHERE order_type LIKE '%Printing%'").fetchone()[0]
        return {
            "total_sales": total_sales,
            "total_orders": total_orders,
            "total_products": total_products,
            "low_stock": low_stock,
            "completed_orders": completed,
            "printing_revenue": printing_revenue,
        }

    def top_products_by_sales(self, limit: int = 5) -> List[sqlite3.Row]:
        return self.table_rows(
            """
            SELECT product_name AS name, SUM(quantity) AS qty, SUM(line_total) AS sales
            FROM order_items
            GROUP BY product_name
            ORDER BY qty DESC
            LIMIT ?
            """,
            (limit,),
        )


DB = DatabaseManager()
