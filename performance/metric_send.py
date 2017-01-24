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
import httplib
import random
import simplejson
import sys
import time
import TokenHandler
import yaml
from urlparse import urlparse
from multiprocessing import Process, Queue
from write_logs import create_file, write_line_to_file


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
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
    parser.add_argument('-daley', action="store", dest='delay', type=int, required=False)
    return parser.parse_args()

TEST_NAME = 'metric_send'
if len(sys.argv) <= 1:
    TEST_CONF = yaml.load(file('test_configuration.yaml'))
    BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
    METRIC_API_URL = BASIC_CONF['url']['metrics_api'] + "/metrics"
    KEYSTONE_URL = BASIC_CONF['url']['keystone']
    TENANT_CREDENTIAL = {"name": BASIC_CONF['users']['tenant_name'],
                         "password": BASIC_CONF['users']['tenant_password'],
                         "project": BASIC_CONF['users']['tenant_project']}

    NUM_THREADS = TEST_CONF[TEST_NAME]['num_threads']
    NUM_METRIC_PER_REQUEST = TEST_CONF[TEST_NAME]['num_metrics_per_request']
    LOG_EVERY_N = TEST_CONF[TEST_NAME]['LOG_EVERY_N']
    RUNTIME = TEST_CONF[TEST_NAME]['runtime']
    FREQUENCY = TEST_CONF[TEST_NAME]['ticker']
    METRIC_NAME = TEST_CONF[TEST_NAME]['metric_name']
    METRIC_DIMENSION = TEST_CONF[TEST_NAME]['metric_dimension']
    DELAY = None
else:
    program_argument = create_program_argument_parser()
    KEYSTONE_URL = program_argument.keystone_url
    TENANT_CREDENTIAL = {"name": program_argument.tenant_name,
                         "password": program_argument.tenant_password,
                         "project": program_argument.tenant_project}
    METRIC_API_URL = program_argument.metric_api_url + "/metrics"
    NUM_THREADS = program_argument.num_threads
    NUM_METRIC_PER_REQUEST = program_argument.num_metric_per_request
    LOG_EVERY_N = program_argument.log_every_n
    RUNTIME = program_argument.runtime
    FREQUENCY = program_argument.frequency
    METRIC_NAME = program_argument.metric_name
    METRIC_DIMENSION = [{'key': 'test', 'value': 'systemTest'}]
    DELAY = program_argument.delay

TOKEN_HANDLER = TokenHandler.TokenHandler(TENANT_CREDENTIAL['name'],
                                          TENANT_CREDENTIAL['password'],
                                          TENANT_CREDENTIAL['project'],
                                          KEYSTONE_URL)

headers = {"Content-type": "application/json"}


def create_metric_body(process_id):
    """Create json metric request body that contain fallowing filed:
    name, dimension, timestamp and value """
    multiple_metric_body = []
    current_utc_time = int((round(time.time() * 1000)))
    for i in range(NUM_METRIC_PER_REQUEST):
        dimensions = {}
        for dimension in METRIC_DIMENSION:
            dimensions[dimension['key']] = dimension['value']
        dimensions['count'] = process_id + "_" + str(i)
        multiple_metric_body.append({"name": METRIC_NAME, "dimensions": dimensions,
                                     "timestamp": current_utc_time, "value": random.randint(0, 100)})
    return multiple_metric_body


def send_metrics(process_id, url_parse, conn):
    headers["X-Auth-Token"] = TOKEN_HANDLER.get_valid_token()
    body = simplejson.dumps(create_metric_body(process_id))
    conn.request("POST", url_parse.path, body, headers)
    request_response = conn.getresponse()
    request_status = request_response.status
    request_response.read()
    return request_status


def run_metric_test(process_id, num_of_sent_metric_queue, result_file):
    print process_id
    start_time = time.time()
    count_metric_request_sent = 0
    time_before_logging = start_time
    url_parse = urlparse(METRIC_API_URL)
    connection = httplib.HTTPConnection(url_parse.netloc)
    while time.time() < (start_time + RUNTIME):

        time_before_request = time.time()
        request_status = send_metrics(process_id, url_parse, connection)

        if request_status is 204:

            count_metric_request_sent += 1
            if count_metric_request_sent % LOG_EVERY_N is 0:

                time_after_logging = time.time()
                print("{}: count: {} = {} per second"
                      .format(process_id, count_metric_request_sent * NUM_METRIC_PER_REQUEST,
                              LOG_EVERY_N * NUM_METRIC_PER_REQUEST / (time_after_logging - time_before_logging)))
                time_before_logging = time.time()

            time_after_request = time.time()

            sleep_time = (1.0 / FREQUENCY) - (time_after_request - time_before_request)
            if sleep_time > 0:
                time.sleep(sleep_time)
        else:

            print "Failed to send metric. Error code: " + str(request_status)
    stop_time = time.time()
    total_metric_send = count_metric_request_sent * NUM_METRIC_PER_REQUEST
    test_duration = stop_time - start_time
    metric_send_per_sec = total_metric_send / test_duration
    write_line_to_file(result_file, "{} , {} , {} , {} , {} , {}"
                       .format(process_id, time.strftime('%H:%M:%S', time.localtime(start_time)),
                               time.strftime('%H:%M:%S', time.localtime(stop_time)), total_metric_send,
                               test_duration, metric_send_per_sec))
    num_of_sent_metric_queue.put(count_metric_request_sent * NUM_METRIC_PER_REQUEST)
    return


def create_result_file():
    """create result file and save header line to this file """
    res_file = create_file(TEST_NAME)
    header_line = ("Thread#, Start Time, Stop Time, #sent Metrics, "
                   "Used Time, Average per second ,Number of threads: {}")
    write_line_to_file(res_file, header_line)
    return res_file


def write_final_result_line_to_file(metric_send):
    print "Total metric send =" + str(metric_send)
    write_line_to_file(result_file,
                       "Total metric send = {}\nNumber of metrics per request: {} Number of threads: {}".
                       format(metric_send, NUM_METRIC_PER_REQUEST, NUM_THREADS))


if __name__ == "__main__":
    if DELAY is not None:
        print "wait {}s before starting test".format(DELAY)
        time.sleep(DELAY)
    process_list = []
    total_num_metric_sent_queue = Queue()
    result_file = create_result_file()
    for i in range(NUM_THREADS):
        process = Process(target=run_metric_test,
                          args=("Process-{}".format(i), total_num_metric_sent_queue, result_file, ))
        process.daemon = True
        process.start()
        process_list.append(process)

    total_metric_send = 0
    for process in process_list:
        process.join()
        total_metric_send += total_num_metric_sent_queue.get()

    write_final_result_line_to_file(total_metric_send)
    result_file.close()

