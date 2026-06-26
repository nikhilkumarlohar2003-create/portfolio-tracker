import os
import json
import streamlit as st

_client = None


def _get():
    global _client
    if _client is None:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        if not url or not key:
            try:
                url = st.secrets.get("SUPABASE_URL", "")
                key = st.secrets.get("SUPABASE_KEY", "")
            except Exception:
                pass
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY are not set.")
        _client = create_client(url, key)
    return _client


def init_db():
    pass  # tables created via setup_supabase.sql


def add_holding(symbol, company_name, quantity, avg_buy_price, buy_date, sector, notes):
    _get().table("holdings").insert({
        "symbol": symbol.upper(), "company_name": company_name,
        "quantity": quantity, "avg_buy_price": avg_buy_price,
        "buy_date": buy_date, "sector": sector, "notes": notes,
    }).execute()


def update_holding(holding_id, quantity, avg_buy_price, notes):
    _get().table("holdings").update({
        "quantity": quantity, "avg_buy_price": avg_buy_price, "notes": notes,
    }).eq("id", holding_id).execute()


def delete_holding(holding_id):
    _get().table("holdings").delete().eq("id", holding_id).execute()


def get_holdings():
    res = _get().table("holdings").select("*").order("symbol").execute()
    return res.data or []


def add_transaction(symbol, action, quantity, price, date, notes):
    _get().table("transactions").insert({
        "symbol": symbol.upper(), "action": action,
        "quantity": quantity, "price": price, "date": date, "notes": notes,
    }).execute()


def get_transactions(symbol=None):
    q = _get().table("transactions").select("*").order("date", desc=True)
    if symbol:
        q = q.eq("symbol", symbol.upper())
    return q.execute().data or []


def add_alert(symbol, alert_type, target_price):
    _get().table("price_alerts").insert({
        "symbol": symbol.upper(), "alert_type": alert_type,
        "target_price": target_price, "triggered": False,
    }).execute()


def get_alerts(triggered=False):
    res = (_get().table("price_alerts")
           .select("*")
           .eq("triggered", triggered)
           .order("created_at", desc=True)
           .execute())
    return res.data or []


def trigger_alert(alert_id):
    _get().table("price_alerts").update({"triggered": True}).eq("id", alert_id).execute()


def delete_alert(alert_id):
    _get().table("price_alerts").delete().eq("id", alert_id).execute()


def save_document(symbol, doc_type, filename, filepath, year, quarter):
    _get().table("documents").insert({
        "symbol": symbol.upper(), "doc_type": doc_type,
        "filename": filename, "filepath": filepath or "",
        "year": year, "quarter": quarter,
    }).execute()


def update_document_analysis(doc_id, analysis, key_metrics):
    _get().table("documents").update({
        "analysis": analysis, "key_metrics": key_metrics,
    }).eq("id", doc_id).execute()


def get_documents(symbol=None):
    q = _get().table("documents").select("*").order("year", desc=True)
    if symbol:
        q = q.eq("symbol", symbol.upper())
    return q.execute().data or []


def delete_document(doc_id):
    _get().table("documents").delete().eq("id", doc_id).execute()


def add_watchlist(symbol, company_name):
    try:
        _get().table("watchlist").insert({
            "symbol": symbol.upper(), "company_name": company_name,
        }).execute()
    except Exception:
        pass  # duplicate


def get_watchlist():
    return _get().table("watchlist").select("*").order("symbol").execute().data or []


def remove_watchlist(symbol):
    _get().table("watchlist").delete().eq("symbol", symbol.upper()).execute()
