import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "portfolio.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            company_name TEXT,
            quantity REAL NOT NULL,
            avg_buy_price REAL NOT NULL,
            buy_date TEXT,
            sector TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            date TEXT NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS price_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            target_price REAL NOT NULL,
            triggered INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            year INTEGER,
            quarter TEXT,
            analysis TEXT,
            key_metrics TEXT,
            uploaded_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL UNIQUE,
            company_name TEXT,
            added_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    conn.commit()
    conn.close()


def add_holding(symbol, company_name, quantity, avg_buy_price, buy_date, sector, notes):
    conn = get_conn()
    conn.execute(
        "INSERT INTO holdings (symbol, company_name, quantity, avg_buy_price, buy_date, sector, notes) VALUES (?,?,?,?,?,?,?)",
        (symbol.upper(), company_name, quantity, avg_buy_price, buy_date, sector, notes)
    )
    conn.commit()
    conn.close()


def update_holding(holding_id, quantity, avg_buy_price, notes):
    conn = get_conn()
    conn.execute(
        "UPDATE holdings SET quantity=?, avg_buy_price=?, notes=? WHERE id=?",
        (quantity, avg_buy_price, notes, holding_id)
    )
    conn.commit()
    conn.close()


def delete_holding(holding_id):
    conn = get_conn()
    conn.execute("DELETE FROM holdings WHERE id=?", (holding_id,))
    conn.commit()
    conn.close()


def get_holdings():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM holdings ORDER BY symbol").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_transaction(symbol, action, quantity, price, date, notes):
    conn = get_conn()
    conn.execute(
        "INSERT INTO transactions (symbol, action, quantity, price, date, notes) VALUES (?,?,?,?,?,?)",
        (symbol.upper(), action, quantity, price, date, notes)
    )
    conn.commit()
    conn.close()


def get_transactions(symbol=None):
    conn = get_conn()
    if symbol:
        rows = conn.execute("SELECT * FROM transactions WHERE symbol=? ORDER BY date DESC", (symbol.upper(),)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM transactions ORDER BY date DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_alert(symbol, alert_type, target_price):
    conn = get_conn()
    conn.execute(
        "INSERT INTO price_alerts (symbol, alert_type, target_price) VALUES (?,?,?)",
        (symbol.upper(), alert_type, target_price)
    )
    conn.commit()
    conn.close()


def get_alerts(triggered=False):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM price_alerts WHERE triggered=? ORDER BY created_at DESC",
        (1 if triggered else 0,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def trigger_alert(alert_id):
    conn = get_conn()
    conn.execute("UPDATE price_alerts SET triggered=1 WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()


def delete_alert(alert_id):
    conn = get_conn()
    conn.execute("DELETE FROM price_alerts WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()


def save_document(symbol, doc_type, filename, filepath, year, quarter):
    conn = get_conn()
    conn.execute(
        "INSERT INTO documents (symbol, doc_type, filename, filepath, year, quarter) VALUES (?,?,?,?,?,?)",
        (symbol.upper(), doc_type, filename, filepath, year, quarter)
    )
    conn.commit()
    conn.close()


def update_document_analysis(doc_id, analysis, key_metrics):
    conn = get_conn()
    conn.execute(
        "UPDATE documents SET analysis=?, key_metrics=? WHERE id=?",
        (analysis, key_metrics, doc_id)
    )
    conn.commit()
    conn.close()


def get_documents(symbol=None):
    conn = get_conn()
    if symbol:
        rows = conn.execute(
            "SELECT * FROM documents WHERE symbol=? ORDER BY year DESC, uploaded_at DESC",
            (symbol.upper(),)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_document(doc_id):
    conn = get_conn()
    conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    conn.commit()
    conn.close()


def add_watchlist(symbol, company_name):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO watchlist (symbol, company_name) VALUES (?,?)",
            (symbol.upper(), company_name)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()


def get_watchlist():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM watchlist ORDER BY symbol").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def remove_watchlist(symbol):
    conn = get_conn()
    conn.execute("DELETE FROM watchlist WHERE symbol=?", (symbol.upper(),))
    conn.commit()
    conn.close()
