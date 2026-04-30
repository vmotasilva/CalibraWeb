import sys
from pathlib import Path
import pandas as pd

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_xlsm.py <absolute_path_to_xlsm>")
        sys.exit(1)
    path = Path(sys.argv[1])
    print("File:", path)
    print("Exists:", path.exists())
    if not path.exists():
        sys.exit(2)
    try:
        xls = pd.ExcelFile(path, engine="openpyxl")
        print("Sheets:", xls.sheet_names)
        for name in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=name, nrows=5)
                cols = list(df.columns)
                print("--", name, "cols:", cols)
                print(df.head(2).to_string(index=False))
            except Exception as e:
                print("Error reading sheet", name, ":", e)
    except Exception as e:
        print("Failed to open Excel:", e)
        sys.exit(3)
