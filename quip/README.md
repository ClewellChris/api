<h1 align="center">Quip</h1> 

<p>Quip did not offer a buit in SCIM integration with Okta but we still wanted to explore how we could automate User Provisioning and Deprovisiong.  We settled on using Okta Workflows in combination with AWS Lambda to achieve this<p>

<h2 align="center">Steps Taken To Achieve Provisioning</h2>

1. Build out Okta Workflows
  - Trigger off of a User being added to the Quip app in Okta 
  - Read the User in Okta
  - Confirm application ID matches 
  - Compose a message and send to Slack to alert IT Admins the process has started 
  - Construct Object with the Email and User's Name
  - Invoke Lambda function 
  - Send results to Slack to confirm success or failure 

![Okta_Flow1](/quip/images/okta_workflow1.png)
![Okta_Flow2](/quip/images/okta_workflow2.png)

2. Build out Lambda Function
  - Create IAM User to Drive Lambda 
  - Add API Token to Secrets Manager 
  - Create IAM Policy for Secrets Manager and Lambda
    - secrets_manager.json 
  - Build out Python script to provision users using Quip API Endpoint
    - provisioning_lambda_function.py

<h2 align="center">Steps Taken To Achieve Deprovisioning</h2>

1. Build out Okta Workflows
  - Trigger off of a User being removed from the Quip app in Okta 
  - Read the User in Okta
  - Confirm application ID matches 
  - Compose a message and send to Slack to alert IT Admins the process has started 
  - Construct Object with the Email
  - Invoke Lambda function 
  - Send results to Slack to confirm success or failure 

![Okta_Flow1](/quip/images/okta_workflow_3.png)
![Okta_Flow2](/quip/images/okta_workflow_4.png)

2. Build out Lambda Function
  - Create IAM User to Drive Lambda 
  - Add API Token to Secrets Manager 
  - Create IAM Policy for Secrets Manager and Lambda
    - secrets_manager.json 
  - Build out Python script to provision users using Quip API Endpoint
    - deprovisioning_lambda_function.py