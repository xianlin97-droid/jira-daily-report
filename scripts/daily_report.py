import os
import requests
from datetime import date
from base64 import b64encode
import anthropic


def fetch_tickets():
    email = os.environ["JIRA_EMAIL"]
    token = os.environ["JIRA_TOKEN"]
    domain = os.environ["JIRA_DOMAIN"]
    auth = b64encode(f"{email}:{token}".encode()).decode()

    response = requests.post(
        f"https://{domain}.atlassian.net/rest/api/3/search/jql",
        headers={
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        },
        json={
            "jql": "project = SD AND updated >= -1d ORDER BY priority DESC",
            "fields": ["summary", "status", "priority", "assignee"]
        }
    )
    response.raise_for_status()
    return response.json()["issues"]


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
        system="You are a helpful project manager. Write a daily triage email summary of these Jira tickets as clean HTML. Use >h2> for priority headings, <table> for ticket lists with columns for Ticket, Summary, and Status, and <strong> to highlight blockers. Do not include ```html code fences.",
        messages=[{"role": "user", "content": ticket_lines}]
    )
    return response.content[0].text


def send_email(report):
    webhook_url = os.environ["POWER_AUTOMATE_WEBHOOK_URL"]
    requests.post(webhook_url, json={
        "subject": f"Daily Jira Report — {date.today():%B %d, %Y}",
        "body": report
    })


tickets = fetch_tickets()
if tickets:
    report = summarize(tickets)
    send_email(report)
    print("Report sent!")
else:
    print("No tickets updated in the last 24 hours.")
