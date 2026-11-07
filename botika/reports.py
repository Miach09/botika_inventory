"""File layer: CSV export and import with friendly error handling."""
import csv
from pathlib import Path


class ReportError(Exception):
    """A file operation failed. The message is written for the end user."""


def write_csv(path, headers, rows) -> int:
    """Write rows to a CSV file (UTF-8 with BOM so Excel opens it correctly)."""
    path = Path(path)
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)
    except FileNotFoundError as exc:
        raise ReportError(f"The folder does not exist: {path.parent}") from exc
    except PermissionError as exc:
        raise ReportError("Permission denied. The file may be open in another "
                          "program, or the folder is read-only.") from exc
    except OSError as exc:
        raise ReportError(f"The file could not be written: {exc.strerror or exc}") from exc
    return len(rows)


def read_csv(path, required_headers):
    """Read a CSV file. Returns a list of (line_number, row_dict) pairs."""
    path = Path(path)
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ReportError("The file is empty.")
            headers = [h.strip().lower() for h in reader.fieldnames if h]
            missing = [h for h in required_headers if h not in headers]
            if missing:
                raise ReportError("The file is missing required column(s): "
                                  + ", ".join(missing))
            rows = []
            for line_no, row in enumerate(reader, start=2):
                clean = {k.strip().lower(): (v or "").strip()
                         for k, v in row.items() if k and isinstance(v, (str, type(None)))}
                if any(clean.values()):
                    rows.append((line_no, clean))
            return rows
    except FileNotFoundError as exc:
        raise ReportError(f"File not found: {path}") from exc
    except PermissionError as exc:
        raise ReportError("Permission denied while reading the file.") from exc
    except UnicodeDecodeError as exc:
        raise ReportError("The file is not a valid UTF-8 text/CSV file.") from exc
    except csv.Error as exc:
        raise ReportError(f"The CSV file is malformed: {exc}") from exc
    except IsADirectoryError as exc:
        raise ReportError("Please choose a file, not a folder.") from exc
