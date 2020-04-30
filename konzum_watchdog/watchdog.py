import logging
from random import randint
import sys
import time
from time import sleep

import requests
from bs4 import BeautifulSoup
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Email, To, Content, Mail

from .settings import (
    KONZUM_KLIK_USERNAME,
    KONZUM_KLIK_PASSWORD,
    SENDGRID_API_KEY,
    NOTIFY_TO_ADDRESS,
    NOTIFY_FROM_ADDRESS,
)

logging.basicConfig(
    level=logging.INFO, 
    format='[%(asctime)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def active_sleep(seconds):
    wakeup_time = time.time() + seconds

    while True:
        sleep(1)
        if time.time() > wakeup_time:
            return


class PageParser:
    TIMEOUT = 60

    BASE_URL = 'https://www.konzum.hr/web'
    LOGIN_URL = f'{BASE_URL}/sign_in'
    TARGET_URL = f'{BASE_URL}/raspolozivi-termini'

    HEADERS = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:32.0) Gecko/20100101 Firefox/32.0',
    }

    def __init__(self):
        self._session = requests.Session()
        self._logged_in = False

    def try_get(self, url, max_attempts=3, wait=10):
        response_code = None

        while response_code != 200 and max_attempts > 0:
            try:
                response = self._session.get(url, headers=self.HEADERS, timeout=self.TIMEOUT)
                response_code = response.status_code

                if response_code == 200:
                    return response
            except Exception:
                pass

            max_attempts -= 1
            active_sleep(wait)

    def login(self):
        response = self.try_get(self.LOGIN_URL)

        if response is not None and response.status_code == 200:
            bs = BeautifulSoup(response.text, 'lxml')
            form_result = bs.select('#new_spree_user')

            form = None
            if form_result:
                form = form_result[0]

            if form is not None:
                utf8 = form.select('input[name=utf8]')[0]
                auth_token = form.select('input[name=authenticity_token]')[0]

                post_data = {
                    'spree_user[email]': KONZUM_KLIK_USERNAME,
                    'spree_user[password]': KONZUM_KLIK_PASSWORD,
                    'utf8': utf8.attrs['value'],
                    'authenticity_token': auth_token.attrs['value'],
                }

                response = self._session.post(
                    PageParser.LOGIN_URL,
                    post_data,
                    headers=self.HEADERS,
                    timeout=self.TIMEOUT,
                )

                if response.status_code == 200:
                    self._logged_in = True

    def check_delivery_terms_exist(self):
        response = self.try_get(self.TARGET_URL)

        if response is not None and response.status_code == 200:
            bs = BeautifulSoup(response.text, 'lxml')

            delivery_terms_result = bs.select(
                'section.section-availability-calendar div[data-tab-type=delivery] div.delivery-terms'
            )

            if delivery_terms_result:
                no_available_terms = delivery_terms_result[0].find(string='Trenutno nema dostupnih termina')
                available_terms = delivery_terms_result[0].select('div.availability-calendar')

                if no_available_terms is not None:
                    return KonzumWatchdog.State.UNAVAILABLE
                elif available_terms is not None:
                    return KonzumWatchdog.State.AVAILABLE

        return KonzumWatchdog.State.ERROR


    def available_terms_exist(self):
        if not self._logged_in:
            self.login()

        terms_exist = self.check_delivery_terms_exist()

        return terms_exist


class KonzumWatchdog:

    class State:
        AVAILABLE = 'available'
        UNAVAILABLE = 'unavailable'
        ERROR = 'error'

    def __init__(self):
        logging.info('Initializing KonzumWatchdog...')
        self._page_parser = PageParser()

        self._previous_state = None
        self._current_state = self._page_parser.available_terms_exist()

        logging.info('Watch started, initial state: %s', self._current_state)

        if self._current_state == self.State.AVAILABLE:
            self._notify()

    def _notify(self):
        Notifier.send_email(to_address=NOTIFY_TO_ADDRESS)

    @staticmethod
    def random_sleep(base=300):
        offset = base // 5
        sleep_time = base + randint(-offset, offset)
        logging.info('Sleeping for %s seconds', sleep_time)
        active_sleep(sleep_time)

    def run(self):
        while True:
            self.random_sleep(300)

            state_changed = False
            new_state = self._page_parser.available_terms_exist()

            try:
                if new_state != self._current_state:
                    self._previous_state = self._current_state
                    self._current_state = new_state
                    state_changed = True

            except (KeyboardInterrupt, Exception):
                self._current_state = self._previous_state

            if state_changed:
                if self._current_state == self.State.AVAILABLE:
                    self._notify()
                logging.info('State change: %s -> %s', self._previous_state, self._current_state)

            else:
                logging.info('No change: %s', self._current_state)


class Notifier:

    @classmethod
    def send_email(cls, to_address):
        from_email = Email(NOTIFY_FROM_ADDRESS)
        to_email = To(to_address)
        subject = 'Termin za dostavu dostupan!'
        content = Content(
            'text/html',
            'Upravo su se pojavili novi dostupni termini za dostavu!\n'
            f'<a href={PageParser.TARGET_URL} target="_blank">Provjeri ih ovdje</a>'
        )
        mail = Mail(from_email, to_email, subject, content)

        sendgrid_client = SendGridAPIClient(api_key=SENDGRID_API_KEY)
        response = sendgrid_client.client.mail.send.post(request_body=mail.get())

        if response.status_code == 202:
            logger.info('%s notified', to_address)
        else:
            logger.error('Failed to notify %s, error code %s', to_address, response.status_code)
