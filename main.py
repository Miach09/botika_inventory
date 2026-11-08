"""Entry point: python main.py"""
import logging
import sys
import tkinter as tk
from tkinter import messagebox

from botika import config
from botika.api_client import DrugInfoClient
from botika.database import Database, DatabaseError
from botika.gui.app import BotikaApp
from botika.gui.login import run_login
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
    service = InventoryService(db, DrugInfoClient())
    try:
        while run_login(service):               # log in, work, log out, repeat
            app = BotikaApp(service)
            app.mainloop()
            if not app.logged_out:              # window closed or File > Exit
                break
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
