import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = ["https://spreadsheets.google.com/feeds",
          "https://www.googleapis.com/auth/drive"]

print("Loading credentials...")
try:
    creds  = Credentials.from_service_account_file(
        "credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)
    print("Authorised OK")
    sheet = client.open("Attendance Log").sheet1
    print("Sheet opened OK")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([ts, "TEST USER", "test", "test"])
    print(f"SUCCESS: Row written at {ts}")
    print("Check your Google Sheet.")
except Exception as e:
    print(f"ERROR: {e}")