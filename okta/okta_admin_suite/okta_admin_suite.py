#!/usr/bin/env python3
import os
import re
import csv
import time
import argparse
import requests
from sensitive import api_key, domain, local_non_identity_repo
from concurrent.futures import ThreadPoolExecutor, as_completed

# Summary: This part of the code connects to the Okta API and retrieves user data, 
# group data, and group assigned application data for a specified domain, as well as 
# cleaning up a CSV file of user data.

# Define the default location of the repo
default_repo_location = os.path.join(os.path.expanduser("~") + "/Documents/GitHub/" + local_non_identity_repo)

# Check if the repo exists in the default location
if os.path.exists(default_repo_location):
    repo_location = default_repo_location
else:
    # If the repo does not exist in the default location, prompt the user to find it
    print(f"\nThis program needs to know the location of your locally cloned non-identity repo.\n\nIt could not locate {local_non_identity_repo} in the default location: {default_repo_location}")
    repo_location = input(f"\nPlease enter the file path location of {local_non_identity_repo}: ")

# A list of variables to hold user data from the Okta API
HUMAN_FILES = []
OKTA_USER_IDS = []
USER_ROLE_GROUPS = []
USER_ORGTEAM_GROUPS = []
USER_ORGTEAM_GROUP_IDS = []
USER_ORGTEAM_ASSOCIATED_APPS = []


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

# Define a function to handle rate limit errors from the Okta API
class OktaApiRateLimitError(Exception):
    pass

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

# This finds all of the apps that are associated with a user's org- and team- groups.
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

# Define a function that makes all the API calls
def get_data_from_okta():
    find_okta_user_ids()
    find_user_role_groups()
    find_group_ids()
    set_list = set(USER_ORGTEAM_GROUP_IDS)
    for id in set_list:
        find_associated_apps_names(id)


# These are all just functions to call to display the data we pulled up.
def print_user_roles():
    set_user_role_groups = set(USER_ROLE_GROUPS)
    for group in set_user_role_groups:
        print(f'{group}\r')
    print("\n-----------------------------")

def print_user_orgteams():
    set_user_orgteam_groups = set(USER_ORGTEAM_GROUPS)
    for group in set_user_orgteam_groups:
        print((f'{group}\r'))
    print("\n-----------------------------")

def print_user_orgteam_associated_apps():
    set_user_orgteam_associated_apps = set(USER_ORGTEAM_ASSOCIATED_APPS)
    for app in set_user_orgteam_associated_apps:
        print(f'{app}\r')

# Adding our TF syntax to be around the groups.
def format_groups(group):
    formatted_groups = []
    for item in group:
        formatted_groups.append(f'(\\"' + item + '\\")')
    return formatted_groups

# Here are some functions to handle big changes to our infrastructure.
# This one finds a line of text in a specified directory, and inserts
# a new line of text above it. This is to stage the role access when 
# preparing to switch roles.

def search_and_insert(directory, old_text, new_text):
    for subdir, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.tf'):
                file_path = os.path.join(subdir, file)
                with open(file_path, 'r') as f:
                    lines = f.readlines()

                with open(file_path, 'w') as f:
                    group_lines = []
                    for i, line in enumerate(lines):
                        if old_text in line and not line.lstrip().startswith('#'):
                            group_lines.append(line)
                            # Search upwards for group lines
                            for j in range(i-1, -1, -1):
                                if not re.search(r'.*isMemberOfGroupNameContains\("[^"]*"\).*\n', lines[j]):
                                    break
                                group_lines.insert(0, lines[j])

                            # Write new text and group lines to file
                            if group_lines and not any(new_text.strip() in group_line.strip() for group_line in group_lines):
                                f.write(new_text + '\n')
                                f.write(''.join(group_lines))
                                group_lines = []
                            else:
                                for group_line in group_lines:
                                    if old_text in group_line:
                                        f.write(new_text + '\n')
                                    else:
                                        f.write(group_line)
                                group_lines = []
                        else:
                            f.write(line)


# This is a clean-up function. It looks for all instances of the old
# role and removes it.
def search_and_destroy(directory, old_text, bottom_of_access_group_role):
    for subdir, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.tf'):
                file_path = os.path.join(subdir, file)
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                
                # This while loop handled the tweaking of code that needs to occur
                # at the bottom of an access group, removing OR ", and replacing 
                # with "")"
                with open(file_path, 'w') as f:
                    i = 0
                    while i < len(lines):
                        if bottom_of_access_group_role in lines[i]:
                            f.write(lines[i-1].replace('\\") OR ",', '\\")"'))
                            i += 1
                        elif old_text in lines[i]:
                            del lines[i]
                        else:
                            f.write(lines[i])
                            i += 1

# Some argparse commands.
def print_user_info(args):
    get_data_from_okta()
    print("-----------------------------\n")
    print("Here are the user(s) currently assigned role-group(s):\n")
    print_user_roles()
    print("\nHere are the user(s) currently assigned team- and org-groups:\n")
    print_user_orgteams()
    print("\nList of apps that are associated with the team- and org-groups the user(s) is in.\n")
    if len(USER_ORGTEAM_ASSOCIATED_APPS) == 0:
        print("There are no associated apps for the org- and team- groups listed.")
        print("\n-----------------------------")
    else:
        print_user_orgteam_associated_apps()
        print("\n-----------------------------")

def stage_new_role(args):
    get_data_from_okta()
    current_role = USER_ROLE_GROUPS[0]
    new_role = args.new_role
    formatted_current_role = f'"isMemberOfGroupNameContains(\\"{current_role}\\")'
    formatted_new_role = f'      "isMemberOfGroupNameContains(\\"role-{new_role}\\") OR ",'
    search_and_insert(repo_location, formatted_current_role, formatted_new_role)
    for group in format_groups(USER_ORGTEAM_GROUPS):
        search_and_insert(repo_location, group, formatted_new_role)

def apply_rbac(args):
    get_data_from_okta()
    formatted_orgteam_groups = []
    for group in USER_ORGTEAM_GROUPS:
        formatted_orgteam_groups.append(f'      "isMemberOfGroupNameContains(\\"{group}\\")')
    users_current_role = f'      "isMemberOfGroupNameContains(\\"{USER_ROLE_GROUPS[0]}\\") OR ",'
    for group in formatted_orgteam_groups:
        search_and_insert(repo_location, group, users_current_role)

def remove_old_role(args):
    old_role = args.old_role
    formatted_old_role = f'(\\"role-{old_role}\\")'
    bottom_of_access_group_role = f'(\\"role-{old_role}\\")"'
    search_and_destroy(repo_location, formatted_old_role, bottom_of_access_group_role)
                  
# Here's the argparse UI.
def main():
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(description = "Welcome to the Okta Admin Suite!")

        subparsers = parser.add_subparsers(title = "commands", dest = "command")

        parser_print_user_info = subparsers.add_parser("print_user_info", help = "Retrieves the role-, org-, and team- group memberships of one or more users,\r and displays all of the apps associated with the org- and team- groups.")
        parser_print_user_info.add_argument("-o", help = "cmd: python3 okta_admin_suite.py print_user_info")

        parser_apply_rbac = subparsers.add_parser("apply_rbac", help = "Add's a user's role- group above all of their team- and org- group access.")
        parser_apply_rbac.add_argument(
            "-r",
            help = "cmd: python3 okta_admin_suite.py apply_rbac"
        )

        parser_stage_new_role = subparsers.add_parser("stage_new_role", help = "Adds a specified role to all of the user's org-, team-, and role- access groups in the non-identity repo for one user.")
        parser_stage_new_role.add_argument(
            "-new_role",
            required=True,
            help = "cmd: python3 okta_admin_suite.py stage_new_role -new_role it-system-administrator"
        )

        parser_remove_old_role = subparsers.add_parser("remove_old_role", help = "Removes retired role from access groups.")
        parser_remove_old_role.add_argument(
            "-old_role",
            required=True,
            help = "cmd: python3 okta_admin_suite.py remove_old_role -old_role it-support-administrator"
        )

        args = parser.parse_args()

        if args.command == "print_user_info":
            print_user_info(args)
        if args.command == "apply_rbac":
            apply_rbac(args)
        if args.command == "stage_new_role":
            stage_new_role(args)
        if args.command == "remove_old_role":
            remove_old_role(args)
        else:
            parser.print_help()

main()