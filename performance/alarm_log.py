#
# Copyright 2017 FUJITSU LIMITED
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied. See the License for the specific language governing permissions and limitations under
# the License.
#

"""
This program is used to measure the required time to trigger alarms based on logs.
The program created specifies alarm definition via Metric API and sends specified log entries that trigger
the previously created alarm definitions, then starts searching for alarms form the metric API.
The program measures the time it takes between sending the metric entry until the appearance of alarms.
"""

import argparse
import httplib
import re
import time
import simplejson
import sys
import yaml
from monascaclient import client
from urlparse import urlparse
import TokenHandler
from write_logs import create_file, write_line_to_file


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-keystone_url', action="store", dest='keystone_url')
    parser.add_argument('-log_api_url', action="store", dest='log_api_url')
    parser.add_argument('-metric_api_url', action="store", dest='metric_api_url')
    parser.add_argument('-tenant_name', action="store", dest='tenant_name')
    parser.add_argument('-tenant_password', action="store", dest='tenant_password')
    parser.add_argument('-tenant_project', action="store", dest='tenant_project')
    parser.add_argument('-alarm_definition_name', action="store", dest='alarm_definition_name')
    parser.add_argument('-alarms_per_alarm_definition', action="store", dest='alarms_per_alarm_definition', type=int)
    parser.add_argument('-number_of_alarm_definition', action="store", dest='number_of_alarm_definition', type=int)
    return parser.parse_args()

TEST_NAME = 'alarm_log'

if len(sys.argv) <= 1:
    BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
    TEST_CONF = yaml.load(file('test_configuration.yaml'))
    KEYSTONE_URL = BASIC_CONF['url']['keystone']
    METRIC_API_URL = BASIC_CONF['url']['metrics_api']
    URL_BULK_LOG_API = BASIC_CONF['url']['log_api_url'] + '/v3.0/logs'
    ALARM_DEFINITION_NAME = TEST_CONF[TEST_NAME]['alarm_definition_name']
    LOGS_PER_ALARM_DEFINITION = TEST_CONF[TEST_NAME]['alarms_per_alarm_definition']
    NUMBER_OF_ALARM_DEFINITION = TEST_CONF[TEST_NAME]['number_of_alarm_definition']
    USER_CREDENTIAL = {"name": BASIC_CONF['users']['tenant_name'],
                       "password": BASIC_CONF['users']['tenant_password'],
                       "project": BASIC_CONF['users']['tenant_project']}
else:
    program_argument = create_program_argument_parser()
    KEYSTONE_URL = program_argument.keystone_url
    METRIC_API_URL = program_argument.metric_api_url
    URL_BULK_LOG_API = program_argument.log_api_url + '/v3.0/logs'
    ALARM_DEFINITION_NAME = program_argument.alarm_definition_name
    LOGS_PER_ALARM_DEFINITION = program_argument.alarms_per_alarm_definition
    NUMBER_OF_ALARM_DEFINITION = program_argument.number_of_alarm_definition
    USER_CREDENTIAL = {"name": program_argument.tenant_name,
                       "password": program_argument.tenant_password,
                       "project": program_argument.tenant_project}

TIMEOUT = 300
token_handler = TokenHandler.TokenHandler(USER_CREDENTIAL['name'],
                                          USER_CREDENTIAL['password'],
                                          USER_CREDENTIAL['project'],
                                          KEYSTONE_URL)
headers_post = {"Content-type": "application/json"}
metric_dimension = 'service'


def clear_alarm_definition(monasca_client):
    """ Delete all alarm definition that have in name pattern specified in ALARM_DEFINITION_NAME filed"""
    pattern = re.compile(ALARM_DEFINITION_NAME + '[0-9]+')

    for alarm_definition in monasca_client.alarm_definitions.list():
        try:
            if pattern.match(alarm_definition['name']):
                monasca_client.alarm_definitions.delete(alarm_id=alarm_definition['id'])
        except Exception as e:
            print('Failed to delete alarm definition ERROR:')
            print e


def create_alarm_definition(monasca_client, name, alarm_def_count):
    try:
        resp = monasca_client.alarm_definitions.create(
            name=name + str(alarm_def_count),
            expression='count(log.error{path=/var/log/systemTest,hostname=systemtest,component=systemtest,'
                       'count=' + str(alarm_def_count) + '}) > 0',
            match_by=[metric_dimension],

        )
        print('Created Alarm Definition NAME: {} ID: {}'.format(resp['name'], resp['id']))
        return resp['id']
    except Exception as e:
        print('Failed to create alarm definition ERROR')
        print e

    return None


def send_logs(token, alarm_def_count):
    """send log to log api, this log api should trigger alarm definition"""
    url = urlparse(URL_BULK_LOG_API)
    conn = httplib.HTTPConnection(url.netloc)
    log_list = []
    headers_post['X-Auth-Token'] = token
    for i in range(LOGS_PER_ALARM_DEFINITION):
        log_list.append({'message': 'ERROR tmp', 'dimensions':
                                     {'service': 'systemTest' + str(i), 'path': '/var/log/systemTest',
                                      'hostname': 'systemtest', 'component': 'systemtest', 'count': str(alarm_def_count)}})

    body = simplejson.dumps({'logs': log_list})
    conn.request("POST", url.path, body, headers_post)
    res = conn.getresponse()
    if res.status is not 204:
        print "Failed to send logs ERROR: {}".format(res.read())
        return 0

    return LOGS_PER_ALARM_DEFINITION


def wait_for_all_alarms(alarm_def_id_list, mon_client, number_of_expected_alarms):
    """this program check till all alarm will be created """
    print('Waiting for alarms to be created')
    check_start_time = time.time()
    alarm_count = 0
    while alarm_count < number_of_expected_alarms:
        alarm_count = 0
        for id in alarm_def_id_list:
            num = len(mon_client.alarms.list(alarm_definition_id=id))
            alarm_count += num

        if check_start_time + TIMEOUT < time.time():
            print "TIMEOUT. Found only {} alarms expect {}".format(alarm_count, number_of_expected_alarms)
            break

    return alarm_count


def perform_aol_test():
    token = token_handler.get_valid_token()
    alarm_def_id_list = []
    total_log_send = 0
    mon_client = client.Client('2_0', METRIC_API_URL, token=token)
    clear_alarm_definition(mon_client)

    for alarm_def_count in range(NUMBER_OF_ALARM_DEFINITION):
        alarm_def_id = create_alarm_definition(mon_client, ALARM_DEFINITION_NAME, alarm_def_count)
        if alarm_def_id is not None:
            alarm_def_id_list.append(alarm_def_id)

    for alarm_def_count in range(len(alarm_def_id_list)):
        total_log_send += send_logs(token, alarm_def_count)

    start_time = time.time()
    alarm_found = wait_for_all_alarms(alarm_def_id_list, mon_client, total_log_send)
    write_result("Found {} alarms in {}s".format(alarm_found, str(time.time() - start_time)))


def write_result(result_string):
    print result_string
    lg_file = create_file(TEST_NAME)
    write_line_to_file(lg_file, result_string)
    lg_file.close()

if __name__ == "__main__":
    perform_aol_test()
