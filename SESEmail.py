import os
import boto3
from threading import Thread

from botocore.exceptions import ClientError
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

class SESEmail:
    """
    Class that calls SES using a dedicated thread 
    """
    def __init__(self, Date, Name, StudentID, Temp, Class):
        self.Date = Date
        self.Name = Name
        self.StudentID = StudentID
        self.Temp = Temp
        self.Class = Class
        self.stopped = False

    def start(self):
        Thread(target=self.send_email, args=()).start()
        return self

    def send_email(self):
        # This address must be verified with Amazon SES.
        SENDER = "xin.isa.raspberry@gmail.com"

        # Replace recipient@example.com with a "To" address. If your account 
        # is still in the sandbox, this address must be verified.
        RECIPIENT = "xin.isa.raspberry@gmail.com"

        # The subject line for the email.
        SUBJECT = "High Temperature Detected (" + self.Class + ")"  

        client = boto3.client('ses')

        msg = MIMEMultipart()
        msg['Subject'] = SUBJECT
        msg['From'] = SENDER
        msg['To'] = RECIPIENT

        part = MIMEText('Hello, \n\nYou are receiving this email because there is a high temperature recorded for your student with the details below.\nPlease kindly ask the student to exit the campus and seek medical attention.\n\n\nDate:'+ str(self.Date)+ '\nClass:' + self.Class + '\nName:'+ self.Name+' \nStudent ID:'+self.StudentID+'\nTemperature:'+ str(self.Temp) + "°C")
        msg.attach(part)

        msg_body = MIMEMultipart('alternative')

        att = MIMEApplication(open('/home/pi/Desktop/RaspiTAR_App/LocalFile/Image.jpg','rb').read())
        att.add_header('Content-Disposition','attachment',filename = os.path.basename('/home/pi/Desktop/RaspiTAR_App/LocalFile/Image.jpg'))
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
                
                
Name = "Chong Yijing ISabel"
StudID = "106F"
temp = "37.5"
Class = "CED22"
SESEmail("time", Name, StudID, temp, Class).start()