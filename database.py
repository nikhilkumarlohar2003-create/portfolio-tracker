import os

def _check_cloud():
    if os.getenv("SUPABASE_URL"):
        return True
    try:
        import streamlit as st
        return bool(st.secrets.get("SUPABASE_URL", ""))
    except Exception:
        return False

_USE_CLOUD = _check_cloud()

if _USE_CLOUD:
    from _db_supabase import (
        init_db, add_holding, update_holding, delete_holding, get_holdings,
        add_transaction, get_transactions,
        add_alert, get_alerts, trigger_alert, delete_alert,
        save_document, update_document_analysis, get_documents,
        add_watchlist, get_watchlist, remove_watchlist,
    )
else:
    from _db_sqlite import (
        init_db, add_holding, update_holding, delete_holding, get_holdings,
        add_transaction, get_transactions,
        add_alert, get_alerts, trigger_alert, delete_alert,
        save_document, update_document_analysis, get_documents,
        add_watchlist, get_watchlist, remove_watchlist,
    )
