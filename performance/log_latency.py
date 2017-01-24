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
import httplib
import sys
import simplejson
import threading
import time
import TokenHandler
import string
import random
import search_logs
import yaml
import datetime
from Queue import Queue
from urlparse import urlparse
from threading import Thread
from write_logs import create_file, write_line_to_file, serialize_logging


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
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

TEST_NAME = 'log_latency'
BULK_URL_PATH = '/v3.0/logs'
SINGLE_LOG_API_URL_PATH = '/v2.0/log/single'


if len(sys.argv) <= 1:
    BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
    TEST_CONF = yaml.load(file('test_configuration.yaml'))
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


token_handler = TokenHandler.TokenHandler(TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT, KEYSTONE_URL)

headers_post = {"Content-type": "application/json"}
if LOG_API_TYPE == 'single':
    headers_post = {"X-Dimensions": "applicationname:latency_test,environment:productioni",
                    "X-Application-Type": 'SystemTest'}


def search_logs_in_elastic(message, duration, check_rate):
    """this function search logs entry that contain specified message in database,
    If function find expected log entry will return 'OK' message,
    If function could not find all expected log entry in specified time will return FAILED string
    Parameters:
        message :searched message in log
        duration : maximum time with function try to find all log entry
        check_rate: time that determinate time break between checks
    """
    if LOG_API_TYPE == 'bulk':
        number_of_search_log = NUM_Of_LOGS_IN_ONE_BULK
    else:
        number_of_search_log = 1
    timeout = time.time() + duration
    while time.time() < timeout:
        if search_logs.count_logs_by_app_message(message, ELASTIC_URL)[0] >= number_of_search_log:
            return 'OK'
        time.sleep(check_rate)
    return 'FAILED'


def check_latency(message):
    """ this send log entry in single ol bul mode  to the log api
    then invoke function that try to find just sent log entry """

    if LOG_API_TYPE == 'bulk':
        send_status = send_bulk_log(message)
    else:
        send_status = send_single_log(message)
    search_status = search_logs_in_elastic(message, 200, 0.5)
    return send_status, search_status


def send_single_log(message):
    generate_valid_token()
    conn = httplib.HTTPConnection(urlparse(LOG_API_URL).netloc)
    body = simplejson.dumps({'message': message})
    conn.request("POST", SINGLE_LOG_API_URL_PATH, body, headers_post)
    res = conn.getresponse()
    return res.status


def generate_valid_token():
    token_id = token_handler.get_valid_token()
    headers_post["X-Auth-Token"] = token_id


def send_bulk_log(message):
    generate_valid_token()
    conn = httplib.HTTPConnection(urlparse(LOG_API_URL).netloc)
    body = simplejson.dumps({'logs': NUM_Of_LOGS_IN_ONE_BULK * [{'message': message}]})
    conn.request("POST", BULK_URL_PATH, body, headers_post)
    res = conn.getresponse()
    return res.status


def generate_unique_message(message=None, msg_size=50):
    letters = string.ascii_lowercase

    def rand(size):
        return ''.join((random.choice(letters) for _ in range(size)))
    if not message:
        message = rand(msg_size)
    return message


def run_latency_test(res_file):
    thread_name = threading.currentThread().getName()
    latency_check_count = 0
    print("{}: Start Time: {} ".format(thread_name, datetime.datetime.now().strftime("%H:%M:%S.%f")))
    start_time = time.time()
    while time.time() < (start_time + RUNTIME):
        check_start_time = time.time()
        send_status, search_status = check_latency(generate_unique_message(msg_size=LOG_SIZE))
        check_end_time = time.time()
        latency_check_count += 1
        write_latency_check_result(res_file, send_status, search_status, check_start_time, check_end_time, thread_name,
                                   str(latency_check_count))

    final_time = time.time()
    print("-----Test Results-----")
    print("{}: End Time: {}".format(thread_name, thread_name, datetime.datetime.now().strftime("%H:%M:%S.%f")))
    print("{}: {} log entries in {} seconds".format(thread_name, latency_check_count, final_time-start_time))


def write_latency_check_result(res_file, send_status, search_status, start_time, end_time, name, count):
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
        serialize_logging(res_file, result_line)
    else:
        print("{} Time: {}, Send Injector log Failed after: {}"
              .format(name, datetime.datetime.now().strftime("%H:%M:%S.%f"), latency)+" seconds!")


def create_result_file():
    """create file for result then write header line to this file """
    test_info_line = "Log_api_mode: {}, Number of threads: {}, RunTime: {}, Log_size: {}"\
                     .format(LOG_API_TYPE, THREADS_NUM, RUNTIME, LOG_SIZE)
    header_line = "Thread#, Count, Send_Status, Search_Result, Start Time, Stop Time, Latency"
    if LOG_API_TYPE == 'bulk':
        test_info_line += ", Number of logs in one Bulk: {}".format(NUM_Of_LOGS_IN_ONE_BULK)
    res_file = create_file(TEST_NAME)
    write_line_to_file(res_file, test_info_line)
    write_line_to_file(res_file, header_line)
    return res_file

if __name__ == "__main__":
    print("Test Start, :" + str(THREADS_NUM) + " thread(s)")
    result_file = create_result_file()
    q = Queue(THREADS_NUM)
    thread_list = []
    for i in range(THREADS_NUM):
        thread = Thread(target=run_latency_test, args=(result_file,))
        time.sleep(0.3)
        thread.start()
        thread_list.append(thread)

    for thread in thread_list:
        thread.join()
    result_file.close()
