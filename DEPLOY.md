# Deploying CampusCrew so anyone can open it with a link

Two free options. **Option A (PythonAnywhere) is recommended** because it keeps your data permanently.
Before either: decide an **admin password** — otherwise anyone with the link can edit your data.

---
## Option A — PythonAnywhere (free, data persists)  → `https://YOURNAME.pythonanywhere.com`

1. Sign up (free "Beginner" account) at pythonanywhere.com. Your username becomes part of the link.
2. **Upload the code.** Go to the **Files** tab → make a folder `CampusCrew` → upload the zip contents
   (or open a **Bash console** and run `unzip` after uploading the zip, or `git clone` if you used GitHub).
   You should end with `/home/YOURNAME/CampusCrew/app.py`.
3. **Install Flask.** Open a **Bash console**:
   ```bash
   cd ~/CampusCrew
   python3 -m venv ~/venv
   source ~/venv/bin/activate
   pip install Flask
   ```
   (gunicorn is not needed on PythonAnywhere.)
4. **Create the web app.** **Web** tab → *Add a new web app* → *Next* → **Manual configuration** → pick Python 3.10+ (the newest offered).
5. On the Web tab set:
   - **Source code**: `/home/YOURNAME/CampusCrew`
   - **Virtualenv**: `/home/YOURNAME/venv`
6. Click the **WSGI configuration file** link, delete everything in it, and paste (edit the 3 values):
   ```python
   import os, sys
   path = "/home/YOURNAME/CampusCrew"
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ["ADMIN_PASSWORD"] = "choose-a-password"
   os.environ["SECRET_KEY"] = "paste-a-long-random-string-here"
   os.environ["DATABASE_PATH"] = "/home/YOURNAME/CampusCrew/instance/campuscrew.db"

   from app import app as application
   ```
   Save.
7. Back on the Web tab click the big green **Reload** button, then open `https://YOURNAME.pythonanywhere.com`.
   Share that link. Log in via **Admin login** (top right) to add data.

Notes: on the free plan you must click **"Run until 3 months from today"** on the Web tab every few months or the app is disabled.
To update the code later: upload the changed files and press **Reload**. Your database file is kept.
To back up data: download `instance/campuscrew.db` from the Files tab.

---
## Option B — Render (free, but data resets)  → `https://campuscrew-xxxx.onrender.com`

⚠ Render's free plan has **no persistent disk**: the SQLite file is wiped whenever the service restarts or redeploys,
and the free service sleeps after ~15 min idle (first visit then takes ~30 s). Fine for a demo/presentation,
not for real records. For permanent data on Render you need a paid plan with a disk
(then set `DATABASE_PATH=/var/data/campuscrew.db` and mount the disk at `/var/data`).

1. Put the `CampusCrew` folder in a new GitHub repository (github.com → New repository → upload files).
2. On render.com: **New → Web Service** → connect that repo.
3. Settings: Runtime **Python 3**, Build command `pip install -r requirements.txt`,
   Start command `gunicorn app:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT`, Plan **Free**.
   (Or choose **New → Blueprint** and Render reads `render.yaml` automatically.)
4. Under **Environment** add `ADMIN_PASSWORD` and `SECRET_KEY` (long random string).
5. Click **Create Web Service**. After the build, Render shows your public URL.

---
## Updating an existing deployment
Upload the new files over the old ones (keep your `instance/` folder), then press **Reload** (PythonAnywhere) or redeploy (Render).
Your database upgrades itself automatically the first time the new version runs; no data is lost.
Uploaded club logos live in `instance/logos/` next to the database, so back that folder up too.

## Troubleshooting
- **"Internal Server Error" on PythonAnywhere**: Web tab → *Error log* link. Usually a wrong path or virtualenv in step 5/6.
- **"unable to open database file"**: the `instance` folder must exist and be writable; keep the `instance/` folder from the zip.
- **Can't edit anything**: you're not logged in (when a password is set, visitors are view-only). Click *Admin login*.
- **Charts blank or fonts look plain**: they load from Google Fonts and a Chart.js CDN, so the visitor needs internet access.
- **Logo upload fails**: use PNG, JPG, GIF or WebP under 2 MB, and make sure `instance/` is writable.
- **Want MySQL/PostgreSQL instead?** All database code is in `core.py`; it would need the `?` placeholders and the
  `ON CONFLICT` clauses adapted. SQLite is the right choice unless you expect many simultaneous editors.
