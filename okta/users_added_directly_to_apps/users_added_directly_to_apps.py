import sensitive as sensitive
from webbrowser import get
import json
from pip._vendor import requests

oktaFile=('sensitive.py')

api_creds = {
"Accept" : "application/json",
"Contect-Type" : "application/json",
"Authorization" : "SSWS " + sensitive.api_key
}

class my_dictionary(dict):
    def __init__(self):
        self = dict()
    def add(self, key, value):
        self[key] = value

dict_obj = my_dictionary()
# Get list of all application IDs and Labels and add to dict_obj
respone = requests.get("https://redcanary.okta.com/api/v1/apps?limit=200",
                        headers = api_creds)

data = respone.json()

def myFunc(e):
    return e['id']
def myFunc2(e):
    return e['label']
def myFunc3(e):
    return e['status']
data.sort(key=myFunc)
data.sort(key=myFunc2)
data.sort(key=myFunc3)
apps=[]
for app in data:
    if app['status'] == 'ACTIVE': 
        dict_obj.add(app['label'], app['id'])
# Get list of users for all application IDs in dict_obj
for key, value in dict_obj.items():
    resptwo = requests.get("https://redcanary.okta.com/api/v1/apps/" + value + "/users?limit=500",
                        headers = api_creds)
    datatwo = resptwo.json()
    def myFunc(e):
        return e['credentials']['userName']

    # Filter for null values
    filtered_data = [user for user in datatwo if user['scope'] == 'USER' and user['credentials'] is not None]

    filtered_data.sort(key=myFunc)

    usrs = []
    for user in filtered_data:
        usrs.append(user['credentials']['userName'])

    output = json.dumps(usrs, indent=1)
    output_fmt = output.replace('"', '').replace("]", "").replace("[", "").replace(",", "")

    if output_fmt == "":
        continue
    else:
        print("Okta users assigned directly to " + key + ": ")
        print("")
        print(output_fmt)
                  


    




