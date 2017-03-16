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
import argparse
import datetime
import logging
import MySQLdb
import search_logs
import time
import threading
import random
import os
import string
import sys
import yaml
from urlparse import urlparse
from write_logs import create_file, write_line_to_file
import db_saver

TEST_NAME = "logagent_latency"
BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
MARIADB_HOSTNAME = BASIC_CONF['mariadb']['hostname']
MARIADB_USERNAME = BASIC_CONF['mariadb']['user']
MARIADB_PASSWORD = BASIC_CONF['mariadb']['password'] if BASIC_CONF['mariadb']['password'] is not None else ''
MARIADB_DATABASE = BASIC_CONF['mariadb']['database']


class LatencyTest(threading.Thread):
    def __init__(self, elastic_url, check_ticker, search_ticker, check_timeout, runtime, log_file, log_directory,
                 log_level, msg_size, file_number, mariadb_status, testID, mariadb_username=None, mariadb_password=None,
                 mariadb_hostname=None, mariadb_database=None):
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
        if mariadb_status == 'enabled':
            self.mariadb_status = mariadb_status
            self.mariadb_hostname = mariadb_hostname
            self.mariadb_username = mariadb_username
            self.mariadb_password = mariadb_password
            self.mariadb_database = mariadb_database
            self.testID = testID
            self.file_number = file_number

    def run(self):

        print " Start checking latency for {}".format(self.log_file)
        test_start_time = time.time()
        count = 0
        test_latencies = list()
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
                test_latencies.append(['latency'+str(self.file_number), str(latency_time),
                                       datetime.datetime.fromtimestamp(write_log_time).replace(microsecond=0)])
                self.write_latency_result(write_log_time, search_status, latency_time)
            else:
                print 'COUNT :{} | FILE: {} | TIME: {} | Failed to find log in {} s'. \
                    format(count,  self.log_file, time.strftime('%H:%M:%S ', time.localtime()), self.check_timeout)
                self.write_latency_result(write_log_time, search_status, '__')
                test_latencies.append(['latency'+str(self.file_number), '-',
                                       datetime.datetime.fromtimestamp(write_log_time).replace(microsecond=0)])
            time.sleep(self.check_ticker)
        if self.mariadb_status == 'enabled':
            db = MySQLdb.connect(self.mariadb_hostname, self.mariadb_username,
                                 self.mariadb_password, self.mariadb_database)
            db_saver.save_test_results(db, self.testID, test_latencies)
            db.close()

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
    def __init__(self, elastic_url, check_timeout, check_ticker, search_ticker, runtime, log_files,
                 mariadb_status, mariadb_username=None, mariadb_password=None, mariadb_hostname=None,
                 mariadb_database=None, testCaseID=1):
        threading.Thread.__init__(self, )
        self.mariadb_status = mariadb_status
        self.elastic_url = elastic_url
        self.check_timeout = check_timeout
        self.check_ticker = check_ticker
        self.search_ticker = search_ticker
        self.runtime = runtime
        self.log_files = log_files
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
                test_params = [['start_time', str(datetime.datetime.now().replace(microsecond=0))],
                               ['runtime', str(self.runtime)],
                               ['check_ticker', str(self.check_ticker)],
                               ['search_ticker', str(self.search_ticker)]]
                for counter, lg_file in enumerate(self.log_files):
                    test_params.append(['log_level'+str(counter), str(lg_file['log_level'])])
                    test_params.append(['msg_size'+str(counter), str(lg_file['msg_size'])])
                db_saver.save_test_params(db, self.testID, test_params)
                db.close()
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()

    def run(self):
        print ">>>>Start Latency test<<<<"
        thread_list = []
        for counter, log_file in enumerate(self.log_files):
            t = LatencyTest(self.elastic_url, self.check_ticker, self.search_ticker, self.check_timeout, self.runtime,
                            log_file['file'], log_file['directory'], log_file['log_level'], log_file['msg_size'],
                            counter, self.mariadb_status, self.testID, self.mariadb_username, self.mariadb_password,
                            self.mariadb_hostname, self.mariadb_database)
            t.start()
            thread_list.append(t)

        for thread in thread_list:
            thread.join()

def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-mariadb_status', action='store', dest='mariadb_status')
    parser.add_argument('-mariadb_username', action='store', dest='mariadb_username')
    parser.add_argument('-mariadb_password', action='store', dest='mariadb_password')\
        if BASIC_CONF['mariadb']['password'] is not None else ''
    parser.add_argument('-mariadb_hostname', action='store', dest='mariadb_hostname')
    parser.add_argument('-mariadb_database', action='store', dest='mariadb_database')
    parser.add_argument('-runtime', action='store', dest='runtime', type=int)
    parser.add_argument('-elastic_url', action='store', dest='elastic_url', type=str)
    parser.add_argument('-check_timeout', action='store', dest='check_timeout', type=int)
    parser.add_argument('-check_ticker', action='store', dest='check_ticker', type=float)
    parser.add_argument('-search_ticker', action='store', dest='search_ticker', type=float)
    parser.add_argument('-log_files', action='store', dest='log_files', nargs='+')
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
        ELASTIC_URL = urlparse(BASIC_CONF['url']['elastic_url']).netloc
        CHECK_TIMEOUT = TEST_CONF[TEST_NAME]['check_timeout']
        CHECK_TICKER = TEST_CONF[TEST_NAME]['check_ticker']
        SEARCH_TICKER = TEST_CONF[TEST_NAME]['search_ticker']
        RUNTIME = TEST_CONF[TEST_NAME]['runtime']
        LOG_FILES = TEST_CONF[TEST_NAME]['log_files']
    else:
        program_argument = create_program_argument_parser()
        MARIADB_STATUS = program_argument.mariadb_status
        MARIADB_USERNAME = program_argument.mariadb_username
        MARIADB_PASSWORD = program_argument.mariadb_password
        MARIADB_HOSTNAME = program_argument.mariadb_hostname
        MARIADB_DATABASE = program_argument.mariadb_database
        ELASTIC_URL = urlparse(program_argument.elastic_url).netloc
        CHECK_TIMEOUT = program_argument.check_timeout
        CHECK_TICKER = program_argument.check_ticker
        SEARCH_TICKER = program_argument.search_ticker
        RUNTIME = program_argument.runtime
        LOG_FILES = [{'file': log_file[0], 'directory': log_file[1], 'log_level': log_file[2],
                      'msg_size': int(log_file[3])} for log_file in
                     [log_file.split(':') for log_file in program_argument.log_files]]

    logagent_latency = LogagentLatency(ELASTIC_URL, CHECK_TIMEOUT, CHECK_TICKER, SEARCH_TICKER, RUNTIME, LOG_FILES,
                                       MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE)
    logagent_latency.start()
