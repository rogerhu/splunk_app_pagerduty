#!/usr/bin/env python
"""PagerDuty Saved Search Alert Script for Splunk.

Derived from @samuelks' Python Pagerduty Module
https://github.com/samuel/python-pagerduty
"""

__author__ = 'Greg Albrecht <gba@splunk.com>'
__copyright__ = 'Copyright 2012 Splunk, Inc.'
__license__ = 'Apache License 2.0'


import ConfigParser
import csv
import gzip
try:
    import json
except ImportError:
    import simplejson as json
import os
import urllib2


EVENTS_URL = 'events.pagerduty.com/generic/2010-04-15/create_event.json'


class PagerDutyException(Exception):
    """Exceptions for PagerDuty objects and methods."""
    def __init__(self, status, message, errors):
        super(PagerDutyException, self).__init__(message)
        self.msg = message
        self.status = status
        self.errors = errors

    def __repr__(self):
        return "%s(%r, %r, %r)" % (
            self.__class__.__name__, self.status, self.msg, self.errors)

    def __str__(self):
        txt = "%s: %s" % (self.status, self.msg)
        if self.errors:
            txt += "\n" + "\n".join("* %s" % x for x in self.errors)
        return txt


class PagerDuty(object):
    """Class for triggering PagerDuty Incidents."""
    def __init__(self, service_key, https=True, timeout=15):
        self.service_key = service_key
        self.api_endpoint = '://'.join([('http', 'https')[https], EVENTS_URL])
        self.timeout = timeout

    def trigger(self, description, incident_key=None, details=None):
        """Triggers PagerDuty Incident"""
        return self._request(
            'trigger', description=description, incident_key=incident_key,
            details=details)

    def _request(self, event_type, **kwargs):
        """Handle PagerDuty API calls."""
        event = {'service_key': self.service_key, 'event_type': event_type}
        for kwk, kwv in kwargs.items():
            if kwv is not None:
                event[kwk] = kwv
        encoded_event = json.dumps(event)
        try:
            res = urllib2.urlopen(
                self.api_endpoint, encoded_event, self.timeout)
        except urllib2.HTTPError, exc:
            if exc.code != 400:
                raise
            res = exc

        result = json.loads(res.read())

        if result['status'] != 'success':
            raise PagerDutyException(
                result['status'], result['message'], result['errors'])

        return result.get('incident_key')


def extract_events(events_file):
    """Extracts event data from Splunk CSV file.

    @param events_file: Path to GZIP compressed CSV file.
    @type events_file: str

    @return: Events from CSV file.
    @rtype: list
    """
    events = []
    if events_file is not None and os.path.exists(events_file):
        events = csv.DictReader(gzip.open(events_file))
    return events


def trigger_pagerduty(description, details, pagerduty_api_key,
                      incident_key=None):
    """Triggers PagerDuty Incident with given params.

    @param description:
    @param details:
    @param pagerduty_api_key: PagerDuty Service Integration API Key.
    @incident_key: (default=None)

    @type description: str
    @type details: str
    @type pagerduty_api_key: str
    @type incident_key: str

    @return: pagerduty.trigger object.
    @rtype: pagerduty.trigger object.
    """
    pagerduty = PagerDuty(pagerduty_api_key)
    return pagerduty.trigger(description, incident_key, details)


def get_pagerduty_api_key(config_file):
    """Extracts PagerDuty Service Integration API Key from Splunk Config.

    @param config_file: Full path to file containing Pagerduty API Credentials.
    @type config_file: str
    @return: PagerDuty Service Integration API Key.
    @rtype: str
    """
    config = ConfigParser.ConfigParser()
    config.read(config_file)
    return config.get('pagerduty_api', 'pagerduty_api_key')


def main():
    """main, duh?"""
    # We'll serialize this dict into JSON -> PagerDuty Details.
    details = {'env': {}, 'events': []}

    config_file = os.path.join(
        os.environ['SPLUNK_HOME'], 'etc', 'apps', 'splunk_app_pagerduty',
        'local', 'pagerduty.conf')

    pagerduty_api_key = get_pagerduty_api_key(config_file)

    for k in os.environ:
        if 'SPLUNK_ARG' in k:
            details['env'][k] = os.environ.get(k)

    events = extract_events(os.environ.get('SPLUNK_ARG_8'))
    for event in events:
        details['events'].append(event)

    # This description could be any field in your event.
    if details['events'] and '_raw' in details['events'][0]:
        default_description = details['events'][0]['_raw']
    else:
        default_description = ''

    description = os.environ.get('SPLUNK_ARG_5', default_description)
    trigger_pagerduty(description, details, pagerduty_api_key)


if __name__ == '__main__':
    main()
