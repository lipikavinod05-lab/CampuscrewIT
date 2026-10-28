"""CampusCrew core logic (SQLite version of the original MySQL notebook code)."""
import os
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "campuscrew.db"),
)
DT_FORMAT = "%Y-%m-%d %H:%M"
SQL_DT = "%Y-%m-%d %H:%M:%S"
ROLE_NAMES = ["Tech", "Art", "PR/Management"]
ROLE_ALIASES = {"tech": "Tech", "art": "Art", "pr/management": "PR/Management", "pr": "PR/Management"}

DEFAULT_CLUBS = [
    ("Trendles", "Social"), ("Wildbeats", "Cultural"), ("GDG", "Technology"),
    ("Coders Club", "Technology"), ("BetaLabs", "Technology"),
    ("Cybersecurity Club", "Cybersecurity"), ("Enigma", "Technical"), ("Elix", "Technical"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS clubs (
    club_id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    logo TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS volunteers (
    volunteer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    skills TEXT DEFAULT '',
    preferred_role TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER NOT NULL REFERENCES clubs(club_id),
    title TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    location TEXT DEFAULT '',
    UNIQUE (club_id, title, start_time)
);
CREATE TABLE IF NOT EXISTS roles (
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    role_name TEXT NOT NULL,
    required_count INTEGER NOT NULL DEFAULT 1,
    UNIQUE (event_id, role_name)
);
CREATE TABLE IF NOT EXISTS assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    volunteer_id INTEGER NOT NULL REFERENCES volunteers(volunteer_id),
    role_id INTEGER NOT NULL REFERENCES roles(role_id),
    status TEXT NOT NULL DEFAULT 'assigned',
    attended INTEGER DEFAULT NULL,
    hours_worked REAL DEFAULT 0,
    assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (volunteer_id, role_id)
);
"""


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class CampusCrew:
    def __init__(self, conn=None):
        self.conn = conn or connect()
        self.conn.executescript(SCHEMA)
        # migrate databases created by the previous version (no logo column)
        cols = [r["name"] for r in self.conn.execute("PRAGMA table_info(clubs)")]
        if "logo" not in cols:
            self.conn.execute("ALTER TABLE clubs ADD COLUMN logo TEXT DEFAULT ''")
        self.conn.commit()
        self.seed_clubs()

    # ---------- helpers ----------
    def execute(self, sql, values=()):
        cur = self.conn.execute(sql, values)
        self.conn.commit()
        return cur.lastrowid

    def query(self, sql, values=()):
        return [dict(r) for r in self.conn.execute(sql, values).fetchall()]

    def query_df(self, sql, values=()):
        """Handy in notebooks: returns a pandas DataFrame."""
        import pandas as pd
        return pd.DataFrame(self.query(sql, values))

    # ---------- clubs ----------
    def seed_clubs(self):
        for name, cat in DEFAULT_CLUBS:
            self.conn.execute(
                "INSERT INTO clubs (club_name, category) VALUES (?, ?) "
                "ON CONFLICT(club_name) DO NOTHING", (name, cat))
        self.conn.commit()

    def add_club(self, club_name, category):
        if not club_name.strip() or not category.strip():
            raise ValueError("Club name and category are required.")
        self.execute(
            "INSERT INTO clubs (club_name, category) VALUES (?, ?) "
            "ON CONFLICT(club_name) DO UPDATE SET category=excluded.category",
            (club_name.strip(), category.strip()))

    def list_clubs(self):
        return self.query(
            """SELECT c.club_id, c.club_name, c.category, c.logo, COUNT(e.event_id) AS event_count
               FROM clubs c LEFT JOIN events e ON e.club_id=c.club_id
               GROUP BY c.club_id ORDER BY c.club_name""")

    def get_club(self, club_id):
        rows = self.query("SELECT club_id, club_name, category, logo FROM clubs WHERE club_id=?", (club_id,))
        return rows[0] if rows else None

    def set_club_logo(self, club_id, filename):
        self.execute("UPDATE clubs SET logo=? WHERE club_id=?", (filename, club_id))

    # ---------- volunteers ----------
    def add_volunteer(self, name, email, skills="", preferred_role=""):
        if not name.strip() or not email.strip():
            raise ValueError("Name and email are required.")
        if "@" not in email:
            raise ValueError("That doesn't look like a valid email.")
        pref = ROLE_ALIASES.get(preferred_role.strip().lower(), "")
        self.execute(
            "INSERT INTO volunteers (name, email, skills, preferred_role) VALUES (?,?,?,?) "
            "ON CONFLICT(email) DO UPDATE SET name=excluded.name, skills=excluded.skills, "
            "preferred_role=excluded.preferred_role",
            (name.strip(), email.strip().lower(), skills.strip(), pref))

    def list_volunteers(self):
        return self.query(
            "SELECT volunteer_id, name, email, skills, preferred_role FROM volunteers ORDER BY name")

    # ---------- events & roles ----------
    def add_event(self, club_name, title, start_time, end_time, location,
                  tech_count=2, art_count=2, pr_count=2):
        if not title.strip():
            raise ValueError("Event title is required.")
        try:
            start = datetime.strptime(start_time.replace("T", " "), DT_FORMAT)
            end = datetime.strptime(end_time.replace("T", " "), DT_FORMAT)
        except ValueError:
            raise ValueError("Invalid date/time.")
        if end <= start:
            raise ValueError("Event end time must be after start time.")
        club = self.query("SELECT club_id FROM clubs WHERE club_name=?", (club_name,))
        if not club:
            raise ValueError("Club not found.")
        cid = club[0]["club_id"]
        s, e = start.strftime(SQL_DT), end.strftime(SQL_DT)
        self.execute(
            "INSERT INTO events (club_id, title, start_time, end_time, location) VALUES (?,?,?,?,?) "
            "ON CONFLICT(club_id, title, start_time) DO UPDATE SET "
            "location=excluded.location, end_time=excluded.end_time",
            (cid, title.strip(), s, e, location.strip()))
        event_id = self.query(
            "SELECT event_id FROM events WHERE club_id=? AND title=? AND start_time=?",
            (cid, title.strip(), s))[0]["event_id"]
        for role_name, required in zip(ROLE_NAMES, (tech_count, art_count, pr_count)):
            if required < 0:
                raise ValueError("Required volunteer count cannot be negative.")
            self.execute(
                "INSERT INTO roles (event_id, role_name, required_count) VALUES (?,?,?) "
                "ON CONFLICT(event_id, role_name) DO UPDATE SET required_count=excluded.required_count",
                (event_id, role_name, required))
        return event_id

    def list_events(self):
        return self.query(
            """SELECT e.event_id, c.club_id, c.club_name, c.category, c.logo,
                      e.title, e.start_time, e.end_time, e.location
               FROM events e JOIN clubs c ON e.club_id=c.club_id ORDER BY e.start_time""")

    def get_event(self, event_id):
        rows = self.query(
            """SELECT e.event_id, c.club_id, c.club_name, c.category, c.logo,
                      e.title, e.start_time, e.end_time, e.location
               FROM events e JOIN clubs c ON e.club_id=c.club_id WHERE e.event_id=?""", (event_id,))
        return rows[0] if rows else None

    def list_roles(self, event_id=None):
        sql = """SELECT r.role_id, e.event_id, e.title, r.role_name, r.required_count,
                        COUNT(CASE WHEN a.status <> 'cancelled' THEN a.assignment_id END) AS assigned_count
                 FROM roles r JOIN events e ON e.event_id=r.event_id
                 LEFT JOIN assignments a ON a.role_id=r.role_id"""
        values = ()
        if event_id is not None:
            sql += " WHERE e.event_id=?"
            values = (event_id,)
        sql += " GROUP BY r.role_id ORDER BY r.role_id"
        return self.query(sql, values)

    def role_members(self, event_id):
        """{role_id: [volunteer names]} for active (non-cancelled) assignments of an event."""
        rows = self.query(
            """SELECT r.role_id, v.name FROM assignments a
               JOIN roles r ON r.role_id=a.role_id JOIN volunteers v ON v.volunteer_id=a.volunteer_id
               WHERE r.event_id=? AND a.status <> 'cancelled' ORDER BY a.assignment_id""", (event_id,))
        out = {}
        for r in rows:
            out.setdefault(r["role_id"], []).append(r["name"])
        return out

    def role_event(self, role_id):
        rows = self.query(
            """SELECT r.role_id, r.role_name, r.required_count, e.event_id,
                      e.start_time, e.end_time, e.title
               FROM roles r JOIN events e ON e.event_id=r.event_id WHERE r.role_id=?""", (role_id,))
        if not rows:
            raise ValueError("Role ID not found.")
        return rows[0]

    # ---------- scheduling ----------
    def has_conflict(self, volunteer_id, start_time, end_time, exclude_role_id=None):
        sql = """SELECT e.title, e.start_time, e.end_time
                 FROM assignments a JOIN roles r ON r.role_id=a.role_id
                 JOIN events e ON e.event_id=r.event_id
                 WHERE a.volunteer_id=? AND a.status <> 'cancelled'
                   AND e.start_time < ? AND e.end_time > ?"""
        values = [volunteer_id, end_time, start_time]
        if exclude_role_id is not None:
            sql += " AND a.role_id <> ?"
            values.append(exclude_role_id)
        return self.query(sql, tuple(values))

    def recommend_volunteers(self, role_id):
        role = self.role_event(role_id)
        candidates = self.query(
            """SELECT v.volunteer_id, v.name, v.skills, v.preferred_role,
                      COUNT(a.assignment_id) AS workload
               FROM volunteers v
               LEFT JOIN assignments a ON a.volunteer_id=v.volunteer_id AND a.status <> 'cancelled'
               GROUP BY v.volunteer_id""")
        role_key = role["role_name"].lower().replace("/management", "")
        out = []
        for p in candidates:
            if self.has_conflict(p["volunteer_id"], role["start_time"], role["end_time"]):
                continue
            if self.query("SELECT 1 FROM assignments WHERE volunteer_id=? AND role_id=? AND status<>'cancelled'",
                          (p["volunteer_id"], role_id)):
                continue
            skills = (p["skills"] or "").lower()
            pref = (p["preferred_role"] or "").lower()
            match = int(role_key in skills or pref == role["role_name"].lower())
            out.append({**p, "skill_match": match, "current_assignments": int(p["workload"])})
        out.sort(key=lambda x: (-x["skill_match"], x["current_assignments"], x["name"]))
        return role, out

    def assign_volunteer(self, role_id, volunteer_id):
        role = self.role_event(role_id)
        vol = self.query("SELECT volunteer_id, name FROM volunteers WHERE volunteer_id=?", (volunteer_id,))
        if not vol:
            raise ValueError("Volunteer not found.")
        current = self.query(
            "SELECT COUNT(*) AS n FROM assignments WHERE role_id=? AND status <> 'cancelled'",
            (role_id,))[0]["n"]
        if current >= role["required_count"]:
            raise ValueError("This role is already full.")
        existing = self.query(
            "SELECT assignment_id, status FROM assignments WHERE volunteer_id=? AND role_id=?",
            (volunteer_id, role_id))
        if existing and existing[0]["status"] != "cancelled":
            raise ValueError("This volunteer is already assigned to this role.")
        conflicts = self.has_conflict(volunteer_id, role["start_time"], role["end_time"])
        if conflicts:
            raise ValueError("Schedule conflict with: " + ", ".join(c["title"] for c in conflicts))
        if existing:  # re-activate a previously cancelled assignment
            self.execute("UPDATE assignments SET status='assigned', attended=NULL, hours_worked=0 "
                         "WHERE assignment_id=?", (existing[0]["assignment_id"],))
        else:
            self.execute("INSERT INTO assignments (volunteer_id, role_id) VALUES (?, ?)",
                         (volunteer_id, role_id))
        return f"{vol[0]['name']} assigned to {role['role_name']} for {role['title']}."

    def list_assignments(self):
        return self.query(
            """SELECT a.assignment_id, v.name AS volunteer, v.email, e.title AS event, e.event_id,
                      c.club_name, c.category, c.logo,
                      r.role_name AS role, e.start_time, e.end_time, a.status, a.attended, a.hours_worked
               FROM assignments a JOIN volunteers v ON v.volunteer_id=a.volunteer_id
               JOIN roles r ON r.role_id=a.role_id JOIN events e ON e.event_id=r.event_id
               JOIN clubs c ON c.club_id=e.club_id
               ORDER BY e.start_time, r.role_name, v.name""")

    def mark_attendance(self, assignment_id, attended, hours_worked=0):
        if hours_worked < 0:
            raise ValueError("Hours worked cannot be negative.")
        self.execute(
            "UPDATE assignments SET attended=?, hours_worked=?, "
            "status=CASE WHEN ?=1 THEN 'attended' ELSE 'absent' END WHERE assignment_id=?",
            (int(attended), hours_worked if attended else 0, int(attended), assignment_id))

    def cancel_assignment(self, assignment_id):
        self.execute("UPDATE assignments SET status='cancelled' WHERE assignment_id=?", (assignment_id,))

    # ---------- analytics ----------
    def volunteer_analytics(self):
        return self.query(
            """SELECT v.volunteer_id, v.name,
                      COUNT(a.assignment_id) AS total_assignments,
                      COALESCE(SUM(CASE WHEN a.attended=1 THEN 1 ELSE 0 END),0) AS attended_events,
                      COALESCE(SUM(CASE WHEN a.attended=0 THEN 1 ELSE 0 END),0) AS absences,
                      COALESCE(SUM(a.hours_worked),0) AS total_hours,
                      CASE WHEN SUM(CASE WHEN a.attended IS NOT NULL THEN 1 ELSE 0 END)=0 THEN NULL
                           ELSE ROUND(100.0*SUM(CASE WHEN a.attended=1 THEN 1 ELSE 0 END)/
                                SUM(CASE WHEN a.attended IS NOT NULL THEN 1 ELSE 0 END),2) END
                      AS attendance_percentage
               FROM volunteers v
               LEFT JOIN assignments a ON a.volunteer_id=v.volunteer_id AND a.status <> 'cancelled'
               GROUP BY v.volunteer_id ORDER BY total_assignments DESC, v.name""")

    def role_report(self):
        return self.query(
            """SELECT e.title AS event, r.role_name, r.required_count,
                      COUNT(CASE WHEN a.status <> 'cancelled' THEN a.assignment_id END) AS assigned_count,
                      MAX(r.required_count - COUNT(CASE WHEN a.status <> 'cancelled' THEN a.assignment_id END), 0)
                        AS unfilled_positions
               FROM roles r JOIN events e ON e.event_id=r.event_id
               LEFT JOIN assignments a ON a.role_id=r.role_id
               GROUP BY r.role_id ORDER BY unfilled_positions DESC, e.title""")
