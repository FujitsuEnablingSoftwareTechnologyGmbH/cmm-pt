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
This program writes a defined log entry to the log files which the Monasca log agent monitors.
The Monasca Log Agent processes the entries of these log files and sends the content to the Monasca server.
The number of written logs per second will be used to determine the load given to the agent.

The public variables are described in common.yaml file.
All public variables are described in basic_configuration.yaml and test_configuration.yaml files
"""

import threading
import time
import logging
import yaml
import datetime
from Queue import Queue, Empty
from write_logs import create_file, write_line_to_file


TEST_NAME = 'logagent_write'
TEST_CONF = yaml.load(file('test_configuration.yaml'))
RUNTIME = TEST_CONF[TEST_NAME]['runtime']
LOG_EVERY_N = TEST_CONF[TEST_NAME]['log_ever_n']
INP_FILE_DIR = TEST_CONF[TEST_NAME]['inp_file_dir']
INP_FILES = TEST_CONF[TEST_NAME]['inp_file_list']
OUTP_FILE_DIR = TEST_CONF[TEST_NAME]['outp_file_dir']
OUTP_FILES_NAME_LIST = TEST_CONF[TEST_NAME]['outp_file_name']
UUID_DIR = TEST_CONF[TEST_NAME]['latency_uuid_dir']

#Queue empty: Timeout parameter
QUEUE_TIME_OUT = 5


class LogWriter(threading.Thread):
    def __init__(self, outfile, queue):
        threading.Thread.__init__(self)
        self.outfile = outfile
        self.queue = queue
        self.total_log_wrote = 0
        self.total_log_wrote_freq = 0

    def get_logger_configuration(self):
        logger = logging.getLogger(self.outfile)
        log_handler = logging.FileHandler(self.outfile)
        log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        log_handler.setFormatter(log_formatter)
        logger.addHandler(log_handler)
        logger.setLevel(logging.DEBUG)
        return logger

    def run(self):
        """check if queue is not empty, if find any message then write this message to the log file """
        start_time = time.time()
        pstart_time = datetime.datetime.now().strftime("%H:%M:%S.%f")
        interim_time_beg = time.time()
        logger = self.get_logger_configuration()

        try:
            while True:

                try:
                    msg = self.queue.get(True, QUEUE_TIME_OUT)
                    logger.log(logging.getLevelName(msg[0]), msg[1])
                    self.total_log_wrote += 1

                    if self.total_log_wrote % LOG_EVERY_N == 0:
                        interim_time_end = time.time()
                        print("count_all: {}; Time: {} seconds used to write {} log entries. {} logs/s"
                              .format(self.total_log_wrote, (interim_time_end - interim_time_beg), LOG_EVERY_N,
                                      LOG_EVERY_N / (interim_time_end - interim_time_beg)))
                        interim_time_beg = time.time()

                except Empty:
                    print("-----Queue empty-----")

                    if time.time() > (start_time + RUNTIME + QUEUE_TIME_OUT):
                        break
                    else:
                        continue
        finally:
            final_time = time.time()

            write_end_time = final_time - start_time - QUEUE_TIME_OUT

            self.total_log_wrote_freq = round((self.total_log_wrote / write_end_time), 2)
            print("-----Test Results----- :" + TEST_NAME)
            print("Start Time: ", pstart_time)
            print("End Time: ", datetime.datetime.now().strftime("%H:%M:%S.%f"))
            print("{} log entries in {} seconds".format(self.total_log_wrote, write_end_time))
            print("{} per second".format(round(self.total_log_wrote / write_end_time), 2))


class LogGenerator(threading.Thread):

    def __init__(self, msg, freq, input_file_name, outp_file_name, queue, log_level, latency_string=None):
        threading.Thread.__init__(self)
        self.freq = freq
        self.msg = msg
        self.input_file_name = input_file_name
        self.latency_string = latency_string
        self.outp_file_name = outp_file_name
        self.total = 0
        self.queue = queue
        self.log_level = log_level

    def write_results_to_file(self, size_of_message):

        result_str = "{},{},{},{}".format(str(self.input_file_name), str(size_of_message),
                                          str(self.freq), str(self.total))
        file_name = "ReadThread_{}_{}".format(self.input_file_name, self.outp_file_name)
        head_result_str = "input_file_name, length_of_message, frequency_written, total_logs_written_to_queue"
        lg_file1 = create_file(file_name)
        write_line_to_file(lg_file1, head_result_str)
        write_line_to_file(lg_file1, result_str)
        lg_file1.close()

    def run(self):
        """this method put specified logs to the queue in predefine interval"""
        start_time = time.time()
        message_to_write = [self.log_level, self.msg.replace("\n", "")]

        while time.time() < (start_time + RUNTIME):
            write_time_begin = time.time()

            if self.latency_string:
                message_to_write = [self.log_level, self.input_file_name + ": " + str(self.latency_string) + ":" + str(
                    self.total) + " " + self.msg.replace("\n", "")]
            self.queue.put(message_to_write)
            self.total += 1
            write_time_end = time.time()
            sleep_time = (1.0 / self.freq) - (write_time_end - write_time_begin)

            if sleep_time > 0:
                time.sleep(sleep_time)

        self.write_results_to_file(len(message_to_write))


def get_message_from_input_file(file_path):
    """Get log message from the specified file, this message will be write to the log file """
    with open(file_path) as f:
        return f.read()


if __name__ == "__main__":
    write_thread_list = []
    test_start_date = (datetime.datetime.now().strftime("%Y-%m-%dT%H_%M_%S.%f"))[:-3]

    total_log_count = 0

    for output_file_name in OUTP_FILES_NAME_LIST:
        q = Queue()

        for input_file in INP_FILES:
            message = get_message_from_input_file(INP_FILE_DIR + input_file['name'])
            t = LogGenerator(message, input_file['frequency'], input_file['name'], output_file_name, q, input_file['loglevel'])
            t.start()

        write_thread = LogWriter(OUTP_FILE_DIR + output_file_name, q)
        write_thread.start()
        write_thread_list.append(write_thread)
    final_result_file = create_file(TEST_NAME + "_final")

    for thread_index, thread in enumerate(write_thread_list):
        thread.join()
        final_result_file.write("Thread = {}, file = {}, log_wrote = {}, frequency = {}\n"
                                .format(str(thread_index), thread.outfile, thread.total_log_wrote,
                                        thread.total_log_wrote_freq))
        total_log_count += thread.total_log_wrote
    final_result_file.write("Total logs wrote ={}".format(total_log_count))
    final_result_file.close()



