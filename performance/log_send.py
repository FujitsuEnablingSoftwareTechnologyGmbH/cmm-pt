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
This program sends specific sized log entries in predefined intervals via the LOG API to the Monasca system.
This program supports bulk mode api and sine mode api(deprecated).
All public variables are described in basic_configuration.yaml and test_configuration.yaml files and
can be passed as program arguments.
"""

import argparse
from datetime import datetime
import httplib
import MySQLdb
import random
import simplejson
import string
import sys
import time
import yaml
from threading import Thread
import threading
from urlparse import urlparse
from write_logs import create_file, write_line_to_file
import TokenHandler
import db_saver

TEST_NAME = 'log_send'
BULK_URL_PATH = '/v3.0/logs'
SINGLE_LOG_API_URL_PATH = '/v2.0/log/single'

BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
MARIADB_HOSTNAME = BASIC_CONF['mariadb']['hostname']
MARIADB_USERNAME = BASIC_CONF['mariadb']['user']
MARIADB_PASSWORD = BASIC_CONF['mariadb']['password'] if BASIC_CONF['mariadb']['password'] is not None else ''
MARIADB_DATABASE = BASIC_CONF['mariadb']['database']


class LogSend(threading.Thread):
    def __init__(self, keystone_url, log_api_url, tenant_username, tenant_password, tenant_project, thread_num,
                 runtime, log_every_n, log_api_type, bulk_size, frequency, log_size, log_level, log_dimension,
                 delay, mariadb_status, mariadb_username=None, mariadb_password=None, mariadb_hostname=None,
                 mariadb_database=None, testCaseID=1):
        threading.Thread.__init__(self)
        self.mariadb_status = mariadb_status
        self.keystone_url = keystone_url
        self.log_api_url = log_api_url
        self.tenant_username = tenant_username
        self.tenant_password = tenant_password
        self.tenant_project = tenant_project
        self.thread_num = thread_num
        self.runtime = runtime
        self.log_every_n = log_every_n
        self.log_api_type = log_api_type
        self.bulk_size = bulk_size
        self.frequency = frequency
        self.log_size = log_size
        self.log_level = log_level
        self.log_dimension = log_dimension
        self.delay = delay
        self.token_handler = TokenHandler.TokenHandler(self.tenant_username, self.tenant_password, self.tenant_project,
                                                       self.keystone_url)
        self.result_file = self.create_result_file()
        self.token_handler.get_valid_token()
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
                self.test_params = list()
                db.close()
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()

    def generate_log_message(self, size=50, count=0):
        """Return unique massage that contain current data, Count value and random massage
        Parameters:
            size - size of the message
            count - number that wil be added to the message
        """
        def rand(size):
            return ''.join((random.choice(letters + ' ') for _ in range(size)))

        letters = string.ascii_lowercase
        basic_msg = "{} {} Count={} ".format(datetime.now().strftime("%H:%M:%S.%f"), self.log_level, str(count))
        if size > len(basic_msg):
            message = rand(size - len(basic_msg))
            gen_mes = ("".join(message))
        else:
            gen_mes = ""
        return '{} {}'.format(basic_msg, gen_mes)

    def send_log_in_single_mod(self, log_api_conn, message):
        """Send log to log api in single mode and return request status code
        """
        headers_post = {'X-Dimensions': 'applicationname:SystemTest,environment:productioni',
                        'X-Application-Type': 'SystemTest',
                        'X-Auth-Token': self.token_handler.get_valid_token()}
        dimensions = {}
        for dimension in LOG_DIMENSION:
            dimensions[dimension['key']] = dimension['value']
        dimensions['application_type'] = 'SystemTest'
        body = simplejson.dumps({'message': message, 'dimensions': dimensions})
        log_api_conn.request("POST", SINGLE_LOG_API_URL_PATH, body, headers_post)
        res = log_api_conn.getresponse()
        return res.status

    def send_bulk(self, log_api_conn, message):
        """Send multiple log in bulk mode to log api ane return request status code
        """
        headers_post = {'Content-type': 'application/json',
                        'X-Auth-Token': self.token_handler.get_valid_token()}
        log_list = []
        dimensions = {}
        for dimension in self.log_dimension:
            dimensions[dimension['key']] = dimension['value']
        dimensions['application_type'] = 'SystemTest'

        for i in range(self.bulk_size):
            single_log_dimensions = dimensions.copy()
            single_log_dimensions.update({'log_count': str(i)})
            single_log = {'message': message, 'dimensions': single_log_dimensions}
            log_list.append(single_log)

        body = simplejson.dumps({'logs': log_list})
        log_api_conn.request("POST", BULK_URL_PATH, body, headers_post)
        res = log_api_conn.getresponse()
        res.read()
        return res.status

    def run_log_send_test(self):
        """ Function start  test that send specified log in interval to log api.
        """
        request_count = 0

        if self.log_api_type == 'bulk':
            num_of_logs_in_one_request = self.bulk_size

        else:
            num_of_logs_in_one_request = 1
        thread_name = threading.currentThread().getName()
        start_time = time.time()
        print("{}: Start Time: {} ".format(threading.currentThread().getName(),
                                           time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))))
        interim_time = time.time()
        log_api_connection = httplib.HTTPConnection(urlparse(self.log_api_url).netloc)
        while time.time() < (start_time + self.runtime):
            log_api_connection.connect()
            req_start_time = time.time()
            if self.log_api_type == 'bulk':
                send_status = self.send_bulk(log_api_connection,
                                             self.generate_log_message(size=self.log_size, count=request_count))
            else:
                send_status = self.send_log_in_single_mod(log_api_connection,
                                                          self.generate_log_message(size=self.log_size,
                                                                                    count=request_count))
            if send_status != 204:
                print("One request is failed!")
            else:
                request_count += 1
                if request_count % self.log_every_n == 0:
                    print(thread_name+": count: {} = {} per second".format(request_count * num_of_logs_in_one_request,
                                                                           (self.log_every_n * num_of_logs_in_one_request) /
                                                                           (time.time() - interim_time)))
                    interim_time = time.time()
            duration_time = 1.0 / self.frequency - (time.time() - req_start_time)
            time.sleep((duration_time + abs(duration_time)) / 2)

        end_time = time.time()
        total_number_of_sent_logs = request_count * num_of_logs_in_one_request
        test_duration = end_time - start_time
        log_send_per_sec = total_number_of_sent_logs / test_duration
        print("-----Test Results-----test_name")
        print(thread_name+": End Time: ", datetime.now().strftime("%H:%M:%S.%f"))
        print(thread_name+": {} log entries in {} seconds".format(total_number_of_sent_logs, test_duration))
        print(thread_name+": {} per second".format(round(total_number_of_sent_logs / test_duration), 2))
        write_line_to_file(self.result_file, "{} , {} , {} , {} , {}, {}".
                           format(thread_name, time.strftime('%H:%M:%S', time.localtime(start_time)),
                                  time.strftime('%H:%M:%S', time.localtime(end_time)), total_number_of_sent_logs,
                                  "{0:.2f}".format(test_duration), "{0:.2f}".format(log_send_per_sec)))
        if self.mariadb_status == 'enabled':
            self.test_params = [['total_number_of_sent_logs', str(total_number_of_sent_logs)],
                                ['start_time', str(datetime.fromtimestamp(start_time).replace(microsecond=0))],
                                ['end_time', str(datetime.fromtimestamp(end_time).replace(microsecond=0))],
                                ['runtime', str(self.runtime)],
                                ['average_per_second', str(log_send_per_sec)],
                                ['log_level', str(self.log_level)],
                                ['log_size', str(self.log_size)],
                                ['bulk_size', self.bulk_size],
                                ['frequency', str(self.frequency)]]
            db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                 self.mariadb_password, self.mariadb_database)
            db_saver.save_test_params(db, self.testID, self.test_params)
            db.close()

    def create_result_file(self):
        """create file for result and write header string to this file
        """
        header_line = "Thread#, Start Time, Stop Time, # of sent Logs, Used Time, Average per second"
        res_file = create_file("{}_{}_".format(TEST_NAME,self.log_level))
        write_line_to_file(res_file, header_line)
        return res_file

    def write_final_result_line(self):
        write_line_to_file(self.result_file,
                           "Number of threads: {}, RunTime: {}, Log_size: {},"
                           "Log api type {}, Number of logs in one bulk mode: {} ".
                           format(self.thread_num, self.runtime, self.log_size, self.log_api_type, self.bulk_size))

    def run(self):
        if self.delay is not None:
            print "wait {}s before starting test".format(self.delay)
            time.sleep(self.delay)
        thread_list = []

        for i in range(self.thread_num):
            thread = Thread(target=self.run_log_send_test)
            thread.start()
            thread_list.append(thread)

        for thread in thread_list:
            thread.join()

        self.write_final_result_line()
        self.result_file.close()


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-mariadb_status', action='store', dest='mariadb_status')
    parser.add_argument('-mariadb_username', action='store', dest='mariadb_username')
    parser.add_argument('-mariadb_password', action='store', dest='mariadb_password')\
        if BASIC_CONF['mariadb']['password'] is not None else ''
    parser.add_argument('-mariadb_hostname', action='store', dest='mariadb_hostname')
    parser.add_argument('-mariadb_database', action='store', dest='mariadb_database')
    parser.add_argument('-keystone_url', action="store", dest='keystone_url')
    parser.add_argument('-log_api_url', action="store", dest='log_api_url')
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
    parser.add_argument('-daley', action="store", dest='delay', type=int, required=False)
    parser.add_argument('-log_level', action="store", dest='log_level', type=str)
    parser.add_argument('-log_dimension', action="store", dest='log_dimension', nargs='+')

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
        LOG_API_URL = BASIC_CONF['url']['log_api_url']
        TENANT_USERNAME = BASIC_CONF['users']['tenant_name']
        TENANT_PASSWORD = BASIC_CONF['users']['tenant_password']
        TENANT_PROJECT = BASIC_CONF['users']['tenant_project']
        THREADS_NUM = TEST_CONF[TEST_NAME]['num_threads']
        RUNTIME = TEST_CONF[TEST_NAME]['runtime']
        LOG_EVERY_N = TEST_CONF[TEST_NAME]['log_every_n']
        LOG_API_TYPE = TEST_CONF[TEST_NAME]['log_api_type']
        NUM_Of_LOGS_IN_ONE_BULK = TEST_CONF[TEST_NAME]['num_of_logs_in_one_bulk']
        FREQUENCY = TEST_CONF[TEST_NAME]['frequency']
        LOG_SIZE = TEST_CONF[TEST_NAME]['log_size']
        LOG_LEVEL = TEST_CONF[TEST_NAME]['log_level']
        LOG_DIMENSION = TEST_CONF[TEST_NAME]['dimension']
        DELAY = None
    else:
        program_argument = create_program_argument_parser()
        MARIADB_STATUS = program_argument.mariadb_status
        MARIADB_USERNAME = program_argument.mariadb_username
        MARIADB_PASSWORD = program_argument.mariadb_password
        MARIADB_HOSTNAME = program_argument.mariadb_hostname
        MARIADB_DATABASE = program_argument.mariadb_database
        KEYSTONE_URL = program_argument.keystone_url
        LOG_API_URL = program_argument.log_api_url
        TENANT_USERNAME = program_argument.tenant_name
        TENANT_PASSWORD = program_argument.tenant_password
        TENANT_PROJECT = program_argument.tenant_project
        THREADS_NUM = program_argument.num_threads
        RUNTIME = program_argument.runtime
        LOG_EVERY_N = program_argument.log_every_n
        LOG_API_TYPE = program_argument.log_api_type
        NUM_Of_LOGS_IN_ONE_BULK = program_argument.num_of_logs_in_one_bulk
        FREQUENCY = program_argument.frequency
        LOG_SIZE = program_argument.log_size
        DELAY = program_argument.delay
        LOG_LEVEL = program_argument.log_level
        LOG_DIMENSION = [{'key': dimension[0], 'value': dimension[1]} for dimension in
                         [dimension.split(':') for dimension in program_argument.log_dimension]]

    log_send = LogSend(KEYSTONE_URL, LOG_API_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT, THREADS_NUM,
                       RUNTIME, LOG_EVERY_N, LOG_API_TYPE, NUM_Of_LOGS_IN_ONE_BULK, FREQUENCY, LOG_SIZE,
                       LOG_LEVEL, LOG_DIMENSION, DELAY, MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD,
                       MARIADB_HOSTNAME, MARIADB_DATABASE)
    log_send.start()



