import argparse
import MySQLdb
import yaml
from urlparse import urlparse
import db_saver
from alarm_on_log_test import AOLTest
from logagent_write import LogagentWrite
from logagent_latency import LogagentLatency
from log_latency import LogLatency
from log_send import LogSend
from log_throughput import LogThroughput
from metric_latency import MetricLatency
from metric_send import MetricSend
from metric_throughput import MetricThroughput



def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-suite', action='store', dest='suite')
    # todo  parser.add_argument('-config_file', asction='store', dest='')
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
TEST_CASE_ID = 1

TEST_NAME = 'log_metric_test_launch'
program_argument = create_program_argument_parser()
SUITE = program_argument.suite
DELAY = 10

TESTSUITE_CONF = yaml.load(file('./launch_configuration1.yaml'), Loader=yaml.Loader)

if __name__ == "__main__":

    if SUITE == 'TestSuite1':
        if MARIADB_STATUS == 'enabled':
            if ((MARIADB_HOSTNAME is not None) and
                (MARIADB_USERNAME is not None) and
                    (MARIADB_DATABASE is not None)):
                db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
                TEST_CASE_ID = db_saver.save_testCase(db, SUITE)
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()
        program_list = []
        for i in TESTSUITE_CONF[SUITE]['Program']['log_throughput']:
            print("LogThroughput:, parameter:")
            print("    LOG_EVERY_N          : " + str(i['LOG_EVERY_N']))
            print("    runtime          : " + str(i['runtime']))
            print("    ticker          : " + str(i['ticker']))
            print("    num_stop          : " + str(i['num_stop']))
            print("    search_field          : " + str(i['search_field']))
            print("    search_string          : " + str(i['search_string']))
            log_throughput = LogThroughput(TENANT_PROJECT, ELASTIC_URL, i['runtime'], i['ticker'], i['search_string'],
                                           i['search_field'], i['num_stop'], MARIADB_STATUS, MARIADB_USERNAME,
                                           MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            log_throughput.start()
            program_list.append(log_throughput)

        for i in TESTSUITE_CONF[SUITE]['Program']['log_send']:
            print("LogSend:, parameter:")
            print("    num_threads          : " + str(i['num_threads']))
            print("    log_every_n           : " + str(i['log_every_n']))
            print("    log_api_type   : " + str(i['log_api_type']))
            print("    num_of_logs_in_one_bulk      : " + str(i['num_of_logs_in_one_bulk']))
            print("    log_size: " + str(i['log_size']))
            print("    runtime: " + str(i['runtime']))
            print("    frequency: " + str(i['frequency']))
            print("    log_level: " + str(i['log_level']))
            print("    dimension: " + str(i['dimension']))
            log_send = LogSend(KEYSTONE_URL, LOG_API_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                               i['num_threads'], i['runtime'], i['log_every_n'], i['log_api_type'],
                               i['num_of_logs_in_one_bulk'], i['frequency'], i['log_size'], i['log_level'],
                               i['dimension'], DELAY, MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD,
                               MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            log_send.start()
            program_list.append(log_send)

        for i in TESTSUITE_CONF[SUITE]['Program']['log_latency']:
            print("LogLatency:, parameter:")
            print("    num_threads          : " + str(i['num_threads']))
            print("    log_api_type          : " + str(i['log_api_type']))
            print("    num_of_logs_in_one_bulk          : " + str(i['num_of_logs_in_one_bulk']))
            print("    log_size          : " + str(i['log_size']))
            print("    runtime          : " + str(i['runtime']))
            print("    ticker          : " + str(i['ticker']))

            log_latency = LogLatency(KEYSTONE_URL, LOG_API_URL, ELASTIC_URL, TENANT_USERNAME, TENANT_PASSWORD,
                                     TENANT_PROJECT, i['runtime'], i['num_threads'], i['log_api_type'],
                                     i['num_of_logs_in_one_bulk'], i['log_size'], MARIADB_STATUS, MARIADB_USERNAME,
                                     MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            log_latency.start()
            program_list.append(log_latency)

        for program in program_list:
            program.join()
        if MARIADB_STATUS == 'enabled' and TEST_CASE_ID != 1:
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db, TEST_CASE_ID)
            db.close()

    if SUITE == 'TestSuite2a':
        if MARIADB_STATUS == 'enabled':
            if ((MARIADB_HOSTNAME is not None) and
                (MARIADB_USERNAME is not None) and
                    (MARIADB_DATABASE is not None)):
                db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
                TEST_CASE_ID = db_saver.save_testCase(db, SUITE)
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()

        program_list = []
        for i in TESTSUITE_CONF[SUITE]['Program']['metric_throughput']:
            print("MetricThroughput:, parameter:")
            print("    runtime          : " + str(i['runtime']))
            print("    ticker           : " + str(i['ticker']))
            print("    ticker_to_stop   : " + str(i['ticker_to_stop']))
            print("    metric_name      : " + str(i['metric_name']))
            print("    metric_dimensions: " + str(i['metric_dimensions']))
            metric_throughput = MetricThroughput(INFLUX_URL.split(':')[0], INFLUX_URL.split(':')[1], INFLUX_USER,
                                                 INFLUX_PASSWORD, INFLUX_DATABASE, i['runtime'], i['ticker'],
                                                 i['ticker_to_stop'], i['metric_name'], i['metric_dimensions'],
                                                 MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                                 MARIADB_DATABASE, TEST_CASE_ID)
            metric_throughput.start()
            program_list.append(metric_throughput)

        for i in TESTSUITE_CONF[SUITE]['Program']['metric_send']:
            print("MetricSend:, parameter:")
            print("    num_threads          : " + str(i['num_threads']))
            print("    num_metrics_per_request           : " + str(i['num_metrics_per_request']))
            print("    LOG_EVERY_N   : " + str(i['LOG_EVERY_N']))
            print("    runtime      : " + str(i['runtime']))
            print("    frequency: " + str(i['frequency']))
            print("    metric_name: " + str(i['metric_name']))
            print("    metric_dimension: " + str(i['metric_dimension']))
            metric_send = MetricSend(KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                     METRIC_API_URL + "/metrics", i['num_threads'], i['num_metrics_per_request'],
                                     i['LOG_EVERY_N'], i['runtime'], i['frequency'], i['metric_name'],
                                     i['metric_dimension'], DELAY, MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD,
                                     MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            metric_send.start()
            program_list.append(metric_send)

        for i in TESTSUITE_CONF[SUITE]['Program']['metric_latency']:
            print("MetricSend:, parameter:")
            print("    runtime          : " + str(i['runtime']))
            print("    check_frequency           : " + str(i['check_frequency']))
            print("    send_frequency   : " + str(i['send_frequency']))
            print("    runtime      : " + str(i['timeout']))
            metric_latency = MetricLatency(KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                           METRIC_API_URL + "/metrics", i['runtime'], i['check_frequency'],
                                           i['send_frequency'], i['timeout'], MARIADB_STATUS, MARIADB_USERNAME,
                                           MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            metric_latency.start()
            program_list.append(metric_latency)

        for program in program_list:
            program.join()
        if MARIADB_STATUS == 'enabled' and TEST_CASE_ID != 1:
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db, TEST_CASE_ID)
            db.close()

    if SUITE == 'TestSuite2b':
        if MARIADB_STATUS == 'enabled':
            if ((MARIADB_HOSTNAME is not None) and
                (MARIADB_USERNAME is not None) and
                    (MARIADB_DATABASE is not None)):
                db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
                TEST_CASE_ID = db_saver.save_testCase(db, SUITE)
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()
        program_list = []
        for i in TESTSUITE_CONF[SUITE]['Program']['log_throughput']:
            print("LogThroughput:, parameter:")
            print("    LOG_EVERY_N          : " + str(i['LOG_EVERY_N']))
            print("    runtime          : " + str(i['runtime']))
            print("    ticker          : " + str(i['ticker']))
            print("    num_stop          : " + str(i['num_stop']))
            print("    search_field          : " + str(i['search_field']))
            print("    search_string          : " + str(i['search_string']))
            log_throughput = LogThroughput(TENANT_PROJECT, ELASTIC_URL, i['runtime'], i['ticker'], i['search_string'],
                                           i['search_field'], i['num_stop'], MARIADB_STATUS, MARIADB_USERNAME,
                                           MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            log_throughput.start()
            program_list.append(log_throughput)

        for i in TESTSUITE_CONF[SUITE]['Program']['log_send']:
            print("LogSend:, parameter:")
            print("    num_threads          : " + str(i['num_threads']))
            print("    log_every_n           : " + str(i['log_every_n']))
            print("    log_api_type   : " + str(i['log_api_type']))
            print("    num_of_logs_in_one_bulk      : " + str(i['num_of_logs_in_one_bulk']))
            print("    log_size: " + str(i['log_size']))
            print("    runtime: " + str(i['runtime']))
            print("    frequency: " + str(i['frequency']))
            print("    log_level: " + str(i['log_level']))
            print("    dimension: " + str(i['dimension']))
            log_send = LogSend(KEYSTONE_URL, LOG_API_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                               i['num_threads'], i['runtime'], i['log_every_n'], i['log_api_type'],
                               i['num_of_logs_in_one_bulk'], i['frequency'], i['log_size'], i['log_level'],
                               i['dimension'], DELAY, MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD,
                               MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            log_send.start()
            program_list.append(log_send)

        for i in TESTSUITE_CONF[SUITE]['Program']['log_latency']:
            print("LogLatency:, parameter:")
            print("    num_threads          : " + str(i['num_threads']))
            print("    log_api_type          : " + str(i['log_api_type']))
            print("    num_of_logs_in_one_bulk          : " + str(i['num_of_logs_in_one_bulk']))
            print("    log_size          : " + str(i['log_size']))
            print("    runtime          : " + str(i['runtime']))
            print("    ticker          : " + str(i['ticker']))

            log_latency = LogLatency(KEYSTONE_URL, LOG_API_URL, ELASTIC_URL, TENANT_USERNAME, TENANT_PASSWORD,
                                     TENANT_PROJECT, i['runtime'], i['num_threads'], i['log_api_type'],
                                     i['num_of_logs_in_one_bulk'], i['log_size'], MARIADB_STATUS, MARIADB_USERNAME,
                                     MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            log_latency.start()
            program_list.append(log_latency)

        for i in TESTSUITE_CONF[SUITE]['Program']['metric_throughput']:
            print("MetricThroughput:, parameter:")
            print("    runtime          : " + str(i['runtime']))
            print("    ticker           : " + str(i['ticker']))
            print("    ticker_to_stop   : " + str(i['ticker_to_stop']))
            print("    metric_name      : " + str(i['metric_name']))
            print("    metric_dimensions: " + str(i['metric_dimensions']))
            metric_throughput = MetricThroughput(INFLUX_URL.split(':')[0], INFLUX_URL.split(':')[1], INFLUX_USER,
                                                 INFLUX_PASSWORD, INFLUX_DATABASE, i['runtime'], i['ticker'],
                                                 i['ticker_to_stop'], i['metric_name'], i['metric_dimensions'],
                                                 MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                                 MARIADB_DATABASE, TEST_CASE_ID)
            metric_throughput.start()
            program_list.append(metric_throughput)

        for i in TESTSUITE_CONF[SUITE]['Program']['metric_send']:
            print("MetricSend:, parameter:")
            print("    num_threads          : " + str(i['num_threads']))
            print("    num_metrics_per_request           : " + str(i['num_metrics_per_request']))
            print("    LOG_EVERY_N   : " + str(i['LOG_EVERY_N']))
            print("    runtime      : " + str(i['runtime']))
            print("    frequency: " + str(i['frequency']))
            print("    metric_name: " + str(i['metric_name']))
            print("    metric_dimension: " + str(i['metric_dimension']))
            metric_send = MetricSend(KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                     METRIC_API_URL + "/metrics", i['num_threads'], i['num_metrics_per_request'],
                                     i['LOG_EVERY_N'], i['runtime'], i['frequency'], i['metric_name'],
                                     i['metric_dimension'], DELAY, MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD,
                                     MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            metric_send.start()
            program_list.append(metric_send)

        for i in TESTSUITE_CONF[SUITE]['Program']['metric_latency']:
            print("MetricSend:, parameter:")
            print("    runtime          : " + str(i['runtime']))
            print("    check_frequency           : " + str(i['check_frequency']))
            print("    send_frequency   : " + str(i['send_frequency']))
            print("    runtime      : " + str(i['timeout']))
            metric_latency = MetricLatency(KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                           METRIC_API_URL + "/metrics", i['runtime'], i['check_frequency'],
                                           i['send_frequency'], i['timeout'], MARIADB_STATUS, MARIADB_USERNAME,
                                           MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            metric_latency.start()
            program_list.append(metric_latency)

        for program in program_list:
            program.join()

        if MARIADB_STATUS == 'enabled' and TEST_CASE_ID != 1:
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db, TEST_CASE_ID)
            db.close()

    if SUITE == 'TestSuite3':
        # todo TestSuite3
        if MARIADB_STATUS == 'enabled':
            if ((MARIADB_HOSTNAME is not None) and
                    (MARIADB_USERNAME is not None) and
                    (MARIADB_DATABASE is not None)):
                db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
                TEST_CASE_ID = db_saver.save_testCase(db, SUITE)
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()
        program_list = []
        for i in TESTSUITE_CONF[SUITE]['Program']['log_throughput']:
            print("LogThroughput:, parameter:")
            print("    LOG_EVERY_N          : " + str(i['LOG_EVERY_N']))
            print("    runtime          : " + str(i['runtime']))
            print("    ticker          : " + str(i['ticker']))
            print("    num_stop          : " + str(i['num_stop']))
            print("    search_field          : " + str(i['search_field']))
            print("    search_string          : " + str(i['search_string']))
            log_throughput = LogThroughput(TENANT_PROJECT, ELASTIC_URL, i['runtime'], i['ticker'], i['search_string'],
                                           i['search_field'], i['num_stop'], MARIADB_STATUS, MARIADB_USERNAME,
                                           MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            log_throughput.start()
            program_list.append(log_throughput)

        for i in TESTSUITE_CONF[SUITE]['Program']['log_send']:
            print("LogSend:, parameter:")
            print("    num_threads          : " + str(i['num_threads']))
            print("    log_every_n           : " + str(i['log_every_n']))
            print("    log_api_type   : " + str(i['log_api_type']))
            print("    num_of_logs_in_one_bulk      : " + str(i['num_of_logs_in_one_bulk']))
            print("    log_size: " + str(i['log_size']))
            print("    runtime: " + str(i['runtime']))
            print("    frequency: " + str(i['frequency']))
            print("    log_level: " + str(i['log_level']))
            print("    dimension: " + str(i['dimension']))
            log_send = LogSend(KEYSTONE_URL, LOG_API_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                               i['num_threads'], i['runtime'], i['log_every_n'], i['log_api_type'],
                               i['num_of_logs_in_one_bulk'], i['frequency'], i['log_size'], i['log_level'],
                               i['dimension'], DELAY, MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD,
                               MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            log_send.start()
            program_list.append(log_send)

        for i in TESTSUITE_CONF[SUITE]['Program']['logagent_write']:
            print("LogSend:, parameter:")
            print("    log_ever_n          : " + str(i['log_ever_n']))
            print("    runtime           : " + str(i['runtime']))
            print("    inp_file_dir   : " + str(i['inp_file_dir']))
            print("    inp_file_list      : " + str(i['inp_file_list']))
            print("    outp_file_dir: " + str(i['outp_file_dir']))
            print("    outp_file_name: " + str(i['outp_file_name']))
            print("    outp_count: " + str(i['outp_count']))
            logagent_write = LogagentWrite(i['runtime'], i['log_ever_n'], i['inp_file_dir'], i['inp_file_list'],
                                           i['outp_file_dir'], i['outp_file_name'], i['outp_count'],
                                           MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_HOSTNAME,
                                           MARIADB_DATABASE, TEST_CASE_ID)
            logagent_write.start()
            program_list.append(logagent_write)

        for i in TESTSUITE_CONF[SUITE]['Program']['logagent_latency']:
            print("LogSend:, parameter:")
            print("    check_timeout          : " + str(i['check_timeout']))
            print("    check_ticker           : " + str(i['check_ticker']))
            print("    search_ticker   : " + str(i['search_ticker']))
            print("    runtime      : " + str(i['runtime']))
            print("    log_files: " + str(i['log_files']))
            logagent_latency = LogagentLatency(ELASTIC_URL, i['check_timeout'], i['check_ticker'], i['search_ticker'],
                                               i['runtime'], i['log_files'], MARIADB_STATUS, MARIADB_USERNAME,
                                               MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            logagent_latency.start()
            program_list.append(logagent_latency)

        for program in program_list:
            program.join()
        if MARIADB_STATUS == 'enabled' and TEST_CASE_ID != 1:
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db, TEST_CASE_ID)
            db.close()

    if SUITE == 'TestSuite4a':
        if MARIADB_STATUS == 'enabled':
            if ((MARIADB_HOSTNAME is not None) and
                (MARIADB_USERNAME is not None) and
                    (MARIADB_DATABASE is not None)):
                db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
                TEST_CASE_ID = db_saver.save_testCase(db, SUITE)
                db.close()
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()

        program_list = []
        METRIC_THROUGHPUT_P = TESTSUITE_CONF[SUITE]['Program']['metric_throughput']
        for i in METRIC_THROUGHPUT_P:
            print("MetricThroughput: " + str(i) + ", parameter")
            print("    runtime          : " + str(i['runtime']))
            print("    ticker           : " + str(i['ticker']))
            print("    ticker_to_stop   : " + str(i['ticker_to_stop']))
            print("    metric_name      : " + str(i['metric_name']))
            print("    metric_dimensions: " + str(i['metric_dimensions']))
            metric_throughput = MetricThroughput(INFLUX_URL.split(':')[0], INFLUX_URL.split(':')[1], INFLUX_USER,
                                                 INFLUX_PASSWORD, INFLUX_DATABASE,
                                                 i['runtime'],
                                                 i['ticker'],
                                                 i['ticker_to_stop'],
                                                 i['metric_name'],
                                                 i['metric_dimensions'],
                                                 MARIADB_STATUS,
                                                 MARIADB_USERNAME,
                                                 MARIADB_PASSWORD,
                                                 MARIADB_HOSTNAME,
                                                 MARIADB_DATABASE,
                                                 TEST_CASE_ID)
            metric_throughput.start()
            program_list.append(metric_throughput)

        # scw: fixed code
        DELAY = 10
        LOG_SEND_P = TESTSUITE_CONF[SUITE]['Program']['log_send']
        for i in LOG_SEND_P:
            print("LogSend: " + str(i) + ", parameter")
            print("    num_threads            : " + str(i['num_threads']))
            print("    runtime                : " + str(i['runtime']))
            print("    log_every_n            : " + str(i['log_every_n']))
            print("    log_api_type           : " + str(i['log_api_type']))
            print("    num_of_logs_in_one_bulk: " + str(i['num_of_logs_in_one_bulk']))
            print("    frequency              : " + str(i['frequency']))
            print("    num_of_logs_in_one_bulk: " + str(i['log_size']))
            print("    log_level              : " + str(i['log_level']))
            print("    dimension              : " + str(i['dimension']))
            log_send = LogSend(KEYSTONE_URL, LOG_API_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                               i['num_threads'],
                               i['runtime'],
                               i['log_every_n'],
                               i['log_api_type'],
                               i['num_of_logs_in_one_bulk'],
                               i['frequency'],
                               i['log_size'],
                               i['log_level'],
                               i['dimension'],
                               DELAY,
                               MARIADB_STATUS,
                               MARIADB_USERNAME,
                               MARIADB_PASSWORD,
                               MARIADB_HOSTNAME,
                               MARIADB_DATABASE,
                               TEST_CASE_ID)

            log_send.start()
            program_list.append(log_send)

        for program in program_list:
            program.join()
        if MARIADB_STATUS == 'enabled' and TEST_CASE_ID != 1:
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db, TEST_CASE_ID)
            db.close()

    if SUITE == 'TestSuite4':
        if MARIADB_STATUS == 'enabled':
            if ((MARIADB_HOSTNAME is not None) and
                    (MARIADB_USERNAME is not None) and
                    (MARIADB_DATABASE is not None)):
                db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
                TEST_CASE_ID = db_saver.save_testCase(db, SUITE)
            else:
                print 'One of mariadb params is not set while mariadb_status=="enabled"'
                exit()
        program_list = []

        for i in TESTSUITE_CONF[SUITE]['Program']['log_send']:
            print("LogSend:, parameter:")
            print("    num_threads          : " + str(i['num_threads']))
            print("    log_every_n           : " + str(i['log_every_n']))
            print("    log_api_type   : " + str(i['log_api_type']))
            print("    num_of_logs_in_one_bulk      : " + str(i['num_of_logs_in_one_bulk']))
            print("    log_size: " + str(i['log_size']))
            print("    runtime: " + str(i['runtime']))
            print("    frequency: " + str(i['frequency']))
            print("    log_level: " + str(i['log_level']))
            print("    dimension: " + str(i['dimension']))
            log_send = LogSend(KEYSTONE_URL, LOG_API_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                               i['num_threads'], i['runtime'], i['log_every_n'], i['log_api_type'],
                               i['num_of_logs_in_one_bulk'], i['frequency'], i['log_size'], i['log_level'],
                               i['dimension'], DELAY, MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD,
                               MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            log_send.start()
            program_list.append(log_send)

        for i in TESTSUITE_CONF[SUITE]['Program']['metric_send']:
            print("MetricSend:, parameter:")
            print("    num_threads          : " + str(i['num_threads']))
            print("    num_metrics_per_request           : " + str(i['num_metrics_per_request']))
            print("    LOG_EVERY_N   : " + str(i['LOG_EVERY_N']))
            print("    runtime      : " + str(i['runtime']))
            print("    frequency: " + str(i['frequency']))
            print("    metric_name: " + str(i['metric_name']))
            print("    metric_dimension: " + str(i['metric_dimension']))
            metric_send = MetricSend(KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT,
                                     METRIC_API_URL + "/metrics", i['num_threads'], i['num_metrics_per_request'],
                                     i['LOG_EVERY_N'], i['runtime'], i['frequency'], i['metric_name'],
                                     i['metric_dimension'], DELAY, MARIADB_STATUS, MARIADB_USERNAME, MARIADB_PASSWORD,
                                     MARIADB_HOSTNAME, MARIADB_DATABASE, TEST_CASE_ID)
            metric_send.start()
            program_list.append(metric_send)

        print("Alarm on LOG, parameter:")
        print("    runtime          : " + str(TESTSUITE_CONF[SUITE]['Program']['alarm_on_log']['runtime']))
        print("    alarm_conf           : " + str(TESTSUITE_CONF[SUITE]['Program']['alarm_on_log']['alarm_conf']))
        aol = AOLTest(KEYSTONE_URL, TENANT_USERNAME, TENANT_PASSWORD, TENANT_PROJECT, METRIC_API_URL, LOG_API_URL,
                      TESTSUITE_CONF[SUITE]['Program']['alarm_on_log']['alarm_conf'],
                      TESTSUITE_CONF[SUITE]['Program']['alarm_on_log']['runtime'])
        aol.start()
        program_list.append(aol)

        for program in program_list:
            program.join()

        if MARIADB_STATUS == 'enabled' and TEST_CASE_ID != 1:
            db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)
            db_saver.close_testCase(db, TEST_CASE_ID)
            db.close()
