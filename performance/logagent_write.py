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
import argparse
import datetime
import logging
import sys
import threading
import time
import yaml
from Queue import Queue, Empty
from write_logs import create_file, write_line_to_file

TEST_NAME = 'logagent_write'

#Queue empty: Timeout parameter
QUEUE_TIME_OUT = 5


class LogWriter(threading.Thread):
    def __init__(self, outfile, queue, log_every_n, runtime):
        threading.Thread.__init__(self)
        self.outfile = outfile
        self.queue = queue
        self.log_every_n = log_every_n
        self.runtime = runtime
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

                    if self.total_log_wrote % self.log_every_n == 0:
                        interim_time_end = time.time()
                        interim_time_diff = interim_time_end - interim_time_beg
                        print("file {}- count_all: {}; Time: {} seconds used to write {} log entries. {} logs/s"
                              .format(self.outfile, self.total_log_wrote, interim_time_diff, self.log_every_n,
                                      self.log_every_n / interim_time_diff))
                        interim_time_beg = time.time()

                except Empty:
                    print("-----Queue empty-----")

                    if time.time() > (start_time + self.runtime + QUEUE_TIME_OUT):
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

    def __init__(self, runtime, msg, freq, input_file_name, outp_file_name, queue, log_level, latency_string=None):
        threading.Thread.__init__(self)
        self.freq = freq
        self.msg = msg
        self.runtime = runtime
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

        while time.time() < (start_time + self.runtime):
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


class LogagentWrite(threading.Thread):
    def __init__(self, runtime, log_every_n, inp_file_dir, inp_files, outp_file_dir, outp_file_name, outp_count):
        threading.Thread.__init__(self)
        self.runtime = runtime
        self.log_every_n = log_every_n
        self.inp_file_dir = inp_file_dir
        self.inp_files = inp_files
        self.outp_file_dir = outp_file_dir
        self.outp_file = outp_file_name
        self.outp_count = outp_count
        self.result_file = create_file(TEST_NAME + "_final")

    def run(self):
        write_thread_list = []
        total_log_count = 0

        for i in range(self.outp_count):
            q = Queue()
            out_file = self.outp_file.split('.')[0] + str(i) + "." + self.outp_file.split('.')[1]
            for input_file in self.inp_files:
                message = self.get_message_from_input_file(self.inp_file_dir + input_file['name'])
                t = LogGenerator(self.runtime, message, input_file['frequency'], input_file['name'], out_file,
                                 q, input_file['loglevel'])
                t.start()

            write_thread = LogWriter(out_file, q, self.log_every_n, self.runtime)
            write_thread.start()
            write_thread_list.append(write_thread)

        for thread_index, thread in enumerate(write_thread_list):
            thread.join()
            self.result_file.write("Thread = {}, file = {}, log_wrote = {}, frequency = {}\n".
                                   format(str(thread_index), thread.outfile, thread.total_log_wrote,
                                          thread.total_log_wrote_freq))
            total_log_count += thread.total_log_wrote
        self.result_file.write("Total logs wrote ={}".format(total_log_count))
        self.result_file.close()

    def get_message_from_input_file(self, file_path):
        """Get log message from the specified file, this message will be write to the log file """
        with open(file_path) as f:
            return f.read()


def create_program_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-runtime', action='store', dest='runtime', type=int)
    parser.add_argument('-log_every_n', action='store', dest='log_every_n', type=int)
    parser.add_argument('-inp_file_dir', action='store', dest='inp_file_dir', type=str)
    parser.add_argument('-inp_file_list', action='store', dest='inp_file_list', nargs='+')
    parser.add_argument('-outp_file_dir', action='store', dest='outp_file_dir', type=str)
    parser.add_argument('-outp_file_name', action='store', dest='outp_file_name', type=str)
    parser.add_argument('-outp_count', action='store', dest='outp_count',type=int)
   

    return parser.parse_args()

if __name__ == "__main__":

    if len(sys.argv) <= 1:
        TEST_CONF = yaml.load(file('test_configuration.yaml'))
        RUNTIME = TEST_CONF[TEST_NAME]['runtime']
        LOG_EVERY_N = TEST_CONF[TEST_NAME]['log_ever_n']
        INP_FILE_DIR = TEST_CONF[TEST_NAME]['inp_file_dir']
        INP_FILES = TEST_CONF[TEST_NAME]['inp_file_list']
        OUTP_FILE_DIR = TEST_CONF[TEST_NAME]['outp_file_dir']
        OUTP_FILES_NAME = TEST_CONF[TEST_NAME]['outp_file_name']
        OUTP_COUNT = TEST_CONF[TEST_NAME]['outp_count']
        
    else:
        program_argument = create_program_argument_parser()
        RUNTIME = program_argument.runtime
        LOG_EVERY_N = program_argument.log_every_n
        INP_FILE_DIR = program_argument.inp_file_dir
        INP_FILES = [{'name': int_file_cfg[0], 'frequency': int(int_file_cfg[1]), 'loglevel': int_file_cfg[2]}
                     for int_file_cfg in [int_file_cfg.split(':') for int_file_cfg in program_argument.inp_file_list]]
        OUTP_FILE_DIR = program_argument.outp_file_dir
        OUTP_FILES_NAME = program_argument.outp_file_name
        OUTP_COUNT = program_argument.outp_count
       

    logagnet_write = LogagentWrite(RUNTIME, LOG_EVERY_N, INP_FILE_DIR, INP_FILES, OUTP_FILE_DIR, OUTP_FILES_NAME, OUTP_COUNT)
    logagnet_write.start()



