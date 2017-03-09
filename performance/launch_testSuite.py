import argparse
import MySQLdb
import yaml
from urlparse import urlparse
from log_send import LogSend
from log_throughput import LogThroughput
from log_latency import LogLatency
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
db = MySQLdb.connect(MARIADB_HOSTNAME, MARIADB_USERNAME, MARIADB_PASSWORD, MARIADB_DATABASE)

TEST_NAME = 'log_metric_test_launch'
program_argument = create_program_argument_parser()
SUITE = program_argument.suite

TESTSUITE_CONF = yaml.load(file('./launch_configuration1.yaml'), Loader=yaml.Loader)

if __name__ == "__main__":

    if SUITE == 'TestSuite1':
        DELAY = 10
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
                                           MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE)
            log_throughput.start()

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
                               MARIADB_HOSTNAME, MARIADB_DATABASE)
            log_send.start()

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
                                     MARIADB_PASSWORD, MARIADB_HOSTNAME, MARIADB_DATABASE)
            log_latency.start()

    if SUITE == 'TestSuite2a':
        # todo TestSuite2a
        print('still Todo')
    if SUITE == 'TestSuite2b':
        # todo TestSuite2b
        print('still Todo')
    if SUITE == 'TestSuite3':
        # todo TestSuite3
        print('still Todo')

    if SUITE == 'TestSuite4a':
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
                                                 MARIADB_STATUS)
            metric_throughput.start()

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
                               MARIADB_STATUS)

            log_send.start()

    if SUITE == 'TestSuite4':
        # todo TestSuite4
        print('still Todo')
