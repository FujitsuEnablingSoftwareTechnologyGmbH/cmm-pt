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
This program is able to send metrics (multi-threaded):
    Single metrics per request / bundled metrics per request
    Predefined time slices
Metric requests are sent via the Metric API to the Monasca system.
The sent number of requests per seconds will be used to measure the throughput.
All public variables are described in basic_configuration.yaml and test_configuration.yaml files, this variable can be
passed as program parameters"""

import argparse
from datetime import datetime
import httplib
import MySQLdb
import random
import simplejson
import sys
import threading
import time
import TokenHandler
import yaml
from urlparse import urlparse
from multiprocessing import Process, Queue
from write_logs import create_file, write_line_to_file
import db_saver

TEST_NAME = 'metric_send'
BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
MARIADB_HOSTNAME = BASIC_CONF['mariadb']['hostname']
MARIADB_USERNAME = BASIC_CONF['mariadb']['user']
MARIADB_PASSWORD = BASIC_CONF['mariadb']['password'] if BASIC_CONF['mariadb']['password'] is not None else ''
MARIADB_DATABASE = BASIC_CONF['mariadb']['database']


class MetricSend(threading.Thread):
    def __init__(self, keystone_url, tenant_name, tenant_password, tenant_project, metric_api_url, num_threads,
                 num_metric_per_request, log_every_n, runtime, frequency, metric_name, metric_dimension, delay,
                 mariadb_status, mariadb_username=None,mariadb_password=None, mariadb_hostname=None,
                 mariadb_database=None, testCaseID=1):
        threading.Thread.__init__(self)
        self.mariadb_status = mariadb_status
        self.headers = {"Content-type": "application/json"}
        self.keystone_url = keystone_url
        self.tenant_name = tenant_name
        self.tenant_password = tenant_password
        self.tenant_project = tenant_project
        self.metric_api_url = metric_api_url
        self.num_threads = num_threads
        self.num_metric_per_request = num_metric_per_request
        self.log_every_n = log_every_n
        self.runtime = runtime
        self.frequency = frequency
        self.metric_name = metric_name
        self.metric_dimension = metric_dimension
        self.delay = delay
        self.result_file = self.create_result_file()
        self.TOKEN_HANDLER = TokenHandler.TokenHandler(self.tenant_name, self.tenant_password, self.tenant_project,
                                                       self.keystone_url)
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
                self.testID = db_saver.save_test(db, self.testCaseID, TEST_NAME)
                db.close()
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()

    def create_metric_body(self, process_id):
        """Create json metric request body that contain fallowing filed:
        name, dimension, timestamp and value """
        multiple_metric_body = []
        current_utc_time = int((round(time.time() * 1000)))
        for i in range(self.num_metric_per_request):
            dimensions = {}
            for dimension in self.metric_dimension:
                dimensions[dimension['key']] = dimension['value']
            dimensions['count'] = process_id + "_" + str(i)
            multiple_metric_body.append({"name": self.metric_name, "dimensions": dimensions,
                                         "timestamp": current_utc_time, "value": random.randint(0, 100)})
        return multiple_metric_body

    def send_metrics(self, process_id, url_parse, conn):
        header = self.headers.copy()
        header.update({"X-Auth-Token": self.TOKEN_HANDLER.get_valid_token()})
        body = simplejson.dumps(self.create_metric_body(process_id))
        conn.request("POST", url_parse.path, body, header)
        request_response = conn.getresponse()
        request_status = request_response.status
        request_response.read()
        return request_status

    def run_metric_test(self, process_id, num_of_sent_metric_queue, result_file):
        print process_id
        start_time = time.time()
        strt_time = datetime.utcnow().replace(microsecond=0)
        count_metric_request_sent = 0
        time_before_logging = start_time
        url_parse = urlparse(self.metric_api_url)
        connection = httplib.HTTPConnection(url_parse.netloc)
        while time.time() < (start_time + self.runtime):

            time_before_request = time.time()
            request_status = self.send_metrics(process_id, url_parse, connection)

            if request_status is 204:

                count_metric_request_sent += 1
                if count_metric_request_sent % self.log_every_n is 0:

                    time_after_logging = time.time()
                    print("{}: count: {} = {} per second"
                          .format(process_id, count_metric_request_sent * self.num_metric_per_request,
                                  self.log_every_n * self.num_metric_per_request / (time_after_logging - time_before_logging)))
                    time_before_logging = time.time()

                time_after_request = time.time()

                sleep_time = (1.0 / self.frequency) - (time_after_request - time_before_request)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            else:

                print "Failed to send metric. Error code: " + str(request_status)
        stop_time = time.time()
        stp_time = datetime.utcnow().replace(microsecond=0)
        total_metric_send = count_metric_request_sent * self.num_metric_per_request
        test_duration = stop_time - start_time
        metric_send_per_sec = total_metric_send / test_duration
        write_line_to_file(result_file, "{} , {} , {} , {} , {} , {}"
                           .format(process_id, time.strftime('%H:%M:%S', time.localtime(start_time)),
                                   time.strftime('%H:%M:%S', time.localtime(stop_time)), total_metric_send,
                                   test_duration, metric_send_per_sec))
        if self.mariadb_status == 'enabled':
            test_params = [['total_number_of_sent_metrics', str(total_metric_send)],
                           ['start_time', strt_time],
                           ['end_time', stp_time],
                           ['runtime', str(self.runtime)],
                           ['test_duration', str(test_duration)],
                           ['average_per_second', str(metric_send_per_sec)],
                           ['frequency', str(self.frequency)]]
            db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                 self.mariadb_password, self.mariadb_database)
            db_saver.save_test_params(db, self.testID, test_params)
            db.close()
        num_of_sent_metric_queue.put(count_metric_request_sent * self.num_metric_per_request)
        return

    def create_result_file(self):
        """create result file and save header line to this file """
        res_file = create_file(TEST_NAME)
        header_line = ("Thread#, Start Time, Stop Time, #sent Metrics, "
                       "Used Time, Average per second ,Number of threads: {}")
        write_line_to_file(res_file, header_line)
        return res_file

    def write_final_result_line_to_file(self, metric_send):
        print "Total metric send =" + str(metric_send)
        write_line_to_file(self.result_file,
                           "Total metric send = {}\nNumber of metrics per request: {} Number of threads: {}".
                           format(metric_send, self.num_metric_per_request, self.num_threads))
        if self.mariadb_status == 'enabled':
            test_params = [['num_metrics_per_request', str(self.num_metric_per_request)],
                           ['num_threads', str(self.num_threads)],
                           ['total_number_of_sent_metrics', str(metric_send)]]
            db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                 self.mariadb_password, self.mariadb_database)
            db_saver.save_test_params(db, self.testID, test_params)
            db.close

    def run(self):
        if self.delay is not None:
            print "wait {}s before starting test".format(self.delay)
            time.sleep(self.delay)
        process_list = []
        total_num_metric_sent_queue = Queue()

        for i in range(self.num_threads):
            process = Process(target=self.run_metric_test,
                              args=("Process-{}".format(i), total_num_metric_sent_queue, self.result_file,))
            process.daemon = True
            process.start()
            process_list.append(process)

        total_metric_send = 0
        for process in process_list:
            process.join()
            total_metric_send += total_num_metric_sent_queue.get()

        self.write_final_result_line_to_file(total_metric_send)
        self.result_file.close()


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-mariadb_status', action='store', dest='mariadb_status')
    parser.add_argument('-mariadb_username', action='store', dest='mariadb_username')
    parser.add_argument('-mariadb_password', action='store', dest='mariadb_password')
    parser.add_argument('-mariadb_hostname', action='store', dest='mariadb_hostname')
    parser.add_argument('-mariadb_database', action='store', dest='mariadb_database')
    parser.add_argument('-keystone_url', action="store", dest='keystone_url')
    parser.add_argument('-metric_api_url', action="store", dest='metric_api_url')
    parser.add_argument('-tenant_name', action="store", dest='tenant_name')
    parser.add_argument('-tenant_password', action="store", dest='tenant_password')
    parser.add_argument('-tenant_project', action="store", dest='tenant_project')
    parser.add_argument('-runtime', action="store", dest='runtime', type=int)
    parser.add_argument('-num_threads', action="store", dest='num_threads', type=int)
    parser.add_argument('-log_every_n', action="store", dest='log_every_n', type=int)
    parser.add_argument('-metric_name', action="store", dest='metric_name', type=str)
    parser.add_argument('-num_metric_per_request', action="store", dest='num_metric_per_request', type=int)
    parser.add_argument('-frequency', action="store", dest='frequency', type=int)
    parser.add_argument('-metric_dimension', action="store", dest='metric_dimension', nargs='+')
    parser.add_argument('-daley', action="store", dest='delay', type=int, required=False)
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
        METRIC_API_URL = BASIC_CONF['url']['metrics_api'] + "/metrics"
        KEYSTONE_URL = BASIC_CONF['url']['keystone']
        TENANT_CREDENTIAL = {"name": BASIC_CONF['users']['tenant_name'],
                             "password": BASIC_CONF['users']['tenant_password'],
                             "project": BASIC_CONF['users']['tenant_project']}
        NUM_THREADS = TEST_CONF[TEST_NAME]['num_threads']
        NUM_METRIC_PER_REQUEST = TEST_CONF[TEST_NAME]['num_metrics_per_request']
        LOG_EVERY_N = TEST_CONF[TEST_NAME]['LOG_EVERY_N']
        RUNTIME = TEST_CONF[TEST_NAME]['runtime']
        FREQUENCY = TEST_CONF[TEST_NAME]['frequency']
        METRIC_NAME = TEST_CONF[TEST_NAME]['metric_name']
        METRIC_DIMENSION = TEST_CONF[TEST_NAME]['metric_dimension']
        DELAY = None
    else:
        program_argument = create_program_argument_parser()
        MARIADB_STATUS = program_argument.mariadb_status
        MARIADB_USERNAME = program_argument.mariadb_username
        MARIADB_PASSWORD = program_argument.mariadb_password \
            if program_argument.mariadb_password is not None else ''
        MARIADB_HOSTNAME = program_argument.mariadb_hostname
        MARIADB_DATABASE = program_argument.mariadb_database
        KEYSTONE_URL = program_argument.keystone_url
        TENANT_CREDENTIAL = {"name": program_argument.tenant_name,
                             "password": program_argument.tenant_password,
                             "project": program_argument.tenant_project}
        METRIC_API_URL = program_argument.metric_api_url + "/metrics"
        NUM_THREADS = program_argument.num_threads
        NUM_METRIC_PER_REQUEST = program_argument.num_metric_per_request
        LOG_EVERY_N = program_argument.log_every_n
        RUNTIME = program_argument.runtime
        FREQUENCY = program_argument.frequencygit
        METRIC_NAME = program_argument.metric_name
        METRIC_DIMENSION = [{'key': dimension[0], 'value': dimension[1]} for dimension in
                            [dimension.split(':') for dimension in program_argument.metric_dimension]]
        DELAY = program_argument.delay

    TOKEN_HANDLER = TokenHandler.TokenHandler(TENANT_CREDENTIAL['name'],
                                              TENANT_CREDENTIAL['password'],
                                              TENANT_CREDENTIAL['project'],
                                              KEYSTONE_URL)
    metric_send = MetricSend(KEYSTONE_URL, TENANT_CREDENTIAL['name'], TENANT_CREDENTIAL['password'],
                             TENANT_CREDENTIAL['project'], METRIC_API_URL, NUM_THREADS, NUM_METRIC_PER_REQUEST,
                             LOG_EVERY_N, RUNTIME, FREQUENCY, METRIC_NAME, METRIC_DIMENSION, DELAY, MARIADB_STATUS,
                             MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE)
    metric_send.start()
