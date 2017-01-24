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

"""This script is used to handle Keystone token operation"""

import os
import yaml
import ciso8601
import time
from monascaclient import ksclient


if os.path.isfile('test_configuration.yaml'):
    test_conf = yaml.load(file('test_configuration.yaml'))
    token_renew_time = test_conf['parameters']['token_renew_time']
else:
    token_renew_time = 1800


class TokenHandler:

    def __init__(self, username, password, project, auth_uri=None):
        self.username = username
        self.password = password
        self.project = project
        if auth_uri:
            self.auth_uri = auth_uri
        else:
            basic_conf = yaml.load(file('basic_configuration.yaml'))
            auth_uri = basic_conf['url']['keystone']
        self.auth_uri = auth_uri
        self.token_info = {"token_id": None,
                           "token_expire_time": 0,
                           "token_renew_time": token_renew_time}

    def get_valid_token(self):
        if self.token_info["token_id"] is None:
            token_id, token_expire_time = self.__get_new_token()
            self.token_info["token_id"] = token_id
            self.token_info["token_expire_time"] = token_expire_time
            return token_id

        else:
            if self.token_info["token_expire_time"]-time.time() <= self.token_info["token_renew_time"]:
                token_id, token_expire_time = self.__get_new_token()
                self.token_info["token_id"] = token_id
                self.token_info["token_expire_time"] = token_expire_time
                return token_id
            else:
                return self.token_info["token_id"]

    def __correct_token_time(self, t_time=None):
        """Return offset of local zone from GMT, either at present or at time t."""

        if t_time is None:
            t_time = time.time()

        if time.localtime(t_time).tm_isdst and time.daylight:
            return -time.altzone
        else:
            return -time.timezone

    def __get_new_token(self):
        """This function get new token from keystone then return this token and expiration time of this toke"""
        keystone = {
            'username': self.username,
            'password': self.password,
            'project_name': self.project,
            'auth_url':  self.auth_uri
        }

        ks_client = ksclient.KSClient(**keystone)
        convert_time = ciso8601.parse_datetime(str(ks_client._keystone.auth_ref.expires))
        tmp_str = str(convert_time).split('.')
        token_exp = time.mktime(time.strptime(tmp_str[0], '%Y-%m-%d %H:%M:%S'))
        factor = self.__correct_token_time()

        print ("Get new Token:                                      {}".format(ks_client.token))
        print ("Expiration time in UTC:                             {}".format(ks_client._keystone.auth_ref.expires))
        print ("Expiration time in seconds since beginning of time: {}".format(token_exp))
        print ("The FACTOR:                                         {}".format(factor))
        return ks_client.token, (token_exp + factor)

