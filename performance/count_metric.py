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
This program count number of metric specified by name in influx database in specified time-frame
"""
import argparse
import datetime
import sys
import yaml
from influxdb import InfluxDBClient
from write_logs import create_file, write_line_to_file

TEST_NAME = 'count_metric'


class CountMetric:
    def __init__(self, influx_address, influx_user, influx_password, influx_database, start_time, end_time,
                 metric_name):
        self.influx_Client = InfluxDBClient(influx_address.split(':')[0], influx_address.split(':')[1],
                                            influx_user, influx_password, influx_database)
        self.start_time = start_time
        self.end_time = end_time
        self.query_time_range = self.prepare_time_range()
        self.metric_name = metric_name

    def prepare_time_range(self):
        time_range = list()
        start_time = self.start_time
        while start_time < self.end_time:
            end_time = start_time + datetime.timedelta(hours=2)
            if end_time > self.end_time:
                time_range.append({'start': start_time, 'end': self.end_time})
            else:
                time_range.append({'start': start_time, 'end': end_time})

            start_time = end_time
        return time_range

    def count_metric(self):
        count = 0
        for query_time in self.query_time_range:
            query = 'select count(value) from \"{}\" WHERE time >= \'{}\' and time < \'{}\''.format(self.metric_name,
                                                                                                    query_time['start'],
                                                                                                    query_time['end'])
            res = self.parse_query_response(self.influx_Client.query(query))
            print ('Metric_number: {}  time start: {} end: {}'.format(res, query_time['start'], query_time['end']))
            count += res
        self.write_result(count)

    def parse_query_response(self, response):
        if len(list(response)) is 0:
            return 0
        else:
            return list(response)[0][0]['count']

    def write_result(self, metric_count):
        print('Total number of metric: {}'.format(metric_count))
        test_result = create_file(TEST_NAME)
        write_line_to_file(test_result, 'start_date:{} end_date:{}'.format(self.start_time, self.end_time))
        write_line_to_file(test_result, 'Total number of metric:{}'.format(metric_count))





def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-mariadb_status', action='store', dest='mariadb_status')
    parser.add_argument('-mariadb_username', action='store', dest='mariadb_username')
    parser.add_argument('-mariadb_password', action='store', dest='mariadb_password', default='')
    parser.add_argument('-mariadb_hostname', action='store', dest='mariadb_hostname')
    parser.add_argument('-mariadb_database', action='store', dest='mariadb_database')
    parser.add_argument('-influx_adder', action='store', dest='influx_adder', type=str)
    parser.add_argument('-influx_usr', action='store', dest='influx_usr', type=str)
    parser.add_argument('-influx_password', action='store', dest='influx_password', type=str)
    parser.add_argument('-influx_database', action='store', dest='influx_database', type=str)
    parser.add_argument('-metric_name', action="store", dest='metric_name')
    parser.add_argument('-start_time', action="store", dest='start_time')
    parser.add_argument('-end_time', action="store", dest='end_time')

    return parser.parse_args()


if __name__ == "__main__":
    if len(sys.argv) <= 1:
        TEST_CONF = yaml.load(file('test_configuration.yaml'))
        BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
        MARIADB_STATUS = BASIC_CONF['mariadb']['status']
        MARIADB_USERNAME = BASIC_CONF['mariadb']['user']
        MARIADB_PASSWORD = BASIC_CONF['mariadb']['password'] \
            if BASIC_CONF['mariadb']['password'] is not None else ''
        MARIADB_HOSTNAME = BASIC_CONF['mariadb']['hostname']
        MARIADB_DATABASE = BASIC_CONF['mariadb']['database']
        INFLUX_ADDRESS = BASIC_CONF['url']['influxdb']
        INFLUX_USER = BASIC_CONF['influxdb']['user']
        INFLUX_PASSWORD = BASIC_CONF['influxdb']['password']
        INFLUX_DATABASE = BASIC_CONF['influxdb']['database']
        STAT_TIME = TEST_CONF[TEST_NAME]['start_time']
        END_TIME = TEST_CONF[TEST_NAME]['end_time']
        METRIC_NAME = TEST_CONF[TEST_NAME]['metric_name']
    else:
        program_argument = create_program_argument_parser()
        MARIADB_STATUS = program_argument.mariadb_status
        MARIADB_USERNAME = program_argument.mariadb_username
        MARIADB_PASSWORD = program_argument.mariadb_password
        MARIADB_HOSTNAME = program_argument.mariadb_hostname
        MARIADB_DATABASE = program_argument.mariadb_database
        INFLUX_URL = program_argument.influx_url
        INFLUX_USER = program_argument.influx_usr
        INFLUX_PASSWORD = program_argument.influx_password
        INFLUX_DATABASE = program_argument.influx_database
        STAT_TIME = program_argument.star_time
        END_TIME = program_argument.end_time
        METRIC_NAME = program_argument.metric_name

    count_metric = CountMetric(INFLUX_ADDRESS, INFLUX_USER, INFLUX_PASSWORD, INFLUX_DATABASE, STAT_TIME, END_TIME,
                               METRIC_NAME)
    count_metric.count_metric()

