# Perseus Equipment Analytics

Local analytics dashboard for `perseus_equipment_database.db`.

## Setup

From this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The app looks for the database at:

```text
C:\Bobbi - Hacakthon Exercise 2\perseus_equipment_database.db
```

You can change the database path from the sidebar after the app starts.

## What It Does

- Adds an active invoice dashboard with invoice type and item type charts.
- Discovers database tables automatically.
- Shows table row counts, loaded rows, column counts, and missing-cell counts.
- Lets you preview table data.
- Builds quick charts from detected numeric, categorical, and date/time-like columns.
- Provides a read-only SQL workspace for custom `SELECT` and `WITH` queries.
- Exports SQL query results as CSV.

## Notes

The dashboard does not assume a fixed schema, so it can start working before custom equipment-specific metrics are defined. Once the most important tables and columns are known, the next step is to add dedicated KPIs such as utilization, downtime, maintenance activity, cost, location, or status summaries.
