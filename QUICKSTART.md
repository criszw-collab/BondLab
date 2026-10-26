# Open and run BondLab

Created by **Crispen Chachengwa — Applied AI and ML Specialist**  
Contact: **cris2214zw@gmail.com**

## Windows: easiest method

1. Download the repository using **Code → Download ZIP**.
2. Extract it. Open the folder containing `app.py`, `Setup_BondLab.bat` and `Start_BondLab.bat`.
3. Install 64-bit Python 3.10 or later if it is not already installed.
4. Double-click **Setup_BondLab.bat** once. It creates a local virtual environment and installs dependencies.
5. When setup completes successfully, double-click **Start_BondLab.bat**.
6. Open **http://127.0.0.1:8000** if the browser does not open automatically.
7. Keep the terminal window open. Stop the app with **Ctrl+C**.

Do not double-click `index.html`: it needs the Python API running. GitHub hosts the source code; it does not automatically host the running application.

## Windows PowerShell commands

Replace the folder path below if you extracted the repository somewhere else. A GitHub ZIP folder may be named `BondLab-main`.

```powershell
cd "C:\Users\Cris2\Desktop\BondLab"
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

On later visits:

```powershell
cd "C:\Users\Cris2\Desktop\BondLab"
.\.venv\Scripts\python.exe app.py
```

## macOS and Linux

Run inside the folder containing `app.py`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

## First calculation

1. Open **Bond valuation**.
2. Keep **10-year Treasury reopening** selected.
3. Click **Calculate valuation**.
4. With the original default $1,000 face amount, confirm:

| Output | Expected |
|---|---:|
| Clean quote per $100 | 100.114150 |
| Dirty quote per $100 | 100.478100 |
| Accrued interest | $3.64 |
| Settlement amount | $1,004.78 |
| Yield | 4.235% |

These are historical example inputs, not a current trading quote.

## Run validation

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe validate.py
```

The release contains 45 automated test methods, independent price checks and real-data validation. Read the generated `VALIDATION.md`. If validation fails, the command prints failing-test details and also saves `validation/test_output.txt`.

## Troubleshooting

| Problem | Action |
|---|---|
| Python is not found | Install 64-bit Python 3.10 or later, then reopen PowerShell. |
| `.venv` interpreter does not exist | Run `Setup_BondLab.bat` from the extracted folder. |
| Port 8000 is already in use | Run `.\.venv\Scripts\python.exe app.py --port 8001` and open http://127.0.0.1:8001. |
| Browser does not open | Enter the local address manually and confirm the terminal reports that Uvicorn is running. |
| Session token missing or expired | Reload the page after restarting the server. |
| Latest Fed download fails | Use the included real-data snapshot or retry when internet access is available. |
| An irregular coupon schedule is rejected | Check the original dated date. Odd coupon periods are outside this release's supported scope. |

For the complete walkthrough, read [USER_GUIDE.md](USER_GUIDE.md).
