-- Run this in Supabase SQL Editor (supabase.com → your project → SQL Editor)

CREATE TABLE IF NOT EXISTS holdings (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    company_name TEXT,
    quantity REAL NOT NULL,
    avg_buy_price REAL NOT NULL,
    buy_date TEXT,
    sector TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    date TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS price_alerts (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    target_price REAL NOT NULL,
    triggered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    filepath TEXT,
    year INTEGER,
    quarter TEXT,
    analysis TEXT,
    key_metrics TEXT,
    uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS watchlist (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL UNIQUE,
    company_name TEXT,
    added_at TIMESTAMPTZ DEFAULT NOW()
);
