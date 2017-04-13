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
This program sends specific sized and marked metric entries in predefined intervals via the Metric API to the Monasca system.
Once a Metric entry is sent to the Monasca system the test starts reading the just sent metric entry from the Metric API.
The time it takes from sending the metric entry until retrieving the same entry is measured.
The duration, this 'roundtrip' needs, is used as an (indirect) measurement to verify the performance of the system under test.
The public variables are described in basic_configuration.yaml and test_configuration.yaml files.
"""

import argparse
import httplib
import json
import MySQLdb
import random
import threading
import time
import sys
import yaml
import simplejson
from datetime import datetime
from urlparse import urlparse
import TokenHandler
from write_logs import create_file, write_line_to_file
import db_saver


TEST_NAME = 'metric_latency'
BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
MARIADB_HOSTNAME = BASIC_CONF['mariadb']['hostname']
MARIADB_USERNAME = BASIC_CONF['mariadb']['user']
MARIADB_PASSWORD = BASIC_CONF['mariadb']['password'] if BASIC_CONF['mariadb']['password'] is not None else ''
MARIADB_DATABASE = BASIC_CONF['mariadb']['database']


class MetricLatency(threading.Thread):
    def __init__(self, keystone_url, tenant_name, tenant_password, tenant_project, metric_api_url, runtime,
                 check_ticker, send_ticker, timeout, mariadb_status, mariadb_username=None,mariadb_password=None,
                 mariadb_hostname=None, mariadb_database=None, testCaseID=1):
        threading.Thread.__init__(self)
        self.mariadb_status = mariadb_status
        self.keystone_url = keystone_url
        self.tenant_name = tenant_name
        self.tenant_password = tenant_password
        self.tenant_project = tenant_project
        self.metric_api_url = urlparse(metric_api_url)
        self.runtime = runtime
        self.check_ticker = check_ticker
        self.send_ticker = send_ticker
        self.timeout = timeout
        self.result_file = create_file(TEST_NAME)
        self.toke_handler = TokenHandler.TokenHandler(self.tenant_name, self.tenant_password, self.tenant_project,
                                                      self.keystone_url)
        if self.mariadb_status == 'enabled':
            self.mariadb_database = mariadb_database
            self.mariadb_username = mariadb_username
            self.mariadb_password = mariadb_password
            self.mariadb_hostname = mariadb_hostname
            if ((self.mariadb_hostname is not None) and
                (self.mariadb_username is not None) and
                    (self.mariadb_database is not None)):
                db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                     self.mariadb_password, self.mariadb_database)
                self.testCaseID = testCaseID
                self.testID = db_saver.save_test(db, self.testCaseID, TEST_NAME)
                db.close()
                self.test_results = list()
                self.test_params = list()
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()

    def writ_header_to_result_file(self):
        write_line_to_file(self.result_file, "Metric Latency Test, Runtime = {}, Metric check frequency = {}, Metric send frequency ={}"
                           .format(self.runtime, self.check_ticker, self.send_ticker))
        if self.mariadb_status == 'enabled':
            self.test_params = [['check_ticker', str(self.check_ticker)],
                           ['runtime', str(self.runtime)],
                           ['send_ticker', str(self.send_ticker)]]
            db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                 self.mariadb_password, self.mariadb_database)
            db_saver.save_test_params(db, self.testID, self.test_params)
            db.close
        write_line_to_file(self.result_file, "start_time, send_status, end_time, Latency")

    def write_result_to_result_file(self, start_time, check_status, end_time):
        start_time_str = datetime.fromtimestamp(start_time).strftime("%H:%M:%S.%f")
        end_time_str = datetime.fromtimestamp(end_time).strftime("%H:%M:%S.%f")
        latency = end_time - start_time
        if check_status is "OK":
            print("Time = {}  Latency = {}s".format(start_time_str, latency))
            write_line_to_file(self.result_file,
                               "{},{},{},{}".format(start_time_str, check_status, end_time_str, latency))
        else:
            print("timeout metric not found")
            write_line_to_file(self.result_file,
                               "{},{},{},{}".format(start_time_str, check_status, "---", "< " + str(self.timeout)))
            latency = self.timeout
        if self.mariadb_status == 'enabled':
            return ["latency", str(latency), datetime.utcnow().replace(microsecond=0)]

    def get_request_header(self):
        """ return header for request"""
        return {"Content-type": "application/json", "X-Auth-Token": self.toke_handler.get_valid_token()}

    def create_metric_post_request_body(self, metric_timestamp):
        return simplejson.dumps({"name": "tmp.latency", "timestamp": metric_timestamp, "value": random.randint(0, 100)})

    def send_metric(self, metric_timestamp):
        connection = httplib.HTTPConnection(self.metric_api_url.netloc)
        body = self.create_metric_post_request_body(metric_timestamp)
        connection.request("POST", self.metric_api_url.path, body, self.get_request_header())
        request_response = connection.getresponse()
        connection.close()
        return request_response.status

    def create_get_metric_request(self, metric_timestamp):
        metric_timestamp_iso = datetime.utcfromtimestamp(metric_timestamp/1000).isoformat()
        ent_time_metric_timestamp_iso = datetime.utcfromtimestamp(metric_timestamp/1000 + 1).isoformat()
        return "?name=tmp.latency&start_time={}&end_time={}".format(metric_timestamp_iso, ent_time_metric_timestamp_iso)

    def get_metric(self, metric_timestamp):
        """"send query to log api to search metric """
        connection = httplib.HTTPConnection(self.metric_api_url.netloc)
        connection.request("GET", "{}/measurements{}".format(self.metric_api_url.path,
                                                             self.create_get_metric_request(metric_timestamp)),
                           headers=self.get_request_header())
        request_response = connection.getresponse().read()
        connection.close()
        return request_response

    def check_until_metric_is_available(self, metric_timestamp):
        """function search  metric in metric-api
          if function find specified metric return 'OK'
          if could not find specified metric in expected time return 'TIMEOUT' """

        time_out_time = self.timeout + time.time()
        while time_out_time > time.time():
            response_json = json.loads(self.get_metric(metric_timestamp))
            try:
                if len(response_json['elements']) > 0:
                    return "OK"
            except:
                print "Unexpected error:" + sys.exc_info()[0]
            time.sleep(self.check_ticker)

        return "TIMEOUT"

    def run(self):
        self.writ_header_to_result_file()
        test_start_time = time.time()
        start_time = datetime.utcnow().replace(microsecond=0)
        while time.time() < (test_start_time + self.runtime):
            metric_timestamp_milliseconds = int((round(time.time() * 1000)))
            send_status = self.send_metric(metric_timestamp_milliseconds)
            if send_status is not 204:
                print "Fail to send metrics"

            else:
                time_before_check = time.time()
                check_status = self.check_until_metric_is_available(metric_timestamp_milliseconds)
                if self.mariadb_status == 'enabled':
                    self.test_results.append(
                        self.write_result_to_result_file(
                            time_before_check, check_status, time.time()))
                else:
                    self.write_result_to_result_file(time_before_check, check_status, time.time())
            time.sleep(self.send_ticker)
        if self.mariadb_status == 'enabled':
            db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                 self.mariadb_password, self.mariadb_database)
            db_saver.save_test_results(db, self.testID, self.test_results)
            test_params = [['start_time', str(start_time)],
                           ['end_time', str(datetime.utcnow().replace(microsecond=0))]]
            db_saver.save_test_params(db, self.testID, test_params)
            db.close()


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-mariadb_status', action='store', dest='mariadb_status')
    parser.add_argument('-mariadb_username', action='store', dest='mariadb_username')
    parser.add_argument('-mariadb_password', action='store', dest='mariadb_password')
    parser.add_argument('-mariadb_hostname', action='store', dest='mariadb_hostname')
    parser.add_argument('-mariadb_database', action='store', dest='mariadb_database')
    parser.add_argument('-keystone_url', action="store", dest='keystone_url')
    parser.add_argument('-metric_api_url', action="store", dest='metric_api_url', type=str)
    parser.add_argument('-tenant_name', action="store", dest='tenant_name', type=str)
    parser.add_argument('-tenant_password', action="store", dest='tenant_password', type=str)
    parser.add_argument('-tenant_project', action="store", dest='tenant_project', type=str)
    parser.add_argument('-runtime', action="store", dest='runtime', type=int)
    parser.add_argument('-check_ticker', action="store", dest='check_ticker', type=float)
    parser.add_argument('-send_ticker', action="store", dest='send_ticker', type=int)
    parser.add_argument('-timeout', action="store", dest='timeout', type=int)
    return parser.parse_args()

if __name__ == "__main__":

    if len(sys.argv) <= 1:
        TEST_CONF = yaml.load(file('test_configuration.yaml'))
        BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
        MARIADB_STATUS = BASIC_CONF['mariadb']['status']
        MARIADB_USERNAME = BASIC_CONF['mariadb']['user']
        MARIADB_PASSWORD = BASIC_CONF['mariadb']['password']\
            if BASIC_CONF['mariadb']['password'] is not None else ''
        MARIADB_HOSTNAME = BASIC_CONF['mariadb']['hostname']
        MARIADB_DATABASE = BASIC_CONF['mariadb']['database']
        KEYSTONE_URL = BASIC_CONF['url']['keystone']
        USER_CREDENTIAL = {"name": BASIC_CONF['users']['tenant_name'],
                           "password": BASIC_CONF['users']['tenant_password'],
                           "project": BASIC_CONF['users']['tenant_project']}
        METRIC_API_URL = BASIC_CONF['url']['metrics_api'] + "/metrics"
        RUNTIME = TEST_CONF[TEST_NAME]['runtime']
        CHECK_TICKER = TEST_CONF[TEST_NAME]['check_ticker']
        SEND_TICKER = TEST_CONF[TEST_NAME]['send_ticker']
        TIMEOUT = TEST_CONF[TEST_NAME]['timeout']

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
        METRIC_API_URL = program_argument.metric_api_url + "/metrics"
        RUNTIME = program_argument.runtime
        CHECK_TICKER = program_argument.check_ticker
        SEND_TICKER = program_argument.send_ticker
        TIMEOUT = program_argument.timeout

    metric_latency = MetricLatency(KEYSTONE_URL, USER_CREDENTIAL['name'], USER_CREDENTIAL['password'],
                                   USER_CREDENTIAL['project'], METRIC_API_URL, RUNTIME, CHECK_TICKER, SEND_TICKER,
                                   TIMEOUT, MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD,
                                   MARIADB_HOSTNAME, MARIADB_DATABASE)
    metric_latency.start()


