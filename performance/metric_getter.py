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
import httplib
import json
import MySQLdb
from urlparse import urlparse
import db_saver
from monascaclient import client
import TokenHandler

monasca_api_version = '2_0'
test_metrics = [{'name': 'cpu.percent', 'dimensions': {}},
                {'name': 'mem.used_mb', 'dimensions': {}}]
kafka_metrics_dimensions = [{'consumer_group': '1_metrics'},
                            {'consumer_group': 'transformer-logstash-consumer'},
                            {'consumer_group': 'logstash-persister'}]


class MetricGetter:
    def __init__(self, metric_api_url, keystone_url, keystone_user, keystone_password, keystone_project, monasca_hosts,
                 mariadb_username=None, mariadb_password=None, mariadb_hostname=None, mariadb_database=None,
                 test_case_id=1):
        self.metric_api_url = urlparse(metric_api_url)
        self.toke_handler = TokenHandler.TokenHandler(keystone_user, keystone_password, keystone_project, keystone_url)
        self.monasca_client = client.Client(monasca_api_version, metric_api_url,
                                            token=self.toke_handler.get_valid_token())
        self.monasca_hosts = monasca_hosts
        self.mariadb_con = MySQLdb.connect(mariadb_hostname, mariadb_username, mariadb_password, mariadb_database)
        self.test_case_id = test_case_id

    def get_and_save_tests_metrics(self, start_time, end_time):
        for metric in test_metrics:
            for host in self.monasca_hosts:
                metrics = self.get_metrics(metric['name'], host, start_time, end_time, metric['dimensions'])
                db_saver.save_metrics(self.mariadb_con, self.test_case_id, metric['name'], metrics, host)
        kafka_metric_list = list()
        for dimensions in kafka_metrics_dimensions:
            kafka_metric_list.append(self.get_metrics('kafka.consumer_lag',
                                                      self.monasca_hosts[0], start_time, end_time, dimensions))

        kafka_metric_combine = [[kafka_metric[0]] for kafka_metric in kafka_metric_list[0]]
        for i in range(len(kafka_metric_combine)):
            for j in range(len(kafka_metric_list)):
                kafka_metric_combine[i].append(kafka_metric_list[0][j][1])
        print kafka_metric_combine
        db_saver.save_kafka_lag_metrics(self.mariadb_con, self.test_case_id, kafka_metric_combine)

    def get_metrics(self, metric_name, hostname, start_time, end_time, dimensions):
        connection = httplib.HTTPConnection(self.metric_api_url.netloc)
        dimensions_str = 'hostname:{},{}'.format(hostname,
                                                 ','.join(['%s:%s' % (key, value) for (key, value) in dimensions.items()]))
        request_str = "{}/measurements?name={}&start_time={}&end_time={}&dimensions={}"\
            .format(self.metric_api_url.path, metric_name, str(start_time).replace(" ", "T"),
                    str(end_time).replace(" ", "T"), dimensions_str)
        connection.request("GET", request_str, headers=self.get_request_header())
        response = connection.getresponse()
        response_json = json.loads(response.read())
        print response_json
        measurements = [[measurement[0], measurement[1]] for measurement in response_json['elements'][0]['measurements']]
        print measurements
        connection.close()
        return measurements

    def get_request_header(self):
        """ return header for request"""
        return {"Content-type": "application/json", "X-Auth-Token": self.toke_handler.get_valid_token()}


