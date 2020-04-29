# Konzum Watchdog

In this time of scarce delivery times for groceries from Konzum Klik, this script is not the script we need, but the script we deserve. Or something like that.

## Prerequisites
1. Install [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/)
2. Install [pyenv](https://github.com/pyenv/pyenv#installation)
3. Register on [Konzum Klik](https://www.konzum.hr/web/sign_up)
4. Register on [Sendgrid](https://sendgrid.com/pricing/) - need to verify a sending domain or setup a single sender address
5. Generate a [Sendgrid API key](https://app.sendgrid.com/settings/api_keys)

## Setup
1. `git clone`
2. `cd konzum_watchdog`
3. `pyenv local`
4. `mkvirtualenv konzum_watchdog`
5. `cp env.sh.example env.sh`
6. `vim env.sh  # input your own data`
7. `pip install -r requirements.txt`

## Run
`source env.sh && python main.py`
