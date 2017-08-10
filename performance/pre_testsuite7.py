import httplib
import random
from urlparse import urlparse
import time
import simplejson
import yaml
from influxdb import InfluxDBClient
from keystoneclient.v2_0 import client

from performance import TokenHandler

number_of_metric_per_user = [250, 200, 140, 80, 60, 30, 2]
default_tenant_name = 'stuser'
NUMBER_OF_USERS = len(number_of_metric_per_user)
METRIC_API_URL = 'http://10.172.196.74:8070/v2.0/metrics'
METRIC_NAME = 'test.jmetertest'
BASIC_CONF = yaml.load(file('./basic_configuration.yaml'))
INFLUX_URL = BASIC_CONF['url']['influxdb']
INFLUX_USER = BASIC_CONF['influxdb']['user']
INFLUX_PASSWORD = BASIC_CONF['influxdb']['password']
INFLUX_DATABASE = BASIC_CONF['influxdb']['database']
METRIC_API_URL = BASIC_CONF['url']['metrics_api'] + '/metrics'
KEYSTONE_URL_V2 = 'http://10.172.196.76:35357/v2.0'
KEYSTONE_URL_V3 = 'http://10.172.196.76:35357/v3'


def create_user():
    token = (TokenHandler.TokenHandler('admin', 'admin', 'admin', KEYSTONE_URL_V3)).get_valid_token()
    print token
    keystone = client.Client(auth_url=KEYSTONE_URL_V2, token=token,
                             endpoint=KEYSTONE_URL_V2)
    old_user = keystone.users.list()
    old_tenants = keystone.tenants.list()
    roles = keystone.roles.list()
    admin_role = [x for x in roles if x.name == 'admin'][0]
    cmm_user_role = [x for x in roles if x.name == 'cmm-user'][0]
    print old_user

    for i in range(1, NUMBER_OF_USERS + 1):

        if not [x for x in old_tenants if x.name == '{}{}'.format(default_tenant_name, i)]:
            tenant = keystone.tenants.create('{}{}'.format(default_tenant_name, i),
                                             description="SystemTest tenanats".format(i), enabled=True)
        else:
            tenant = [x for x in old_tenants if x.name == '{}{}'.format(default_tenant_name, i)][0]
        if not [x for x in old_user if x.name == '{}{}'.format(default_tenant_name, i)]:
            user = keystone.users.create(name='{}{}'.format(default_tenant_name, i),
                                         password='{}{}'.format(default_tenant_name, i).format(i), tenant_id=tenant.id)
        else:
            keystone.users.delete(user=[x for x in old_user if x.name == '{}{}'.format(default_tenant_name, i)][0])
            user = keystone.users.create(name='{}{}'.format(default_tenant_name, i),
                                         password='{}{}'.format(default_tenant_name, i), tenant_id=tenant.id)

        keystone.roles.add_user_role(user, admin_role, tenant)
        keystone.roles.add_user_role(user, cmm_user_role, tenant)


def get_tokens_for_all_new_user():
    return [TokenHandler.TokenHandler('{}{}'.format(default_tenant_name, i), '{}{}'.format(default_tenant_name, i),
                                      '{}{}'.format(default_tenant_name, i),
                                      KEYSTONE_URL_V3).get_valid_token()
            for i in range(1, NUMBER_OF_USERS + 1)]


def delete_test_metric():
    influx_client = InfluxDBClient(INFLUX_URL.split(':')[0], INFLUX_URL.split(':')[1], INFLUX_USER, INFLUX_PASSWORD,
                                   INFLUX_DATABASE)
    influx_client.query('drop series from "{}"'.format(METRIC_NAME))


def create_metric_for_all_user():
    tokens = get_tokens_for_all_new_user()
    url_parse = urlparse(METRIC_API_URL)
    conn = httplib.HTTPConnection(url_parse.netloc)
    current_utc_time = int((round(time.time() * 1000)))
    for idx, number_of_metric in enumerate(number_of_metric_per_user):
        print tokens[idx]
        header = {"Content-type": "application/json", "X-Auth-Token": tokens[idx]}
        body = list()
        for i in range(number_of_metric):
            body.append({'name': METRIC_NAME, 'dimensions': {'hostname': 'virtualSystmeTest'},
                         'timestamp': current_utc_time + i, 'value': random.randint(0, 100),
                         'value_meta': {'user': default_tenant_name + str(idx + 1)}})
        json_body = simplejson.dumps(body)
        conn.request("POST", url_parse.path, json_body, header)
        response = conn.getresponse()
        response.read()


if __name__ == "__main__":
    create_user()
    delete_test_metric()
    create_metric_for_all_user()
