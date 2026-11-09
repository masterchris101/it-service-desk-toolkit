# IT Service Desk Toolkit

A **Python command-line IT help desk simulator** for practicing common service desk workflows. It models incident ticketing, endpoint compliance, video conference endpoint monitoring, Windows 365 Cloud PC administration, and IT certification quizzes.

**Important:** This is a local simulation for learning and portfolio demonstration. It does **not** connect to ServiceNow, Microsoft Intune, Cisco, or Windows 365 APIs.

## Features

- **Incident ticketing:** Create, list, update, and close tickets, with priority calculated from impact and urgency and simulated SLA deadlines.
- **Endpoint compliance:** Check simulated Windows/macOS devices for OS version, disk encryption, antivirus status, and recent check-in.
- **Video conferencing monitoring:** Review simulated Cisco endpoint status, registration, and packet loss; optionally create incident tickets for alerts.
- **Cloud PC management:** Simulate provisioning, listing, restarting, reprovisioning, and deprovisioning Windows 365 Cloud PCs.
- **Certification practice:** Answer sample CompTIA A+, Network+, and ITIL Foundation multiple-choice questions.
- **SQLite persistence:** Save demonstration data locally in a `helpdesk.db` file.

## Tech stack

- Python 3
- SQLite (`sqlite3` standard library)
- `argparse` command-line interface
- Python standard library (`datetime`, `random`)

No third-party packages are required.

## Getting started

Clone or download the repository, open a terminal in its folder, and run:

```bash
python3 it_helpdesk_toolkit.py seed
```

This loads sample data. **Warning:** Running `seed` again deletes and replaces data in the local demo database.

Try these commands:

```bash
# Incident tickets
python3 it_helpdesk_toolkit.py ticket list
python3 it_helpdesk_toolkit.py ticket new "VPN won't connect" --user maria --impact 2 --urgency 2
python3 it_helpdesk_toolkit.py ticket update 1 --state "In Progress" --note "Investigating login failure"
python3 it_helpdesk_toolkit.py ticket close 1 --note "Resolved and confirmed"

# Device compliance
python3 it_helpdesk_toolkit.py devices list
python3 it_helpdesk_toolkit.py devices compliance
python3 it_helpdesk_toolkit.py devices compliance --auto-ticket

# Video endpoint health
python3 it_helpdesk_toolkit.py video list
python3 it_helpdesk_toolkit.py video health --auto-ticket

# Simulated Cloud PCs
python3 it_helpdesk_toolkit.py w365 list
python3 it_helpdesk_toolkit.py w365 provision --user carlos --size 4vCPU/16GB

# Certification quiz
python3 it_helpdesk_toolkit.py quiz --cert Network+ --count 5
```

To see all available commands:

```bash
python3 it_helpdesk_toolkit.py --help
```

## How it works

The program uses `argparse` to route a requested command to a feature handler. SQLite tables store tickets, devices, video endpoints, and Cloud PCs. Sample records are created by the `seed` command.

The ticketing workflow derives priority from an impact/urgency matrix and assigns an SLA due date. Compliance checks and endpoint health checks can generate sample incident tickets.

## Scope and limitations

- Training/portfolio simulator—not production help desk software.
- All endpoint and Cloud PC actions operate on simulated database records, not real managed devices.
- SLA and priority rules are illustrative.
- Quiz content is a small practice set, not an official certification exam.
- Data is stored locally in `helpdesk.db`, which is intentionally excluded from Git.

## Future improvements

- Add automated tests for ticketing and compliance logic.
- Add user input validation and clearer reporting for invalid IDs.
- Build a web dashboard to browse tickets and compliance results.