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
This program is used to measure the latency directly in elasticsearch.
log entries are searched for using LATENCY:<uuid>:<count>:<timestamp>.
The logfile written contains this information.
"""

import search_logs
import yaml
import datetime
import sys
from write_logs import create_file, write_line_to_file, serialize_logging

test_name = "logagent_latency"

TEST_CONF = yaml.load(file('test_configuration.yaml'))
LOG_EVERY_N = TEST_CONF[test_name]['LOG_EVERY_N']
SEARCH_COUNT = TEST_CONF[test_name]['count']
UUID_FILE = sys.argv[1] if len(sys.argv) > 1 else TEST_CONF[test_name]['uuid_file']


def get_uuid_list_from_file():
    return [line.rstrip('\n').split("uuid=")[1] for line in open(UUID_FILE)]


def get_log_timestamp(log_json):
    """get timestamp filed from response returned by elasticsearch"""
    utc_time = datetime.datetime.strptime(log_json[0]['_source']['@timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ")
    return utc_time + datetime.timedelta(hours=2)


def get_log_create_time(log_json):
    """get log creation time  filed from response returned by elasticsearch"""
    msg_org = log_json[0]['_source']['message'].split(" ")
    return datetime.datetime.strptime("".join(msg_org[0:2]), "%Y-%m-%d%H:%M:%S,%f")


def run_latency_check(search_uuid):
    print("Start Time: {} ".format(datetime.datetime.now().strftime("%H:%M:%S.%f")))
    count = 1
    while count < SEARCH_COUNT:
        latency_search_str = search_uuid + ":" + str(count)
        response_data, status = search_logs.search_logs_by_message_simplematach(latency_search_str)

        if len(response_data) > 0:
            log_timestamp = get_log_timestamp(response_data)
            log_create_time = get_log_create_time(response_data)
            log_latency = (log_timestamp - log_create_time).total_seconds()
            my_logger = "{},True,{},{},{}".format(str(count), str(log_create_time), str(log_timestamp), str(log_latency))
        else:
            my_logger = str(count) + ",False,0,0,0"

        serialize_logging(lg_file, my_logger)
        if count % LOG_EVERY_N == 0:
            print("Time: {}; count: {}".format(datetime.datetime.now().strftime("%H:%M:%S.%f"), count))

        count += 1

    print("-----Test Results----- :" + test_name)
    print("End Time: ", datetime.datetime.now().strftime("%H:%M:%S.%f"))

if __name__ == "__main__":
    for uuid in get_uuid_list_from_file():
        lg_file = create_file(test_name)
        header_line = "count, search_status, message_write_time, timestamp_in_DB, latency(in second)"
        result = write_line_to_file(lg_file, header_line)
        run_latency_check(uuid)
        lg_file.close()
