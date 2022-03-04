import boto3
import time
import datetime
from threading import Thread
from decimal import Decimal
from boto3.dynamodb.conditions import Key
import cv2
import os
import io
import sys
import numpy

class AddItems:
    """
    Class that calls Dynamo add_items API
    using a dedicated thread after SearchFaces return Name
    """
    def __init__(self, add_Class, add_StuID, add_Name,add_Temp):
        self.add_Class = add_Class
        self.add_StuID = add_StuID
        self.add_Name = add_Name
        self.add_Temp = add_Temp
        self.stopped = False

    def start(self):
        Thread(target=self.add_items, args=()).start()
        return self

    def add_items(self):
        #Get the present month
        ts = datetime.datetime.now()
        Present_Month = datetime.datetime.now().month
        #Convert month into string
        Month_dict = { 1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 7: "July", 8: "August", 9: "September", 10: "October", 11:"November", 12:"December"}
        strPresent_Month = Month_dict.get(Present_Month)
        
        try:
            client = boto3.client('dynamodb')
            dynamodb = boto3.resource('dynamodb')
            #Creating DynamoDB
            table = dynamodb.create_table(
            TableName= strPresent_Month,
            KeySchema=[
            {
                'AttributeName': 'Date',
                'KeyType': 'HASH'
            },
            {
                'AttributeName': 'Name',
                'KeyType': 'RANGE'
            }
            ],
            AttributeDefinitions=[
            {
                'AttributeName': 'Date',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'Name',
                'AttributeType': 'S'
            },
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 4,
                'WriteCapacityUnits': 4
            },
            )
    
            #Set Created_Table = True when a table is created
            Created_Table = 1
            

        except:
        #Get existing table
            try:
                client = boto3.client('dynamodb')
                resp = client.update_table(
                # Any attributes used in your new global secondary index must be declared in AttributeDefinitions
                    AttributeDefinitions=[
                        {
                            "AttributeName": "Class",
                            "AttributeType": "S"
                        }
                    ],
                    TableName = strPresent_Month,
                    # This is where you add, update, or delete any global secondary indexes on your table.
                    GlobalSecondaryIndexUpdates=[
                    {
                        "Create": {
                            # You need to name your index and specifically refer to it when using it for queries.
                            "IndexName": "Class_Index",
                            # Like the table itself, you need to specify the key schema for an index.
                            # For a global secondary index, you can use a simple or composite key schema.
                            "KeySchema": [
                            {
                                "AttributeName": "Class",
                                "KeyType": "HASH"
                            }
                            ],
                            # You can choose to copy only specific attributes from the original item into the index.
                            # You might want to copy only a few attributes to save space.
                            "Projection": {
                                "ProjectionType": "ALL"
                            },
                            # Global secondary indexes have read and write capacity separate from the underlying table.
                            "ProvisionedThroughput": {
                                "ReadCapacityUnits": 1,
                                "WriteCapacityUnits": 1,
                            }
                        }
                    }
                    ]
                )
                print("Secondary index added!")
            except:
                #print("failed to create index")
                pass
            Created_Table = 0
            table = dynamodb.Table(strPresent_Month)

        # To get the get the 7th month in the past
        if Created_Table is 1:
            
            Del_Month = Present_Month - 6
            if Del_Month < 1:
                Del_Month = 12 + Del_Month

            #Convert month into string
            strDelMonth = Month_dict.get(Del_Month)
            print(strDelMonth)

            #Delete table
            try:
                response = client.delete_table(
                TableName= DelMonth)
            
            except:
                print("No Past Table exists")
            
            #Changing the provisioned throughput
            try:
               Past_Month = Present_Month - 1
               if Past_Month < 1:
                    Past_Month = 12 + Past_Month
               strPast_Month = Month_dict.get(Past_Month)
               response = client.update_table(
               TableName = strPast_Month,
               ProvisionedThroughput = {
                    'ReadCapacityUnits': 1,
                    'WriteCapacityUnits': 1
                }
                )
               print(strPast_Month)
               
            except:
                print("No previous table")
        
        #Dynamo.Initiate()
        table = dynamodb.Table(strPresent_Month)
        table.put_item(
            Item={
                'Date': ts.strftime("%Y-%m-%d %H:%M"),
                'Name': self.add_Name,
                'Class': self.add_Class,
                'Student ID': self.add_StuID,
                'Temperature': round(Decimal(self.add_Temp),2)
            }
        )
        
    
