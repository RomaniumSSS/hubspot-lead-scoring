import json
import os

import httpx
from dotenv import load_dotenv

# Load the .env file from this folder into environment variables.
load_dotenv()

# Read the token. If it is missing, fail loudly with a clear message
# instead of sending a broken request to HubSpot.
TOKEN = os.environ.get("HUBSPOT_TOKEN")
if not TOKEN:
    raise SystemExit(
        "HUBSPOT_TOKEN is not set. Put it in a .env file (see .env.example)."
    )

# Every HubSpot API call goes to this host.
BASE_URL = "https://api.hubapi.com"


def main():
    # The CRM endpoint that lists contact records.
    url = f"{BASE_URL}/crm/v3/objects/contacts"

    # The token travels in the Authorization header as a Bearer token.
    # This is the "pass" our Service Key issued.
    headers = {"Authorization": f"Bearer {TOKEN}"}

    # Ask for 10 contacts and only the properties we care about.
    params = {
        "limit": 10,
        "properties": "email,firstname,lastname,company",
    }

    response = httpx.get(url, headers=headers, params=params)

    # The HTTP status code is the first thing to read:
    #   200 = ok, 401 = bad/missing token, 403 = token lacks the scope.
    print(f"HTTP status: {response.status_code}")
    response.raise_for_status()

    # Turn the raw JSON response into a Python object and pretty-print it,
    # so you can see exactly how HubSpot shapes a contact.
    data = response.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
