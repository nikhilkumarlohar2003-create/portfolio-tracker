DEPLOY TO STREAMLIT COMMUNITY CLOUD
=====================================
Follow these steps once. After setup, the app will be live at a permanent URL
you can open from any device, any network — forever free.

STEP 1 — Create a Supabase account (free database)
----------------------------------------------------
1. Go to https://supabase.com → Sign Up (free, no credit card)
2. Click "New Project" → give it any name (e.g. "portfolio") → choose a region → Create
3. Wait ~2 minutes for the project to be ready
4. Go to SQL Editor (left sidebar) → New Query
5. Paste ALL the contents of setup_supabase.sql → click Run
   (This creates your tables)
6. Go to Project Settings → API (left sidebar)
   Copy these two values — you'll need them soon:
   - Project URL  (looks like https://abcdefgh.supabase.co)
   - anon public key  (long JWT string starting with eyJ...)

STEP 2 — Push code to GitHub
------------------------------
1. Go to https://github.com → Sign in (or create free account)
2. Click "+" → "New repository" → name it "portfolio-tracker" → Private → Create
3. Open PowerShell in the project folder and run:

   cd "C:\Users\Asus\Documents\Claude\Projects\portfolio_tracker"
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/portfolio-tracker.git
   git push -u origin main

   (Replace YOUR_USERNAME with your GitHub username)

STEP 3 — Deploy on Streamlit Community Cloud
----------------------------------------------
1. Go to https://share.streamlit.io → Sign in with GitHub
2. Click "New app"
3. Select your repository: portfolio-tracker
4. Main file path: app.py
5. Click "Advanced settings" → Secrets tab
6. Paste this (fill in YOUR actual values):

   ANTHROPIC_API_KEY = "sk-ant-api03-..."
   SUPABASE_URL = "https://abcdefgh.supabase.co"
   SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

7. Click "Deploy!" → Wait 2-3 minutes

Your app will be live at:
   https://YOUR_USERNAME-portfolio-tracker-app-XXXX.streamlit.app

STEP 4 — Import your portfolio data to the cloud
--------------------------------------------------
The cloud app uses Supabase — your local SQLite data won't transfer automatically.
Two options:

Option A: Re-enter holdings manually in the app (Portfolio → Add/Edit)

Option B: Run this script to push local data to Supabase:
   (set SUPABASE_URL and SUPABASE_KEY in your .env first, then run)
   python migrate_to_cloud.py

NOTES
------
- Local app (localhost:8501) still uses SQLite — nothing changes there
- Cloud app uses Supabase automatically (detects SUPABASE_URL env var)
- Annual report PDFs are processed in memory on cloud — not stored
  (the analysis text IS saved to Supabase)
- To update the cloud app: git add . && git commit -m "update" && git push
  Streamlit will auto-redeploy within ~1 minute
