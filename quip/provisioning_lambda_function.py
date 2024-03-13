import json
from pip._vendor import requests
import boto3
from botocore.exceptions import ClientError


def get_secret():

    secret_name = "prod/quip_token"
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    return get_secret_value_response['SecretString']
    
def lambda_handler(event, context):
    secret = get_secret()
    token = json.loads(secret)
    bearer = token.get("quip_token")
    api_creds = {
    "Accept" : "application/json",
    "Content-Type" : "application/json",
    "Authorization" : "Bearer " + bearer
    }
   
    email = event.get('email', '')
    name = event.get('name', '')

    userInfo = {
        "name": {
            "formatted": name
        },
        "emails": [
            {
            "value": email
            }
        ],
    }
    json_data = json.dumps(userInfo)

    response = requests.post ("https://scim.quip.com/2/Users", headers = api_creds, data=json_data)
    return {
        'statusCode': 200,
        'body': response
    }
