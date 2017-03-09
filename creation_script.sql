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

ALTER TABLE `Test` ADD CONSTRAINT `Test_TestCase_fk` FOREIGN KEY (`testCaseID`) REFERENCES `TestCase`(`testCaseID`) ON DELETE CASCADE;

ALTER TABLE `Result` ADD CONSTRAINT `Result_Test_fk` FOREIGN KEY (`testID`) REFERENCES `Test`(`testID`) ON DELETE CASCADE;

-- The following line will be deleted once the launcher program is ready
Insert into TestCase(testCaseID, testSuite, startTime) values ('1', 'default', NOW());