# 🎓 CampusCrew

A web app for managing campus club events and volunteers: create events, define the
volunteer roles they need, get smart volunteer recommendations, block double-bookings,
track attendance/hours, and view analytics. Converted from the original MySQL notebook.

## What changed from the notebook
| Notebook | Web app |
|---|---|
| `input()` prompts | Browser forms and buttons |
| MySQL (needs a server + password) | SQLite (a single file, zero setup, works on free hosts) |
| Plotly charts in cells | Chart.js charts on the Analytics page |
| CSV export cell | Download buttons |
| Anyone running the notebook can edit | Optional admin password: everyone can view, only admins can edit |

All the original rules are kept: no schedule overlaps, roles can't exceed capacity,
no duplicate assignments, recommendations rank skill-match first then lightest workload,
attendance % and hours per volunteer. One small improvement: a cancelled volunteer can now be re-assigned.

## The interface
- **Dashboard:** a live countdown to the next event, a scrolling ribbon of club logos, animated totals, and the roles that still need people.
- **Club logos:** every club gets a generated emblem (initials, colour, and an icon for its category). Admins can upload the club's real logo on the **Clubs** page (PNG, JPG, GIF or WebP, up to 2 MB) and remove it later to go back to the emblem. Logos are stored in `instance/logos/`.
- **Motion:** smooth page transitions, progress rings that fill as roles are staffed, toasts for every action, loading buttons, animated charts. Anyone who has "reduce motion" turned on in their device settings gets the calm version automatically.
- **Light and dark theme** (follows the device, with a toggle in the sidebar) and a layout that works on phones.

## Files
```
app.py           Flask web app (routes)
core.py          All business logic + database (the notebook's CampusCrew class, on SQLite)
templates/       HTML pages          static/style.css, static/app.js   Styling and animations
requirements.txt Dependencies        Procfile / render.yaml / wsgi.py   Deployment configs
CampusCrew_web.ipynb                      Notebook edition using the same core.py
CampusCrew_interactive_ORIGINAL_mysql.ipynb   Your original notebook, untouched
DEPLOY.md        Step-by-step deployment guide
```

## Run it on your computer
```bash
cd CampusCrew
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000. The database file is created automatically at `instance/campuscrew.db`.

Optional settings (environment variables): `ADMIN_PASSWORD` (turns on admin-only editing),
`SECRET_KEY` (any long random string; needed with a password), `DATABASE_PATH`, `PORT`.

Example with a password: `ADMIN_PASSWORD=mypass SECRET_KEY=longrandomtext python app.py`
(Windows PowerShell: `$env:ADMIN_PASSWORD="mypass"; $env:SECRET_KEY="longrandomtext"; python app.py`)

## Typical workflow
1. **Volunteers** → add people with skills and a preferred role.
2. **Events** → create an event and how many Tech / Art / PR volunteers it needs.
3. Open the event → **Find volunteers** on a role → click **Assign** on a recommended person.
4. **Assignments** → after the event, record Present/Absent and hours.
5. **Analytics** → workload, attendance, unfilled positions, CSV downloads.
