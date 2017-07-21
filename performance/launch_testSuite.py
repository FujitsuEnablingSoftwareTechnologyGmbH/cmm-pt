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

import argparse
import MySQLdb
import yaml
import os
import os.path
from urlparse import urlparse
from datetime import datetime
import db_saver
from alarm_on_log_test import AOLTest
from count_metric import CountMetric
from logagent_write import LogagentWrite
from logagent_latency import LogagentLatency
from log_latency import LogLatency
from log_send import LogSend
from log_throughput import LogThroughput
from metric_getter import MetricGetter
from metric_latency import MetricLatency
from metric_send import MetricSend
from metric_throughput import MetricThroughput


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-suite', action='store', dest='suite')
    parser.add_argument('-config_file', action='store', dest='conf_file')
    return parser.parse_args()


BASIC_CONF = yaml.load(file('./basic_configuration.yaml'), Loader=yaml.Loader)
KEYSTONE_URL = BASIC_CONF['url']['keystone']
LOG_API_URL = BASIC_CONF['url']['log_api_url']
ELASTIC_URL = urlparse(BASIC_CONF['url']['elastic_url']).netloc
METRIC_API_URL = BASIC_CONF['url']['metrics_api']
TENANT_USERNAME = BASIC_CONF['users']['tenant_name']
TENANT_PASSWORD = BASIC_CONF['users']['tenant_password']
TENANT_PROJECT = BASIC_CONF['users']['tenant_project']
INFLUX_URL = BASIC_CONF['url']['influxdb']
INFLUX_USER = BASIC_CONF['influxdb']['user']
INFLUX_PASSWORD = BASIC_CONF['influxdb']['password']
INFLUX_DATABASE = BASIC_CONF['influxdb']['database']
MARIADB_HOSTNAME = BASIC_CONF['mariadb']['hostname']
MARIADB_USERNAME = BASIC_CONF['mariadb']['user']
MARIADB_PASSWORD = BASIC_CONF['mariadb']['password'] if BASIC_CONF['mariadb']['password'] is not None else ''
MARIADB_DATABASE = BASIC_CONF['mariadb']['database']
MARIADB_STATUS = BASIC_CONF['mariadb']['status']
MONASCA_HOSTNAME = BASIC_CONF['monasca_hostname']
TEST_CASE_ID = [0,""]

TEST_NAME = 'log_metric_test_launch'
program_argument = create_program_argument_parser()
SUITE = program_argument.suite
CONF_FILE = program_argument.conf_file
DELAY = 10

if CONF_FILE:
    TESTSUITE_CONF = yaml.load(file('./' + CONF_FILE), Loader=yaml.Loader)
else:
    TESTSUITE_CONF = yaml.load(file('./launch_configuration1.yaml'), Loader=yaml.Loader)


def create_file(strdir):
    path = "results/"+ strdir + '_' + (datetime.now().strftime("%Y-%m-%dT%H_%M_%S") + '/')
    if os.path.isfile('result_dir_for_Suite.yaml'):
        os.remove('result_dir_for_Suite.yaml')
    fp = open('result_dir_for_Suite.yaml', 'w')

    fp.write("write_result:"  + '\n')
    fp.write("    directory:  " + path)
    fp.flush()
    fp.close()


def create_and_get_test_case_id(test_suite):
    if MARIADB_STATUS == 'enabled':
        if ((MARIADB_HOSTNAME is not None) and
                (MARIADB_USERNAME is not None) and
                (MARIADB_DATABASE is not None)):
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            return db_saver.save_testCase(db, test_suite)
        else:
            raise ValueError('One of mariadb params is not set while mariadb_status=="enabled"')


def start_log_throughput_program(config, test_case_id):
    print("LogThroughput:, parameter:")
    print("    LOG_EVERY_N          : " + str(config['LOG_EVERY_N']))
    print("    runtime          : " + str(config['runtime']))
    print("    ticker          : " + str(config['ticker']))
    print("    num_stop          : " + str(config['num_stop']))
    print("    search_field          : " + str(config['search_field']))
    print("    search_string          : " + str(config['search_string']))
    log_throughput = LogThroughput(TENANT_PROJECT, ELASTIC_URL, config['runtime'], config['ticker'], config['search_string'],
                                   config['search_field'], config['num_stop'], MARIADB_STATUS, MARIADB_USERNAME,
                                   MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE, test_case_id)
    log_throughput.start()
    return log_throughput


def start_log_send_program(config, test_case_id, application_type_dimension='SystemTest'):
    print("LogSend:, parameter:")
    print("    num_threads          : " + str(config['num_threads']))
    print("    log_every_n           : " + str(config['log_every_n']))
    print("    log_api_type   : " + str(config['log_api_type']))
    print("    num_of_logs_in_one_bulk      : " + str(config['num_of_logs_in_one_bulk']))
    print("    log_size: " + str(config['log_size']))
    print("    runtime: " + str(config['runtime']))
    print("    frequency: " + str(config['frequency']))
    print("    log_level: " + str(config['log_level']))
    print("    dimension: " + str(config['dimension']))
    log_send = LogSend(KEYSTONE_URL, LOG_API_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                       config['num_threads'], config['runtime'], config['log_every_n'], config['log_api_type'],
                       config['num_of_logs_in_one_bulk'], config['frequency'], config['log_size'], config['log_level'],
                       config['dimension'], DELAY, MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD,
                       MARIADB_HOSTNAME, MARIADB_DATABASE, test_case_id, application_type_dimension)
    log_send.start()
    return log_send


def start_log_latency_program(config, test_case_id):
    print("LogLatency:, parameter:")
    print("    num_threads          : " + str(config['num_threads']))
    print("    log_api_type          : " + str(config['log_api_type']))
    print("    num_of_logs_in_one_bulk          : " + str(config['num_of_logs_in_one_bulk']))
    print("    log_size          : " + str(config['log_size']))
    print("    runtime          : " + str(config['runtime']))
    print("    ticker          : " + str(config['ticker']))

    log_latency = LogLatency(KEYSTONE_URL, LOG_API_URL, ELASTIC_URL, TENANT_USERNAME, TENANT_PASSWORD,
                             TENANT_PROJECT, config['runtime'], config['num_threads'], config['log_api_type'],
                             config['num_of_logs_in_one_bulk'], config['log_size'], MARIADB_STATUS, MARIADB_USERNAME,
                             MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE, test_case_id)
    log_latency.start()
    return log_latency


def start_metric_throughput_program(config, test_case_id):
    print("MetricThroughput:, parameter:")
    print("    runtime          : " + str(config['runtime']))
    print("    ticker           : " + str(config['ticker']))
    print("    ticker_to_stop   : " + str(config['ticker_to_stop']))
    print("    metric_name      : " + str(config['metric_name']))
    print("    metric_dimensions: " + str(config['metric_dimensions']))
    metric_throughput = MetricThroughput(INFLUX_URL.split(':')[0], INFLUX_URL.split(':')[1], INFLUX_USER,
                                         INFLUX_PASSWORD, INFLUX_DATABASE, config['runtime'], config['ticker'],
                                         config['ticker_to_stop'], config['metric_name'], config['metric_dimensions'],
                                         MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                         MARIADB_DATABASE, test_case_id)
    metric_throughput.start()
    return metric_throughput


def start_metric_send_program(config, test_case_id):
    print("MetricSend:, parameter:")
    print("    num_threads          : " + str(config['num_threads']))
    print("    num_metrics_per_request           : " + str(config['num_metrics_per_request']))
    print("    LOG_EVERY_N   : " + str(config['LOG_EVERY_N']))
    print("    runtime      : " + str(config['runtime']))
    print("    frequency: " + str(config['frequency']))
    print("    metric_name: " + str(config['metric_name']))
    print("    metric_dimension: " + str(config['metric_dimension']))
    metric_send = MetricSend(KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                             METRIC_API_URL + "/metrics", config['num_threads'], config['num_metrics_per_request'],
                             config['LOG_EVERY_N'], config['runtime'], config['frequency'], config['metric_name'],
                             config['metric_dimension'], DELAY, MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD,
                             MARIADB_HOSTNAME, MARIADB_DATABASE, test_case_id)
    metric_send.start()
    return metric_send


def start_metric_latency_program(config, test_case_id):
    print("MetricLatency:, parameter:")
    print("    runtime          : " + str(config['runtime']))
    print("    check_ticker           : " + str(config['check_ticker']))
    print("    send_ticker   : " + str(config['send_ticker']))
    print("    runtime      : " + str(config['timeout']))
    metric_latency = MetricLatency(KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                   METRIC_API_URL + "/metrics", config['runtime'], config['check_ticker'],
                                   config['send_ticker'], config['timeout'], MARIADB_STATUS, MARIADB_USERNAME,
                                   MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE, test_case_id)
    metric_latency.start()
    return metric_latency


def start_logagent_write(config, test_case_id):
    print("LogSend:, parameter:")
    print("    log_ever_n          : " + str(config['log_ever_n']))
    print("    runtime           : " + str(config['runtime']))
    print("    inp_file_dir   : " + str(config['inp_file_dir']))
    print("    inp_file_list      : " + str(config['inp_file_list']))
    print("    outp_file_dir: " + str(config['outp_file_dir']))
    print("    outp_file_name: " + str(config['outp_file_name']))
    print("    outp_count: " + str(config['outp_count']))
    logagent_write = LogagentWrite(config['runtime'], config['log_ever_n'], config['inp_file_dir'],
                                   config['inp_file_list'], config['outp_file_dir'], config['outp_file_name'],
                                   config['outp_count'], MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD,
                                   MARIADB_HOSTNAME, MARIADB_DATABASE, test_case_id)
    logagent_write.start()
    return logagent_write


def start_logagent_latency(config, test_case_id):
    print("LogSend:, parameter:")
    print("    check_timeout          : " + str(config['check_timeout']))
    print("    check_ticker           : " + str(config['check_ticker']))
    print("    search_ticker   : " + str(config['search_ticker']))
    print("    runtime      : " + str(config['runtime']))
    print("    log_files: " + str(config['log_files']))
    logagent_latency = LogagentLatency(ELASTIC_URL, config['check_timeout'], config['check_ticker'],
                                       config['search_ticker'], config['runtime'], config['log_files'], MARIADB_STATUS,
                                       MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE,
                                       test_case_id)
    logagent_latency.start()
    return logagent_latency


if __name__ == "__main__":

    TEST_CASE_ID[1] = "results/" + SUITE + '_' + (datetime.now().strftime("%Y-%m-%dT%H_%M_%S") + '/')

    if SUITE == 'TestSuite1':


        if MARIADB_STATUS == 'enabled':
            TEST_CASE_ID[0] = create_and_get_test_case_id(SUITE)
            metric_getter = MetricGetter(METRIC_API_URL, KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                         MONASCA_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                         MARIADB_DATABASE, TEST_CASE_ID[0])
            start_time = datetime.utcnow()
        program_list = []
        for configuration in TESTSUITE_CONF[SUITE]['Program']['log_throughput']:
            program_list.append(start_log_throughput_program(configuration, TEST_CASE_ID))


        for configuration in TESTSUITE_CONF[SUITE]['Program']['log_send']:
            program_list.append(start_log_send_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['log_latency']:
            program_list.append(start_log_latency_program(configuration, TEST_CASE_ID))

        for program in program_list:
            program.join()

        if MARIADB_STATUS == 'enabled':
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db, TEST_CASE_ID[0])
            db.close()
            metric_getter.get_and_save_tests_metrics(start_time, datetime.utcnow())


    elif SUITE == 'TestSuite2a':

        if MARIADB_STATUS == 'enabled':
            TEST_CASE_ID[0] = create_and_get_test_case_id(SUITE)
            start_time = datetime.utcnow()
        program_list = []
        metric_getter = MetricGetter(METRIC_API_URL, KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                     MONASCA_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                     MARIADB_DATABASE, TEST_CASE_ID[0])

        for configuration in TESTSUITE_CONF[SUITE]['Program']['metric_throughput']:
            program_list.append(start_metric_throughput_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['metric_send']:
            program_list.append(start_metric_send_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['metric_latency']:
            program_list.append(start_metric_latency_program(configuration, TEST_CASE_ID))

        for program in program_list:
            program.join()
        if MARIADB_STATUS == 'enabled':
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db, TEST_CASE_ID[0])
            db.close()
            metric_getter.get_and_save_tests_metrics(start_time, datetime.utcnow())

    elif SUITE == 'TestSuite2b':
        if MARIADB_STATUS == 'enabled':
            TEST_CASE_ID[0] = create_and_get_test_case_id(SUITE)
            metric_getter = MetricGetter(METRIC_API_URL, KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                         MONASCA_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                         MARIADB_DATABASE,  TEST_CASE_ID[0])
            start_time = datetime.utcnow()
        program_list = []

        for configuration in TESTSUITE_CONF[SUITE]['Program']['log_throughput']:
            program_list.append(start_log_throughput_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['log_send']:
            program_list.append(start_log_send_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['log_latency']:
            program_list.append(start_log_latency_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['metric_throughput']:
            program_list.append(start_metric_throughput_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['metric_send']:
            program_list.append(start_metric_send_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['metric_latency']:
            program_list.append(start_metric_latency_program(configuration, TEST_CASE_ID))

        for program in program_list:
            program.join()

        if MARIADB_STATUS == 'enabled':
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db,  TEST_CASE_ID[0])
            db.close()
            metric_getter.get_and_save_tests_metrics(start_time, datetime.utcnow())

    elif SUITE == 'TestSuite3':
        if MARIADB_STATUS == 'enabled':
            TEST_CASE_ID[0] = create_and_get_test_case_id(SUITE)
            metric_getter = MetricGetter(METRIC_API_URL, KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                         MONASCA_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                         MARIADB_DATABASE,  TEST_CASE_ID[0])
            start_time = datetime.utcnow()
        program_list = []

        for configuration in TESTSUITE_CONF[SUITE]['Program']['log_throughput']:
            program_list.append(start_log_throughput_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['log_send']:
            program_list.append(start_log_send_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['logagent_write']:
            program_list.append(start_logagent_write(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['logagent_latency']:

            program_list.append(start_logagent_latency(configuration, TEST_CASE_ID))

        for program in program_list:
            program.join()
        if MARIADB_STATUS == 'enabled':
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db,  TEST_CASE_ID[0])
            db.close()
            metric_getter.get_and_save_tests_metrics(start_time, datetime.utcnow())

    elif SUITE == 'TestSuite4a':
        if MARIADB_STATUS == 'enabled':
            TEST_CASE_ID[0] = create_and_get_test_case_id(SUITE)
            metric_getter = MetricGetter(METRIC_API_URL, KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                         MONASCA_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                         MARIADB_DATABASE,  TEST_CASE_ID[0])
            start_time = datetime.utcnow()
        program_list = []
        for configuration in TESTSUITE_CONF[SUITE]['Program']['metric_throughput']:
            program_list.append(start_metric_throughput_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['log_send']:
            program_list.append(start_log_send_program(configuration, TEST_CASE_ID))

        for program in program_list:
            program.join()
        if MARIADB_STATUS == 'enabled':
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db,  TEST_CASE_ID[0])
            db.close()
            metric_getter.get_and_save_tests_metrics(start_time, datetime.utcnow())

    elif SUITE == 'TestSuite4':
        if MARIADB_STATUS == 'enabled':
            TEST_CASE_ID[0] = create_and_get_test_case_id(SUITE)
            metric_getter = MetricGetter(METRIC_API_URL, KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                         MONASCA_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                         MARIADB_DATABASE,  TEST_CASE_ID[0])
            start_time = datetime.utcnow()
        program_list = []

        for configuration in TESTSUITE_CONF[SUITE]['Program']['log_send']:
            program_list.append(start_log_send_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['metric_send']:
            program_list.append(start_metric_send_program(configuration, TEST_CASE_ID))

        print("Alarm on LOG, parameter:")
        print("    runtime          : " + str(TESTSUITE_CONF[SUITE]['Program']['alarm_on_log']['runtime']))
        print("    alarm_conf           : " + str(TESTSUITE_CONF[SUITE]['Program']['alarm_on_log']['alarm_conf']))
        aol = AOLTest(KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT, METRIC_API_URL, LOG_API_URL,
                      TESTSUITE_CONF[SUITE]['Program']['alarm_on_log']['alarm_conf'],
                      TESTSUITE_CONF[SUITE]['Program']['alarm_on_log']['runtime'], MARIADB_STATUS, MARIADB_USERNAME,
                      MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
        aol.start()
        program_list.append(aol)

        for program in program_list:
            program.join()

        if MARIADB_STATUS == 'enabled':
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db,  TEST_CASE_ID[0])
            db.close()
            metric_getter.get_and_save_tests_metrics(start_time, datetime.utcnow())

    elif SUITE == 'TestSuite5':
        if MARIADB_STATUS == 'enabled':
            TEST_CASE_ID[0] = create_and_get_test_case_id(SUITE)
            metric_getter = MetricGetter(METRIC_API_URL, KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                         MONASCA_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                         MARIADB_DATABASE,  TEST_CASE_ID[0])
            start_time = datetime.utcnow()

        program_list_before_stress = list()
        for configuration in TESTSUITE_CONF[SUITE]['Program_before_stress']['log_throughput']:
            program_list_before_stress.append(start_log_throughput_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program_before_stress']['log_send']:
            program_list_before_stress.append(start_log_send_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program_before_stress']['log_latency']:
            program_list_before_stress.append(start_log_latency_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program_before_stress']['metric_throughput']:
            program_list_before_stress.append(start_metric_throughput_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program_before_stress']['metric_send']:
            program_list_before_stress.append(start_metric_send_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program_before_stress']['metric_latency']:
            program_list_before_stress.append(start_metric_latency_program(configuration, TEST_CASE_ID))

        for program in program_list_before_stress:
            program.join()

        program_list_stress = list()

        for configuration in TESTSUITE_CONF[SUITE]['Program_stress']['log_send']:
            program_list_stress.append(start_log_send_program(configuration, TEST_CASE_ID, 'Stress'))

        for configuration in TESTSUITE_CONF[SUITE]['Program_stress']['metric_send']:
            program_list_stress.append(start_metric_send_program(configuration, TEST_CASE_ID))

        for program in program_list_stress:
            program.join()

        program_list_after_stress = list()

        for configuration in TESTSUITE_CONF[SUITE]['Program_after_stress']['log_throughput']:
            program_list_after_stress.append(start_log_throughput_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program_after_stress']['log_send']:
            program_list_after_stress.append(start_log_send_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program_after_stress']['log_latency']:
            program_list_after_stress.append(start_log_latency_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program_after_stress']['metric_throughput']:
            program_list_after_stress.append(start_metric_throughput_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program_after_stress']['metric_send']:
            program_list_after_stress.append(start_metric_send_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program_after_stress']['metric_latency']:
            program_list_after_stress.append(start_metric_latency_program(configuration, TEST_CASE_ID))

        for program in program_list_after_stress:
            program.join()

        if MARIADB_STATUS == 'enabled':
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db,  TEST_CASE_ID[0])
            db.close()
            metric_getter.get_and_save_tests_metrics(start_time, datetime.utcnow())

    elif SUITE == 'TestSuite6':
        if MARIADB_STATUS == 'enabled':
            TEST_CASE_ID[0] = create_and_get_test_case_id(SUITE)
            metric_getter = MetricGetter(METRIC_API_URL, KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                         MONASCA_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                         MARIADB_DATABASE,  TEST_CASE_ID[0])
            start_time = datetime.utcnow()

        test_suite_start_time = datetime.utcnow().replace(microsecond=0)
        count_script_metric_name = list()
        program_list = []
        for configuration in TESTSUITE_CONF[SUITE]['Program']['log_throughput']:
            program_list.append(start_log_throughput_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['log_send']:
            program_list.append(start_log_send_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['log_latency']:
            program_list.append(start_log_latency_program(configuration, TEST_CASE_ID))

        for configuration in TESTSUITE_CONF[SUITE]['Program']['metric_send']:
            program_list.append(start_metric_send_program(configuration, TEST_CASE_ID))
            count_script_metric_name.append(configuration['metric_name'])

        for i in TESTSUITE_CONF[SUITE]['Program']['metric_latency']:
            program_list.append(start_metric_send_program(configuration, TEST_CASE_ID))

        for program in program_list:
            program.join()
        test_suite_end_time = datetime.utcnow().replace(microsecond=0)
        for metric_name in count_script_metric_name:
            print("CountMetric, parameter:")
            print("    metric_name          : " + metric_name)
            print("    start_time          : " + str(test_suite_start_time))
            print("    end_time          : " + str(test_suite_end_time))

            count_metric = CountMetric(INFLUX_URL, INFLUX_USER, INFLUX_PASSWORD, INFLUX_DATABASE,
                                       test_suite_start_time, test_suite_end_time, metric_name,
                                       MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                       MARIADB_DATABASE, TEST_CASE_ID)
            count_metric.count_metric()

        if MARIADB_STATUS == 'enabled':
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db,  TEST_CASE_ID[0])
            db.close()
            metric_getter.get_and_save_tests_metrics(start_time, datetime.utcnow())

    else:
        raise ValueError('incorrect Suite parameter ({})'.format(SUITE))
