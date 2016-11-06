#!/usr/bin/python
from ediplug import smartplug
import signal
import time
import sys
import argparse
import requests


def t(message):
    sys.stdout.write(message)
    sys.stdout.write('\n')
    sys.stdout.flush()


def e(message):
    sys.stderr.write(message)
    sys.stderr.write('\n')
    sys.stderr.flush()


class Killer(object):
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True


class Pushover(object):
    def __init__(self, user_token, app_token):
        self.user_token = user_token
        self.app_token = app_token

    def push(self, title, message):
        post_data = {'token': self.app_token, 'user': self.user_token, 'message': message, 'title': title}
        post_response = requests.post(url='https://api.pushover.net/1/messages.json', data=post_data)
        if post_response.status_code == requests.codes.ok:
            t('Pushed OK: "%s", "%s"' % (title, message))
        else:
            e('Failed to push a notification: Status-code=%s' % post_response.status_code)


class Miele(object):
    IDLE_CURRENT = 0.06
    TUMBLE_DRY_FLOOR_CURRENT = 1.5
    TUMBLE_DRY_CEIL_CURRENT = 5.0
    IDLE_POLL_INTERVAL = 60
    ON_POLL_INTERVAL = 2
    TUMBLE_DRY_DURATION = 600


class IdleState(object):
    def __init__(self, pusher):
        self.pusher = pusher
        self.started = time.time()

    def handle(self, current):
        if current > Miele.IDLE_CURRENT:
            return MachineOnState(self.pusher)

        return self

    def sleep(self):
        time.sleep(Miele.IDLE_POLL_INTERVAL)
        return self


class MachineOnState(object):
    def __init__(self, pusher):
        self.pusher = pusher
        self.started = time.time()
        self.tumble_dry_guard = 0

    def handle(self, current):
        if current <= Miele.IDLE_CURRENT:
            self.tumble_dry_guard = 0
            return IdleState(self.pusher)
        elif Miele.TUMBLE_DRY_FLOOR_CURRENT <= current <= Miele.TUMBLE_DRY_CEIL_CURRENT:
            """
            To avoid accidental triggering when the water heater is switched on (~9A) or off
            and the current is measured just when it transits through 1.5..5A.
            """
            self.tumble_dry_guard += 1
            if self.tumble_dry_guard > 1:
                return TumbleDryState(self.pusher)
            else:
                return self
        else:
            self.tumble_dry_guard = 0
            return self

    def sleep(self):
        time.sleep(Miele.ON_POLL_INTERVAL)
        return self


class TumbleDryState(object):
    def __init__(self, pusher):
        self.pusher = pusher
        self.started = time.time()

    def handle(self, current):
        if current <= Miele.IDLE_CURRENT:
            pusher.push('Home', 'The washing machine has powered down.')
            return IdleState(self.pusher)
        elif Miele.TUMBLE_DRY_FLOOR_CURRENT <= current <= Miele.TUMBLE_DRY_CEIL_CURRENT:
            self.started = time.time()

        return self

    def sleep(self):
        if (self.started + Miele.TUMBLE_DRY_DURATION) <= time.time():
            pusher.push('Home', 'The washing machine has finished.')
            return MachineOnState(self.pusher)

        time.sleep(Miele.ON_POLL_INTERVAL)
        return self


class Watcher(object):
    def __init__(self, killer, pusher, plug):
        self.killer = killer
        self.pusher = pusher
        self.plug = plug
        self.state = IdleState(pusher)

    def transit(self, new_state):
        if new_state != self.state:
            t('%s -> %s' % (self.state.__class__.__name__, new_state.__class__.__name__))
            self.state = new_state
            return True

        return False

    def spin(self):
        t('None -> %s' % self.state.__class__.__name__)
        while not killer.kill_now:
            current = float(self.plug.current)

            if arguments.verbose:
                t('%s %s' % (time.time(), current))

            if not self.transit(self.state.handle(current)):
                self.transit(self.state.sleep())

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='The washing machine end-of-cycle monitor')

    parser.add_argument('-a', action='store', dest='plug_ip', help='Edimax smart plug IP address', required=True)
    parser.add_argument('-u', action='store', dest='plug_user', help='Edimax smart plug user name', required=True)
    parser.add_argument('-p', action='store', dest='plug_password', help='Edimax smart plug password', required=True)
    parser.add_argument('-at', action='store', dest='app_token', help='Pushover application token', required=True)
    parser.add_argument('-ut', action='store', dest='user_token', help='Pushover user token', required=True)
    parser.add_argument('--verbose', action='store_true', dest='verbose', help='Enable verbose tracing', default=False)

    arguments = parser.parse_args()

    killer = Killer()
    pusher = Pushover(arguments.user_token, arguments.app_token)
    plug = smartplug.SmartPlug(arguments.plug_ip, (arguments.plug_user, arguments.plug_password))

    watcher = Watcher(killer, pusher, plug)

    t('Startup')

    watcher.spin()

    t('Shutdown')
