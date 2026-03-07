import json
import csv

def load_json(file):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return {}

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def load_items():
    items = []
    with open("items.csv", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row["duped_value"] == "N/A":
                row["duped_value"] = row["value"]
            items.append(row)
    return items
items_data = []

def load_items():
    global items_data
    items_data.clear()
    with open("items.csv", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row["duped_value"] == "N/A":
                row["duped_value"] = row["value"]
            items_data.append(row)


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)
