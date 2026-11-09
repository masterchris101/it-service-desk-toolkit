#!/usr/bin/env python3
"""
IT Service Desk Toolkit: a simulation covering five skill areas.

  1. ticket   -> ServiceNow-style incident ticketing (priority matrix, SLAs)
  2. devices  -> Intune-style endpoint compliance checks
  3. video    -> Cisco endpoint video conferencing health monitor
  4. w365     -> Windows 365 Cloud PC provisioning and management
  5. quiz     -> CompTIA A+ / Network+ / ITIL Foundation practice questions

Everything is simulated and stored in a local SQLite file (helpdesk.db).
No real Intune, Cisco, Microsoft, or ServiceNow APIs are called.

Usage examples:
  python it_helpdesk_toolkit.py seed
  python it_helpdesk_toolkit.py ticket new "VPN won't connect" --user maria --impact 2 --urgency 2
  python it_helpdesk_toolkit.py ticket list
  python it_helpdesk_toolkit.py ticket update 1 --state "In Progress" --note "Reset VPN profile"
  python it_helpdesk_toolkit.py ticket close 1 --note "Profile re-pushed, user confirmed"
  python it_helpdesk_toolkit.py devices compliance
  python it_helpdesk_toolkit.py video health --auto-ticket
  python it_helpdesk_toolkit.py w365 provision --user carlos --size 4vCPU/16GB
  python it_helpdesk_toolkit.py w365 restart 2
  python it_helpdesk_toolkit.py quiz --cert Network+ --count 5
"""
import argparse
import random
import sqlite3
from datetime import datetime, timedelta

DB = "helpdesk.db"
NOW = lambda: datetime.now().replace(microsecond=0)

# ServiceNow default priority matrix: (impact, urgency) -> priority
PRIORITY = {(1, 1): 1, (1, 2): 2, (2, 1): 2, (1, 3): 3, (2, 2): 3,
            (3, 1): 3, (2, 3): 4, (3, 2): 4, (3, 3): 5}
PRIORITY_NAME = {1: "1 - Critical", 2: "2 - High", 3: "3 - Moderate",
                 4: "4 - Low", 5: "5 - Planning"}
SLA_HOURS = {1: 4, 2: 8, 3: 24, 4: 72, 5: 120}

# Intune-style compliance policy
POLICY = {"min_windows": 10.0, "min_macos": 13.0, "max_checkin_days": 7}


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE IF NOT EXISTS tickets(
        id INTEGER PRIMARY KEY, short_desc TEXT, caller TEXT, category TEXT,
        impact INT, urgency INT, priority INT, state TEXT,
        opened TEXT, sla_due TEXT, closed TEXT, notes TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS devices(
        name TEXT PRIMARY KEY, owner TEXT, os TEXT, os_version REAL,
        encrypted INT, antivirus INT, last_checkin TEXT);
    CREATE TABLE IF NOT EXISTS video(
        name TEXT PRIMARY KEY, model TEXT, room TEXT, status TEXT,
        firmware TEXT, packet_loss REAL);
    CREATE TABLE IF NOT EXISTS cloudpcs(
        id INTEGER PRIMARY KEY, user TEXT, size TEXT, status TEXT, created TEXT);
    """)
    return con


# ---------------------------------------------------------------- ServiceNow
def create_ticket(con, desc, caller, impact, urgency, category="General"):
    pr = PRIORITY[(impact, urgency)]
    opened = NOW()
    due = opened + timedelta(hours=SLA_HOURS[pr])
    cur = con.execute(
        "INSERT INTO tickets(short_desc,caller,category,impact,urgency,priority,"
        "state,opened,sla_due) VALUES(?,?,?,?,?,?,?,?,?)",
        (desc, caller, category, impact, urgency, pr, "New",
         opened.isoformat(" "), due.isoformat(" ")))
    con.commit()
    return cur.lastrowid


def inc(n):
    return f"INC{n:07d}"


def cmd_ticket(a):
    con = db()
    if a.action == "new":
        n = create_ticket(con, a.summary, a.user, a.impact, a.urgency, a.category)
        pr = PRIORITY[(a.impact, a.urgency)]
        print(f"Created {inc(n)}  priority {PRIORITY_NAME[pr]}  SLA {SLA_HOURS[pr]}h")
    elif a.action == "list":
        rows = con.execute(
            "SELECT * FROM tickets WHERE state != 'Closed' ORDER BY priority, opened"
        ).fetchall()
        if not rows:
            print("No open tickets.")
        for r in rows:
            breached = datetime.fromisoformat(r["sla_due"]) < NOW()
            flag = "  ** SLA BREACHED **" if breached else ""
            print(f"{inc(r['id'])}  {PRIORITY_NAME[r['priority']]:<13} "
                  f"{r['state']:<12} {r['caller']:<10} {r['short_desc']}{flag}")
    elif a.action in ("update", "close"):
        row = con.execute("SELECT * FROM tickets WHERE id=?", (a.id,)).fetchone()
        if not row:
            return print("Ticket not found.")
        state = "Closed" if a.action == "close" else (a.state or row["state"])
        note = f"{row['notes']}\n[{NOW()}] {a.note}".strip() if a.note else row["notes"]
        closed = NOW().isoformat(" ") if state == "Closed" else None
        con.execute("UPDATE tickets SET state=?, notes=?, closed=? WHERE id=?",
                    (state, note, closed, a.id))
        con.commit()
        print(f"{inc(a.id)} -> {state}")


# -------------------------------------------------------------------- Intune
def check_device(d):
    issues = []
    minimum = POLICY["min_windows"] if d["os"] == "Windows" else POLICY["min_macos"]
    if d["os_version"] < minimum:
        issues.append(f"OS {d['os_version']} below minimum {minimum}")
    if not d["encrypted"]:
        issues.append("disk not encrypted (BitLocker/FileVault)")
    if not d["antivirus"]:
        issues.append("antivirus disabled")
    days = (NOW() - datetime.fromisoformat(d["last_checkin"])).days
    if days > POLICY["max_checkin_days"]:
        issues.append(f"no check-in for {days} days")
    return issues


def cmd_devices(a):
    con = db()
    rows = con.execute("SELECT * FROM devices ORDER BY name").fetchall()
    if a.action == "list":
        for d in rows:
            print(f"{d['name']:<12} {d['owner']:<8} {d['os']} {d['os_version']}")
        return
    bad = 0
    print("Compliance report")
    print("-" * 60)
    for d in rows:
        issues = check_device(d)
        if issues:
            bad += 1
            print(f"NON-COMPLIANT  {d['name']} ({d['owner']})")
            for i in issues:
                print(f"    - {i}")
        else:
            print(f"compliant      {d['name']} ({d['owner']})")
    print("-" * 60)
    print(f"{len(rows) - bad}/{len(rows)} compliant")
    if a.auto_ticket:
        for d in rows:
            issues = check_device(d)
            if issues:
                n = create_ticket(con, f"Device {d['name']} non-compliant: {issues[0]}",
                                  d["owner"], 3, 2, "Endpoint Management")
                print(f"  opened {inc(n)} for {d['name']}")


# --------------------------------------------------------------------- Cisco
def cmd_video(a):
    con = db()
    rows = con.execute("SELECT * FROM video ORDER BY room").fetchall()
    print(f"{'Room':<14}{'Model':<18}{'Status':<14}{'Firmware':<10}Loss%")
    for v in rows:
        print(f"{v['room']:<14}{v['model']:<18}{v['status']:<14}"
              f"{v['firmware']:<10}{v['packet_loss']}")
    if a.action == "health":
        print()
        for v in rows:
            problem = None
            if v["status"] != "Registered":
                problem = f"{v['status']} (check network, SIP/Webex registration)"
            elif v["packet_loss"] > 2.0:
                problem = f"high packet loss {v['packet_loss']}% (check QoS/uplink)"
            if problem:
                print(f"ALERT {v['room']} ({v['model']}): {problem}")
                if a.auto_ticket:
                    n = create_ticket(con, f"{v['room']} video endpoint: {problem}",
                                      "facilities", 2, 2, "Video Conferencing")
                    print(f"  opened {inc(n)}")


# ---------------------------------------------------------------------- W365
def cmd_w365(a):
    con = db()
    if a.action == "provision":
        cur = con.execute("INSERT INTO cloudpcs(user,size,status,created) VALUES(?,?,?,?)",
                          (a.user, a.size, "Provisioned", NOW().isoformat(" ")))
        con.commit()
        print(f"Cloud PC CPC-{cur.lastrowid:03d} provisioned for {a.user} ({a.size})")
    elif a.action == "list":
        for r in con.execute("SELECT * FROM cloudpcs"):
            print(f"CPC-{r['id']:03d}  {r['user']:<10} {r['size']:<14} {r['status']}")
    elif a.action in ("restart", "reprovision", "deprovision"):
        status = {"restart": "Running", "reprovision": "Provisioning",
                  "deprovision": "Deprovisioned"}[a.action]
        con.execute("UPDATE cloudpcs SET status=? WHERE id=?", (status, a.id))
        con.commit()
        print(f"CPC-{a.id:03d}: {a.action} -> {status}")


# ---------------------------------------------------------------------- Certs
QUESTIONS = [
    ("A+", "Which command displays a Windows device's IP configuration?",
     ["ipconfig", "ifconfig", "netstat", "tracert"], 0),
    ("A+", "Which tool is used to manage disk partitions in Windows?",
     ["Task Manager", "Disk Management", "Device Manager", "msconfig"], 1),
    ("A+", "A laptop won't power on but the charger LED is lit. What should you test first?",
     ["Replace the motherboard", "Reinstall the OS", "Try a known-good battery/power cycle", "Update BIOS"], 2),
    ("Network+", "Which port does HTTPS use by default?",
     ["80", "443", "22", "3389"], 1),
    ("Network+", "Which protocol dynamically assigns IP addresses?",
     ["DNS", "DHCP", "NAT", "ARP"], 1),
    ("Network+", "Which OSI layer is responsible for routing?",
     ["Layer 2", "Layer 3", "Layer 4", "Layer 7"], 1),
    ("Network+", "Which port does RDP use by default?",
     ["3389", "443", "25", "110"], 0),
    ("ITIL", "In ITIL, an unplanned interruption to a service is called a(n):",
     ["Change", "Incident", "Problem", "Request"], 1),
    ("ITIL", "The underlying cause of one or more incidents is a:",
     ["Known error", "Problem", "Release", "Event"], 1),
    ("ITIL", "A pre-approved, low-risk, well-understood change is a:",
     ["Emergency change", "Normal change", "Standard change", "Major change"], 2),
]


def cmd_quiz(a):
    pool = [q for q in QUESTIONS if a.cert in ("all", q[0])] or QUESTIONS
    picks = random.sample(pool, min(a.count, len(pool)))
    score = 0
    for i, (cert, q, opts, ans) in enumerate(picks, 1):
        print(f"\nQ{i} [{cert}] {q}")
        for n, o in enumerate(opts, 1):
            print(f"  {n}. {o}")
        try:
            choice = int(input("Answer: ")) - 1
        except ValueError:
            choice = -1
        if choice == ans:
            score += 1
            print("Correct.")
        else:
            print(f"Incorrect. Answer: {opts[ans]}")
    print(f"\nScore: {score}/{len(picks)}")


# ----------------------------------------------------------------------- Seed
def cmd_seed(_):
    con = db()
    for t in ("tickets", "devices", "video", "cloudpcs"):
        con.execute(f"DELETE FROM {t}")
    ago = lambda d: (NOW() - timedelta(days=d)).isoformat(" ")
    con.executemany("INSERT INTO devices VALUES(?,?,?,?,?,?,?)", [
        ("WIN-LT-001", "maria", "Windows", 11.0, 1, 1, ago(1)),
        ("WIN-LT-002", "carlos", "Windows", 10.0, 0, 1, ago(2)),
        ("WIN-DT-003", "ana", "Windows", 10.0, 1, 0, ago(12)),
        ("MAC-LT-004", "luis", "macOS", 14.2, 1, 1, ago(0)),
        ("MAC-LT-005", "sofia", "macOS", 12.6, 1, 1, ago(3)),
    ])
    con.executemany("INSERT INTO video VALUES(?,?,?,?,?,?)", [
        ("SX-01", "Cisco Room Kit", "Boardroom", "Registered", "RoomOS 11", 0.3),
        ("SX-02", "Cisco Desk Pro", "Huddle A", "Registered", "RoomOS 11", 4.1),
        ("SX-03", "Cisco Board 55", "Training", "Offline", "RoomOS 10", 0.0),
    ])
    con.executemany("INSERT INTO cloudpcs(user,size,status,created) VALUES(?,?,?,?)", [
        ("maria", "2vCPU/8GB", "Running", ago(30)),
        ("carlos", "4vCPU/16GB", "Running", ago(10)),
    ])
    con.commit()
    create_ticket(con, "Outlook keeps asking for password", "ana", 3, 2, "Email")
    create_ticket(con, "Conference room display blank", "facilities", 2, 2, "Video Conferencing")
    print("Sample data loaded.")


def main():
    p = argparse.ArgumentParser(description="IT Service Desk Toolkit (simulated)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("seed").set_defaults(fn=cmd_seed)

    t = sub.add_parser("ticket")
    ts = t.add_subparsers(dest="action", required=True)
    n = ts.add_parser("new")
    n.add_argument("summary")
    n.add_argument("--user", default="unknown")
    n.add_argument("--impact", type=int, choices=[1, 2, 3], default=3)
    n.add_argument("--urgency", type=int, choices=[1, 2, 3], default=3)
    n.add_argument("--category", default="General")
    ts.add_parser("list")
    u = ts.add_parser("update")
    u.add_argument("id", type=int)
    u.add_argument("--state", choices=["New", "In Progress", "On Hold", "Resolved"])
    u.add_argument("--note")
    c = ts.add_parser("close")
    c.add_argument("id", type=int)
    c.add_argument("--note")
    t.set_defaults(fn=cmd_ticket)

    d = sub.add_parser("devices")
    d.add_argument("action", choices=["list", "compliance"])
    d.add_argument("--auto-ticket", action="store_true")
    d.set_defaults(fn=cmd_devices)

    v = sub.add_parser("video")
    v.add_argument("action", choices=["list", "health"])
    v.add_argument("--auto-ticket", action="store_true")
    v.set_defaults(fn=cmd_video)

    w = sub.add_parser("w365")
    ws = w.add_subparsers(dest="action", required=True)
    pr = ws.add_parser("provision")
    pr.add_argument("--user", required=True)
    pr.add_argument("--size", default="2vCPU/8GB")
    ws.add_parser("list")
    for name in ("restart", "reprovision", "deprovision"):
        ws.add_parser(name).add_argument("id", type=int)
    w.set_defaults(fn=cmd_w365)

    q = sub.add_parser("quiz")
    q.add_argument("--cert", choices=["all", "A+", "Network+", "ITIL"], default="all")
    q.add_argument("--count", type=int, default=5)
    q.set_defaults(fn=cmd_quiz)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()