import os
import requests
from datetime import date
from base64 import b64encode
import anthropic

# --- Step 1: Fetch tickets from Jira ---
def fetch_tickets():
    email = os.environ["JIRA_EMAIL"]
    token = os.environ["JIRA_TOKEN"]
    domain = os.environ["JIRA_DOMAIN"]
    auth = b64encode(f"{email}:{token}".encode()).decode()

    response = requests.get(
        f"https://{domain}.atlassian.net/rest/api/3/search",
        headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
        params={
            "jql": "project = SD AND updated >= -1d ORDER BY priority DESC",
            "fields": "summary,status,priority,assignee"
        }
    )
    response.raise_for_status()
    return response.json()["issues"]

# --- Step 2: Ask Claude to summarize ---
def summarize(tickets):
    ticket_lines = "\n".join([
        f"- [{t['key']}] {t['fields']['summary']} | "
        f"Status: {t['fields']['status']['name']} | "
        f"Priority: {t['fields']['priority']['name']}"
        for t in tickets
    ])

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system="You are a helpful project manager. Write a short daily triage email summary of these Jira tickets. Group by priority. Flag any blockers.",
        messages=[{"role": "user", "content": ticket_lines}]
    )
    return response.content[0].text

# --- Step 3: Send via Power Automate ---
def send_email(report):
    webhook_url = os.environ["POWER_AUTOMATE_WEBHOOK_URL"]
    requests.post(webhook_url, json={
        "subject": f"Daily Jira Report — {date.today():%B %d, %Y}",
        "body": report
    })

# --- Run everything ---
tickets = fetch_tickets()
if tickets:
    report = summarize(tickets)
    send_email(report)
    print("Report sent!")
else:
    print("No tickets updated in the last 24 hours.")
