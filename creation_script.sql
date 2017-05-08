create database cmm;
use cmm;

CREATE TABLE `TestCase` (
	`testCaseID` INT NOT NULL auto_increment,
	`testSuite` VARCHAR(12) NOT NULL,
	`startTime` DATETIME NOT NULL,
	`endTime` DATETIME,
	PRIMARY KEY (`testCaseID`)
);

CREATE TABLE `Test` (
	`testID` INT NOT NULL auto_increment,
	`testCaseID` INT NOT NULL,
	`testName` varchar(30) NOT NULL,
	PRIMARY KEY (`testID`)
);

CREATE TABLE `Result` (
	`resultID` INT NOT NULL auto_increment,
	`testID` INT(20) NOT NULL,
	`resultName` varchar(30) NOT NULL,
	`resultValue` varchar(30) NOT NULL,
	`timeStamp` DATETIME,
	PRIMARY KEY (`resultID`)
);

CREATE TABLE `cpu_percent` (
	`cpu_percent_ID`   INT NOT NULL auto_increment,
	`testCaseID` INT NOT NULL,
	`value` FLOAT NOT NULL,
	`time_stamp` DATETIME NOT NULL,
	`hostname` VARCHAR(100),
	PRIMARY KEY (`cpu_percent_ID`)
);

CREATE TABLE `mem_used_mb` (
	`mem_used_mb_ID` INT NOT NULL auto_increment,
	`testCaseID` INT NOT NULL,
	`value` DECIMAL NOT NULL,
	`time_stamp` DATETIME NOT NULL,
	`hostname` VARCHAR(100),
	PRIMARY KEY (`mem_used_mb_ID`)
);

CREATE TABLE `disk_usage` (
	`disk_usage_ID` INT NOT NULL auto_increment,
	`testCaseID` INT NOT NULL,
	`value_before` DECIMAL,
	`value_after` DECIMAL,
	`hostname` VARCHAR(100),
	PRIMARY KEY (`disk_usage_ID`)
);

CREATE TABLE `kafka_lag` (
	`kafka_lag_ID` INT NOT NULL auto_increment,
	`testCaseID` INT NOT NULL,
	`time_stamp` DATETIME NOT NULL,
	`logstash_persister` DECIMAL NOT NULL,
	`1_metrics` DECIMAL NOT NULL,
	`transformer_logstash_consumer` DECIMAL NOT NULL,	
	PRIMARY KEY (`kafka_lag_ID`)
);

ALTER TABLE `Test` ADD CONSTRAINT `Test_TestCase_fk` FOREIGN KEY (`testCaseID`) REFERENCES `TestCase`(`testCaseID`) ON DELETE CASCADE;

ALTER TABLE `cpu_percent` ADD CONSTRAINT `cpu_percent_TestCase_fk` FOREIGN KEY (`testCaseID`) REFERENCES `TestCase`(`testCaseID`) ON DELETE CASCADE;

ALTER TABLE `mem_used_mb` ADD CONSTRAINT `ram_usage_TestCase_fk` FOREIGN KEY (`testCaseID`) REFERENCES `TestCase`(`testCaseID`) ON DELETE CASCADE;

ALTER TABLE `disk_usage` ADD CONSTRAINT `disk_usage_TestCase_fk` FOREIGN KEY (`testCaseID`) REFERENCES `TestCase`(`testCaseID`) ON DELETE CASCADE;

ALTER TABLE `kafka_lag` ADD CONSTRAINT `kafka_lag_TestCase_fk` FOREIGN KEY (`testCaseID`) REFERENCES `TestCase`(`testCaseID`) ON DELETE CASCADE;

ALTER TABLE `Result` ADD CONSTRAINT `Result_Test_fk` FOREIGN KEY (`testID`) REFERENCES `Test`(`testID`) ON DELETE CASCADE;

-- The following line in needed in case some scripts are to be launched individually and not within a test suite
Insert into TestCase(testCaseID, testSuite, startTime) values ('1', 'default', NOW());