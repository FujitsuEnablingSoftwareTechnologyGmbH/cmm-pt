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
This program write specific sized and marked log entries in to the log file
Once a log entry is write  to the file that is monitored by monasca-log-agent the test starts reading the just sent log
entry from the Elasticsearch API.
The time it takes from write  until retrieving the same entry via the Elasticsearch API is measured.
"""
import logging
import search_logs
import time
import threading
import random
import os
import string
import yaml
from urlparse import urlparse
from write_logs import create_file, write_line_to_file

TEST_NAME = "logagent_latency"


class LatencyTest(threading.Thread):
    def __init__(self, elastic_url, check_ticker, search_ticker, check_timeout, runtime, log_file, log_directory, log_level,
                 msg_size):
        threading.Thread.__init__(self, )
        self.elastic_url = elastic_url
        self.log_directory = log_directory
        self.log_file = log_file
        self.log_level = log_level
        self.msg_size = msg_size
        self.result_file = self.create_result_file()
        self.check_ticker = check_ticker
        self.search_ticker = search_ticker
        self.check_timeout = check_timeout
        self.runtime = runtime
        self.logger = self.create_logger()

    def run(self):

        print " Start checking latency for {}".format(self.log_file)
        test_start_time = time.time()
        count = 0
        while test_start_time + self.runtime > time.time():
            count += 1
            msg = self.generate_unique_message()
            self.write_log_to_file(msg)
            write_log_time = time.time()
            search_status = self.search_logs_in_elastic(message=msg)
            latency_time = '{0:.2f}'.format(time.time() - write_log_time)
            if search_status is 'OK':
                print 'COUNT: {} | FILE: {} | TIME: {} | Log Found. Latency = {} s'.\
                    format(count, self.log_file, time.strftime('%H:%M:%S ', time.localtime()), latency_time)
                self.write_latency_result(write_log_time, search_status, latency_time)
            else:
                print 'COUNT :{} | FILE: {} | TIME: {} | Failed to find log in {} s'. \
                    format(count,  self.log_file, time.strftime('%H:%M:%S ', time.localtime()), self.check_timeout)
                self.write_latency_result(write_log_time, search_status, '__')
            time.sleep(self.check_ticker)

    def generate_unique_message(self):
        letters = string.ascii_lowercase

        def rand(msg_size):
            return ''.join((random.choice(letters) for _ in range(msg_size)))

        message = rand(self.msg_size)
        return message

    def create_logger(self):
        logger = logging.getLogger(self.log_file)
        log_handler = logging.FileHandler(os.path.join(self.log_directory, self.log_file))
        log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        log_handler.setFormatter(log_formatter)
        logger.addHandler(log_handler)
        logger.setLevel(logging.DEBUG)
        return logger

    def write_log_to_file(self, msg):

        self.logger.log(logging.getLevelName(self.log_level), msg)

    def search_logs_in_elastic(self, message):
        """this function search logs entry that contain specified message in database,
        If function find expected log entry will return 'OK' message,
        If function could not find all expected log entry in specified time will return FAILED string
        Parameters:
            message :searched message in log
        """
        timeout = time.time() + self.check_timeout
        while time.time() < timeout:
            if search_logs.count_logs_by_app_message(message, self.elastic_url)[0] > 0:
                return 'OK'
            time.sleep(self.search_ticker)
        return 'FAILED'

    def create_result_file(self):
        """create result file and save header line to this file """
        res_file = create_file("{}_{}_".format(TEST_NAME, self.log_file))
        header_line = "Start Time, Status, Latency"
        write_line_to_file(res_file, header_line)
        return res_file

    def write_latency_result(self, latency_check_time, latency_check_status, latency):
        """write result to result file """
        write_line_to_file(self.result_file, "{} , {} , {}"
                           .format(time.strftime('%H:%M:%S', time.localtime(latency_check_time)),
                                   latency_check_status,
                                   latency))

class LogagentLatency(threading.Thread):
    def __init__(self, elastic_url, check_timeout, check_ticker, search_ticker, runtime, log_files):
        threading.Thread.__init__(self, )
        self.elastic_url = elastic_url
        self.check_timeout = check_timeout
        self.check_ticker = check_ticker
        self.search_ticker = search_ticker
        self.runtime = runtime
        self.log_files = log_files

    def run(self):
        print ">>>>Start Latency test<<<<"
        thread_list = []
        for log_file in self.log_files:
            t = LatencyTest(self.elastic_url, self.check_ticker, self.search_ticker, self.check_timeout, self.runtime,
                            log_file['file'], log_file['directory'], log_file['log_level'], log_file['msg_size'])
            t.start()
            thread_list.append(t)

        for thread in thread_list:
            thread.join()

if __name__ == "__main__":
    TEST_CONF = yaml.load(file('test_configuration.yaml'))
    BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
    ELASTIC_URL = urlparse(BASIC_CONF['url']['elastic_url']).netloc
    CHECK_TIMEOUT = TEST_CONF[TEST_NAME]['check_timeout']
    CHECK_TICKER = TEST_CONF[TEST_NAME]['check_ticker']
    SEARCH_TICKER = TEST_CONF[TEST_NAME]['search_ticker']
    RUNTIME = TEST_CONF[TEST_NAME]['runtime']
    LOG_FILES = TEST_CONF[TEST_NAME]['log_files']
    logagent_latency = LogagentLatency(ELASTIC_URL, CHECK_TIMEOUT, CHECK_TICKER, SEARCH_TICKER, RUNTIME, LOG_FILES)
    logagent_latency.start()
