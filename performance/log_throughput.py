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
This program is used to measure the throughput directly in elasticsearch.
"_count" query requests are sent to count the number of log entries that have been added to the database.
log entries are searched for using applicationname. Currently only one applicationname can be searched for.
The ticker specifies the number of seconds between count queries.
After each query, the difference in the number of log entries found is determined, thus the throughput.
The logfile written contains this information.
"""

import argparse
import datetime
import MySQLdb
import time
import threading
import search_logs
import sys
import yaml
from write_logs import create_file, write_line_to_file, serialize_logging
from urlparse import urlparse
import db_saver

TEST_NAME = "log_throughput"
BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
MARIADB_HOSTNAME = BASIC_CONF['mariadb']['hostname']
MARIADB_USERNAME = BASIC_CONF['mariadb']['user']
MARIADB_PASSWORD = BASIC_CONF['mariadb']['password'] if BASIC_CONF['mariadb']['password'] is not None else ''
MARIADB_DATABASE = BASIC_CONF['mariadb']['database']


class LogThroughput(threading.Thread):
    def __init__(self, tenant_project, elastic_url, runtime, ticker,
                 search_string_list, search_field, num_to_stop, mariadb_status, mariadb_username=None,
                 mariadb_password=None, mariadb_hostname=None, mariadb_database=None, testCaseID=1):
        threading.Thread.__init__(self)
        self.mariadb_status = mariadb_status
        self.tenant_project = tenant_project
        self.elastic_url = elastic_url
        self.runtime = runtime
        self.ticker = ticker
        self.search_string_list = search_string_list
        self.search_field = search_field
        self.num_to_stop = num_to_stop
        self.result_file = self.create_result_file()
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
                self.test_params = list()
                db.close()
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()

    def count_log_entries(self, search_str):
        """this function return number of specified log entries from elasticsearch database
        """
        if self.search_field == "application_name":
            num_found, status = search_logs.count_logs_by_app_name(search_str, self.elastic_url)
        elif self.search_field == "application_type":
            num_found, status = search_logs.count_logs_by_app_type(search_str, self.elastic_url)
        else:
            num_found, status = search_logs.count_logs_by_app_message(search_str, self.elastic_url)
        return num_found, status

    def run(self):
        """start test that check number of specified logs in database in every x seconds
        """
        log_check_count = 0
        number_of_log_check_with_the_same_log_number = 0
        test_start_time = time.time()
        start_time = datetime.datetime.now().replace(microsecond=0)
        initial_number_of_log_list = [0] * len(self.search_string_list)
        different_log_entries_list = [0] * len(self.search_string_list)

        for index, search_string in enumerate(self.search_string_list):
            initial_number_of_log_list[index], status = self.count_log_entries(search_string)
        number_of_log_in_last_request_list = list(initial_number_of_log_list)
        previous_log_check_time = time.time()
        time.sleep(self.ticker)
        testresults = list()
        while True:
            for index, search_string in enumerate(self.search_string_list):
                check_result, status = self.count_log_entries(search_string)
                different_log_entries_list[index] = check_result - number_of_log_in_last_request_list[index]
                number_of_log_in_last_request_list[index] = check_result
                print ("search_string:{} num_found:{} difference:{}".
                       format(search_string, check_result, different_log_entries_list[index]))
            log_check_count += 1
            log_check_time = time.time()
            if self.mariadb_status == 'enabled':
                testresults.append(
                    self.save_result_log_to_file(
                        status, log_check_time, previous_log_check_time, different_log_entries_list))
            else:
                self.save_result_log_to_file(status, log_check_time, previous_log_check_time, different_log_entries_list)
            previous_log_check_time = log_check_time
            if sum(different_log_entries_list) == 0:
                if time.time() > (test_start_time + self.runtime - self.ticker):
                    number_of_log_check_with_the_same_log_number += 1
                    if number_of_log_check_with_the_same_log_number > self.num_to_stop:
                        break
            else:
                number_of_log_check_with_the_same_log_number = 0

            time.sleep(self.ticker - ((time.time() - log_check_time) % self.ticker))
        test_end_time = time.time()
        print("-----Test Results----- :" + TEST_NAME)
        print("End Time: ", datetime.datetime.now().strftime("%H:%M:%S.%f"))
        if self.mariadb_status == 'enabled':
            db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                 self.mariadb_password, self.mariadb_database)
            end_time = datetime.datetime.now().replace(microsecond=0)
            db_saver.save_test_results(db, self.testID, testresults)
            db.close
        for index, search_string in enumerate(self.search_string_list):
            print("{}:{} log entries in {} seconds"
                  .format(search_string, number_of_log_in_last_request_list[index] - initial_number_of_log_list[index],
                          test_end_time - test_start_time))
            serialize_logging(self.result_file, "total logs={}".
                              format(str(number_of_log_in_last_request_list[index] - initial_number_of_log_list[index])))
        if self.mariadb_status == 'enabled':
            db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                 self.mariadb_password, self.mariadb_database)
            self.test_params = [['total_logs', str(number_of_log_in_last_request_list[index] - initial_number_of_log_list[index])],
                                ['start_time', str(start_time)],
                                ['end_time', str(end_time)],
                                ['runtime', str(self.runtime)]]
            db_saver.save_test_params(db, self.testID, self.test_params)
            db.close()

    def save_result_log_to_file(self, count_status, count_time, last_count_time, num_entries_list):
        duration_secs = count_time - last_count_time
        my_logger = "{}, {}, {}"\
            .format(count_status, time.strftime('%H:%M:%S', time.localtime(count_time)), (round(duration_secs, 2)))
        for index, search_string in enumerate(self.search_string_list):
            my_logger += ", {}, {}".format(str(num_entries_list[index]),
                                           round((num_entries_list[index] / duration_secs), 2))
        serialize_logging(self.result_file, my_logger)
        if self.mariadb_status == 'enabled':
            return ["throughput", round((num_entries_list[index] / duration_secs), 2),
                    datetime.datetime.now().replace(microsecond=0)]

    def create_result_file(self):
        """create result file and save header line to this file """
        header_line = "Request_status, throughput_check_timestamp, duration_sec"
        res_file = create_file(TEST_NAME)
        for search_string in self.search_string_list:
            header_line = "{}, {} count, {} Log Entries Per Sec".format(header_line, search_string, search_string)
            write_line_to_file(res_file, header_line)
        return res_file


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-mariadb_status', action='store', dest='mariadb_status')
    parser.add_argument('-mariadb_username', action='store', dest='mariadb_username')
    parser.add_argument('-mariadb_password', action='store', dest='mariadb_password')\
        if BASIC_CONF['mariadb']['password'] is not None else ''
    parser.add_argument('-mariadb_hostname', action='store', dest='mariadb_hostname')
    parser.add_argument('-mariadb_database', action='store', dest='mariadb_database')
    parser.add_argument('-tenant_project', action="store", dest='tenant_project')
    parser.add_argument('-elastic_url', action="store", dest='elastic_url')
    parser.add_argument('-runtime', action="store", dest='runtime', type=int)
    parser.add_argument('-search_field', action="store", dest='search_field')
    parser.add_argument('-search_string', action="store", dest='search_string', nargs='*')
    parser.add_argument('-num_stop', action="store", dest='num_stop', type=int)
    parser.add_argument('-ticker', action="store", dest='ticker', type=int)
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
        TENANT_PROJECT = BASIC_CONF['users']['tenant_project']
        ELASTIC_URL = urlparse(BASIC_CONF['url']['elastic_url']).netloc
        RUNTIME = TEST_CONF[TEST_NAME]['runtime']
        TICKER = TEST_CONF[TEST_NAME]['ticker']
        SEARCH_STRING_LIST = TEST_CONF[TEST_NAME]['search_string']
        NUM_TO_STOP = TEST_CONF[TEST_NAME]['num_stop']
        SEARCH_FIELD = TEST_CONF[TEST_NAME]['search_field']
    else:
        program_argument = create_program_argument_parser()
        MARIADB_STATUS = program_argument.mariadb_status
        MARIADB_USERNAME = program_argument.mariadb_username
        MARIADB_PASSWORD = program_argument.mariadb_password
        MARIADB_HOSTNAME = program_argument.mariadb_hostname
        MARIADB_DATABASE = program_argument.mariadb_database
        TENANT_PROJECT = program_argument.tenant_project
        ELASTIC_URL = urlparse(program_argument.elastic_url).netloc
        RUNTIME = program_argument.runtime
        TICKER = program_argument.ticker
        SEARCH_STRING_LIST = program_argument.search_string
        SEARCH_FIELD = program_argument.search_field
        NUM_TO_STOP = program_argument.num_stop
    print("Start Time: {} ".format(datetime.datetime.now().strftime("%H:%M:%S.%f")))

    log_throughput = LogThroughput(TENANT_PROJECT, ELASTIC_URL, RUNTIME, TICKER, SEARCH_STRING_LIST, SEARCH_FIELD,
                                   NUM_TO_STOP, MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                   MARIADB_DATABASE)
    log_throughput.start()
