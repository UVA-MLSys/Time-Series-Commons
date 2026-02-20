#!/usr/bin/env python3
"""
Reclassify sensor-labeled datasets in models.json with accurate domain descriptions.
"""
import json

RECLASSIFICATIONS = {
    "allgesturewiimotex": "Motion (Gesture Recognition)",
    "allgesturewiimotey": "Motion (Gesture Recognition)",
    "allgesturewiimotez": "Motion (Gesture Recognition)",
    "pickupgesturewiimotez": "Motion (Gesture Recognition)",
    "shakegesturewiimotez": "Motion (Gesture Recognition)",
    "gesturepebblez1": "Motion (Gesture Recognition)",
    "gesturepebblez2": "Motion (Gesture Recognition)",
    "har": "Human Activity Recognition",
    "car": "Transportation (Vehicle Sensor)",
    "cincecgtorso": "Health (ECG)",
    "dodgerloopday": "Transportation (Traffic Monitoring)",
    "dodgerloopgame": "Transportation (Traffic Monitoring)",
    "dodgerloopweekend": "Transportation (Traffic Monitoring)",
    "earthquakes": "Nature (Seismology)",
    "forda": "Industry (Vehicle Diagnostics)",
    "fordb": "Industry (Vehicle Diagnostics)",
    "freezerregulartrain": "Industry (Appliance Monitoring)",
    "freezersmalltrain": "Industry (Appliance Monitoring)",
    "gas-sensor-array-low-concentration": "Nature (Air Quality Monitoring)",
    "insectwingbeatsound": "Audio (Bioacoustics)",
    "iot-timebench": "Industry (Industrial IoT)",
    "italypowerdemand": "Energy (Electricity Demand)",
    "electricity-transformer-dataset-ett-small-h1/h2": "Energy (Electricity Transformer)",
    "electricity-transformer-dataset-ett-small-m1/m2": "Energy (Electricity Transformer)",
    "lightning2": "Nature (Meteorology)",
    "lightning7": "Nature (Meteorology)",
    "motestrain": "Environmental Monitoring (Temperature)",
    "plane": "Transportation (Aviation)",
    "sonyaiborobotsurface1": "Industry (Robotics)",
    "sonyaiborobotsurface2": "Industry (Robotics)",
    "trace": "Industry (Industrial Monitoring)",
    "wafer": "Industry (Semiconductor Manufacturing)",
    "chlorineconcentration": "Health (Water Quality Monitoring)",
}

data_path = "../data/models.json"

with open(data_path, "r", encoding="utf-8") as f:
    data = json.load(f)

updated = 0
for entry in data["models"]:
    entry_id = entry.get("id", "").lower()
    if entry_id in RECLASSIFICATIONS:
        old = entry["domain"]
        entry["domain"] = RECLASSIFICATIONS[entry_id]
        print(f"  [{entry_id}] '{old}' -> '{entry['domain']}'")
        updated += 1

with open(data_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\nUpdated {updated} entries.")
