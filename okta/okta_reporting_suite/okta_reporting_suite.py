#!bin/bash/python
import csv
import time
import requests
from sensitive import api_key
from sensitive import domain
from concurrent.futures import ThreadPoolExecutor, as_completed

# Summary: This code connects to the Okta API and retrieves user data, 
# group data, and group assigned application data for a specified domain, as well as 
# cleaning up a CSV file of user data.

# A list of variables to hold user data from the Okta API
HUMAN_FILES = []
OKTA_USER_IDS = []
USER_ROLE_GROUPS = []
USER_ORGTEAM_GROUPS = []
USER_ORGTEAM_GROUP_IDS = []
USER_ORGTEAM_ASSOCIATED_APPS = []

# Define a function to handle rate limit errors from the Okta API
class OktaApiRateLimitError(Exception):
    pass

# This function just cleans up the data in our names.csv file, and adds the first.last of each user to
# the human_files array.
def input_cleanup():
    user_list = []
    # Reads a CSV list of either First and Last names or e-mails (it can detect which one it is-- it can also be a mixture of both),
    # and adds them to the user_list variable in a first.last format:
    with open('names.csv') as csvfile:
        file = csv.reader(csvfile, delimiter=' ')
        for row in file:
            row = ('.'.join(row))
            row = row.replace(f"@{domain}.com", "")
            row = row.replace(",", "")
            row = row.replace(" ", "")
            user_list.append(row)

    # Lower-cases our list of name and assigns them to the human_files variable:
    for user in user_list:
        lowercase = user.lower()
        HUMAN_FILES.append(lowercase)

input_cleanup()

# This is the API get request with the API token included. The urls can be swapped depending on what API call we're trying to make,
# but it is important to user this function for get requests because it the function the multi-threading references. The delay is the 
# time that it waits between requests.

def okta_get_request(url):
    headers = {'Authorization': 'SSWS' + api_key}
    response = requests.get(url, headers=headers)
    data = response.json()
    if response.status_code == 404:
        return None
    elif response.status_code == 429:
        retries = 0
        while retries < 6:  # set the maximum number of retries to 6
            wait_time = 2 ** retries  # exponential wait time
            print(f"Exceeded rate limit. Waiting for {wait_time} seconds before retrying...")
            time.sleep(wait_time)
            response = requests.get(url, headers=headers)
            data = response.json()
            if response.status_code == 429:
                retries += 1
            else:
                break
        else:
            raise OktaApiRateLimitError("Exceeded rate limit after 5 retries")
    return data


# Find Okta user IDs for each user in the HUMAN_FILES list
def find_okta_user_ids():

    user_object_url_list = []
    fields = 'id'
    limit = 200
    offset = 0
    while True:
        # Create a list of Okta API URLs to retrieve user data for each user in the HUMAN_FILES list, with pagination
        for user in HUMAN_FILES:
            user_object_url_list.append(f'https://{domain}.okta.com/api/v1/users?filter=profile.login%20eq%20%22{user}@{domain}.com%22&fields={fields}&limit={limit}&offset={offset}')
        # Use ThreadPoolExecutor to asynchronously execute Okta API GET requests for each user URL
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(okta_get_request, url): url for url in user_object_url_list}
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    okta_user_data = future.result()
                    if bool(okta_user_data) == True:
                        user_id = okta_user_data[0]['id']
                        OKTA_USER_IDS.append(user_id)
                except Exception as exc:
                    exceptions = f'{url} generated an exception: {exc}'

        if len(okta_user_data) < limit:
            break
        offset += limit
        user_object_url_list.clear()  

# Find the associated role-, org-, and team- groups a user is in.
def find_user_role_groups():
    user_role_url_list = []

    for id in OKTA_USER_IDS:
        user_role_url_list.append(f"https://{domain}.okta.com/api/v1/users/{id}/groups?fields=profile.name")

    # Use ThreadPoolExecutor to asynchronously execute Okta API GET requests for each group URL
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(okta_get_request, url): url for url in user_role_url_list}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                okta_user_group_data = future.result()

                role_list = []
                user_orgteam_list = []

                # Iterate through each group in the list
                for group in okta_user_group_data:
                    if group.get('profile', {}).get('name', '').startswith('role-'):
                        role_list.append(group['profile']['name'])
                    elif group.get('profile', {}).get('name', '').startswith(('org-', 'team-')):
                        user_orgteam_list.append(group['profile']['name'])


                USER_ORGTEAM_GROUPS.extend(set(user_orgteam_list))
                USER_ROLE_GROUPS.extend(set(role_list))
            except Exception as exc:
                exceptions = f'{url} generated an exception: {exc}'

# Finds the Okta ID number of a group given its name.
def find_group_ids():
    group_ids_url_list = []

    fields = 'apps'

    set_user_orgteam_groups = set(USER_ORGTEAM_GROUPS)
    for groupname in set_user_orgteam_groups:
        group_ids_url_list.append(f"https://{domain}.okta.com/api/v1/groups?q={groupname}&fields={fields}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(okta_get_request, url): url for url in group_ids_url_list}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                okta_group_data = future.result()
                if bool(okta_group_data) == True:
                    group_ids = okta_group_data[0]['id']
                    USER_ORGTEAM_GROUP_IDS.append(group_ids)
            except Exception as exc:
                exceptions = f'{url} generated an exception: {exc}'

def find_associated_apps_names(group_id):
    try:
        page = 1
        per_page = 100
        while True:
            response = okta_get_request(f"https://redcanary.okta.com/api/v1/groups/{group_id}/apps?page={page}&per_page={per_page}")
            associated_apps_data = response
            if bool(associated_apps_data) == True:
                for app_data in associated_apps_data:
                    USER_ORGTEAM_ASSOCIATED_APPS.append(app_data['name'])
            if len(associated_apps_data) < per_page:
                break
            else:
                page += 1
    except OktaApiRateLimitError:
        # Handle rate limit error
        exceeded_error_log = f"Rate limit exceeded for group {group_id}"
        print(exceeded_error_log)

def print_user_roles():
    set_user_role_groups = set(USER_ROLE_GROUPS)
    for group in set_user_role_groups:
        print(f'{group}\r')

def print_user_orgteams():
    set_user_orgteam_groups = set(USER_ORGTEAM_GROUPS)
    for group in set_user_orgteam_groups:
        print((f'{group}\r'))

def print_user_orgteam_associated_apps():
    set_user_orgteam_associated_apps = set(USER_ORGTEAM_ASSOCIATED_APPS)
    for app in set_user_orgteam_associated_apps:
        print(f'{app}\r')

# Define a function that makes all the API calls
def get_data_from_okta():
    find_okta_user_ids()
    find_user_role_groups()
    find_group_ids()
    set_list = set(USER_ORGTEAM_GROUP_IDS)
    for id in set_list:
        find_associated_apps_names(id)

# A UI to handle presenting information to people using the tool.
def main_menu():
    print("")
    print("Welcome to the Okta Reporting Suite! Please give me some time to gather all of the user data from Okta.")
    print("")
    get_data_from_okta()

    while True:
        print("")
        print("Please select the kind of information you need to pull up about your users:")
        print("")
        print("1. Print the Okta role groups of the users you have provided.")
        print("2. Print the Okta orgteam groups of the users you have provided.")
        print("3. Print all apps associated with the org- and team- Okta groups from the org team groups of the users you have provided.")
        print("4. Exit")
        print("")

        choice = input("> ")
        if choice == "1":
            print("")
            print("Here is a de-duped list of okta role groups for the users you have provided.")
            print("")
            print_user_roles()
            print("")
        elif choice == "2":
            print("")
            print("Here is a de-duped list of okta org team groups for the users you have provided.")
            print("")
            print_user_orgteams()
            print("")
        elif choice == "3":
            print("")
            print("Here is a de-duped list of apps associated with your user's org team groups.")
            print("")
            print_user_orgteam_associated_apps()
            print("")
        elif choice == "4":
            print("")
            print("Goodbye!")
            print("")
            break
        else:
            print("Invalid input. Please select a valid option.")
            input("Press Enter to continue...")

main_menu()