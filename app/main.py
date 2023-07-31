from pynubank import Nubank
from fastapi import FastAPI
from settings.settings import settings
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import google.auth
import uvicorn
import calendar
from decimal import Decimal
import locale
from typing import List

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

app = FastAPI()
nu = Nubank()
locale.setlocale(locale.LC_ALL, 'pt_BR')
nu.authenticate_with_cert(settings.USER_CPF, settings.USER_PASS, "./secrets/cert.p12")


@app.get("/")
async def health():
    return {"Application": "Running"}


@app.get("/cardbill")
async def get_bill_info():
    # Temporarily collecting via qr_code.
    #creds = resolve_credentials()
    creds, _ = google.auth.default()
    service = build("sheets", "v4", credentials=creds)
    values = collect_values()
    _, month, _ = get_current_date_br()
    return append_credit(service, values, month)


def append_credit(service, values, month):
    body = {"values": values}

    result = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=settings.SPREADSHEET_ID,
            range=f"{calendar.month_name[month]}!I6:K",
            body=body,
            valueInputOption="USER_ENTERED",
        )
        .execute()
    )

    return result


def collect_values():
    day, month, year = get_current_date_br()
    info = []
    feed = nu.get_card_statements()
    # feed = nu.get_account_feed() Extrato
    for bill in feed:
        cur_year, cur_month, cur_day = split_date(bill["time"])
        if year != cur_year or month != cur_month or day != cur_day:
            break
        info.append(
            [
                bill["description"],
                locale.currency(Decimal(parse_value(bill["amount"])), grouping=True),
                bill["title"],
            ]
        )
    return info


def get_current_date_br():
    dt = datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
    time = dt.strftime("%d-%m-%Y")
    return split_date(time)


def resolve_credentials():
    creds = None
    token = "./secrets/token.json"
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token):
        creds = Credentials.from_authorized_user_file(token, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "./secrets/credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token, "w") as token:
            token.write(creds.to_json())
    return creds


def parse_value(number: int):
    parsed_number = str(number)
    decimal_value = parsed_number[-2:]
    return f"{parsed_number[:len(parsed_number) - 2]}.{decimal_value}"


def split_date(date: str):
    splitted_date = date.split("T")[0].split("-")
    return map(lambda time: int(time), splitted_date)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
