# Botika Inventory Management System

Desktop inventory system for a small community pharmacy (botika), built with
**Python Tkinter**, **SQLite** and the **openFDA Drug Label REST API**.
Course: Integrative Programming and Technologies.

The system focuses on **inventory only** (no sales module): medicines, suppliers,
stock batches with expiry dates, stock movements, alerts and CSV reports.

## Features

| Area | What it does |
| --- | --- |
| Medicines | Add, view, update, delete; search by brand/generic name; filter by category |
| Stock batches | Receive stock with batch number and expiry date; filter by expiry window |
| Stock movements | Issue/dispense, dispose, or adjust a batch; full history per batch |
| Dashboard | Totals, stock value, expired / expiring / low-stock alerts |
| Suppliers | Add, view, update, delete; search |
| Drug information | "Get Drug Info" calls openFDA and shows indications, warnings, dosage |
| Reports | Export medicines, batches, movements, expiry report to CSV; import medicines from CSV |

Expired stock is not counted as usable stock. Quantities can never go below zero.

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python seed_demo.py            # optional sample data for testing / the demo
python main.py
```

Requires Python 3.10 or newer. Tkinter ships with the standard Windows and macOS
installers. On Ubuntu/Debian run `sudo apt install python3-tk`.
The database is created automatically at `data/botika.db`; errors are logged to
`data/botika.log`.

## Run the tests

```bash
pip install pytest
python -m pytest -v
```

On a machine without a display use: `xvfb-run -a python -m pytest -v`.
The GUI tests are skipped automatically when no display is available.

## Project structure

```
main.py                 entry point
seed_demo.py            optional sample data
botika/
  config.py             settings and shared constants
  rules.py              expiry and stock-status rules (pure functions)
  validators.py         input validation, raises ValidationError
  database.py           SQLite layer (parameterized SQL, transactions)
  api_client.py         openFDA REST client + JSON parsing + error classes
  reports.py            CSV export/import with file error handling
  services.py           InventoryService: application logic used by the GUI
  gui/                  Tkinter interface (one module per tab)
tests/                  automated tests
docs/TEST_CASES.md      test-case table
```

## Architecture and separation of responsibilities

```
Tkinter GUI  ->  InventoryService  ->  Database (SQLite)
 (gui/)           (services.py)    ->  DrugInfoClient -> openFDA REST API
                                   ->  reports.py (CSV files)
```

* The GUI only calls `InventoryService`; it never writes SQL or HTTP requests.
* `database.py` is the only module that touches SQLite, `api_client.py` is the only
  one that touches the network, `reports.py` is the only one that touches CSV files.
* `rules.py` and `validators.py` have no dependencies on the GUI or database, so
  they are reusable and easy to test (high cohesion, low coupling).
* The API call runs in a background thread so the window never freezes; only the
  main thread touches Tk widgets and the database.

## Database design

`categories` 1-N `medicines` 1-N `stock_batches` 1-N `stock_movements`, and
`suppliers` 1-N `stock_batches`.

* A medicine that still has batches cannot be deleted (`ON DELETE RESTRICT`).
* Deleting a supplier keeps its batches (`ON DELETE SET NULL`).
* Deleting a batch deletes its movement history (`ON DELETE CASCADE`).

## openFDA API notes

* Endpoint: `https://api.fda.gov/drug/label.json`, searched with
  `openfda.generic_name:"<name>"`, no API key needed for light use.
* openFDA uses **U.S. generic names** (acetaminophen, not paracetamol). Brand names
  sold only in the Philippines may return "no results", which the app handles.
* Check openFDA's current rate limits before the defense.
* Drug information is for reference only and is not medical advice.

## Known limitations

* Single computer, single user; no login.
* Drug lookup needs an internet connection; everything else works offline.
* Dates are typed as `YYYY-MM-DD`.
