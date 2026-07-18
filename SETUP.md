## Create a Custom uv Python Environment
* uv and intellij get confused, even pyharm,
* Download and run uv to build your system
* Then use uv to install into $HOME/.venv
* 
* python --version
* python -m venv C:\Users\xxxx\.venv-cal
* .\.venv-cal\Scripts\Activate.ps1 
* Settings-python-interpreter-> set to above for pycharm
* Project settings-> SDK (UV) and env (Intellij)
* and then Project settings-> module python (intellij)
* go to requirements.txt and install
* PowerShell scripts is disabled.

# Activate the environment
* in dos
   source C:\Users\xxxx\.venv-cal\Scripts\activate
or in intellij, close the terminal and reopen
```

in Intellij add the above directory available for all projects


# for Oauth Token (Developer !, not User)

* Usage Limits and ThresholdsWhile the API itself is free of charge, Google enforces strict rate limits to maintain system health and prevent service abuse:Daily Project Limit: Your Google Cloud project can make up to 1,000,000 requests per day before any charges or restrictions apply.Per-Minute Project Limit: The application can make up to 10,000 requests per minute globally across all users.Per-User Limit: A single user utilizing your app can make up to 600 requests per minute.

* https://console.cloud.google.com
* Step 1: Create a Google Cloud ProjectOpen the Google Cloud Console.
* * Click the project dropdown in the top left and select New Project.Name your project and click Create.
* Step 2: Enable the Google Calendar API In the Cloud Console, search for Google Calendar API in the top search bar.Select it from the marketplace results and click Enable.
* Step 3: Configure the OAuth Consent Screen Before getting credentials, you must define the user consent screen.Navigate to Menu > APIs & Services > OAuth consent screen.Select External (or Internal if you have a Google Workspace account) and click Create.Fill out the required App Name, User support email, and Developer contact information.Click Save and Continue through the Scopes and Test Users tabs. (Note: If your app is in "Testing" mode, add your own email address as a Test User).
* Step 4: Create OAuth 2.0 Credentials Go to the Credentials tab on the left sidebar.Click + Create Credentials and select OAuth client ID.Choose your Application type:Select Desktop app if you are writing a script (Python, Node.js) that runs locally.Select Web application if you are hosting a public website.Click Create.Click Download JSON on the confirmation screen. Rename this file to credentials.json and save it to your development folder.Step 5: Generate the Final Access Token (token.json)An API "token" consists of a short-lived Access Token and a long-lived Refresh Token. You can generate this using code or Google's testing playground.Option A: Automatically via Code (Recommended)If you run an official Google API Quickstart script (like the Google Calendar Python Quickstart or Node.js Quickstart), the script will read your credentials.json file and automatically open a web browser.The browser will prompt you to log into your Google Account.Once you grant permission, the script automatically saves a new file called token.json in your project folder.
* Step 5: add the user to the test user application account
* Step 6 : run quickstart to get your token
* 
* If refresh fails, go to step 4 to get a new credential and add it to token.json

* Don't Start foundation, then skip this step, so you don't creat a billign arrangement
* menu : go to iam and admin: create a project
* Explore and enable API's
* Calendar API :
*  Enable(not it says at the top CalendarMirror-1)
* Gmail API :
*  Enable
* Menu -> apis + services -> enable apis
* select calendar API
* Support email must be michael@icdelta.ca
* add scope Gmail API _ gmail.modify
* Desktop Application

* menu-> API_Settings -> Outh Consent
*  Select branding on the right
* add authorizes domain icdelta.ca
*  Select audiance on the right
* should be internal
* Select Client on the right
* Add secret, download when created
* Select the customer id and add to code

* takes some time to build :
* https://console.cloud.google.com/home/dashboard?authuser=3&project=calendarmirror-1
* this project is not linked to a billign account
* AUdiace = internal = only in the domain