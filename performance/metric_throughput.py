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
this program is used to measure the metric throughput directly in influx. Specified query requests are sent
to count the number of metric entries that have been added to the db after specified date.
Metrics are searched for using metric name.
After each query, the difference in the number of metric entries found is determined, thus the throughput.
All test result are writen to the file.
"""

import argparse
import datetime
import sys
import time
import yaml
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from write_logs import create_file, serialize_logging


TEST_NAME = 'metric_throughput'


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-influx_url', action="store", dest='influx_url', type=str)
    parser.add_argument('-influx_usr', action="store", dest='influx_usr', type=str)
    parser.add_argument('-influx_password', action="store", dest='influx_password', type=str)
    parser.add_argument('-influx_database', action="store", dest='influx_database', type=str)
    parser.add_argument('-runtime', action="store", dest='runtime', type=int)
    parser.add_argument('-ticker', action="store", dest='ticker', type=float)
    parser.add_argument('-ticker_to_stop', action="store", dest='ticker_to_stop', type=int)
    parser.add_argument('-metric_name', action="store", dest='metric_name', type=str)
    return parser.parse_args()

if len(sys.argv) <= 1:
    TEST_CONF = yaml.load(file('test_configuration.yaml'))
    BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
    INFLUX_URL = BASIC_CONF['url']['influxdb']
    INFLUX_USER = BASIC_CONF['influxdb']['user']
    INFLUX_PASSWORD = BASIC_CONF['influxdb']['password']
    INFLUX_DATABASE = BASIC_CONF['influxdb']['database']
    RUNTIME = TEST_CONF[TEST_NAME]['runtime']
    TICKER = TEST_CONF[TEST_NAME]['ticker']
    TICKER_TO_STOP = TEST_CONF[TEST_NAME]['ticker_to_stop']
    METRIC_NAME = TEST_CONF[TEST_NAME]['metric_name']
else:
    program_argument = create_program_argument_parser()
    INFLUX_URL = program_argument.influx_url
    INFLUX_USER = program_argument.influx_usr
    INFLUX_PASSWORD = program_argument.influx_password
    INFLUX_DATABASE = program_argument.influx_database
    RUNTIME = program_argument.runtime
    TICKER = program_argument.ticker
    TICKER_TO_STOP = program_argument.ticker_to_stop
    METRIC_NAME = program_argument.metric_name


def create_query():
    """create influx select query that return number of test metric """
    current_utc_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return "select count(value) from \"{0}\" WHERE time > \'{1}\'".format(METRIC_NAME, current_utc_time)


def write_result_to_file(log_file, metric_difference, total_metric, metric_per_sec):
    current_time = datetime.datetime.now().strftime("%H:%M:%S.%f")
    print("Time: {}; count: {} = {} per second".format(current_time, total_metric, metric_per_sec))
    serialize_logging(log_file, str(current_time) + ',' + str(total_metric) +
                      ',' + str(metric_difference) + ',' + str(metric_per_sec))


def writ_header_to_file(log_file):
    serialize_logging(log_file, "Time, difference, count, metric per sec")


def get_count_value_from_query_response(response):
    """function parse response from influx and return int value  """
    if len(list(response)) is 0:
        return 0
    else:
        return list(response)[0][0]['count']


if __name__ == "__main__":

    results_file = create_file(TEST_NAME)
    writ_header_to_file(results_file)
    query = create_query()
    client = InfluxDBClient(INFLUX_URL.split(':')[0], INFLUX_URL.split(':')[1], INFLUX_USER, INFLUX_PASSWORD, INFLUX_DATABASE)
    count = 0
    start_time = time.time()
    time_before_query = start_time
    count_ticker_to_stop = 0
    query_time = 0
    last_query_time = time.time()
    while True:

        try:
            time_before_query = time.time()
            query_response = client.query(query)
            count_after_request = get_count_value_from_query_response(query_response)
            count_different = count_after_request - count
            count = count_after_request
            time_after_query = time.time()
            query_time = time_after_query - time_before_query
            write_result_to_file(results_file, count, count_different,
                                 count_different / (time_after_query - last_query_time))
            last_query_time = time.time()
        except InfluxDBClientError as e:

            print str(e)

        if time.time() > (start_time + RUNTIME):

            if count_different is 0:
                count_ticker_to_stop += 1

                if count_ticker_to_stop > TICKER_TO_STOP:
                    break
            else:
                count_ticker_to_stop = 0
        if TICKER > query_time:
            time.sleep(TICKER - query_time)








