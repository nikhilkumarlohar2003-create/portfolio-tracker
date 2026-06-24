# -*- coding: utf-8 -*-
"""
Run this once to copy your local SQLite data to Supabase.
Make sure SUPABASE_URL and SUPABASE_KEY are set in .env before running.
"""
from dotenv import load_dotenv
load_dotenv()

import _db_sqlite as local
import _db_supabase as cloud

print("Migrating local portfolio to Supabase...")

holdings = local.get_holdings()
for h in holdings:
    cloud.add_holding(h["symbol"], h["company_name"], h["quantity"],
                      h["avg_buy_price"], h["buy_date"], h["sector"], h["notes"] or "")
print(f"  OK {len(holdings)} holdings")

txns = local.get_transactions()
for t in txns:
    cloud.add_transaction(t["symbol"], t["action"], t["quantity"],
                          t["price"], t["date"], t["notes"] or "")
print(f"  OK {len(txns)} transactions")

alerts = local.get_alerts(triggered=False)
for a in alerts:
    cloud.add_alert(a["symbol"], a["alert_type"], a["target_price"])
print(f"  OK {len(alerts)} alerts")

watchlist = local.get_watchlist()
for w in watchlist:
    cloud.add_watchlist(w["symbol"], w["company_name"] or "")
print(f"  OK {len(watchlist)} watchlist entries")

docs = local.get_documents()
for d in docs:
    cloud.save_document(d["symbol"], d["doc_type"], d["filename"],
                        d["filepath"], d["year"], d["quarter"])
    if d.get("analysis"):
        remote_docs = cloud.get_documents(d["symbol"])
        if remote_docs:
            cloud.update_document_analysis(remote_docs[0]["id"],
                                           d["analysis"], d.get("key_metrics", "{}"))
print(f"  OK {len(docs)} documents")

print("\nMigration complete! Your Supabase DB is now populated.")
