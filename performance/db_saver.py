import MySQLdb
import yaml


def save_test(db, testCaseID, testName):
    cursor = db.cursor()
    # save test entry
    sql = " INSERT INTO Test (testCaseID, testName) VALUES ({0}, '{1}');".format(testCaseID, testName)
    cursor.execute(sql)
    db.commit()
    # return the test ID
    sql = " select max(testID) from Test where testName like '{0}'".format(testName)
    cursor.execute(sql)
    return int(cursor.fetchone()[0])


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
