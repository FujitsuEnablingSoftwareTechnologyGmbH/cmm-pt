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
This program sends specific sized and marked log entries in predefined intervals via the LOG API to the Monasca system.
Once a log entry is sent to the Monasca system the test starts reading the just sent log entry from the Elasticsearch API.
The time it takes from sending the log entry until retrieving the same entry via the Elasticsearch API is measured.
The duration, this 'roundtrip' needs, is used as an (indirect) measurement to verify the performance of the system under test.
The public variables are described in basic_configuration.yaml and test_configuration.yaml files.
"""

import argparse
import datetime
import httplib
import MySQLdb
import random
import search_logs
import simplejson
import string
import sys
import threading
import time
import yaml
from urlparse import urlparse
from threading import Thread
import TokenHandler
from write_logs import create_file, write_line_to_file, serialize_logging
import db_saver


TEST_NAME = 'log_latency'
BULK_URL_PATH = '/v3.0/logs'
SINGLE_LOG_API_URL_PATH = '/v2.0/log/single'
BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
MARIADB_HOSTNAME = BASIC_CONF['mariadb']['hostname']
MARIADB_USERNAME = BASIC_CONF['mariadb']['user']
MARIADB_PASSWORD = BASIC_CONF['mariadb']['password'] if BASIC_CONF['mariadb']['password'] is not None else ''
MARIADB_DATABASE = BASIC_CONF['mariadb']['database']


class LogLatency(threading.Thread):
    def __init__(self, keystone_url, log_api_url, elastic_url, tenant_username, tenant_password, tenant_project,
                 runtime, thread_num, log_api_type, bulk_size, log_size, mariadb_status, mariadb_username=None,
                 mariadb_password=None, mariadb_hostname=None, mariadb_database=None):
        threading.Thread.__init__(self)
        self.mariadb_status = mariadb_status
        self.keystone_url = keystone_url
        self.log_api_url = log_api_url
        self.elastic_url = elastic_url
        self.tenant_username = tenant_username
        self.tenant_password = tenant_password
        self.tenant_project = tenant_project
        self.runtime = runtime
        self.thread_num = thread_num
        self.log_api_type = log_api_type
        self.bulk_size = bulk_size
        self.log_size = log_size
        self.token_handler = TokenHandler.TokenHandler(tenant_username, tenant_password, tenant_project, keystone_url)
        self.result_file = self.create_result_file()
        if self.mariadb_status == 'enabled':
            if ((self.mariadb_hostname is not None) and
                (self.mariadb_username is not None) and
                    (self.mariadb_password is not None)):
                db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                     self.mariadb_password, self.mariadb_database)
                # The following parameter "1" will be changed into the testCaseID provided by the launcher script
                self.testID = db_saver.save_test(db, 1, TEST_NAME)
                db.close()
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()

    def search_logs_in_elastic(self, message, duration, check_rate):
        """this function search logs entry that contain specified message in database,
        If function find expected log entry will return 'OK' message,
        If function could not find all expected log entry in specified time will return FAILED string
        Parameters:
            message :searched message in log
            duration : maximum time with function try to find all log entry
            check_rate: time that determinate time break between checks
        """
        if self.log_api_type == 'bulk':
            number_of_search_log = self.bulk_size
        else:
            number_of_search_log = 1
        timeout = time.time() + duration
        while time.time() < timeout:
            if search_logs.count_logs_by_app_message(message, self.elastic_url)[0] >= number_of_search_log:
                return 'OK'
            time.sleep(check_rate)
        return 'FAILED'

    def check_latency(self, message):
        """ this send log entry in single ol bul mode  to the log api
        then invoke function that try to find just sent log entry """

        if self.log_api_type == 'bulk':
            send_status = self.send_bulk_log(message)
        else:
            send_status = self.send_single_log(message)
        search_status = self.search_logs_in_elastic(message, 200, 0.5)
        return send_status, search_status

    def send_single_log(self, message):
        self.get_request_header()
        conn = httplib.HTTPConnection(urlparse(self.log_api_url).netloc)
        body = simplejson.dumps({'message': message})
        conn.request("POST", SINGLE_LOG_API_URL_PATH, body, self.get_request_header())
        res = conn.getresponse()
        return res.status

    def get_request_header(self):
        if self.log_api_type == 'single':
            headers_post = {'X-Dimensions': 'applicationname:latency_test,environment:productioni',
                            'X-Application-Type': 'SystemTest'}
        else:
            headers_post = {'Content-type': 'application/json', 'X-Auth-Token': self.token_handler.get_valid_token()}

        return headers_post

    def send_bulk_log(self, message):
        self.get_request_header()
        conn = httplib.HTTPConnection(urlparse(self.log_api_url).netloc)
        body = simplejson.dumps({'logs': self.bulk_size * [{'message': message}]})
        conn.request("POST", BULK_URL_PATH, body, self.get_request_header())
        res = conn.getresponse()
        return res.status

    def generate_unique_message(self, message=None):
        letters = string.ascii_lowercase

        def rand():
            return ''.join((random.choice(letters) for _ in range(self.log_size)))
        if not message:
            message = rand()
        return message

    def run_latency_test(self):
        test_results = list()
        thread_name = threading.currentThread().getName()
        latency_check_count = 0
        print("{}: Start Time: {} ".format(thread_name, datetime.datetime.now().strftime("%H:%M:%S.%f")))
        start_time = time.time()
        strt_time = datetime.datetime.now().replace(microsecond=0)
        while time.time() < (start_time + self.runtime):
            check_start_time = time.time()
            send_status, search_status = self.check_latency(self.generate_unique_message())
            check_end_time = time.time()
            latency_check_count += 1
            if self.mariadb_status == 'enabled':
                test_results.append(
                    self.write_latency_check_result(
                        send_status, search_status, check_start_time, check_end_time,
                                            thread_name, str(latency_check_count)))
            else:
                self.write_latency_check_result(send_status, search_status, check_start_time, check_end_time,
                                                thread_name, str(latency_check_count))
        if self.mariadb_status == 'enabled':
            db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                 self.mariadb_password, self.mariadb_database)
            db_saver.save_test_results(db, self.testID, test_results)
            db.close()
        final_time = time.time()
        print("-----Test Results-----")
        print("{}: End Time: {}".format(thread_name, thread_name, datetime.datetime.now().strftime("%H:%M:%S.%f")))
        if self.mariadb_status == 'enabled':
            db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                 self.mariadb_password, self.mariadb_database)
            test_params = [['log_api_type', str(self.log_api_type)],
                           ['start_time', str(strt_time)],
                           ['end_time', str(datetime.datetime.now().replace(microsecond=0))],
                           ['runtime', str(self.runtime)],
                           ['log_size', str(self.log_size)]]
            db_saver.save_test_params(db, self.testID, test_params)
            db.close()
        print("{}: {} log entries in {} seconds".format(thread_name, latency_check_count, final_time-start_time))

    def write_latency_check_result(self, send_status, search_status, start_time, end_time, name, count):
        def convert_epoch(epoch_time):
            return time.strftime('%H:%M:%S', time.localtime(epoch_time))
        latency = end_time - start_time

        if send_status == 204:
            if search_status == 'OK':
                print("{} Time: {}, Send and search injector log OK in: {} seconds!"
                      .format(name, datetime.datetime.now().strftime("%H:%M:%S.%f"), latency))
            else:
                print("{} Time: {}, Send injector log OK but search failed in: {} seconds!"
                      .format(name, datetime.datetime.now().strftime("%H:%M:%S.%f"), latency))
            result_line = "{}, {}, OK, {}, {}, {}, {}"\
                .format(name, count, search_status, convert_epoch(start_time), convert_epoch(end_time), latency, count)
            serialize_logging(self.result_file, result_line)
        else:
            print("{} Time: {}, Send Injector log Failed after: {}"
                  .format(name, datetime.datetime.now().strftime("%H:%M:%S.%f"), latency)+" seconds!")
        if self.mariadb_status == 'enabled':
            return ["latency", str(latency), datetime.datetime.now().replace(microsecond=0)]

    def create_result_file(self):
        """create file for result then write header line to this file """
        test_info_line = "Log_api_mode: {}, Number of threads: {}, RunTime: {}, Log_size: {}"\
                         .format(self.log_api_type, self.thread_num, self.runtime, self.log_size)
        header_line = "Thread#, Count, Send_Status, Search_Result, Start Time, Stop Time, Latency"
        if self.log_api_type == 'bulk':
            test_info_line += ", Number of logs in one Bulk: {}".format(self.bulk_size)
        res_file = create_file(TEST_NAME)
        write_line_to_file(res_file, test_info_line)
        write_line_to_file(res_file, header_line)
        return res_file

    def run(self):
        print("Test Start, :" + str(self.thread_num) + " thread(s)")
        thread_list = []
        for i in range(self.thread_num):
            thread = Thread(target=self.run_latency_test)
            time.sleep(0.3)
            thread.start()
            thread_list.append(thread)

        for thread in thread_list:
            thread.join()

        self.result_file.close()


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-mariadb_status', action='store', dest='mariadb_status')
    parser.add_argument('-mariadb_username', action='store', dest='mariadb_username')
    parser.add_argument('-mariadb_password', action='store', dest='mariadb_password')
    parser.add_argument('-mariadb_hostname', action='store', dest='mariadb_hostname')
    parser.add_argument('-mariadb_database', action='store', dest='mariadb_database')
    parser.add_argument('-keystone_url', action="store", dest='keystone_url')
    parser.add_argument('-log_api_url', action="store", dest='log_api_url')
    parser.add_argument('-elastic_url', action="store", dest='elastic_url')
    parser.add_argument('-tenant_name', action="store", dest='tenant_name')
    parser.add_argument('-tenant_password', action="store", dest='tenant_password')
    parser.add_argument('-tenant_project', action="store", dest='tenant_project')
    parser.add_argument('-runtime', action="store", dest='runtime', type=int)
    parser.add_argument('-num_threads', action="store", dest='num_threads', type=int)
    parser.add_argument('-log_every_n', action="store", dest='log_every_n', type=int)
    parser.add_argument('-log_api_type', action="store", dest='log_api_type')
    parser.add_argument('-num_of_logs_in_one_bulk', action="store", dest='num_of_logs_in_one_bulk', type=int)
    parser.add_argument('-frequency', action="store", dest='frequency', type=int)
    parser.add_argument('-log_size', action="store", dest='log_size', type=int)
    return parser.parse_args()

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
        TEST_CONF = yaml.load(file('test_configuration.yaml'))
        MARIADB_STATUS = BASIC_CONF['mariadb']['status']
        MARIADB_USERNAME = BASIC_CONF['mariadb']['username']
        MARIADB_PASSWORD = BASIC_CONF['mariadb']['password']
        MARIADB_HOSTNAME = BASIC_CONF['mariadb']['hostname']
        MARIADB_DATABASE = BASIC_CONF['mariadb']['database']
        KEYSTONE_URL = BASIC_CONF['url']['keystone']
        LOG_API_URL = BASIC_CONF['url']['log_api_url']
        ELASTIC_URL = urlparse(BASIC_CONF['url']['elastic_url']).netloc
        TENANT_USERNAME = BASIC_CONF['users']['tenant_name']
        TENANT_PASSWORD = BASIC_CONF['users']['tenant_password']
        TENANT_PROJECT = BASIC_CONF['users']['tenant_project']
        RUNTIME = TEST_CONF[TEST_NAME]['runtime']
        THREADS_NUM = TEST_CONF[TEST_NAME]['num_threads']
        LOG_API_TYPE = TEST_CONF[TEST_NAME]['log_api_type']
        NUM_Of_LOGS_IN_ONE_BULK = TEST_CONF[TEST_NAME]['num_of_logs_in_one_bulk']
        LOG_SIZE = TEST_CONF[TEST_NAME]['log_size']
    else:
        program_argument = create_program_argument_parser()
        MARIADB_STATUS = program_argument.mariadb_status
        MARIADB_USERNAME = program_argument.mariadb_username
        MARIADB_PASSWORD = program_argument.mariadb_password
        MARIADB_HOSTNAME = program_argument.mariadb_hostname
        MARIADB_DATABASE = program_argument.mariadb_database
        KEYSTONE_URL = program_argument.keystone_url
        LOG_API_URL = program_argument.log_api_url
        ELASTIC_URL = urlparse(program_argument.elastic_url).netloc
        TENANT_USERNAME = program_argument.tenant_name
        TENANT_PASSWORD = program_argument.tenant_password
        TENANT_PROJECT = program_argument.tenant_project
        RUNTIME = program_argument.runtime
        THREADS_NUM = program_argument.num_threads
        LOG_API_TYPE = program_argument.log_api_type
        NUM_Of_LOGS_IN_ONE_BULK = program_argument.num_of_logs_in_one_bulk
        LOG_SIZE = program_argument.log_size

    log_latency = LogLatency(KEYSTONE_URL, LOG_API_URL, ELASTIC_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                             RUNTIME, THREADS_NUM, LOG_API_TYPE, NUM_Of_LOGS_IN_ONE_BULK, LOG_SIZE, MARIADB_STATUS,
                             MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE)

    log_latency.start()
