<h1 align="center">Check If Users Are Added Directly To Applications In Okta</h1> 

<p>Okta was managed by RBAC or role-based access control so all our application provisioning was driven by access groups that were supported in Github. Because of this we needed to know if there were users that were added by other means so this script will scrape all our applications and print out if the users were added outside of a group<p>


<h2 align="center">Steps To Use</h2>

1. Generate A Read-Only API Key In Okta

2. Put Key in the Sensitive.py File 

3. Run Script 