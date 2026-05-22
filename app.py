import io
import os
from html import escape
from functools import wraps

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from backend import DB, display_datetime, money, parse_money, safe_int


app = Flask(__name__)
app.secret_key = os.environ.get("ANGIE_SECRET_KEY", "angie-mini-mart-dev-key")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def current_user():
    return session.get("user", {})


def row_dict(row):
    return dict(row) if row is not None else None


def pdf_escape(value):
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def plain_money(value):
    try:
        return f"PHP {float(value):,.2f}"
    except (TypeError, ValueError):
        return "PHP 0.00"


def simple_pdf(title, lines):
    safe_lines = [title, ""] + [str(line) for line in lines]
    content = ["BT", "/F1 11 Tf", "50 792 Td", "14 TL"]
    for line in safe_lines[:48]:
        content.append(f"({pdf_escape(line[:95])}) Tj")
        content.append("T*")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(pdf)


def transaction_lines(transaction):
    unit_price = float(transaction["amount"] or 0) / max(1, int(transaction["items_count"] or 1))
    return [
        "ANGIELU HUB MAIN BRANCH",
        "OFFICIAL RECEIPT",
        "-" * 38,
        f"Receipt No : {transaction['transaction_no']}",
        f"Date       : {display_datetime(transaction['created_at'])}",
        f"Customer   : {transaction['customer_name']}",
        f"Item       : {transaction['paid_for'] or 'Payment'}",
        f"Quantity   : {transaction['items_count']}",
        f"Unit Price : {plain_money(unit_price)}",
        f"Payment    : {transaction['payment_method']}",
        f"Reference  : {transaction['reference_no'] or 'N/A'}",
        f"Status     : {transaction['status']}",
        "-" * 38,
        f"TOTAL      : {plain_money(transaction['amount'])}",
        "-" * 38,
        "Thank you for your payment.",
    ]


def excel_response(filename, title, headers, rows):
    header_html = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
    rows_html = "".join(
        "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    html = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><style>body,table{{font-family:Courier New,monospace}}table{{border-collapse:collapse}}th,td{{border:1px solid #999;padding:7px}}</style></head>
<body><h2>{escape(title)}</h2><table><thead><tr>{header_html}</tr></thead><tbody>{rows_html}</tbody></table></body>
</html>"""
    return Response(
        html,
        mimetype="application/vnd.ms-excel",
        headers={"Content-Disposition": f"attachment; filename={filename}.xls"},
    )


def dashboard_context():
    stats = DB.dashboard_stats()
    return {
        "stats": stats,
        "featured_products": DB.featured_products(6),
        "top_products": DB.top_products_by_sales(5),
        "recent_orders": DB.list_orders()[:5],
        "recent_transactions": DB.list_transactions()[:5],
    }


@app.template_filter("money")
def money_filter(value):
    return money(value)


@app.template_filter("dt")
def datetime_filter(value):
    return display_datetime(value)


@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(os.path.join(app.root_path, "assets"), filename)


@app.route("/")
def index():
    return redirect(url_for("dashboard") if "user" in session else url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = DB.authenticate_user(username, password)
        if not user:
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))
        user.pop("password_hash", None)
        session["user"] = user
        return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="login")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        ok, message = DB.create_user(
            request.form.get("username", "").strip(),
            request.form.get("email", "").strip(),
            request.form.get("password", ""),
        )
        flash(message + (" You can now log in." if ok else ""), "success" if ok else "error")
        return redirect(url_for("login" if ok else "signup"))
    return render_template("auth.html", mode="signup")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", page="dashboard", user=current_user(), **dashboard_context())


@app.route("/products")
@login_required
def products():
    query = request.args.get("q", "").strip().lower()
    category = request.args.get("category", "All Categories")
    products = [row_dict(p) for p in DB.list_products()]
    if query:
        products = [
            p
            for p in products
            if query in p["name"].lower()
            or query in p["sku"].lower()
            or query in p["category_name"].lower()
        ]
    if category and category != "All Categories":
        products = [p for p in products if p["category_name"] == category]
    return render_template(
        "products.html",
        page="products",
        user=current_user(),
        products=products,
        categories=DB.list_categories(),
        selected_category=category,
        query=query,
    )


@app.route("/products/add", methods=["POST"])
@login_required
def add_product():
    ok, message = DB.add_product(product_payload(request.form))
    flash(message, "success" if ok else "error")
    return redirect(url_for("products"))


@app.route("/products/<int:product_id>/update", methods=["POST"])
@login_required
def update_product(product_id):
    ok, message = DB.update_product(product_id, product_payload(request.form))
    flash(message, "success" if ok else "error")
    return redirect(url_for("products"))


@app.route("/products/<int:product_id>/archive", methods=["POST"])
@login_required
def archive_product(product_id):
    ok, message = DB.archive_product(product_id)
    flash(message, "success" if ok else "error")
    return redirect(url_for("products"))


@app.route("/categories/add", methods=["POST"])
@login_required
def add_category():
    ok, message = DB.add_category(request.form.get("name", "").strip())
    flash(message, "success" if ok else "error")
    return redirect(url_for("products"))


def product_payload(form):
    return {
        "name": form.get("name", "").strip(),
        "sku": form.get("sku", "").strip(),
        "category": form.get("category", "Others"),
        "description": form.get("description", "").strip(),
        "price": parse_money(form.get("price", "0")),
        "stock": safe_int(form.get("stock", "0")),
        "unit": form.get("unit", "pcs"),
        "status": form.get("status", "Active"),
        "icon": form.get("icon", "📦"),
        "reorder_level": safe_int(form.get("reorder_level", "20"), 20),
    }


@app.route("/orders")
@login_required
def orders():
    return redirect(url_for("payment"))


@app.route("/payment")
@login_required
def payment():
    selected_id = request.args.get("selected", type=int)
    all_transactions = DB.list_transactions()
    selected = DB.get_transaction(selected_id) if selected_id else (DB.get_transaction(all_transactions[0]["id"]) if all_transactions else None)
    items = DB.transaction_items(selected["id"]) if selected else []
    pending_bills = [t for t in all_transactions if t["status"] == "Pending"]
    paid_transactions = [t for t in all_transactions if t["status"] != "Pending"]
    return render_template(
        "orders.html",
        page="payment",
        user=current_user(),
        transactions=paid_transactions,
        pending_bills=pending_bills,
        selected=selected,
        items=items,
    )


@app.route("/payment/export/pdf")
@login_required
def payment_export_pdf():
    lines = []
    for transaction in DB.list_transactions():
        lines.append(
            f"{transaction['transaction_no']} | {transaction['customer_name']} | "
            f"{transaction['paid_for'] or 'Payment'} | Qty {transaction['items_count']} | "
            f"{transaction['payment_method']} | {plain_money(transaction['amount'])} | {transaction['status']}"
        )
    return Response(
        simple_pdf("ANGIELU HUB - PAYMENT REPORT", lines or ["No payments found."]),
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=payments.pdf"},
    )


@app.route("/payment/export/excel")
@login_required
def payment_export_excel():
    rows = [
        [
            transaction["transaction_no"],
            display_datetime(transaction["created_at"]),
            transaction["customer_name"],
            transaction["paid_for"] or "Payment",
            transaction["items_count"],
            transaction["payment_method"],
            money(transaction["amount"]),
            transaction["status"],
            transaction["reference_no"],
        ]
        for transaction in DB.list_transactions()
    ]
    return excel_response(
        "payments",
        "Angielu Hub Payment Report",
        ["Transaction", "Date", "Customer", "Product / Service", "Qty", "Payment Type", "Amount", "Status", "Reference"],
        rows,
    )


@app.route("/payment/<int:transaction_id>/receipt")
@login_required
def payment_receipt(transaction_id):
    transaction = DB.get_transaction(transaction_id)
    if not transaction:
        flash("Receipt not found.", "error")
        return redirect(url_for("payment"))
    return render_template("receipt.html", transaction=transaction)


@app.route("/payment/<int:transaction_id>/receipt/pdf")
@login_required
def payment_receipt_pdf(transaction_id):
    transaction = DB.get_transaction(transaction_id)
    if not transaction:
        flash("Receipt not found.", "error")
        return redirect(url_for("payment"))
    return Response(
        simple_pdf("ANGIELU HUB RECEIPT", transaction_lines(transaction)),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={transaction['transaction_no']}.pdf"},
    )


@app.route("/payment/<int:transaction_id>/receipt/excel")
@login_required
def payment_receipt_excel(transaction_id):
    transaction = DB.get_transaction(transaction_id)
    if not transaction:
        flash("Receipt not found.", "error")
        return redirect(url_for("payment"))
    unit_price = float(transaction["amount"] or 0) / max(1, int(transaction["items_count"] or 1))
    rows = [
        ["Receipt No", transaction["transaction_no"]],
        ["Date", display_datetime(transaction["created_at"])],
        ["Customer", transaction["customer_name"]],
        ["Product / Service", transaction["paid_for"] or "Payment"],
        ["Quantity", transaction["items_count"]],
        ["Unit Price", money(unit_price)],
        ["Payment Type", transaction["payment_method"]],
        ["Reference", transaction["reference_no"] or "N/A"],
        ["Status", transaction["status"]],
        ["Total", money(transaction["amount"])],
    ]
    return excel_response(transaction["transaction_no"], "Angielu Hub Official Receipt", ["Field", "Value"], rows)


@app.route("/payment/create", methods=["POST"])
@login_required
def create_payment():
    ok, message = DB.create_manual_payment(
        request.form.get("customer_name", "").strip(),
        parse_money(request.form.get("amount", "0")),
        request.form.get("payment_method", "").strip(),
        request.form.get("paid_for", "").strip(),
        safe_int(request.form.get("quantity", 1), 1),
        request.form.get("reference_no", "").strip(),
        request.form.get("action_type", "paid"),
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("payment"))


@app.route("/orders/quick", methods=["POST"])
@login_required
def quick_order():
    product_id = request.form.get("product_id", type=int)
    products = DB.list_products()
    if not product_id and products:
        product_id = products[0]["id"]
    ok, message = DB.create_order_from_product(product_id, request.form.get("customer_name", "Walk-in Customer"), safe_int(request.form.get("quantity", 1), 1))
    flash(message, "success" if ok else "error")
    return redirect(url_for("orders"))


@app.route("/orders/<int:order_id>/status", methods=["POST"])
@login_required
def order_status(order_id):
    ok, message = DB.update_order_status(order_id, request.form.get("status", "Pending"), request.form.get("fulfillment_status") or None)
    flash(message, "success" if ok else "error")
    return redirect(url_for("orders", selected=order_id))


@app.route("/transactions")
@login_required
def transactions():
    return redirect(url_for("history"))


@app.route("/history")
@login_required
def history():
    selected_id = request.args.get("selected", type=int)
    all_transactions = DB.list_transactions()
    selected = DB.get_transaction(selected_id) if selected_id else (DB.get_transaction(all_transactions[0]["id"]) if all_transactions else None)
    items = DB.transaction_items(selected["id"]) if selected else []
    return render_template("transactions.html", page="history", user=current_user(), transactions=all_transactions, selected=selected, items=items)


@app.route("/reports")
@login_required
def reports():
    return redirect(url_for("report"))


@app.route("/report")
@login_required
def report():
    return render_template("reports.html", page="report", user=current_user(), reports=DB.list_reports(), stats=DB.dashboard_stats())


@app.route("/reports/generate", methods=["POST"])
@login_required
def generate_report():
    ok, message = DB.generate_report(request.form.get("report_type", "Sales Report"))
    flash(message, "success" if ok else "error")
    return redirect(url_for("report"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "business":
            keys = ["business_name", "owner_name", "contact_number", "email_address", "store_address"]
            ok, message = DB.save_business_profile({key: request.form.get(key, "").strip() for key in keys})
        elif action == "account":
            ok, message = DB.update_account(request.form.get("username", "").strip(), request.form.get("role", "Administrator"), request.form.get("password", ""))
            if ok:
                session["user"]["username"] = request.form.get("username", "").strip()
                session["user"]["role"] = request.form.get("role", "Administrator")
        elif action == "backup":
            ok, message = DB.backup_database()
        else:
            keys = ["currency", "date_format", "receipt_size", "low_stock_alert_level", "theme"]
            ok, message = DB.save_preferences({key: request.form.get(key, "").strip() for key in keys})
        flash(message, "success" if ok else "error")
        return redirect(url_for("settings"))
    return render_template("settings.html", page="settings", user=current_user(), settings=DB.get_settings())


@app.route("/export/<table_name>")
@login_required
def export_csv(table_name):
    allowed = {
        "products": DB.product_table_rows(),
        "orders": DB.order_table_rows(),
        "transactions": DB.transaction_table_rows(),
        "reports": DB.report_table_rows(),
    }
    headers = {
        "products": ["Product", "SKU", "Category", "Price", "Stock", "Status", "Updated", "Actions"],
        "orders": ["Order ID", "Customer", "Items", "Type", "Total", "Payment", "Status", "Fulfillment"],
        "transactions": ["Transaction ID", "Date", "Customer", "Items", "Method", "Amount", "Status", "Reference"],
        "reports": ["Report", "Type", "Date Range", "Generated By", "Generated At", "Status", "Actions"],
    }
    if table_name not in allowed:
        flash("Unsupported export.", "error")
        return redirect(url_for("dashboard"))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers[table_name])
    writer.writerows(allowed[table_name])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table_name}.csv"},
    )


if __name__ == "__main__":
    app.run(debug=True)
