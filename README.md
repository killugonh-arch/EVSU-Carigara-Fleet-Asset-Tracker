# EVSU Fleet and Asset Tracker

This is our project for our subject. It's a system for managing the vehicles and assets of Eastern Visayas State University (EVSU). Like you can track maintenance, request to use a vehicle, log mileage and stuff like that.

We deployed it online using Render so you can access it through the browser.

---

## What it can do

depending on your role in the system you can do different things

Manager
- add, edit, delete assets and vehicles
- approve or reject maintenance requests
- approve mileage logs
- manage user accounts
- see all the history and financial info

Staff / Driver
- request to use a vehicle
- log mileage
- request for new assets

Auditor
- can only view everything (cannot edit)
- can see financial data

Maintenance Technician
- view maintenance work orders assigned to them
- accept, hold, or complete maintenance tasks
- get notified for new maintenance requests

---

## Tech used

- Python 3.11.9
- Django 4.2
- PostgreSQL (for the live database on Render)
- SQLite (only for local/testing)
- Cloudinary (for storing profile pictures)
- Gunicorn (the server that runs the app)
- WhiteNoise (for static files like css)
- django-axes (locks account if too many wrong passwords)
- Django REST Framework (for the API)

---

## How to run it locally

> you need Python installed first, we used Python 3.11.9

step 1 - clone the repo
```
git clone https://github.com/your-username/evsu-fleet-tracker.git
cd evsu-fleet-tracker
```


step 2 - make a virtual environment
```
python -m venv venv
```

then activate it:

if you're on Windows:
```
venv\Scripts\activate
```

if you're on Mac or Linux:
```
source venv/bin/activate
```


step 3 - install the requirements
```
cd app
pip install -r requirements.txt
```


step 4 - setup the database
```
python manage.py migrate
```


step 5 - create an admin account
```
python manage.py createsuperuser
```


step 6 - run the server
```
python manage.py runserver
```


step 7 - open in browser
```
http://127.0.0.1:8000
```

> note: when running locally you dont need to set any environment variables. it will just use SQLite and save uploaded files in the media folder automatically.

---



## How we deployed it (Render)

1. push the code to GitHub first
2. go to [render.com](https://render.com) and create a new Web Service
3. connect your GitHub repo
4. set the build command to `pip install -r app/requirements.txt`
5. create a PostgreSQL database on Render (New → PostgreSQL) and copy the database URL
6. add all the environment variables (see below)
7. deploy


the app uses a Procfile to tell Render what to do when it starts:
```
web: cd app && python manage.py axes_reset && python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py createsuperuser --noinput --username admin --email admin@evsu.edu.ph || true && gunicorn fleet_tracker.wsgi
```

it basically runs the migrations, collects static files, creates the admin account, then starts the server every deploy.

---


## Environment Variables

these are the values you need to set in Render under Environment. dont put these in the code or commit them to github.

| Variable | What it's for |
|---|---|
| `SECRET_KEY` | secret key for Django, make it a long random string |
| `DEBUG` | set this to `False` when live |
| `ALLOWED_HOSTS` | your render domain like `your-app.onrender.com` |
| `DATABASE_URL` | the postgresql link from Render, it gives this to you automatically |
| `CLOUDINARY_CLOUD_NAME` | from your Cloudinary dashboard |
| `CLOUDINARY_API_KEY` | from your Cloudinary dashboard |
| `CLOUDINARY_API_SECRET` | from your Cloudinary dashboard |
| `DJANGO_SUPERUSER_PASSWORD` | Admin@1234 |


how to get a SECRET_KEY - just run this in terminal:
```
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```


how to get Cloudinary credentials - sign up at cloudinary.com then go to your dashboard, the cloud name, api key and api secret are right there.

---

## Project structure

```
evsu_fleet_updated/
├── Procfile               <- tells Render how to start the app
├── runtime.txt            <- python version
└── app/
    ├── manage.py
    ├── requirements.txt
    ├── logs/
    │   └── audit.log      <- security logs saved here
    ├── fleet_tracker/     <- main settings and urls
    │   ├── settings.py
    │   └── urls.py
    ├── accounts/          <- login, register, users
    │   ├── models.py
    │   ├── views.py
    │   └── forms.py
    ├── assets/            <- assets, maintenance, mileage, requests
    │   ├── models.py
    │   ├── views.py
    │   └── api_views.py
    └── templates/         <- html files
```

---

## Security stuff

we added some security features:

- django-axes - if someone enters the wrong password 5 times the account gets locked for 15 minutes
- rate limiting - the API limits requests so it cant be abused (30/min for guests, 200/min for logged in users)
- audit log - every login, logout, create, update, delete action is saved in `logs/audit.log` with the username and time
- HTTPS and secure cookies - automatically turned on when DEBUG is False (in production)

---

## Notes

- this was made as a school project for EVSU
- if you run it locally it uses SQLite so you dont need to setup PostgreSQL
- the Cloudinary integration only activates if you set the CLOUDINARY_CLOUD_NAME environment variable, otherwise it just saves files locally
