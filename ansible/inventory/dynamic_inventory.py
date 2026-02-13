#!/usr/bin/env python3
import os
import json
import yaml

BASE_DIR = os.path.dirname(__file__)
servers_dir = os.path.abspath(os.path.join(BASE_DIR, "../data/servers"))

inventory = {"_meta": {"hostvars": {}}, "all": {"hosts": [], "children": []}}

for filename in os.listdir(servers_dir):
    if filename.endswith(".yml"):
        path = os.path.join(servers_dir, filename)
        with open(path) as f:
            data = yaml.safe_load(f)

        name = data["server_name"]
        inventory["all"]["hosts"].append(name)
        inventory["_meta"]["hostvars"][name] = {
            "ansible_host": data.get("public_ip", name),
            "ansible_user": data["ssh_user"],
            **{k: v for k, v in data.items() if k not in ("server_name", "ssh_user", "public_ip")}
        }

print(json.dumps(inventory))
