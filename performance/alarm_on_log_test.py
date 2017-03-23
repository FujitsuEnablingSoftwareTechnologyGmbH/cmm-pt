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
import argparse
import datetime
import httplib
import MySQLdb
import simplejson
import threading
import time
import sys
import yaml
from operator import sub
from monascaclient import client
from urlparse import urlparse
import db_saver
import TokenHandler
from write_logs import create_file, write_line_to_file

ALARM_PATH = '/alarms'
BULK_API_PATH = '/v3.0/logs'
TEST_NAME = 'alarm_on_log'

ALARM_TRIGGER_TIMEOUT = 120
RESPONSE_OK_STATUS = 200


class AlarmDefinition:

    def __init__(self, token_handler, alarm_def_conf, metric_api_url):
        self.token_handler = token_handler
        self.alarm_def_conf = alarm_def_conf
        self.monasca_client = client.Client('2_0', metric_api_url, token=self.token_handler.get_valid_token())
        self.alarm_def_list = []
        self.clear_alarms()
        for alarm_group in self.alarm_def_conf:
            severity = alarm_group['severity']
            num_of_alarms = alarm_group['alarms_per_alarm_definition']
            for count in range(alarm_group['number_of_alarm_def']):
                self.create_alarm_definition('st_aol_test_{}_{}'.format(severity, count), severity, num_of_alarms)

    def clear_alarms(self):
        for alarm_def in self.monasca_client.alarm_definitions.list():
            if 'st_aol_test_' in alarm_def['name']:
                self.monasca_client.alarm_definitions.delete(alarm_id=alarm_def['id'])

    def create_alarm_definition(self, alarm_def_name, severity, num_of_alarms):
        try:
            alarm_dimension = 'hostname=systemtest,service={}'.format(alarm_def_name)
            resp = self.monasca_client.alarm_definitions.create(
                name=alarm_def_name,
                expression='count(log.{}{{{}}}) > 0'.format(severity.lower(), alarm_dimension),
                match_by=['count'],
            )

            print('Created Alarm Definition NAME: {} ID: {}'.format(resp['name'], resp['id']))
            alarm_dimension_dict = {'hostname': 'systemtest', 'service': alarm_def_name}
            self.alarm_def_list.append({'id': resp['id'], 'severity': severity, 'dimension': alarm_dimension_dict,
                                        'name': alarm_def_name, 'num_of_alarms': num_of_alarms})
        except Exception as e:
            print('Failed to create alarm definition ERROR')
            print e


class Alarm:
    def __init__(self, alarm_id, token_handler, metric_api_url):
        self.id = alarm_id
        self.metric_alarm_url = urlparse(metric_api_url + ALARM_PATH)
        self.token_handler = token_handler
        self.alarm_occur_time_list, self.alarm_name = self.__get_alarm_occur_time_and_name()

    def __get_alarm_occur_time_and_name(self):
        header = {'X-Auth-Token': self.token_handler.get_valid_token(), 'Content-Type': 'application/json'}
        metric_api_conn = httplib.HTTPConnection(self.metric_alarm_url.netloc)
        metric_api_conn.request("GET",
                                "{}/{}/state-history".format(self.metric_alarm_url.path, self.id),
                                headers=header)

        res = metric_api_conn.getresponse()
        if res.status is not RESPONSE_OK_STATUS:
            print ('FAILED TO RETRIEVE STATE HISTORY')
            return False
        alarms_state_history = simplejson.loads(res.read())
        alarm_occur_timestamp = [alarm_state_history['timestamp'] for alarm_state_history in
                                 alarms_state_history['elements']
                                 if alarm_state_history['new_state'] == 'ALARM']
        alarm_occur_time_list = [datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                                 for timestamp in alarm_occur_timestamp]
        alarm_name = alarms_state_history['elements'][0]['metrics'][0]['dimensions']['service']
        return alarm_occur_time_list, alarm_name

    def get_alarm_latency(self, log_send_time_list):
        return map(sub, self.alarm_occur_time_list, log_send_time_list)


class AOLTest(threading.Thread):
    def __init__(self,  keyston_url, tenant_username, tenant_password, tenant_project, metric_api_url, log_api_url,
                 alarm_def_create_conf, runtime, mariadb_status, mariadb_username=None, mariadb_password=None,
                 mariadb_hostname=None, mariadb_database=None, testCaseID=1):
        threading.Thread.__init__(self)
        self.mariadb_status = mariadb_status
        self.token_handler = TokenHandler.TokenHandler(tenant_username,
                                                       tenant_password,
                                                       tenant_project,
                                                       keyston_url)
        self.log_api_url = urlparse(log_api_url + BULK_API_PATH)
        self.metric_api_url = metric_api_url
        self.metric_alarm_url = urlparse(metric_api_url + ALARM_PATH)
        self.log_send_time_list = []
        self.result_file = create_file(TEST_NAME)
        self.alarm_def = AlarmDefinition(self.token_handler, alarm_def_create_conf, metric_api_url)
        self.runtime = runtime
        if self.mariadb_status == 'enabled':
            self.mariadb_database = mariadb_database
            self.mariadb_username = mariadb_username
            self.mariadb_password = mariadb_password
            self.mariadb_hostname = mariadb_hostname
            if ((self.mariadb_hostname is not None) and
                (self.mariadb_username is not None) and
                    (self.mariadb_database is not None)):
                self.testCaseID = testCaseID
                db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                     self.mariadb_password, self.mariadb_database)
                self.testID = db_saver.save_test(db, testCaseID, TEST_NAME)
                number_of_alarm_def = 0
                total_number_of_alarms = 0
                for alarm_def_conf in self.alarm_def.alarm_def_conf:
                    number_of_alarm_def += alarm_def_conf['number_of_alarm_def']
                    total_number_of_alarms +=\
                        alarm_def_conf['number_of_alarm_def']*alarm_def_conf['alarms_per_alarm_definition']
                test_params = [['start_time', str(datetime.datetime.now().replace(microsecond=0))],
                               ['runtime', str(self.runtime)],
                               ['number_of_alarm_definitions', str(number_of_alarm_def)],
                               ['total_number_of_alarms', str(total_number_of_alarms)]]
                db_saver.save_test_params(db, self.testID, test_params)
                db.close()
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()

    def run(self):

        start_time = time.time()
        alarm_count = 0
        while self.runtime > time.time() - start_time:
            self.send_bulk()
            self.wait_util_all_alarm_are_triggered()
            alarm_count += 1
            while not self.check_if_alarms_status_is_undetermined():
                print "alarm still in alarm state"
                time.sleep(30)

            self.check_latency(alarm_count)
        self.save_result_to_db()

    def wait_util_all_alarm_are_triggered(self):
        start_time = time.time()
        header = {'X-Auth-Token': self.token_handler.get_valid_token(), 'Content-Type': 'application/json'}
        metric_api_conn = httplib.HTTPConnection(self.metric_alarm_url.netloc)
        while time.time() - start_time < ALARM_TRIGGER_TIMEOUT:
            metric_api_conn.request("GET", self.metric_alarm_url.path, headers=header)
            res = metric_api_conn.getresponse()
            if res.status is RESPONSE_OK_STATUS:
                alarms_info = simplejson.loads(res.read())
                for alarm_state in alarms_info['elements']:
                    if alarm_state['state'] != 'ALARM':
                        break
                    return
            else:
                print "Failed to receive query form metric API"
            res.close()
            time.sleep(5)

    def send_bulk(self):
        header = {'X-Auth-Token': self.token_handler.get_valid_token(), 'Content-Type': 'application/json'}
        log_list = []
        log_api_conn = httplib.HTTPConnection(self.log_api_url.netloc)
        for alarm_def in self.alarm_def.alarm_def_list:
            msg = alarm_def['severity'] + " AOL test"
            for i in range(alarm_def['num_of_alarms']):

                dimension = alarm_def['dimension'].copy()
                dimension.update({'count': str(i)})
                log_list.append({'message': msg, 'dimensions': dimension})
        body = simplejson.dumps({'logs': log_list})
        log_api_conn.request("POST", self.log_api_url.path, body, header)
        send_time = datetime.datetime.utcnow()
        res = log_api_conn.getresponse()
        if res.status is not 204:
            print ('FAILED TO SEND BULK')
        else:
            self.log_send_time_list.append(send_time)
            print "{} send logs".format(send_time.strftime('%H:%M:%S.%f'))
        res.close()
        log_api_conn.close()

    def check_if_alarms_status_is_undetermined(self):
        header = {'X-Auth-Token': self.token_handler.get_valid_token(), 'Content-Type': 'application/json'}
        metric_api_conn = httplib.HTTPConnection(self.metric_alarm_url.netloc)
        metric_api_conn.request("GET", self.metric_alarm_url.path, headers=header)
        res = metric_api_conn.getresponse()
        if res.status is not RESPONSE_OK_STATUS:
            print ('FAILED TO RETRIEVE ALARMS STATUS')
            return False
        alarms_info = simplejson.loads(res.read())
        for alarm_state in alarms_info['elements']:
            if alarm_state['state'] != 'UNDETERMINED':
                return False
        return True

    def save_result_to_db(self):
        alarm_list = self.create_all_alarm_instance()
        test_results = list()
        for alarm in alarm_list:
            print alarm.alarm_name
            for latency in alarm.get_alarm_latency(self.log_send_time_list):
                print latency.total_seconds()
                test_results.append(['latency',
                                     str(latency.total_seconds()), datetime.datetime.now().replace(microsecond=0)])
        db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                             self.mariadb_password, self.mariadb_database)
        db_saver.save_test_results(db, self.testID, test_results)
        db.close()

    def check_latency(self, alarm_count):
        alarm_list = self.create_all_alarm_instance()
        self.write_result_to_file(alarm_list, alarm_count)

    def write_result_to_file(self, alarm_list, alarm_count):
        if alarm_count is 1:
            for count, alarm in enumerate(alarm_list):
                header_line = '{},{}({})'.format(count, alarm.alarm_name, alarm.id)
                write_line_to_file(self.result_file, header_line)
        for count, alarm in enumerate(alarm_list):
            res_line = '{},{}'.format(count, (alarm.alarm_occur_time_list[alarm_count - 1] -
                                        self.log_send_time_list[alarm_count - 1]).total_seconds())
            write_line_to_file(self.result_file, res_line)

    def create_all_alarm_instance(self):
        alarms = []
        for alarm_id in self.get_alarms_id():
            alarms.append(Alarm(alarm_id, self.token_handler, self.metric_api_url))
        return alarms

    def get_alarms_id(self):
        header = {'X-Auth-Token': self.token_handler.get_valid_token(), 'Content-Type': 'application/json'}
        metric_api_conn = httplib.HTTPConnection(self.metric_alarm_url.netloc)
        metric_api_conn.request("GET", self.metric_alarm_url.path, headers=header)
        res = metric_api_conn.getresponse()
        if res.status is not RESPONSE_OK_STATUS:
            print ('FAILED TO RETRIEVE ALARMS ID')
            return False
        alarms_info = simplejson.loads(res.read())
        return [alarm_state['id'] for alarm_state in alarms_info['elements']
                if 'st_aol_test' in alarm_state['alarm_definition']['name']]


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-mariadb_status', action='store', dest='mariadb_status')
    parser.add_argument('-mariadb_username', action='store', dest='mariadb_username')
    parser.add_argument('-mariadb_password', action='store', dest='mariadb_password', default='')
    parser.add_argument('-mariadb_hostname', action='store', dest='mariadb_hostname')
    parser.add_argument('-mariadb_database', action='store', dest='mariadb_database')
    parser.add_argument('-keystone_url', action="store", dest='keystone_url')
    parser.add_argument('-metric_api_url', action="store", dest='metric_api_url')
    parser.add_argument('-log_api_url', action="store", dest='log_api_url')
    parser.add_argument('-tenant_name', action="store", dest='tenant_name')
    parser.add_argument('-tenant_password', action="store", dest='tenant_password')
    parser.add_argument('-tenant_project', action="store", dest='tenant_project')
    parser.add_argument('-runtime', action="store", dest='runtime', type=int)
    parser.add_argument('-alarm_conf', action="store", dest='alarm_conf', nargs='+')
    return parser.parse_args()

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
        TEST_CONF = yaml.load(file('test_configuration.yaml'))
        MARIADB_STATUS = BASIC_CONF['mariadb']['status']
        MARIADB_USERNAME = BASIC_CONF['mariadb']['user']
        MARIADB_PASSWORD = BASIC_CONF['mariadb']['password']\
            if BASIC_CONF['mariadb']['password'] is not None else ''
        MARIADB_HOSTNAME = BASIC_CONF['mariadb']['hostname']
        MARIADB_DATABASE = BASIC_CONF['mariadb']['database']
        KEYSTONE_URL = BASIC_CONF['url']['keystone']
        METRIC_API_URL = BASIC_CONF['url']['metrics_api']
        LOG_API_URL = BASIC_CONF['url']['log_api_url']
        USER_CREDENTIAL = {"name": BASIC_CONF['users']['tenant_name'],
                           "password": BASIC_CONF['users']['tenant_password'],
                           "project": BASIC_CONF['users']['tenant_project']}
        RUNTIME = TEST_CONF[TEST_NAME]['runtime']
        ALARM_DEF_CONF = TEST_CONF[TEST_NAME]['alarm_conf']
    else:
        program_argument = create_program_argument_parser()
        MARIADB_STATUS = program_argument.mariadb_status
        MARIADB_USERNAME = program_argument.mariadb_username
        MARIADB_PASSWORD = program_argument.mariadb_password \
            if program_argument.mariadb_password is not None else ''
        MARIADB_HOSTNAME = program_argument.mariadb_hostname
        MARIADB_DATABASE = program_argument.mariadb_database
        KEYSTONE_URL = program_argument.keystone_url
        USER_CREDENTIAL = {"name": program_argument.tenant_name,
                           "password": program_argument.tenant_password,
                           "project": program_argument.tenant_project}
        METRIC_API_URL = program_argument.metric_api_url
        LOG_API_URL = program_argument.log_api_url
        RUNTIME = program_argument.runtime
        ALARM_DEF_CONF = [{'severity': alarm_def_con[0], 'number_of_alarm_def': alarm_def_con[1],
                           'alarms_per_alarm_definition': alarm_def_con[2]} for alarm_def_con in
                          [alarm_def_con.split(':') for alarm_def_con in program_argument.alarm_conf]]

    aolTest = AOLTest(KEYSTONE_URL, USER_CREDENTIAL['name'], USER_CREDENTIAL['password'],
                      USER_CREDENTIAL['project'], METRIC_API_URL, LOG_API_URL, ALARM_DEF_CONF, RUNTIME,
                      MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE)
    aolTest.start()
