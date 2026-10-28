"""CampusCrew web app (Flask). Run locally:  python app.py"""
import csv
import io
import os
import secrets
import zlib
from datetime import datetime
from functools import wraps

from flask import (Flask, Response, flash, redirect, render_template, request,
                   send_from_directory, session, url_for)

import core
from core import CampusCrew, ROLE_NAMES

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB uploads

# Uploaded club logos live next to the database file.
LOGO_DIR = os.path.join(os.path.dirname(core.DB_PATH), "logos")
LOGO_TYPES = {  # extension -> magic bytes (SVG is refused: it can carry scripts)
    "png": (b"\x89PNG",), "jpg": (b"\xff\xd8\xff",), "jpeg": (b"\xff\xd8\xff",),
    "gif": (b"GIF8",), "webp": (b"RIFF",),
}

# Generated emblems for clubs without an uploaded logo: (gradient start, end, text colour)
EMBLEM_PALETTE = [
    ("#0E3B43", "#1B998B", "#FFFFFF"), ("#FFB627", "#F26B38", "#2A1A00"),
    ("#1B998B", "#7BD389", "#06302B"), ("#3D348B", "#7678ED", "#FFFFFF"),
    ("#E4572E", "#A4133C", "#FFFFFF"), ("#0077B6", "#48CAE4", "#FFFFFF"),
    ("#4F772D", "#A7C957", "#14260A"), ("#7B2CBF", "#F15BB5", "#FFFFFF"),
]
GLYPHS = {  # 24x24 stroke icons keyed by category keyword
    "cyber": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    "technolog": '<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>',
    "technical": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1"/>',
    "cultur": '<path d="M9 18V6l11-2v12"/><circle cx="6" cy="18" r="3"/><circle cx="17" cy="16" r="3"/>',
    "social": '<path d="M21 12a8 8 0 0 1-11.5 7.2L4 20l1-4.5A8 8 0 1 1 21 12z"/>',
}
STAR = '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>'


@app.template_global()
def club_style(name):
    c1, c2, fg = EMBLEM_PALETTE[zlib.crc32(name.encode()) % len(EMBLEM_PALETTE)]
    words = name.split()
    if len(words) >= 2:
        initials = (words[0][0] + words[1][0]).upper()
    elif name.isupper() and len(name) <= 4:
        initials = name
    else:
        initials = name[:2].title()
    return {"c1": c1, "c2": c2, "fg": fg, "initials": initials}


@app.template_global()
def club_glyph(category):
    cat = (category or "").lower()
    return next((svg for key, svg in GLYPHS.items() if key in cat), STAR)


@app.template_filter("pretty_dt")
def pretty_dt(value):
    d = datetime.strptime(value[:16], "%Y-%m-%d %H:%M")
    return d.strftime("%a %d %b, %I:%M %p").replace(" 0", " ")


@app.template_filter("short_date")
def short_date(value):
    return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d %b")

# If ADMIN_PASSWORD is set, anyone can VIEW, but only logged-in admins can ADD/EDIT.
# If it is not set, the site is fully open (fine for local use).
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")


def get_app():
    return CampusCrew()


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method != "GET" and ADMIN_PASSWORD and not session.get("admin"):
            flash("Please log in as admin to make changes.", "error")
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    return {"is_admin": (not ADMIN_PASSWORD) or session.get("admin"),
            "auth_enabled": bool(ADMIN_PASSWORD), "role_names": ROLE_NAMES}


def to_int(value, default=0):
    value = (value or "").strip()
    return int(value) if value.isdigit() else default


def run(action, success=None):
    """Run an action, flashing success or the error message."""
    try:
        result = action()
        flash(success or (result if isinstance(result, str) else "Done."), "ok")
        return True
    except ValueError as e:
        flash(str(e), "error")
    except Exception as e:  # database errors etc.
        flash(f"Something went wrong: {e}", "error")
    return False


# ---------------- auth ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if ADMIN_PASSWORD and request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Wrong password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("dashboard"))


@app.route("/healthz")
def healthz():
    return "ok"


# ---------------- pages ----------------
@app.route("/")
def dashboard():
    cc = get_app()
    events, vols = cc.list_events(), cc.list_volunteers()
    report = cc.role_report()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    upcoming = [e for e in events if e["start_time"] >= now]
    next_event = upcoming[0] if upcoming else None
    clubs_list = cc.list_clubs()
    stats = {
        "clubs": len(clubs_list), "volunteers": len(vols), "events": len(events),
        "assignments": len([a for a in cc.list_assignments() if a["status"] != "cancelled"]),
        "unfilled": sum(r["unfilled_positions"] for r in report),
    }
    return render_template("dashboard.html", stats=stats, events=(upcoming or events)[:5],
                           clubs=clubs_list, next_event=next_event,
                           needs=[r for r in report if r["unfilled_positions"] > 0][:6])


@app.route("/clubs", methods=["GET", "POST"])
@admin_required
def clubs():
    cc = get_app()
    if request.method == "POST":
        run(lambda: cc.add_club(request.form.get("club_name", ""), request.form.get("category", "")),
            "Club saved.")
        return redirect(url_for("clubs"))
    return render_template("clubs.html", clubs=cc.list_clubs())


@app.route("/clubs/<int:club_id>/logo", methods=["POST"])
@admin_required
def club_logo(club_id):
    cc = get_app()
    club = cc.get_club(club_id)
    if not club:
        flash("Club not found.", "error")
        return redirect(url_for("clubs"))
    os.makedirs(LOGO_DIR, exist_ok=True)

    def remove_old():
        if club["logo"]:
            try:
                os.remove(os.path.join(LOGO_DIR, club["logo"]))
            except OSError:
                pass

    if request.form.get("remove"):
        remove_old()
        cc.set_club_logo(club_id, "")
        flash(f"{club['club_name']} is back to the standard emblem.", "ok")
        return redirect(url_for("clubs"))
    file = request.files.get("logo")
    ext = (file.filename.rsplit(".", 1)[-1].lower() if file and "." in file.filename else "")
    if not file or ext not in LOGO_TYPES:
        flash("Upload a PNG, JPG, GIF or WebP image (SVG isn't accepted).", "error")
        return redirect(url_for("clubs"))
    head = file.stream.read(12)
    file.stream.seek(0)
    if not any(head.startswith(m) for m in LOGO_TYPES[ext]):
        flash("That file doesn't look like a real image.", "error")
        return redirect(url_for("clubs"))
    name = f"club{club_id}_{secrets.token_hex(4)}.{ext}"
    file.save(os.path.join(LOGO_DIR, name))
    remove_old()
    cc.set_club_logo(club_id, name)
    flash(f"Logo updated for {club['club_name']}.", "ok")
    return redirect(url_for("clubs"))


@app.route("/logos/<path:filename>")
def logo_file(filename):
    return send_from_directory(LOGO_DIR, filename, max_age=3600)


@app.errorhandler(413)
def too_large(_):
    flash("That image is over 2 MB. Choose a smaller one.", "error")
    return redirect(url_for("clubs"))


@app.route("/volunteers", methods=["GET", "POST"])
@admin_required
def volunteers():
    cc = get_app()
    if request.method == "POST":
        f = request.form
        run(lambda: cc.add_volunteer(f.get("name", ""), f.get("email", ""),
                                     f.get("skills", ""), f.get("preferred_role", "")),
            "Volunteer saved.")
        return redirect(url_for("volunteers"))
    return render_template("volunteers.html", volunteers=cc.list_volunteers())


@app.route("/events", methods=["GET", "POST"])
@admin_required
def events():
    cc = get_app()
    if request.method == "POST":
        f = request.form
        ok = {}

        def create():
            ok["id"] = cc.add_event(
                f.get("club_name", ""), f.get("title", ""), f.get("start_time", ""),
                f.get("end_time", ""), f.get("location", ""),
                to_int(f.get("tech_count")), to_int(f.get("art_count")), to_int(f.get("pr_count")))
        if run(create, "Event saved with its volunteer roles."):
            return redirect(url_for("event_detail", event_id=ok["id"]))
        return redirect(url_for("events"))
    return render_template("events.html", events=cc.list_events(), clubs=cc.list_clubs())


@app.route("/events/<int:event_id>")
def event_detail(event_id):
    cc = get_app()
    event = cc.get_event(event_id)
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("events"))
    return render_template("event_detail.html", event=event, roles=cc.list_roles(event_id),
                           members=cc.role_members(event_id))


@app.route("/roles/<int:role_id>", methods=["GET", "POST"])
@admin_required
def role_detail(role_id):
    cc = get_app()
    if request.method == "POST":
        vid = to_int(request.form.get("volunteer_id"), -1)
        run(lambda: cc.assign_volunteer(role_id, vid))
        return redirect(url_for("role_detail", role_id=role_id))
    try:
        role, recs = cc.recommend_volunteers(role_id)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("events"))
    filled = [r for r in cc.list_roles(role["event_id"]) if r["role_id"] == role_id][0]
    return render_template("role_detail.html", role=role, recs=recs, filled=filled)


@app.route("/assignments")
def assignments():
    return render_template("assignments.html", assignments=get_app().list_assignments())


@app.route("/assignments/<int:aid>/attendance", methods=["POST"])
@admin_required
def attendance(aid):
    cc = get_app()
    try:
        hours = float(request.form.get("hours_worked") or 0)
    except ValueError:
        hours = -1
    run(lambda: cc.mark_attendance(aid, to_int(request.form.get("attended")), hours),
        "Attendance updated.")
    return redirect(url_for("assignments"))


@app.route("/assignments/<int:aid>/cancel", methods=["POST"])
@admin_required
def cancel(aid):
    cc = get_app()
    run(lambda: cc.cancel_assignment(aid), "Assignment cancelled.")
    return redirect(url_for("assignments"))


@app.route("/conflicts", methods=["GET", "POST"])
def conflicts():
    cc = get_app()
    result = None
    if request.method == "POST":
        vid, rid = to_int(request.form.get("volunteer_id"), -1), to_int(request.form.get("role_id"), -1)
        try:
            role = cc.role_event(rid)
            result = {"role": role, "conflicts": cc.has_conflict(vid, role["start_time"], role["end_time"])}
        except ValueError as e:
            flash(str(e), "error")
    roles = [r for e in cc.list_events() for r in cc.list_roles(e["event_id"])]
    return render_template("conflicts.html", volunteers=cc.list_volunteers(), roles=roles, result=result)


@app.route("/analytics")
def analytics():
    cc = get_app()
    return render_template("analytics.html", vol=cc.volunteer_analytics(), roles=cc.role_report())


def csv_response(rows, filename):
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.route("/export/volunteers.csv")
def export_vol():
    return csv_response(get_app().volunteer_analytics(), "campuscrew_volunteer_analytics.csv")


@app.route("/export/roles.csv")
def export_roles():
    return csv_response(get_app().role_report(), "campuscrew_role_capacity_report.csv")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
