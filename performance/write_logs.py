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

"""This program provide function for creating unique result file and write test result to the file """

import datetime
import os
import os.path
import time
import uuid
import yaml


if os.path.isfile('test_configuration.yaml'):
    test_conf = yaml.load(file('test_configuration.yaml'))
    LOG_DIR = test_conf['write_result']['directory']
    LOG_FILE_FORMAT = '.csv'
else:
    LOG_DIR = 'test_result/'
    LOG_FILE_FORMAT = '.csv'


def create_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


def create_file(test_name):
    create_directory(LOG_DIR)
    lg_file_long = LOG_DIR + test_name + '_' + (datetime.datetime.now().strftime("%Y-%m-%dT%H_%M_%S.%f"))[:-3]\
        + LOG_FILE_FORMAT
    log_file = open(lg_file_long, 'a')
    return log_file


def write_line_to_file(lg_file, body):
    lg_file.write(body + '\n')
    lg_file.flush()


def create_tmp_file():
    """create temporary file with unique name"""
    filename = LOG_DIR + str(uuid.uuid1())
    fp = open(filename, 'w')
    fp.close()
    return filename


def serialize_logging(lg_file, log_entry):
    """This method is used to write result line to the file when multiple client use the same file"""
    num_tries = 10
    wait_time = 2
    lock_filename = 'logging.lock'
    acquired = False
    for try_num in xrange(num_tries):
        tmp_filename = create_tmp_file()
        if not os.path.exists(LOG_DIR + lock_filename):
            try:
                if os.name != 'nt':  # non-windows needs a create-exclusive operation
                    fd = os.open(LOG_DIR + lock_filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
                    os.close(fd)
                # non-windows os.rename will overwrite lock_filename silently.
                # We leave this call in here just so the tmp file is deleted but
                # it could be refactored so the tmp file is never even generated for a non-windows OS
                os.rename(tmp_filename, LOG_DIR + lock_filename)
                # os.rename(tmp_filename,lock_filename)
                acquired = True
            except (OSError, ValueError, IOError), e:
                pass
        if acquired:
            try:
                write_line_to_file(lg_file, log_entry)
            finally:
                os.remove(LOG_DIR + lock_filename)
            break
        os.remove(tmp_filename)
        time.sleep(wait_time)
    assert acquired, 'maximum tries reached, failed to acquire lock file'
