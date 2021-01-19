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
    def __init__(self, Date, Name, StudentID, Temp):
        self.Date = Date
        self.Name = Name
        self.StudentID = StudentID
        self.Temp = Temp
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
        SUBJECT = "Amazon SES Test (SDK for Python)"  

        client = boto3.client('ses')

        msg = MIMEMultipart()
        msg['Subject'] = SUBJECT
        msg['From'] = SENDER
        msg['To'] = RECIPIENT

        part = MIMEText('Hello, You are receiving this email because there is a high temperature recorded.Please kindly ask the student to exit the campus and seek medical attention.\n\n\nDate:'+ str(self.Date)+ '\nName:'+ self.Name+' \nStudent ID:'+self.StudentID+'\nTemperature:'+ str(self.Temp))
        msg.attach(part)

        msg_body = MIMEMultipart('alternative')

        att = MIMEApplication(open('/home/pi/Codes/AWS-Services/Local File/Image.jpeg','rb').read())
        att.add_header('Content-Disposition','attachment',filename = os.path.basename('/home/pi/Codes/AWS-Services/Local File/Image.jpeg'))
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