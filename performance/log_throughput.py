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
import time
import search_logs
import sys
import yaml
from write_logs import create_file, write_line_to_file, serialize_logging
from urlparse import urlparse


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-tenant_project', action="store", dest='tenant_project')
    parser.add_argument('-elastic_url', action="store", dest='elastic_url')
    parser.add_argument('-runtime', action="store", dest='runtime', type=int)
    parser.add_argument('-search_field', action="store", dest='search_field')
    parser.add_argument('-search_string', action="store", dest='search_string', nargs='*')
    parser.add_argument('-num_stop', action="store", dest='num_stop', type=int)
    parser.add_argument('-ticker', action="store", dest='ticker', type=int)

    return parser.parse_args()

TEST_NAME = "log_throughput"
if len(sys.argv) <= 1:
    TEST_CONF = yaml.load(file('test_configuration.yaml'))
    BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
    TENANT_PROJECT = BASIC_CONF['users']['tenant_project']
    RUNTIME = TEST_CONF[TEST_NAME]['runtime']
    TICKER = TEST_CONF[TEST_NAME]['ticker']
    ELASTIC_URL = urlparse(BASIC_CONF['url']['elastic_url']).netloc
    SEARCH_STRING_LIST = TEST_CONF[TEST_NAME]['search_string']
    NUM_TO_STOP = TEST_CONF[TEST_NAME]['num_stop']
    SEARCH_FIELD = TEST_CONF[TEST_NAME]['search_field']
else:
    program_argument = create_program_argument_parser()
    TENANT_PROJECT = program_argument.tenant_project
    ELASTIC_URL = urlparse(program_argument.elastic_url).netloc
    RUNTIME = program_argument.runtime
    TICKER = program_argument.ticker
    SEARCH_STRING_LIST = program_argument.search_string
    SEARCH_FIELD = program_argument.search_field
    NUM_TO_STOP = program_argument.num_stop


def count_log_entries(search_str):
    """this function return number of specified log entries from elasticsearch database
    """
    if SEARCH_FIELD == "application_name":
        num_found, status = search_logs.count_logs_by_app_name(search_str, ELASTIC_URL)
    elif SEARCH_FIELD == "application_type":
        num_found, status = search_logs.count_logs_by_app_type(search_str, ELASTIC_URL)
    else:
        num_found, status = search_logs.count_logs_by_app_message(search_str, ELASTIC_URL)
    return num_found, status


def run_throughput_check():
    """start test that check number of specified logs in database in every x seconds
    """
    result_file = create_result_file()
    log_check_count = 0
    number_of_log_check_with_the_same_log_number = 0
    test_start_time = time.time()
    initial_number_of_log_list = [0] * len(SEARCH_STRING_LIST)
    different_log_entries_list = [0] * len(SEARCH_STRING_LIST)

    for index, search_string in enumerate(SEARCH_STRING_LIST):
        initial_number_of_log_list[index], status = count_log_entries(search_string)
    number_of_log_in_last_request_list = list(initial_number_of_log_list)
    previous_log_check_time = time.time()
    time.sleep(TICKER)

    while True:
        for index, search_string in enumerate(SEARCH_STRING_LIST):
            check_result, status = count_log_entries(search_string)
            different_log_entries_list[index] = check_result - number_of_log_in_last_request_list[index]
            number_of_log_in_last_request_list[index] = check_result
            print ("search_string:{} num_found:{} difference:{}".
                   format(search_string, check_result, different_log_entries_list[index]))
        log_check_count += 1
        log_check_time = time.time()
        save_result_log_to_file(result_file, status, log_check_time, previous_log_check_time, different_log_entries_list)
        previous_log_check_time = log_check_time
        if sum(different_log_entries_list) == 0:
            if time.time() > (test_start_time + RUNTIME - TICKER):
                number_of_log_check_with_the_same_log_number += 1
                if number_of_log_check_with_the_same_log_number > NUM_TO_STOP:
                    break
        else:
            number_of_log_check_with_the_same_log_number = 0
              
        time.sleep(TICKER - ((time.time() - log_check_time) % TICKER))
    test_end_time = time.time()
    print("-----Test Results----- :" + TEST_NAME)
    print("End Time: ", datetime.datetime.now().strftime("%H:%M:%S.%f"))
    for index, search_string in enumerate(SEARCH_STRING_LIST):
        print("{}:{} log entries in {} seconds"
              .format(search_string, number_of_log_in_last_request_list[index] - initial_number_of_log_list[index],
                      test_end_time - test_start_time))
        serialize_logging(result_file, "total logs=" +
                          str(number_of_log_in_last_request_list[index] - initial_number_of_log_list[index]))


def save_result_log_to_file(result_file, count_status, count_time, last_count_time, num_entries_list):
    duration_secs = count_time - last_count_time
    my_logger = "{}, {}, {}"\
        .format(count_status, time.strftime('%H:%M:%S', time.localtime(count_time)), (round(duration_secs, 2)))
    for index, search_string in enumerate(SEARCH_STRING_LIST):
        my_logger += ", {}, {}".format(str(num_entries_list[index]), round((num_entries_list[index] / duration_secs), 2))
    serialize_logging(result_file, my_logger)


def create_result_file():
    """create result file and save header line to this file """
    header_line = "Request_status, throughput_check_timestamp, duration_sec"
    res_file = create_file(TEST_NAME)
    for search_string in SEARCH_STRING_LIST:
        header_line = "{}, {} count, {} Log Entries Per Sec".format(header_line, search_string, search_string)
        write_line_to_file(res_file, header_line)
    return res_file


if __name__ == "__main__":
    print("Start Time: {} ".format(datetime.datetime.now().strftime("%H:%M:%S.%f")))
    run_throughput_check()
