# AgriPlan — Smart Agriculture Crop Task & Field Planner

**Team Name:** NEXMIND  
**Team ID:** CBC029  
**Problem ID:** PS-19  
**Domain:** Agriculture Technology / Web Development  
**Institution:** Anuvartik Mirji Bhartesh Institute of Technology  

---

## 1. Project Overview

Farmers managing multiple fields and diverse crops must coordinate irrigation, fertilization, pesticide spraying, weeding, and harvesting under tight seasonal windows. Manual planning causes missed spray intervals, worker double-bookings, equipment collisions, and cascading delays when sequential operations depend on earlier activities.

**AgriPlan** is a functional, full-stack smart agricultural operations platform that empowers farmers to manage multiple parcels, schedule farming tasks, enforce prerequisite dependencies, automatically detect resource conflicts, and receive transparent alternative rescheduling suggestions in one click.

---

## 2. Technology Stack

* **Backend:** Python 3.12, Flask 3.0.3, Werkzeug 3.0.3
* **Database:** SQLite (Normalized relational schema with foreign keys and cascade rules)
* **Frontend:** Semantic HTML5, Vanilla CSS3 (Custom design system), Vanilla JavaScript (ES6+)
* **Visualization:** Chart.js 4.4 (Live crop acreage and task status breakdown)
* **Rule Engine:** Transparent Python-based scheduling and conflict detection algorithm
* **Testing:** Pytest 8.2

---

## 3. Key Modules & Features

### A. Authentication & Security
* Farmer registration and session-based login with Werkzeug password hashing.
* Multi-tenant user isolation ensuring farmers only access their private fields, crops, tasks, and machinery.
* Dedicated **1-Click Demo Login** button for hackathon evaluators.

### B. Farm Field Management
* CRUD operations for farm parcels and plots.
* Fields store: Field Name, Location/Coordinates, Size (with units: acres, hectares), Soil Type, Irrigation Type, and Agronomic Notes.
* Automatic tracking of active crops planted on each parcel.

### C. Crop Lifecycle Tracking
* Associates crops with specific fields.
* Tracks variety, sowing date, expected harvest date, and growth status (`Sown`, `Growing`, `Flowering`, `Ready for Harvest`, `Harvested`).

### D. Farm Task Scheduling & Dependency Engine
* Schedule activities: `Irrigation`, `Fertilizer application`, `Pesticide or crop spraying`, `Weeding`, `Pruning`, `Inspection`, `Harvesting`, and custom operations.
* Priority levels: `Low`, `Medium`, `High`, `Critical`.
* **Prerequisite Dependencies:** Enforces task sequences (e.g. soil tilling must complete before fertilizer application).
* **Start Validation:** Dependent tasks cannot transition to `In Progress` while prerequisites are incomplete.
* **Cycle Prevention:** Rejects direct and transitive circular dependencies.

### E. Smart Conflict Detection Engine
Automatically checks and flags 5 conflict categories:
1. **Worker Double-Booking:** The same worker assigned to overlapping tasks (`TaskA.start < TaskB.end AND TaskB.start < TaskA.end`).
2. **Equipment Conflict:** The same tractor, water pump, or sprayer scheduled simultaneously.
3. **Dependency Timing Conflict:** Dependent task scheduled to start before prerequisite finishes.
4. **Deadline Violations:** Task scheduled end time exceeds hard deadline.
5. **Invalid Scheduling:** Prevents tasks with end time prior to start time.

### F. Smart Rescheduling Engine
When a task experiences delays or resource conflicts:
* Identifies required resources (worker, equipment, prerequisite tasks).
* Searches forward for available daytime farm slots (07:00 – 19:00).
* Preserves original task duration.
* Verifies worker availability, equipment readiness, and prerequisite completion.
* Provides transparent explanations for why each slot is suitable.
* Allows 1-click acceptance that atomically updates the SQLite database.

### G. Interactive Farm Calendar & Timeline
* Switch between **Month**, **Week**, and **Day** views.
* Live color-coded status badges (`Pending`, `In Progress`, `Completed`, `Overdue`, `Conflict`).
* Filter calendar events by specific field.
* Click any task to inspect details and prerequisite statuses.

### H. Dashboard Analytics & Notifications
* 7 summary KPI cards: Total Fields, Active Crops, Due Today, Pending, Completed, Overdue, and Conflicts.
* Dynamic Chart.js donuts and bar charts.
* In-app notification center for deadlines, overdue warnings, and conflict alerts.

### I. Future-Ready Weather Architecture
* Compliant with Problem Statement Section 17: The core scheduling engine is independent of weather.
* Dedicated configuration interface and placeholder ready for future Open-Meteo or IMD weather API keys.

### J. AgriPlan Smart Farm Operations Index (AgriIndex — Unique Innovation)
* Proprietary operational health algorithm (0–100) combining schedule conflict density, deadline feasibility, overdue task penalties, and equipment balance.
* Instant visual score dial (*Optimal*, *Good*, *Needs Attention*, *Critical*) providing farmers and judges with immediate operational clarity.

### K. Intelligent Agronomic Advisory & Stress Engine (Unique Innovation)
* **Thermal Microclimate Warning:** Detects foliar spraying scheduled during peak midday heat (11:00 AM – 03:00 PM) and recommends early morning windows (07:00–10:00 AM) to prevent evaporation and drift.
* **Sequential Bottleneck Analysis:** Pinpoints prerequisite tasks holding up downstream operations and prompts prioritization.
* **Machinery Allocation Load Matrix:** Monitors equipment and worker booking density to prevent overuse and equipment motor burnout.

---

## 4. Project Structure

```
CBC2.O/
├── app.py                     # Main Flask application and REST routes
├── config.py                  # Application configuration settings
├── database.py                # SQLite connection manager and schema DDL
├── models.py                  # User authentication and password hashing
├── conflict_detector.py       # Rule-based overlap, dependency & circular check
├── rescheduler.py             # Alternative time slot search engine
├── scheduler.py               # Dashboard metric aggregations & notifications
├── demo_data.py               # Seeder for the 6 hackathon demonstration scenarios
├── requirements.txt           # Python package dependencies
├── README.md                  # Comprehensive documentation
├── .env.example               # Environment variables example
├── .gitignore                 # Version control exclusions
├── instance/
│   └── agriplan.db            # SQLite database file
├── templates/                 # Jinja2 HTML5 responsive templates
│   ├── base.html              # Layout shell (Sidebar, Topbar, Modals)
│   ├── index.html             # Public landing page ("Plan Smarter. Farm Better.")
│   ├── login.html             # Login with 1-click evaluator demo button
│   ├── register.html          # Farmer registration
│   ├── dashboard.html         # Live dashboard with KPI cards and charts
│   ├── fields.html            # Field parcels CRUD
│   ├── crops.html             # Crop planting lifecycle CRUD
│   ├── tasks.html             # Task scheduler with status transitions
│   ├── calendar.html          # Interactive Month/Week/Day calendar
│   ├── workers.html           # Farm labor and skills management
│   ├── equipment.html         # Machinery and implement catalog
│   ├── conflicts.html         # Conflict management and 1-click reschedule
│   ├── notifications.html     # Notification center
│   └── settings.html          # Profile, Weather placeholder, Demo reset
├── static/
│   ├── css/
│   │   └── style.css          # AgriPlan design system and responsive styles
│   └── js/
│       ├── app.js             # Modal manager, AJAX task viewer, reschedule applier
│       ├── dashboard.js       # Chart.js rendering logic
│       └── calendar.js        # Dynamic calendar grid and timeline renderer
└── tests/
    ├── test_agriplan.py       # Pytest suite covering all 12 acceptance criteria
    └── test_live_server.py    # Live HTTP server integration tests
```

---

## 5. Hackathon Demonstration Scenarios

AgriPlan includes pre-configured sample data for **Demo Farmer (`demo@agriplan.com` / `demo123`)** demonstrating all 6 required problem scenarios:

| Scenario | Feature Demonstrated | How to Test in UI |
| :--- | :--- | :--- |
| **Scenario 1** | **Normal Scheduling** | View `Routine Drip Irrigation Cycle` on North Field. Notice clean pending status. |
| **Scenario 2** | **Worker Double-Booking** | Notice `Foliar Micronutrient Spraying` and `Inter-row Weeding` both assigned to **Worker A (Ramesh)** with overlapping hours. Flagged with warning badge. |
| **Scenario 3** | **Equipment Conflict** | Notice `Heavy Sprinkler Irrigation` and `Nursery Furrow Flooding` both booked on **Water Pump (Kirloskar 7.5HP)** at the same time. |
| **Scenario 4** | **Dependency Validation** | `DAP Fertilizer Application` depends on `Deep Sub-Soil Tilling`. Click **Start** &rarr; System blocks start and displays prerequisite explanation. |
| **Scenario 5** | **Smart Rescheduling** | Navigate to **Conflicts** &rarr; Click **"Suggest Alternative Slots"** on conflicted task. The engine calculates free slots respecting duration, worker, and pump availability. Click **"Accept Slot"** to atomically update DB. |
| **Scenario 6** | **Dashboard Live Updates** | Complete any task &rarr; Check Dashboard KPI cards and Chart.js bar charts automatically update in real time. |

*To restore this baseline at any point during your presentation, navigate to **Settings & Demo** and click **"Reset Demonstration Scenarios Now"**.*

---

## 6. Installation & Execution Guide

### Step 1: Clone or Open the Workspace
```powershell
cd c:\Users\huzai\Documents\CBC2.O
```

### Step 2: Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Seed the Demonstration Database
```powershell
python demo_data.py
```
*(Creates `instance/agriplan.db` with demo account and the 6 test scenarios)*

### Step 4: Run the Automated Test Suite
```powershell
python -m pytest tests/test_agriplan.py -v
```
*(Executes all 12 test cases covering authentication, CRUD, conflict detection, circular dependency prevention, and rescheduling)*

### Step 5: Start the AgriPlan Application
```powershell
python app.py
```
Open your browser and navigate to:
**http://127.0.0.1:5000**

**Demo Credentials:**
* **Email:** `demo@agriplan.com`
* **Password:** `demo123`

---

## 7. Automated Test Coverage (12 Acceptance Criteria)

All 12 test criteria defined in Section 23 pass with 100% success rate:

1. `test_user_registration_and_login` — User registration, password hashing, and session authentication.
2. `test_create_and_retrieve_fields` — Field creation, validation of positive acreage, and retrieval.
3. `test_create_and_update_crops` — Crop registration, lifecycle dates, and status editing.
4. `test_create_task` — Task scheduling with valid start and end datetimes.
5. `test_worker_conflict_detection` — Detection of overlapping shifts for the same worker.
6. `test_equipment_conflict_detection` — Detection of overlapping bookings for the same machine.
7. `test_task_dependency_validation` — Blocking premature task execution when prerequisites are pending.
8. `test_circular_dependency_rejection` — Graph cycle detection preventing circular task dependencies.
9. `test_identifying_overdue_tasks` — Identification of tasks past deadlines while preserving completed tasks.
10. `test_find_alternative_time_slots` — Calculation of non-conflicting slots preserving task duration.
11. `test_unauthorized_user_isolation` — Multi-tenant data segregation preventing unauthorized record access.
12. `test_reschedule_updates_database` — Atomic database update and notification generation on slot acceptance.

---

## 8. Technical Architecture & Design Decisions

* **Rule-Based Rescheduling:** Designed as an open, rule-based scheduler rather than a black-box model so farmers always understand the exact reasons for suggested times.
* **Local First:** Operates 100% locally with zero external API dependencies, cloud costs, or subscription barriers.
* **Safe Date Handling:** Datetimes are stored in ISO-8601 format (`YYYY-MM-DDTHH:MM`) allowing standard string comparisons and cross-platform SQLite compatibility.
* **Responsive Layout:** CSS Grid and Flexbox responsive architecture built for desktop monitors, farm office laptops, and mobile screens.

---

**Developed for Hackathon Problem PS-19 by Team NEXMIND (Team ID: CBC029)**
