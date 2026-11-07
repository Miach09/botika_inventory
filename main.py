"""Entry point: python main.py"""
import logging
import sys
import tkinter as tk
from tkinter import messagebox

from botika import config
from botika.api_client import DrugInfoClient
from botika.database import Database, DatabaseError
from botika.gui.app import BotikaApp
from botika.services import InventoryService


def main() -> int:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=config.LOG_PATH, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        db = Database(config.DB_PATH)
    except DatabaseError as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Cannot start", str(exc))
        return 1
    try:
        BotikaApp(InventoryService(db, DrugInfoClient())).mainloop()
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
