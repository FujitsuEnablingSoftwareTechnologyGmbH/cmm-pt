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

"""Module for sending search and count query to elasticserach databases"""

import httplib
from oslo_serialization import jsonutils as json


ELASTIC_SEARCH_PATH = "/_search"
ELASTIC_COUNT_PATH = "/_count"
REST_HEADER = {"Content-type": "application/json", "Accept": "application/json"}


def serialize_to_json(body):
    return json.dumps(body)


def deserialize_json(body):
    return json.loads(body)


def search_logs_by_message(message, elastic_url):
    conn = httplib.HTTPConnection(elastic_url)

    body = serialize_to_json(dict(
        query=dict(
            match=dict(
                message=dict(
                    query=message,
                    operator="and")
            )
        )
    ))

    conn.request("POST", ELASTIC_SEARCH_PATH, body, REST_HEADER)
    res = conn.getresponse()
    body = deserialize_json(res.read())
    return body.get('hits', {}).get('hits', []), res.status


def search_logs_by_message_simplematach(message, elastic_url):
    conn = httplib.HTTPConnection(elastic_url)
    body = serialize_to_json(dict(
        query=dict(
            match_phrase=dict(
                message=dict(
                    query=message,
                    slop=0)
            )
        )
    ))
    conn.request("POST", ELASTIC_SEARCH_PATH, body, REST_HEADER)
    res = conn.getresponse()
    body = deserialize_json(res.read())
    str1 = body.get('hits', {}).get('hits', [])

    return str1, res.status


def count_logs_by_app_name(app_name, elastic_url):
    conn = httplib.HTTPConnection(elastic_url)
    body = serialize_to_json(dict(
        query=dict(
            match=dict(
                applicationname=app_name
            )
        )
    ))

    conn.request("POST", ELASTIC_COUNT_PATH, body, REST_HEADER)
    res = conn.getresponse()
    body = res.read()
    body = deserialize_json(body)
    return body.get('count', {}), res.status


def count_logs_by_app_type(app_type, elastic_url):
    conn = httplib.HTTPConnection(elastic_url)
    body = serialize_to_json(dict(
        query=dict(
            match=dict(
                application_type=app_type
            )
        )
    ))
    conn.request("POST", ELASTIC_COUNT_PATH, body, REST_HEADER)
    res = conn.getresponse()
    body = res.read()
    body = deserialize_json(body)
    return body.get('count', {}), res.status


def count_logs_by_app_message(message, elastic_url):
    conn = httplib.HTTPConnection(elastic_url)
    body = serialize_to_json(dict(
        query=dict(
            match=dict(
                message=message
            )
        )
    ))
    conn.request("POST", ELASTIC_COUNT_PATH, body, REST_HEADER)
    res = conn.getresponse()
    body = deserialize_json(res.read())
    return body.get('count', {}), res.status


