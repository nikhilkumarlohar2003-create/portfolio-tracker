import os

# Auto-detect: if SUPABASE_URL is set, use cloud DB; otherwise use local SQLite
_USE_CLOUD = bool(os.getenv("SUPABASE_URL"))

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
