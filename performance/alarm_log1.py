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
This program is used to measure the required time to trigger alarms based on logs.
The program created specifies alarm definition via Metric API and sends specified log entries that trigger
the previously created alarm definitions, then starts searching for alarms form the metric API.
The program measures the time it takes between sending the metric entry until the appearance of alarms.
"""

import argparse
import httplib
import re
import time
import datetime
import simplejson
import sys
import yaml
import copy
from monascaclient import client
from urlparse import urlparse
import TokenHandler
from write_logs import create_file, write_line_to_file


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-keystone_url', action="store", dest='keystone_url')
    parser.add_argument('-log_api_url', action="store", dest='log_api_url')
    parser.add_argument('-metric_api_url', action="store", dest='metric_api_url')
    parser.add_argument('-tenant_name', action="store", dest='tenant_name')
    parser.add_argument('-tenant_password', action="store", dest='tenant_password')
    parser.add_argument('-tenant_project', action="store", dest='tenant_project')
    parser.add_argument('-alarm_definition_name', action="store", dest='alarm_definition_name')
    parser.add_argument('-alarms_per_alarm_definition', action="store", dest='alarms_per_alarm_definition', type=int)
    parser.add_argument('-number_of_alarm_definition', action="store", dest='number_of_alarm_definition', type=int)
    parser.add_argument('-runtime', action="store", dest='runtime', type=int)
    return parser.parse_args()

TEST_NAME = 'alarm_log'

if len(sys.argv) <= 1:
    BASIC_CONF = yaml.load(file('basic_configuration.yaml'))
    TEST_CONF = yaml.load(file('test_configuration.yaml'))
    KEYSTONE_URL = BASIC_CONF['url']['keystone']
    METRIC_API_URL = BASIC_CONF['url']['metrics_api']
    URL_BULK_LOG_API = BASIC_CONF['url']['log_api_url'] + '/v3.0/logs'
    ALARM_DEFINITION_NAME = TEST_CONF[TEST_NAME]['alarm_definition_name']
    LOGS_PER_ALARM_DEFINITION = TEST_CONF[TEST_NAME]['alarms_per_alarm_definition']
    NUMBER_OF_ALARM_DEFINITION = TEST_CONF[TEST_NAME]['number_of_alarm_definition']
    RUNTIME = TEST_CONF[TEST_NAME]['runtime']
    USER_CREDENTIAL = {"name": BASIC_CONF['users']['tenant_name'],
                       "password": BASIC_CONF['users']['tenant_password'],
                       "project": BASIC_CONF['users']['tenant_project']}
else:
    program_argument = create_program_argument_parser()
    KEYSTONE_URL = program_argument.keystone_url
    METRIC_API_URL = program_argument.metric_api_url
    URL_BULK_LOG_API = program_argument.log_api_url + '/v3.0/logs'
    ALARM_DEFINITION_NAME = program_argument.alarm_definition_name
    LOGS_PER_ALARM_DEFINITION = program_argument.alarms_per_alarm_definition
    NUMBER_OF_ALARM_DEFINITION = program_argument.number_of_alarm_definition
    RUNTIME = program_argument.runtime
    USER_CREDENTIAL = {"name": program_argument.tenant_name,
                       "password": program_argument.tenant_password,
                       "project": program_argument.tenant_project}

TIMEOUT = 600
SLEEP = 10
WAIT_FOR_ALARMS = 10
ALARM_TICKER = 240
token_handler = TokenHandler.TokenHandler(USER_CREDENTIAL['name'],
                                          USER_CREDENTIAL['password'],
                                          USER_CREDENTIAL['project'],
                                          KEYSTONE_URL)
headers_post = {"Content-type": "application/json"}
metric_dimension = 'service'


def clear_alarm_definition(monasca_client):
    """ Delete all alarm definition that have in name pattern specified in ALARM_DEFINITION_NAME filed"""
    pattern = re.compile(ALARM_DEFINITION_NAME + '[0-9]+')

    for alarm_definition in monasca_client.alarm_definitions.list():
        try:
            if pattern.match(alarm_definition['name']):
                monasca_client.alarm_definitions.delete(alarm_id=alarm_definition['id'])
        except Exception as e:
            print('Failed to delete alarm definition ERROR:')
            print e


def create_alarm_definition(monasca_client, name, alarm_def_count):
    try:
        resp = monasca_client.alarm_definitions.create(
            name=name + str(alarm_def_count),
             expression='count(log.error{hostname=systemtest' + str(alarm_def_count) + '},deterministic) > 0',
             match_by=[metric_dimension],

        )
        print('Created Alarm Definition NAME: {} ID: {}'.format(resp['name'], resp['id']))
        return resp['id']
    except Exception as e:
        print('Failed to create alarm definition ERROR')
        print e

    return None


def send_logs(token, alarm_def_count):
    """send log to log api, this log api should trigger alarm definition"""
    url = urlparse(URL_BULK_LOG_API)
    conn = httplib.HTTPConnection(url.netloc)
    log_list = []
    headers_post['X-Auth-Token'] = token
    for i in range(LOGS_PER_ALARM_DEFINITION):
        log_list.append({'message': 'ERROR tmp', 'dimensions':
                                     {'service': 'systemTest' + str(i), 
                                      'hostname': 'systemtest'+ str(alarm_def_count)}})

    body = simplejson.dumps({'logs': log_list})
    conn.request("POST", url.path, body, headers_post)
    res = conn.getresponse()
    if res.status is not 204:
        print "Failed to send logs ERROR: {}".format(res.read())
        

    return LOGS_PER_ALARM_DEFINITION

def send_log(token, dimensions):
    """send log to log api, this log api should trigger an alarm """
    url = urlparse(URL_BULK_LOG_API)
    conn = httplib.HTTPConnection(url.netloc)
    log_list = []
    headers_post['X-Auth-Token'] = token
    log_list.append({'message': 'ERROR tmp', 'dimensions':
                                     dimensions})

    body = simplejson.dumps({'logs': log_list})
    conn.request("POST", url.path, body, headers_post)
    res = conn.getresponse()
    if res.status is not 204:
        print "Failed to send logs ERROR: {}".format(res.read())
        

    


def wait_for_all_alarms(alarm_def_id, mon_client, number_of_expected_alarms):
    """this program check till all alarm will be created """
    print('Waiting for alarms to be created')
    check_start_time = time.time()
    alarm_count = 0
    alarm_list = []
    while  True:
        alarm_count = 0
        alarm_list = mon_client.alarms.list(alarm_definition_id=alarm_def_id)
        num = len(alarm_list)
        if num < number_of_expected_alarms:
            if check_start_time + TIMEOUT < time.time():
                print "TIMEOUT. Found only {} alarms expect {}".format(alarm_count, number_of_expected_alarms)
                break
            else:
                time.sleep(SLEEP)
            
        else:
            return alarm_list
        
        

   


def perform_aol_test():
    start_time = time.time()
    result = None
    token = token_handler.get_valid_token()
    """to store the queryed alarms"""
    alarm_def_id_list = []  
    total_log_send = 0
    mon_client = client.Client('2_0', METRIC_API_URL, token=token)
    clear_alarm_definition(mon_client)
    
    """create all alarms and store in alarm_def_id_list"""
    for alarm_def_count in range(NUMBER_OF_ALARM_DEFINITION):
        alarm_def_id = create_alarm_definition(mon_client, ALARM_DEFINITION_NAME, alarm_def_count)
        if alarm_def_id is not None:
            alarm_def_id_list.append(alarm_def_id)
            
    """send logs first time to trigger all alarms """

    last_send =  datetime.datetime.utcnow().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    print "last_time:" + str(last_send)
    count = len(alarm_def_id_list)
    for i in  range (count):
        total_log_send += send_logs(token, i)
    time.sleep(WAIT_FOR_ALARMS)
    

    """ query for all triggered alarms and store in alarm_elements_list and local_alarm_status  """
    alarm_elements_list = []
    local_alarm_status = []
    index = 0
    
    for id in alarm_def_id_list:

         res = wait_for_all_alarms(id,mon_client,LOGS_PER_ALARM_DEFINITION)
         #for element in res:
         for i in range(len(res)):

                 #alarm_elements_list.append(element)
                 alarm_elements_list.append(res[i])
                 #local_alarm_status.append(element)
                 local_alarm_status = copy.deepcopy(alarm_elements_list)
                 print " alarm_elements_list: " + str(alarm_elements_list[index]['updated_timestamp'] )
                 local_alarm_status[index]['updated_timestamp'] = last_send
                 print " alarm_elements_list: " + str(alarm_elements_list[index]['updated_timestamp'])
                 print " local_alarm_status: " + str(local_alarm_status[index]['updated_timestamp'])

                 index = index + 1






    while  time.time() < (start_time + RUNTIME):


       print " while "
       trace_utc_time()
       #trace_data(index,local_alarm_status)
       

       for i in range(index):
          print "for next i:" +str(i)
          trace_utc_time()

          if local_alarm_status[i]['state'] == 'ALARM':
              print " local_state = ALARM"

              # if (time.time() - local_alarm_status[i]['state_updated_timestamp']) > ALARM_TICKER:
              if get_utc_delta(local_alarm_status[i]['state_updated_timestamp'],ALARM_TICKER) < get_utc(datetime.datetime.utcnow().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.%fZ")):
                   print " local_update_time + ALARM_TICKER  < timeutcnow"
                   trace_utc_timestap(local_alarm_status[i]['state_updated_timestamp'])
                   print "query query query query query query aktuell states"
                   """query alarm state"""
                   result = mon_client.alarms.get(alarm_id=local_alarm_status[i]['id'])
                                                
                   if result['state'] == 'ALARM':
                       print "result.state  = ALARM"

                       print "Alarm after ALARM_TICKER_TIME still in status Alarm"
                        
                   else:
                         print "result.state = OK "
                         print "send log"
                         send_log(token, result['metrics'][0]['dimensions'])
                         #send_log (token,local_alarm_status[i]['metrics'][0]['dimensions'])
                         local_alarm_status[i]['updated_timestamp'] = datetime.datetime.utcnow().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                         local_alarm_status[i]['state'] = 'OK'
              else:

                  print " local state still ALARM no Query "
                  #print " waiting for ALARM_TICKER  until status will change to ok"
                  print " wait time for change to ok is now "

                  change_time = get_utc(datetime.datetime.utcnow().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.%fZ")) - get_utc(local_alarm_status[i]['state_updated_timestamp'])

                  print " wait-time :" + str(change_time)





          
          else:
              print "else local.state = Ok"
              print " local status : " + str(local_alarm_status[i]['state'])
              if local_alarm_status[i]['state'] == 'OK':
                 if get_utc(local_alarm_status[i]['updated_timestamp'] ) < get_utc(local_alarm_status[i]['state_updated_timestamp']):
                   print "local_update_timestamp < local_stateupdatetimestamp"
                   trace_utc_timestap(local_alarm_status[i]['updated_timestamp'])
                   trace_utc_timestap(local_alarm_status[i]['state_updated_timestamp'])
                   print "send log"
                   #if result== None:
                   #    print """query alarm state to get metric-demension"""
                   #   result = mon_client.alarms.get(alarm_id=local_alarm_status[i]['id'])
                   send_log (token,local_alarm_status[i]['metrics'][0]['dimensions'])#cccccccccccccccccccccccccccccccccccc?
                   local_alarm_status[i]['updated_timestamp'] = datetime.datetime.utcnow().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                   local_alarm_status[i]['state'] = 'OK'
                 else:
                     print "log already send"
                     print """query alarm state"""

                     result= mon_client.alarms.get(alarm_id=local_alarm_status[i]['id'])
                     if  result['state'] == 'ALARM':
                         print "result state == ALARM"
                         print """calculate latency"""
                         latency = get_utc(result['state_updated_timestamp']) - get_utc(local_alarm_status[i]['updated_timestamp'])
                         print "result_state_update_timestamp"
                         trace_utc_timestap(result['state_updated_timestamp'])
                         print "local_update_timestamp"
                         trace_utc_timestap(local_alarm_status[i]['updated_timestamp'])
                         print "latency -----------------------------------------------------------------:" +str(latency)
                         local_alarm_status[i]['state_updated_timestamp'] = result['state_updated_timestamp']
                         local_alarm_status[i]['state'] = 'ALARM'
                     else: 
                         print """ result.stata = ok"""
                         print """ test max latency timeout """
                         #if (time.time() - local_alarm_status[i]['updated_timestamp'] ) > TIMEOUT:
                         if get_utc_delta(local_alarm_status[i]['updated_timestamp'],TIMEOUT) < get_utc(datetime.datetime.utcnow().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.%fZ")):

                               print "error: latency timeout"
                               print " latency : local_updated_timestamp + " + str('TIMEOUT ')+ " + : " + str(get_utc_delta(local_alarm_status[i]['updated_timestamp'],TIMEOUT) )
                               trace_utc_time()
                               
                               print """ send log again"""
                               send_log (token,local_alarm_status[i]['metrics'][0]['dimensions'])
                               local_alarm_status[i]['updated_timestamp'] = datetime.datetime.utcnow().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                         
                             
                         else:
                              print "no latency timeout"
                              print """ nothing todo"""




       time.sleep(30)
       
def trace_data(index,local_alarm_status):
    print"local status elements"
    for i in range(index):
        print "i : " + str('i')
        print "updated_timestamp : "   +str(   local_alarm_status[i]['updated_timestamp'])
        print "state : "  + str(   local_alarm_status[i]['state'])
        print "state_updated_timestamp : "  + str(   local_alarm_status[i]['state_updated_timestamp'])
        print "metric_dimension : " + str(  local_alarm_status[i]['metrics'][0]['dimensions'])
        
    
    
    


def trace_utc_time ():
    print " utc_time : " + str(datetime.datetime.utcnow().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    
def trace_utc_timestap (datetime):
    print " utc_time : " + str(datetime)
 
def get_utc (date_time):
    return datetime.datetime.strptime(date_time, "%Y-%m-%dT%H:%M:%S.%fZ")

def get_utc_delta (date_time, sec):
    utc = datetime.datetime.strptime(date_time, "%Y-%m-%dT%H:%M:%S.%fZ")
    utc = utc + datetime.timedelta(seconds=sec)
    return utc

    

def write_result(result_string):
    print result_string
    lg_file = create_file(TEST_NAME)
    write_line_to_file(lg_file, result_string)
    lg_file.close()

if __name__ == "__main__":
    perform_aol_test()

#utc = datetime.datetime.strptime(local_alarm_status[i]['state_updated_timestamp'],"%Y-%m-%dT%H:%M:%S.%fZ")
#    print " time utc " +str(utc)
#    utc = utc + datetime.timedelta(seconds=3)
#   print " time utc " + str(utc)

#element [{'id': u'9a5d43e2-605c-4bc4-9674-b3a42cc5b086'}, {'dimension': {u'hostname': u'systemtest1', u'service': u'systemTest1'}}, {'state': u'OK'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}]
#l#ocal alarm list [[{'id': u'5a2bbadd-425b-47b8-b45d-d3118579f22e'}, {'dimension': {u'hostname': u'systemtest0', u'service': u'systemTest0'}}, {'state': u'OK'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}], [{'id': u'ee1a9454-3f92-47b4-aa81-b289fc8977aa'}, {'dimension': {u'hostname': u'systemtest0', u'service': u'systemTest1'}}, {'state': u'OK'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}], [{'id': u'7000b914-f945-4523-8beb-0af9077a9bca'}, {'dimension': {u'hostname': u'systemtest1', u'service': u'systemTest0'}}, {'state': u'ALARM'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}], [{'id': u'9a5d43e2-605c-4bc4-9674-b3a42cc5b086'}, {'dimension': {u'hostname': u'systemtest1', u'service': u'systemTest1'}}, {'state': u'OK'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}]]
#local alarm list [[{'id': u'5a2bbadd-425b-47b8-b45d-d3118579f22e'}, {'dimension': {u'hostname': u'systemtest0', u'service': u'systemTest0'}}, {'state': u'OK'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}], [{'id': u'ee1a9454-3f92-47b4-aa81-b289fc8977aa'}, {'dimension': {u'hostname': u'systemtest0', u'service': u'systemTest1'}}, {'state': u'OK'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}], [{'id': u'7000b914-f945-4523-8beb-0af9077a9bca'}, {'dimension': {u'hostname': u'systemtest1', u'service': u'systemTest0'}}, {'state': u'ALARM'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}], [{'id': u'9a5d43e2-605c-4bc4-9674-b3a42cc5b086'}, {'dimension': {u'hostname': u'systemtest1', u'service': u'systemTest1'}}, {'state': u'OK'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}]]
#[{'id': u'5a2bbadd-425b-47b8-b45d-d3118579f22e'}, {'dimension': {u'hostname': u'systemtest0', u'service': u'systemTest0'}}, {'state': u'OK'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}]

#element [{'id': u'7000b914-f945-4523-8beb-0af9077a9bca'}, {'dimension': {u'hostname': u'systemtest1', u'service': u'systemTest0'}}, {'state': u'ALARM'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}]
#local alarm list [[{'id': u'5a2bbadd-425b-47b8-b45d-d3118579f22e'}, {'dimension': {u'hostname': u'systemtest0', u'service': u'systemTest0'}}, {'state': u'OK'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}], [{'id': u'ee1a9454-3f92-47b4-aa81-b289fc8977aa'}, {'dimension': {u'hostname': u'systemtest0', u'service': u'systemTest1'}}, {'state': u'OK'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}], [{'id': u'7000b914-f945-4523-8beb-0af9077a9bca'}, {'dimension': {u'hostname': u'systemtest1', u'service': u'systemTest0'}}, {'state': u'ALARM'}, {'state_update_time': u'2017-03-10T17:55:00.000Z'}, {'last_send_time': 1489168499.582526}]]
# alarm _element : {u'lifecycle_state': None, u'links': [{u'href': u'http://10.140.18.49:8070/v2.0/alarms/9a5d43e2-605c-4bc4-9674-b3a42cc5b086', u'rel': u'self'}], u'updated_timestamp': u'2017-03-10T17:55:00.000Z', u'state_updated_timestamp': u'2017-03-10T17:55:00.000Z', u'metrics': [{u'dimensions': {u'hostname': u'systemtest1', u'service': u'systemTest1'}, u'id': None, u'name': u'log.error'}], u'state': u'OK', u'link': None, u'alarm_definition': {u'severity': u'LOW', u'id': u'b054d4e5-c14d-4ce1-99c4-9f6c9efade5e', u'links': [{u'href': u'http://10.140.18.49:8070/v2.0/alarm-definitions/b054d4e5-c14d-4ce1-99c4-9f6c9efade5e', u'rel': u'self'}], u'name': u'SylviaE1'}, u'created_timestamp': u'2017-03-10T17:55:00.000Z', u'id': u'9a5d43e2-605c-4bc4-9674-b3a42cc5b086'}
#id: 9a5d43e2-605c-4bc4-9674-b3a42cc5b086
#dimensios : {u'hostname': u'systemtest1', u'service': u'systemTest1'}
#state : OK


# print " alarm _element : " +str(alarm_element)
# print "id: "+str(alarm_element['id'])
# print "dimensios : " + str(alarm_element['metrics'][0]['dimensions'])
# print "state : " + str(alarm_element['state'])
# print "state_updated_timestamp : " + str(alarm_element['state_updated_timestamp'])
# print "updated_timestamp : " + str(alarm_element['updated_timestamp'])



# local_alarm_status[0]['updated_timestamp'] = time.time()
# print "last_send Time : " + str(local_alarm_status[0]['updated_timestamp'])


# element = [{"id":alarm_element['id']},{"dimension":alarm_element['metrics'][0]['dimensions']},{"state":alarm_element['state']},
#           {"state_update_time":alarm_element['state_updated_timestamp']},{"last_send_time":last_send}]
# print "element " + str(element)
# local_alarm_status.append(element)
# print "local alarm list "+str(local_alarm_status)
'''alarm_elements_list: 2017-03-11T18:32:04.000Z
 local_alarm_status: 2017-03-11T18:32:03.637942Z
 alarm_elements_list: 2017-03-11T18:32:04.000Z
 alarm_elements_list: 2017-03-11T18:32:04.000Z
 local_alarm_status: 2017-03-11T18:32:03.637942Z
Waiting for alarms to be created
 alarm_elements_list: 2017-03-11T18:32:04.000Z
 alarm_elements_list: 2017-03-11T18:32:04.000Z
 local_alarm_status: 2017-03-11T18:32:03.637942Z
 alarm_elements_list: 2017-03-11T18:32:04.000Z
 alarm_elements_list: 2017-03-11T18:32:04.000Z
 local_alarm_status: 2017-03-11T18:32:03.637942Z
 while
for next i:0
log already send
for next i:1
log already send
for next i:2
log already send
for next i:3
nothing todo wait for ALARM_TICKER
 while
for next i:0
log already send
for next i:1
log already send
for next i:2
log already send
for next i:3
nothing todo wait for ALARM_TICKER
 while
for next i:0
log already send
for next i:1
log already send
for next i:2
log already send
for next i:3
nothing todo wait for ALARM_TICKER
 while
for next i:0
log already send
for next i:1
log already send
for next i:2
log already send
for next i:3
nothing todo wait for ALARM_TICKER
 while
for next i:0
log already send
for next i:1
log already send
for next i:2
log already send
for next i:3
nothing todo wait for ALARM_TICKER
 while
for next i:0
log already send
for next i:1
log already send
for next i:2
log already send
for next i:3
nothing todo wait for ALARM_TICKER
 while
for next i:0
log already send
for next i:1
log already send
for next i:2
log already send
for next i:3
nothing todo wait for ALARM_TICKER
 while
for next i:0
log already send
for next i:1
log already send
for next i:2
log already send
for next i:3
nothing todo wait for ALARM_TICKER
 while
for next i:0
log already send
for next i:1
log already send
for next i:2
log already send
for next i:3
 while
for next i:0
log already send
for next i:1
log already send
for next i:2
log already send
for next i:3
log already send
latency -----------------------------------------------------------------:0:00:00.977101
 while
for next i:0
log already send
error: latency timeout updated_timestamp :2017-03-11 18:37:04
time now :2017-03-11 18:37:14.094837
for next i:1
log already send
error: latency timeout updated_timestamp :2017-03-11 18:37:04
time now :2017-03-11 18:37:14.125619
for next i:2
log already send
error: latency timeout updated_timestamp :2017-03-11 18:37:04
time now :2017-03-11 18:37:14.132983
for next i:3
nothing todo wait for ALARM_TICKER
 while
for next i:0
log already send
latency -----------------------------------------------------------------:-1 day, 23:59:59.877493
for next i:1
log already send
latency -----------------------------------------------------------------:-1 day, 23:59:59.870395
for next i:2
log already send
latency -----------------------------------------------------------------:-1 day, 23:59:59.863593
for next i:3
nothing todo wait for ALARM_TICKER '''