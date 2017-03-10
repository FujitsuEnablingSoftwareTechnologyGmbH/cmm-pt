def save_testCase(db, testSuite):
    cursor = db.cursor()
    # save test entry
    sql = " INSERT INTO TestCase (testSuite, startTime) VALUES ('{0}', NOW());".format(testSuite)
    cursor.execute(sql)
    db.commit()
    return int(cursor.lastrowid)


def close_testCase(db, testCaseID):
    cursor = db.cursor()
    # save test entry
    sql = " Update TestCase " \
          "set endTime=NOW() " \
          "where testCaseID={0};".format(testCaseID)
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
