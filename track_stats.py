import requests
import csv
import os
from datetime import datetime

OWNER = "venkatp0566-code"
REPO  = "tqqq-bot"
TOKEN = os.environ.get("GITHUB_TOKEN")

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def fetch(endpoint):
    r = requests.get(
        f"https://api.github.com/repos/{OWNER}/{REPO}/{endpoint}",
        headers=headers
    )
    return r.json()

clones = fetch("traffic/clones")
views  = fetch("traffic/views")
stars_r = requests.get(
    f"https://api.github.com/repos/{OWNER}/{REPO}",
    headers=headers
).json()

print(f"Clones (14d): {clones.get('count')} total, {clones.get('uniques')} unique")
print(f"Views  (14d): {views.get('count')} total, {views.get('uniques')} unique")
print(f"Stars:        {stars_r.get('stargazers_count', 0)}")

csv_file = "repo_stats_history.csv"
file_exists = os.path.exists(csv_file)

with open(csv_file, "a", newline="") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(["date", "clones_total", "clones_unique",
                         "views_total", "views_unique", "stars"])
    writer.writerow([
        datetime.now().strftime("%Y-%m-%d"),
        clones.get("count", 0),
        clones.get("uniques", 0),
        views.get("count", 0),
        views.get("uniques", 0),
        stars_r.get("stargazers_count", 0)
    ])

print(f"Saved to {csv_file}")