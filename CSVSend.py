#Create CSV file from dynamoDB and sends to SES(Email)
from threading import Thread
import boto3
import os
import csv
from datetime import datetime
from pytz import timezone
from boto3.dynamodb.conditions import Key

from botocore.exceptions import ClientError
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

class CSVEmail:
    
    def __init__(self, Find_Table, Class, Recipient, Teacher):
        self.Find_Table = Find_Table
        self.Class = Class
        self.stopped = False
        self.Recipient = str(Recipient)
        self.Teacher = Teacher
    
    def start(self):
        Thread(target=self.CSV, args=()).start()
        return self
    
    def get_timestamps(self):
        asia = timezone('Asia/Singapore')
        asia_date = datetime.now(asia)
        fmt = '%d-%m-%Y'
        date_format = asia_date.strftime(fmt)
        time_format = asia_date.strftime('%I:%M:%p')
        
        return {
            "date_format" : str(date_format),
            "time_format" :str(time_format)
            }
    
    def CSV(self):
        #import dynamodb
        client = boto3.client('dynamodb')
        dynamodb = boto3.resource('dynamodb')
        
        timestamps = self.get_timestamps()

        # name csv file
        fileNameFormat = 'RaspiTAR_Records{}_'.format(timestamps.get("date_format")) + self.Class #datetime.datetime.now()
        csvFileName = '/home/pi/RaspiTAR_App/RaspiTAR/{}.csv'.format(fileNameFormat)

        #######################Query and create csv file##########################
        table = dynamodb.Table(self.Find_Table)
        response = table.query(
                IndexName="Class_Index",
                KeyConditionExpression=Key('Class').eq(self.Class)
                )

        if len(response['Items']) !=0:
            items = response['Items']
            #Get keys of the first object for the headers/ columns for our csv
            keys = items[0].keys()
                
            for i in items:
                with open(csvFileName,'a') as f:
                    dict_writer = csv.DictWriter(f,keys)
                    # Check to see if it is the first write
                    if f.tell() == 0:
                        dict_writer.writeheader()
                        dict_writer.writerow(i)
                    else:
                        dict_writer.writerow(i)
                        
        ##########Sending the CSV file to email.############
        email = "xin.isa.raspberry@gmail.com"
        # This address must be verified with Amazon SES.
        SENDER = "xin.isa.raspberry@gmail.com"

        # Replace recipient@example.com with a "To" address. If your account 
        # is still in the sandbox, this address must be verified.
        RECIPIENT = self.Teacher

        # The subject line for the email.
        SUBJECT = "RaspiTAR Attendance for " + self.Class  

        client = boto3.client('ses')

        msg = MIMEMultipart()
        msg['Subject'] = SUBJECT
        msg['From'] = SENDER
        msg['To'] = RECIPIENT

        part = MIMEText('Hello, \nYou are receiving this email because you have requested for the attendance from the RaspiTAR application. \nRequested from: '+ self.Teacher + '\nClass: '+ self.Class +'\n\nWith Love, \nRaspiTAR Team')
        msg.attach(part)

        msg_body = MIMEMultipart('alternative')

        att = MIMEApplication(open( csvFileName,'rb').read())
        att.add_header('Content-Disposition','attachment',filename = os.path.basename(csvFileName))
        msg.attach(msg_body)
        msg.attach(att)

        try:
            response = client.send_raw_email(
                Source = SENDER,
                Destinations = [RECIPIENT],
                RawMessage = {
                    'Data' : msg.as_string(),
                    },
                )
        except ClientError as e:
                print(e.response['Error']['Message'])

        ############### After sending the csv, delete the csv as it cannot be overwritten. To get updated csv, have to delete.########
        os.remove(csvFileName)