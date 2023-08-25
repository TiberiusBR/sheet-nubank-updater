from pynubank import Nubank
from fastapi import FastAPI
from app.settings.settings import settings
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from datetime import datetime
from zoneinfo import ZoneInfo
from app.exception.received_payment_exception import ReceivedPaymentException
import google.auth
import os
import uvicorn
from decimal import Decimal
from babel import Locale, numbers

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

app = FastAPI()
nu = Nubank()
locale = Locale("pt", "BR")
nu.authenticate_with_cert(settings.USER_CPF, settings.USER_PASS, settings.CERT_PATH)


@app.get("/")
async def health():
    return {"Application": "Running"}


@app.get("/cardbill")
async def cardbill():
    # Temporarily collecting via qr_code.
    creds = resolve_credentials()
    # creds, _ = google.auth.default()
    service = build("sheets", "v4", credentials=creds)
    credit_values = collect_values()
    transfer_values = collect_transfer()
    _, month, _ = get_current_date_br()
    results = {}
    results["credit"] = append_credit(service, credit_values, month)
    results["transfer"] = append_transfer(service, transfer_values, month)
    return results


def append_transfer(service, values, month):
    body = {"values": values}

    result = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=settings.SPREADSHEET_ID,
            range=f"{locale.months['format']['wide'][month]}!N6:Q",
            body=body,
            valueInputOption="USER_ENTERED",
        )
        .execute()
    )

    return result


def append_credit(service, values, month):
    body = {"values": values}

    result = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=settings.SPREADSHEET_ID,
            range=f"{locale.months['format']['wide'][month]}!I6:L",
            body=body,
            valueInputOption="USER_ENTERED",
        )
        .execute()
    )

    return result


def collect_transfer():
    day, month, year = get_current_date_br()
    info = []
    feed = nu.get_account_feed()
    for transfer in feed:
        cur_year, cur_month, cur_day = map(
            lambda time: int(time), transfer["postDate"].split("-")
        )
        if year != cur_year or month != cur_month or day != cur_day:
            break
        try:
            title, destiny, value, date = resolve_values(transfer)
            info.append([title, destiny, value, date])
        except ReceivedPaymentException:
            continue

    return info


def resolve_values(feed_event: dict) -> [str]:
    title = feed_event["title"].lower()
    detail = feed_event["detail"]
    if "recebida" in title:
        raise ReceivedPaymentException()
    elif "nupay" in title:
        title = "NuPay"
        destiny = title.split("em ")[1].split(" via")[0]
        value = detail.split("\n")[1]
    else:
        destiny = detail.split("\n")[0]
        value = detail.split("\n")[1]

    return title, destiny, value, feed_event["postDate"]


def collect_values():
    day, month, year = get_current_date_br()
    info = []
    feed = nu.get_card_statements()
    # feed = nu.get_account_feed() Extrato
    for bill in feed:
        cur_year, cur_month, cur_day = split_date(bill["time"])
        if year != cur_year or month != cur_month or day != cur_day:
            break
        value = numbers.format_currency(
            Decimal(parse_value(bill["amount"])), currency="BRL", locale=locale
        )
        info.append(
            [
                bill["description"],
                value,
                bill["title"],
                "-".join(split_date(bill["time"])),
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
