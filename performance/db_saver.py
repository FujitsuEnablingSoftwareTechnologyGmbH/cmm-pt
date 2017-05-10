from datetime import datetime


def save_testCase(db, testSuite):
    cursor = db.cursor()
    start_time = datetime.utcnow().replace(microsecond=0)
    # save test entry
    sql = " INSERT INTO TestCase (testSuite, startTime) VALUES ('{0}', '{1}');".format(testSuite, start_time)
    cursor.execute(sql)
    db.commit()
    return int(cursor.lastrowid)


def close_testCase(db, testCaseID):
    cursor = db.cursor()
    end_time = datetime.utcnow().replace(microsecond=0)
    # save test entry
    sql = " Update TestCase " \
          "set endTime='{1}' " \
          "where testCaseID={0};".format(testCaseID, end_time)
    cursor.execute(sql)
    db.commit()


def save_test(db, testCaseID, testName):
    cursor = db.cursor()
    # save test entry
    sql = " INSERT INTO Test (testCaseID, testName) VALUES ({0}, '{1}');".format(testCaseID, testName)
    cursor.execute(sql)
    db.commit()
    return int(cursor.lastrowid)


def save_test_params(db, testID, testParams):
    cursor = db.cursor()
    # save test input parameters
    for param in testParams:
        try:
            sql = "insert into Result (testID,resultName,resultValue) values ({0},'{1}','{2}');" \
                .format(testID, param[0], param[1])
            cursor.execute(sql)
            db.commit()
        except:
            db.rollback()
    db.commit()


def save_test_results(db, testID, testResults):
    cursor = db.cursor()
    # save test input parameters
    for res in testResults:
        try:
            sql = "insert into Result (testID,resultName,resultValue, timeStamp) values ({0},'{1}','{2}','{3}');" \
                .format(testID, res[0], res[1], res[2])
            cursor.execute(sql)
            db.commit()
        except:
            db.rollback()
    db.commit()


def save_metrics(db, testID, metric_name, metrics, hostname):
    cursor = db.cursor()
    for metric in metrics:
        try:
            time_stamp = str(datetime.strptime(metric[0], '%Y-%m-%dT%H:%M:%S.%fZ').replace(microsecond=0))
            sql = "insert into {} (testCaseID, time_stamp, value, hostname) values ({}, '{}' ,{}, '{}');" \
                .format(metric_name.replace('.', '_'), testID, time_stamp, metric[1], hostname)
            cursor.execute(sql)
        except Exception as e:
            print "failed to save to db. ", e
    db.commit()


def save_kafka_lag_metrics(db, testID, kafka_metrics):
    cursor = db.cursor()
    print kafka_metrics
    for kafka_metric in kafka_metrics:
        try:
            time_stamp = str(datetime.strptime(kafka_metrics[0][0], '%Y-%m-%dT%H:%M:%S.%fZ').replace(microsecond=0))
            sql = "insert into kafka_lag (testCaseID, time_stamp, logstash_persister, 1_metrics, " \
                  "transformer_logstash_consumer) values ({}, '{}', {}, {}, {});" \
                .format(testID, time_stamp, kafka_metric[1], kafka_metric[2], kafka_metric[3])
            cursor.execute(sql)
        except Exception as e:
            print "failed to save to db. ", e
    db.commit()

