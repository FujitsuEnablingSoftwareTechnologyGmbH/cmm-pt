import datetime
import httplib
import simplejson
import threading
import time
import yaml
from operator import sub
from monascaclient import client
from urlparse import urlparse
import TokenHandler
from write_logs import create_file, write_line_to_file

ALARM_PATH = '/alarms'
BULK_API_PATH = '/v3.0/logs'
TEST_NAME = 'Alarm_on_log'

ALARM_TRIGGER_TIMEOUT = 120
RESPONSE_OK_STATUS = 200


class AlarmDefinition:

    def __init__(self, token_handler, alarm_def_conf, metric_api_url):
        self.token_handler = token_handler
        self.alarm_def_conf = alarm_def_conf
        self.monasca_client = client.Client('2_0', metric_api_url, token=self.token_handler.get_valid_token())
        self.alarm_def_list = []
        self.clear_alarms()
        for alarm_group in self.alarm_def_conf:
            severity = alarm_group['severity']
            num_of_alarms = alarm_group['alarms_per_alarm_definition']
            for count in range(alarm_group['number_of_alarm_def']):
                self.create_alarm_definition('throughput_test_{}_{}'.format(severity, count), severity, num_of_alarms)

    def clear_alarms(self):
        for alarm_def in self.monasca_client.alarm_definitions.list():
            self.monasca_client.alarm_definitions.delete(alarm_id=alarm_def['id'])

    def create_alarm_definition(self, alarm_def_name, severity, num_of_alarms):
        try:
            alarm_dimension = 'hostname=systemtest,service={}'.format(alarm_def_name)
            resp = self.monasca_client.alarm_definitions.create(
                name=alarm_def_name,
                expression='count(log.{}{{{}}}) > 0'.format(severity.lower(), alarm_dimension),
                match_by=['count'],
            )

            print('Created Alarm Definition NAME: {} ID: {}'.format(resp['name'], resp['id']))
            alarm_dimension_dict = {'hostname': 'systemtest', 'service': alarm_def_name}
            self.alarm_def_list.append({'id': resp['id'], 'severity': severity, 'dimension': alarm_dimension_dict,
                                        'name': alarm_def_name, 'num_of_alarms': num_of_alarms})
        except Exception as e:
            print('Failed to create alarm definition ERROR')
            print e


class Alarm:
    def __init__(self, alarm_id, token_handler, metric_api_url):
        self.id = alarm_id
        self.metric_alarm_url = urlparse(metric_api_url + ALARM_PATH)
        self.token_handler = token_handler
        self.alarm_occur_time_list, self.alarm_name = self.__get_alarm_occur_time_and_name()

    def __get_alarm_occur_time_and_name(self):
        header = {'X-Auth-Token': self.token_handler.get_valid_token(), 'Content-Type': 'application/json'}
        metric_api_conn = httplib.HTTPConnection(self.metric_alarm_url.netloc)
        metric_api_conn.request("GET",
                                "{}/{}/state-history".format(self.metric_alarm_url.path, self.id),
                                headers=header)

        res = metric_api_conn.getresponse()
        if res.status is not RESPONSE_OK_STATUS:
            print ('FAILED TO RETRIEVE STATE HISTORY')
            return False
        alarms_state_history = simplejson.loads(res.read())
        alarm_occur_timestamp = [alarm_state_history['timestamp'] for alarm_state_history in
                                 alarms_state_history['elements']
                                 if alarm_state_history['new_state'] == 'ALARM']
        alarm_occur_time_list = [datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                                 for timestamp in alarm_occur_timestamp]
        alarm_name = alarms_state_history['elements'][0]['metrics'][0]['dimensions']['service']
        return alarm_occur_time_list, alarm_name

    def get_alarm_latency(self, log_send_time_list):
        return map(sub, self.alarm_occur_time_list, log_send_time_list)


class AOLTest(threading.Thread):
    def __init__(self,  keyston_url, tenant_username, tenant_password, tenant_project, metric_api_url, log_api_url,
                 alarm_def_create_conf, runtime):
        threading.Thread.__init__(self)
        self.token_handler = TokenHandler.TokenHandler(tenant_username,
                                                       tenant_password,
                                                       tenant_project,
                                                       keyston_url)
        self.log_api_url = urlparse(log_api_url + BULK_API_PATH)
        self.metric_api_url = metric_api_url
        self.metric_alarm_url = urlparse(metric_api_url + ALARM_PATH)
        self.log_send_time_list = []
        self.result_file = create_file(TEST_NAME)
        self.alarm_def = AlarmDefinition(self.token_handler, alarm_def_create_conf, metric_api_url)
        self.runtime = runtime

    def run(self):

        start_time = time.time()
        while self.runtime > time.time() - start_time:
            self.send_bulk()
            self.wait_util_all_alarm_are_triggered()
            while not self.check_if_alarms_status_is_undetermined():
                print "alarm still in alarm state"
                time.sleep(30)
        self.check_alarm_latency()

    def wait_util_all_alarm_are_triggered(self):
        start_time = time.time()
        header = {'X-Auth-Token': self.token_handler.get_valid_token(), 'Content-Type': 'application/json'}
        metric_api_conn = httplib.HTTPConnection(self.metric_alarm_url.netloc)
        while time.time() - start_time < ALARM_TRIGGER_TIMEOUT:
            metric_api_conn.request("GET", self.metric_alarm_url.path, headers=header)
            res = metric_api_conn.getresponse()
            if res.status is RESPONSE_OK_STATUS:
                alarms_info = simplejson.loads(res.read())
                for alarm_state in alarms_info['elements']:
                    if alarm_state['state'] != 'ALARM':
                        break
                    return
            else:
                print "Failed to receive query form metric API"
            res.close()
            time.sleep(5)

    def send_bulk(self):
        header = {'X-Auth-Token': self.token_handler.get_valid_token(), 'Content-Type': 'application/json'}
        log_list = []
        log_api_conn = httplib.HTTPConnection(self.log_api_url.netloc)
        for alarm_def in self.alarm_def.alarm_def_list:
            msg = alarm_def['severity'] + " AOL test"
            for i in range(alarm_def['num_of_alarms']):

                dimension = alarm_def['dimension'].copy()
                dimension.update({'count': str(i)})
                log_list.append({'message': msg, 'dimensions': dimension})
        body = simplejson.dumps({'logs': log_list})
        log_api_conn.request("POST", self.log_api_url.path, body, header)
        send_time = datetime.datetime.utcnow()
        res = log_api_conn.getresponse()
        if res.status is not 204:
            print ('FAILED TO SEND BULK')
        else:
            self.log_send_time_list.append(send_time)
            print "{} send logs".format(send_time.strftime('%H:%M:%S.%f'))
        res.close()
        log_api_conn.close()

    def check_if_alarms_status_is_undetermined(self):
        header = {'X-Auth-Token': self.token_handler.get_valid_token(), 'Content-Type': 'application/json'}
        metric_api_conn = httplib.HTTPConnection(self.metric_alarm_url.netloc)
        metric_api_conn.request("GET", self.metric_alarm_url.path, headers=header)
        res = metric_api_conn.getresponse()
        if res.status is not RESPONSE_OK_STATUS:
            print ('FAILED TO RETRIEVE ALARMS STATUS')
            return False
        alarms_info = simplejson.loads(res.read())
        for alarm_state in alarms_info['elements']:
            if alarm_state['state'] != 'UNDETERMINED':
                return False
        return True

    def check_alarm_latency(self):
        alarm_list = self.create_all_alarm_instance()
        for alarm in alarm_list:
            print alarm.alarm_name
            for latency in alarm.get_alarm_latency(self.log_send_time_list):
                print latency.total_seconds()
        self.write_result_to_file(alarm_list)

    def write_result_to_file(self, alarm_list):
        header_line = 'Log_send'
        for alarm in alarm_list:
            header_line += ',{}({})'.format(alarm.alarm_name, alarm.id)
        write_line_to_file(self.result_file, header_line)
        for count, log_send_time in enumerate(self.log_send_time_list):
            res_line = str(log_send_time.strftime('%H:%M:%S.%f'))
            for alarm in alarm_list:

                res_line += ',{}'.format((alarm.alarm_occur_time_list[count] - log_send_time).total_seconds())
            write_line_to_file(self.result_file, res_line)

    def create_all_alarm_instance(self):
        alarms = []
        for alarm_id in self.get_alarms_id():
            alarms.append(Alarm(alarm_id, self.token_handler, self.metric_api_url))
        return alarms

    def get_alarms_id(self):
        header = {'X-Auth-Token': self.token_handler.get_valid_token(), 'Content-Type': 'application/json'}
        metric_api_conn = httplib.HTTPConnection(self.metric_alarm_url.netloc)
        metric_api_conn.request("GET", self.metric_alarm_url.path, headers=header)
        res = metric_api_conn.getresponse()
        if res.status is not RESPONSE_OK_STATUS:
            print ('FAILED TO RETRIEVE ALARMS ID')
            return False
        alarms_info = simplejson.loads(res.read())
        return [alarm_state['id'] for alarm_state in alarms_info['elements']]

if __name__ == "__main__":
    BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
    TEST_CONF = yaml.load(file('test_configuration.yaml'))
    KEYSTONE_URL = BASIC_CONF['url']['keystone']
    METRIC_API_URL = BASIC_CONF['url']['metrics_api']
    LOG_API_URL = BASIC_CONF['url']['log_api_url']
    USER_CREDENTIAL = {"name": BASIC_CONF['users']['tenant_name'],
                       "password": BASIC_CONF['users']['tenant_password'],
                       "project": BASIC_CONF['users']['tenant_project']}
    RUNTIME = TEST_CONF[TEST_NAME]['runtime']
    ALARM_DEF_CONF = TEST_CONF[TEST_NAME]['alarm_conf']
    aolTest = AOLTest(KEYSTONE_URL, USER_CREDENTIAL['name'], USER_CREDENTIAL['password'],
                      USER_CREDENTIAL['project'], METRIC_API_URL, LOG_API_URL, ALARM_DEF_CONF, RUNTIME)
    aolTest.start()
