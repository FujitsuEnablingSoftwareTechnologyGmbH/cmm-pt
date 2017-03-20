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
import MySQLdb
import sys
import time
import yaml
import threading
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from write_logs import create_file, serialize_logging
import db_saver

TEST_NAME = 'metric_throughput'
BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
MARIADB_HOSTNAME = BASIC_CONF['mariadb']['hostname']
MARIADB_USERNAME = BASIC_CONF['mariadb']['user']
MARIADB_PASSWORD = BASIC_CONF['mariadb']['password'] if BASIC_CONF['mariadb']['password'] is not None else ''
MARIADB_DATABASE = BASIC_CONF['mariadb']['database']


class MetricThroughput(threading.Thread):

    def __init__(self, influx_url, influx_port, influx_user, influx_password, influx_database, runtime, ticker,
                 ticker_to_stop, metric_name, metric_dimension, mariadb_status, mariadb_username=None,
                 mariadb_password=None, mariadb_hostname=None, mariadb_database=None, testCaseID=1):
        threading.Thread.__init__(self)
        self.mariadb_status = mariadb_status
        self.influx_ip = influx_url
        self.influx_port = influx_port
        self.influx_user = influx_user
        self.influx_password = influx_password
        self.influx_database = influx_database
        self.runtime = runtime
        self.ticker = ticker
        self.ticker_to_stop = ticker_to_stop
        self.metric_name = metric_name
        self.metric_dimensions = metric_dimension
        self.results_file = self.create_result_file()
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
                self.test_results = list()
                self.test_params = list()
                db.close()
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()

    def create_query(self):
        """create influx select query that return number of test metric """
        dimensions = []
        for dimension in self.metric_dimensions:
            dimensions.append("{} = \'{}\'".format(dimension['key'], dimension['value']))
        current_utc_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        return "select count(value) from \"{0}\" WHERE time > \'{1}\' AND {2}"\
            .format(self.metric_name, current_utc_time, " AND ".join(dimensions))

    def write_result_to_file(self, metric_difference, total_metric, metric_per_sec):
        current_time = datetime.datetime.now().strftime("%H:%M:%S.%f")
        print("Time: {}; count: {} = {} per second".format(current_time, total_metric, metric_per_sec))
        serialize_logging(self.results_file, str(current_time) + ',' + str(total_metric) +
                          ',' + str(metric_difference) + ',' + str(metric_per_sec))
        if self.mariadb_status == 'enabled':
            return ["throughput", metric_per_sec,
                    datetime.datetime.now().replace(microsecond=0)]

    def write_final_result_line_to_file(self, total_number_of_metric):
        result_line = "Metric received: {}".format(total_number_of_metric)
        print result_line
        serialize_logging(self.results_file, result_line)

    def create_result_file(self):
        res_file = create_file("{}_{}_".format(TEST_NAME, self.metric_name))
        serialize_logging(res_file, "Time, difference, count, metric per sec")
        return res_file

    def get_count_value_from_query_response(self, response):
        """function parse response from influx and return int value  """
        if len(list(response)) is 0:
            return 0
        else:
            return list(response)[0][0]['count']

    def run(self):

        query = self.create_query()
        strt_time = datetime.datetime.now().replace(microsecond=0)
        client = InfluxDBClient(self.influx_ip, self.influx_port, self.influx_user, self.influx_password,
                                self.influx_database)
        count = 0
        start_time = time.time()
        count_ticker_to_stop = 0
        query_time = 0
        count_different = 0
        last_query_time = time.time()
        while True:

            try:
                time_before_query = time.time()
                query_response = client.query(query)
                count_after_request = self.get_count_value_from_query_response(query_response)
                count_different = count_after_request - count
                count = count_after_request
                time_after_query = time.time()
                query_time = time_after_query - time_before_query
                if self.mariadb_status == 'enabled':
                    self.test_results.append(
                        self.write_result_to_file(
                            count, count_different, count_different / (time_after_query - last_query_time)))
                else:
                    self.write_result_to_file(count, count_different, count_different /
                                              (time_after_query - last_query_time))
                last_query_time = time.time()
            except InfluxDBClientError as e:

                print str(e)

            if time.time() > (start_time + self.runtime):

                if int(count_different) is 0:
                    count_ticker_to_stop += 1

                    if count_ticker_to_stop > self.ticker_to_stop:
                        break
                else:
                    count_ticker_to_stop = 0
            if self.ticker > query_time:
                time.sleep(self.ticker - query_time)
        self.write_final_result_line_to_file(count)
        if self.mariadb_status == 'enabled':
            self.test_params = [['start_time', str(strt_time)],
                                ['end_time', str(datetime.datetime.now().replace(microsecond=0))],
                                ['metric_name', str(self.metric_name)],
                                ['runtime', str(self.runtime)],
                                ['total_logs',str(count)]]
            db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                 self.mariadb_password, self.mariadb_database)
            db_saver.save_test_params(db, self.testID, self.test_params)
            db_saver.save_test_results(db, self.testID, self.test_results)
            db.close()


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-mariadb_status', action='store', dest='mariadb_status')
    parser.add_argument('-mariadb_username', action='store', dest='mariadb_username')
    parser.add_argument('-mariadb_password', action='store', dest='mariadb_password')
    parser.add_argument('-mariadb_hostname', action='store', dest='mariadb_hostname')
    parser.add_argument('-mariadb_database', action='store', dest='mariadb_database')
    parser.add_argument('-influx_url', action='store', dest='influx_url', type=str)
    parser.add_argument('-influx_usr', action='store', dest='influx_usr', type=str)
    parser.add_argument('-influx_password', action='store', dest='influx_password', type=str)
    parser.add_argument('-influx_database', action='store', dest='influx_database', type=str)
    parser.add_argument('-runtime', action='store', dest='runtime', type=int)
    parser.add_argument('-ticker', action='store', dest='ticker', type=float)
    parser.add_argument('-ticker_to_stop', action='store', dest='ticker_to_stop', type=int)
    parser.add_argument('-metric_name', action='store', dest='metric_name', type=str)
    parser.add_argument('-dimensions', action='store', dest='dimensions', nargs='+')
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
        INFLUX_URL = BASIC_CONF['url']['influxdb']
        INFLUX_USER = BASIC_CONF['influxdb']['user']
        INFLUX_PASSWORD = BASIC_CONF['influxdb']['password']
        INFLUX_DATABASE = BASIC_CONF['influxdb']['database']
        RUNTIME = TEST_CONF[TEST_NAME]['runtime']
        TICKER = TEST_CONF[TEST_NAME]['ticker']
        TICKER_TO_STOP = TEST_CONF[TEST_NAME]['ticker_to_stop']
        METRIC_NAME = TEST_CONF[TEST_NAME]['metric_name']
        METRIC_DIMENSIONS = TEST_CONF[TEST_NAME]['metric_dimensions']
    else:
        program_argument = create_program_argument_parser()
        MARIADB_STATUS = program_argument.mariadb_status
        MARIADB_USERNAME = program_argument.mariadb_username
        MARIADB_PASSWORD = program_argument.mariadb_password \
            if program_argument.mariadb_password is not None else ''
        MARIADB_HOSTNAME = program_argument.mariadb_hostname
        MARIADB_DATABASE = program_argument.mariadb_database
        INFLUX_URL = program_argument.influx_url
        INFLUX_USER = program_argument.influx_usr
        INFLUX_PASSWORD = program_argument.influx_password
        INFLUX_DATABASE = program_argument.influx_database
        RUNTIME = program_argument.runtime
        TICKER = program_argument.ticker
        TICKER_TO_STOP = program_argument.ticker_to_stop
        METRIC_NAME = program_argument.metric_name
        METRIC_DIMENSIONS = [{'key': dimension[0], 'value': dimension[1]} for dimension in
                             [dimension.split(':') for dimension in program_argument.dimensions]]

    metric_throughput = MetricThroughput(INFLUX_URL.split(':')[0], INFLUX_URL.split(':')[1], INFLUX_USER,
                                         INFLUX_PASSWORD, INFLUX_DATABASE, RUNTIME, TICKER, TICKER_TO_STOP,
                                         METRIC_NAME, METRIC_DIMENSIONS, MARIADB_STATUS, MARIADB_USERNAME,
                                         MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE)
    metric_throughput.start()





