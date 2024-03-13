import json
import os
import sys
import sensitive as senstitive
from pip._vendor import requests


api_creds = {
    "Accept": "application/json",
    "Contect-Type": "application/json",
    "Authorization": "SSWS " + senstitive.api_key,
}

group = sys.argv[1]

# Fetches the group ID
getgroup = requests.get(
    "https://redcanary.okta.com/api/v1/groups?q=" + group, headers=api_creds
)

group_data = getgroup.json()

groupid = group_data[0]["id"]

# Fetches the group members
g_respone = requests.get(
    "https://redcanary.okta.com/api/v1/groups/" + groupid + "/users", headers=api_creds
)

group_data = g_respone.json()

# Creates a list of group members
group_members = [g["id"] for g in group_data]

grouplist = []

# Fetches the role of each group member
for user in group_members:
    getid = requests.get(
        "https://redcanary.okta.com/api/v1/users/" + user + "/groups", headers=api_creds
    )
    data = getid.json()
    role = [
        g["profile"]["name"] for g in data if g["profile"]["name"].startswith("role-")
    ]
    output = json.dumps(role, indent=1)
    strip_1 = output.replace('"', "")
    strip_2 = strip_1.replace("]", "")
    strip_3 = strip_2.replace("[", "")
    output_role = strip_3.replace(",", "")
    grouplist.append(output_role)

# Removes carriage returns from the list
newgrouplist = [item.strip() for item in grouplist]

# Prints duplicates from the list
newgrouplist = list(dict.fromkeys(newgrouplist))

for item in newgrouplist:
    print('"isMemberOfGroupNameContains(\\"' + item + '\\") OR ",')