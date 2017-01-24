# CMM Performance test (CMM-PT)

CMM-PT is test framework designed to test the performance of the different [CMM] components.

With this test suite, you can test:
* Metrics throughput and latency.
* Logs throughput and latency (ingle and bulk mode).
* Alarms on logs.
* Additional features will follow...

## Installation
It is recommanded to install and run this test suite in a virtual environment.

1. Create a virtualenv:
```sh
$ pip install virtualenv
$ cd <virtualenv_directory>
$ virtualenv <name>
$ source <virtualenv_directory>/<name>/bin/activate
```
2. Clone this repository.
3. Install the required python packages
```sh
$ pip install -r <CMM-PT_directory>/requirements.txt
```
4. Create the basic configuration file: use the template provided in basic_configuration_template.yaml
5. Create the test configuration file: use the template provided in test_configuration_template.yaml
6. Enjoy CMM-ST!

## Configuration

##### Basic configuration

The basic  configuration can be set in basic_configuration.yaml
In this file, you have to specify the login credentials for Keystone tenants, InfluxDB and define the URLs of CMM and Keystone components.

##### Test configuration

The test configuration can be set in test_configuration.yaml
In this file, you have to specify the paramters of the test cases (runtime, frequency, output directory...).

## Usage example

To test the log throughput, proceed as follow:
1. Make sure that the variables "keystone", "log_api_url" and "elastic_url" and the "users" section are all set properly in basic_configuration.yaml
2. Configure "log_throughput", "log_send" and "write_result" parts of test_configuration.yaml
3. Run log_throuput.py
4. Run log_send.py
5. The results are stored in the directory set in the "write_result" part of test_configuration.yaml (.csv format is the defalut and recommanded, but can be changed).

## License
----
Apache License, Version 2.0


[CMM]: <http://www.fujitsu.com/global/products/software/infrastructure-software/cloud-management-software/cloud-monitoring-manager/>
