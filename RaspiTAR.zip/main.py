import faulthandler; faulthandler.enable()
import os
import io
import sys
import cv2
import time
import boto3
import numpy
import imutils
import argparse
import datetime
import threading
import traceback
import numpy as np
import tkinter as tk
from time import sleep
from PIL import Image
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

import seeed_mlx9064x
from serial import Serial

from DynamoAdd import AddItems
from SESEmail import SESEmail
from CSVSend import CSVEmail

import gspread
import datetime
from oauth2client.service_account import ServiceAccountCredentials

# For Temperature Map
hetaData = []
lock = threading.Lock()
minHue = 180
maxHue = 360
ChipType = 'MLX90641'
port = 'I2C'

global current_class
currrent_class = "initialise"

################################################### Temp Map Functions

def map_value(value, curMin, curMax, desMin, desMax):
    curDistance = value - curMax
    if curDistance == 0:
        return desMax
    curRange = curMax - curMin
    direction = 1 if curDistance > 0 else -1
    ratio = curRange / curDistance
    desRange = desMax - desMin
    value = desMax + (desRange / ratio)
    return value

def constrain(value, down, up):
    value = up if value > up else value
    value = down if value < down else value
    return value 

def is_digital(value):
    try:
        if value == "nan":
            return False
        else:
            float(value)
        return True
    except ValueError:
        return False
    
################################################### DataReader (QThread)
                  
class DataReader(QThread): #dont care about this, its just a thread to read the temperature
    drawRequire = pyqtSignal()
    I2C = 1
    SERIAL = 0
    MODE = I2C
    pixel_num = 192
    def __init__(self,port,ChipType):
        #Initialise the backend running processes for mlx90641
        super(DataReader, self).__init__()
        self.frameCount = 0
        # i2c mode
        DataReader.pixel_num = 192
        self.dataHandle = seeed_mlx9064x.grove_mxl90641()
        self.dataHandle.refresh_rate = seeed_mlx9064x.RefreshRate.REFRESH_8_HZ
        self.readData = self.i2c_read

    def i2c_read(self):
        #Read from cam and get value
        hetData = [0]*DataReader.pixel_num
        self.dataHandle.getFrame(hetData)
        return hetData
    
    def run(self):
        # throw first frame
        self.readData()
                
        while True:
            maxHet = 0
            minHet = 500
            tempData = []
            nanCount = 0

            hetData = self.readData()
            if  len(hetData) < DataReader.pixel_num :
                continue

            for i in range(0, DataReader.pixel_num):
                curCol = i % 32
                newValueForNanPoint = 0
                curData = None

                if i < len(hetData) and is_digital(hetData[i]):
                    curData = float(format(hetData[i],'.2f'))
                else:
                    interpolationPointCount = 0
                    sumValue = 0
                    print("curCol",curCol,"i",i)

                    abovePointIndex = i-32
                    if (abovePointIndex>0):
                        if hetData[abovePointIndex] is not "nan" :
                            interpolationPointCount += 1
                            sumValue += float(hetData[abovePointIndex])

                    belowPointIndex = i+32
                    if (belowPointIndex<DataReader.pixel_num):
                        print(" ")
                        if hetData[belowPointIndex] is not "nan" :
                            interpolationPointCount += 1
                            sumValue += float(hetData[belowPointIndex])
                            
                    leftPointIndex = i -1
                    if (curCol != 31):
                        if hetData[leftPointIndex]  is not "nan" :
                            interpolationPointCount += 1
                            sumValue += float(hetData[leftPointIndex])

                    rightPointIndex = i + 1
                    if (belowPointIndex<DataReader.pixel_num):
                        if (curCol != 0):
                            if hetData[rightPointIndex] is not "nan" :
                                interpolationPointCount += 1
                                sumValue += float(hetData[rightPointIndex])

                    curData =  sumValue /interpolationPointCount
                    # For debug :
                    # print(abovePointIndex,belowPointIndex,leftPointIndex,rightPointIndex)
                    # print("newValueForNanPoint",newValueForNanPoint," interpolationPointCount" , interpolationPointCount ,"sumValue",sumValue)
                    nanCount +=1

                tempData.append(curData)
                maxHet = tempData[i] if tempData[i] > maxHet else maxHet
                minHet = tempData[i] if tempData[i] < minHet else minHet

            if maxHet == 0 or minHet == 500:
                continue
            # For debug :
            # if nanCount > 0 :
            #     print("____@@@@@@@ nanCount " ,nanCount , " @@@@@@@____")
           
            lock.acquire()
            hetaData.append(
                {
                    "frame": tempData,
                    "maxHet": maxHet,
                    "minHet": minHet
                }
            )
            lock.release()
            self.drawRequire.emit()
            self.frameCount = self.frameCount + 1
        self.com.close()
        
################################################### painter

class painter(QGraphicsView):
    #initialise and use in class only
    narrowRatio = 1.25
    useBlur = 1
    pixelSize = int(15 / narrowRatio)
    width = int (480 / narrowRatio)
    height = int(360 / narrowRatio)
    fontSize = int(30 / narrowRatio)
    anchorLineSize = int(100 / narrowRatio)
    ellipseRadius = int(8 / narrowRatio)
    textInterval = int(90 / narrowRatio)
    col = width / pixelSize
    line = height / pixelSize
    centerIndex = int(round(((line / 2 - 1) * col) + col / 2)) 
    frameCount = 0
    baseZValue = 0
    textLineHeight = fontSize + 7
    blurRaduis = 50
    
    def __init__(self, parent=None):
        super(painter, self).__init__(parent = parent)
        self.showMaximized()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scene = QGraphicsScene()
        self.setGeometry(65, 365, 390, 322)
        self.setScene(self.scene)
        self.blurRaduis = 22
        self.ChipType = "MLX90641"
        # center het text item
        self.centerTextItem = QGraphicsTextItem()
        self.centerTextItem.setPos(self.width / 2 - self.fontSize, 0)
        self.centerTextItem.setZValue(self.baseZValue + 1)
        self.scene.addItem(self.centerTextItem)
        # anchor to get temperature
        centerX = self.width / 2
        centerY = self.height / 2
        self.ellipseItem = QGraphicsEllipseItem(
                0, 0, 
                self.ellipseRadius * 2, 
                self.ellipseRadius * 2
            )
        self.horLineItem = QGraphicsLineItem(0, 0, self.anchorLineSize, 0)
        self.verLineItem = QGraphicsLineItem(0, 0, 0, self.anchorLineSize)
        self.ellipseItem.setPos(
                (centerX - self.ellipseRadius), 
                (centerY - self.ellipseRadius)
            )
        self.horLineItem.setPos(centerX -self.anchorLineSize / 2, centerY)
        self.verLineItem.setPos(centerX , centerY - self.anchorLineSize / 2)
        self.ellipseItem.setPen(QColor(Qt.white))
        self.horLineItem.setPen(QColor(Qt.white))
        self.verLineItem.setPen(QColor(Qt.white))
        self.ellipseItem.setZValue(self.baseZValue + 1)
        self.horLineItem.setZValue(self.baseZValue + 1)
        self.verLineItem.setZValue(self.baseZValue + 1)
        self.scene.addItem(self.ellipseItem)
        self.scene.addItem(self.horLineItem)
        self.scene.addItem(self.verLineItem)
        # camera item
        self.cameraBuffer = QPixmap(self.width, self.height + self.textLineHeight)
        self.cameraItem = QGraphicsPixmapItem()
        if self.useBlur:
            self.gusBlurEffect = QGraphicsBlurEffect()
            self.gusBlurEffect.setBlurRadius(self.blurRaduis)
            self.cameraItem.setGraphicsEffect(self.gusBlurEffect)
            
        self.cameraItem.setPos(0, 0)
        self.cameraItem.setZValue(self.baseZValue)
        self.scene.addItem(self.cameraItem)
        # het text item
        
        #Size if black rectangle
        self.hetTextBuffer = QPixmap(self.width, self.textLineHeight)
        self.hetTextItem = QGraphicsPixmapItem()
        #Below for position of black rec
        self.hetTextItem.setPos(0, self.height)
        self.hetTextItem.setZValue(self.baseZValue)
        self.scene.addItem(self.hetTextItem)

    def draw(self):
        if len(hetaData) == 0:
            return
        font = QFont()
        color = QColor()
        font.setPointSize(self.fontSize)
        font.setFamily("Microsoft YaHei")
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0)
        index = 0
        lock.acquire()
        frame = hetaData.pop(0)
        lock.release()
        maxHet = frame["maxHet"]
        minHet = frame["minHet"]
        frame = frame["frame"]
        p = QPainter(self.cameraBuffer)
        #Bottom black rectangle
        p.fillRect(
                0, 0, self.width, 
                self.height + self.textLineHeight, 
                QBrush(QColor(Qt.black))
            )
        #  camera
        color = QColor()
        for yIndex in range(int(self.height / self.pixelSize / 2 )):
            for xIndex in range(int(self.width / self.pixelSize  / 2 )):
                tempData = constrain(map_value(frame[index], minHet, maxHet, minHue, maxHue), minHue, maxHue)
                color.setHsvF(tempData / 360, 1.0, 1.0)
                p.fillRect(
                    xIndex * self.pixelSize * 2,
                    yIndex * self.pixelSize * 2 ,
                    self.pixelSize * 2, self.pixelSize * 2,
                    QBrush(color)
                )
                index = index + 1
        if self.centerIndex == 0 or self.centerIndex>=192:
            self.centerIndex = 6*16+8            
        
        self.cameraItem.setPixmap(self.cameraBuffer)
        # draw text
        p = QPainter(self.hetTextBuffer)
        p.fillRect(
                0, 0, self.width, 
                self.height + self.textLineHeight, 
                QBrush(QColor(Qt.black))
            )
        hetDiff = maxHet - minHet
        bastNum = round(minHet)
        interval = round(hetDiff / 5)
        for i in range(5):
            hue = constrain(map_value((bastNum + (i * interval)), minHet, maxHet, minHue, maxHue), minHue, maxHue)
            color.setHsvF(hue / 360, 1.0, 1.0)
            p.setPen(color)
            p.setFont(font)
            p.drawText(i * self.textInterval, self.fontSize + 3, "  " + str(bastNum + (i * interval)) + "°")
        self.hetTextItem.setPixmap(self.hetTextBuffer)
        # Temperature is cneter
        global cneter
        cneter = round(frame[self.centerIndex], 1)
        centerText = "<font color=white>%s</font>"
        self.centerTextItem.setFont(font)
        self.centerTextItem.setHtml(centerText % (str(cneter) + "°"))
        self.frameCount = self.frameCount + 1

################################################### WorkerSignal

#Multithreading Worker Signal
class WorkerSignals(QObject):

    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object) #name will be returned here
    progress = pyqtSignal(int)
    
################################################### Worker (QRunnable)

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()


    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''
        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done

################################################### Main Window (QMainWindow)

class MainWindow(QMainWindow):
    def __init__(self, parent = None, *args, **kwargs):
        super().__init__(parent = parent, *args, **kwargs)
        self.setStyleSheet("background-color: white")
        self.counter = 0
        
        self.setWindowTitle("RaspiTAR Application")
        self.showMaximized()
        self.blockLabel = QLabel(" ")
        self.cameraLabel = QLabel("Initialising Camera...")
        self.cameraLabel.setAlignment(Qt.AlignCenter)
        self.snapLabel = QLabel("Waiting for Input...")
        self.snapLabel.setAlignment(Qt.AlignCenter)
        # To make up for the layout, IR camera space user
        
        self.bigFrame = QFrame(self)
        
        self.frame = QFrame()
        self.frame.resize(100, 200)
        #self.frame.setStyleSheet("border: 1px solid black")
        self.namenameLabel = QLabel("Name:")
        self.namenameLabel.setFont(QFont('Arial', 16))
        self.nameInputLabel = QLabel("Waiting for Input...")
        self.nameInputLabel.setFont(QFont('Arial', 16))
        self.countLabel = QLabel("Waiting for Input...")
        self.classLabel = QLabel("Loading Current Class...")
        self.classLabel.setStyleSheet("background-color: yellow")
        self.classLabel.setFont(QFont('Arial', 23))
        self.classLabel.setAlignment(Qt.AlignCenter)
        
        self.temptempLabel = QLabel("Temperature:")
        self.temptempLabel.setFont(QFont('Arial', 16))
        self.tempInputLabel = QLabel("Waiting for Input...")
        self.tempInputLabel.setFont(QFont('Arial', 16))
        
        self.quitButton = QPushButton("Exit Session", self)
        self.quitButton.clicked.connect(self.close)
        
        self.sendAttendanceButton = QPushButton("Send Attendance List", self)
        self.sendAttendanceButton.setStyleSheet("padding: 3px;")
        self.sendAttendanceButton.clicked.connect(self.sendCSV) 
        
        self.dateLabel = QLabel("")
        self.dateLabel.setAlignment(Qt.AlignCenter)
        self.timeLabel = QLabel(" ")
        self.timeLabel.setStyleSheet("background-color: yellow")
        self.timeLabel.setFont(QFont('Arial', 23))
        self.timeLabel.setAlignment(Qt.AlignCenter)
        # A
        self.vBoxOne = QVBoxLayout()
        self.vBoxOne.addWidget(self.cameraLabel)
        self.vBoxOne.addWidget(self.frame)
        
        # B
        self.vBoxTwo = QVBoxLayout()
        self.vBoxTwo.addWidget(self.snapLabel)
        self.gBox = QGridLayout()
        self.gBox.addWidget(self.namenameLabel, 1,0)
        self.gBox.addWidget(self.nameInputLabel, 1,1)
        self.gBox.addWidget(self.temptempLabel, 2,0)
        self.gBox.addWidget(self.tempInputLabel, 2,1)
        self.gBox.addWidget(self.classLabel, 3,0)
        self.gBox.addWidget(self.timeLabel, 3,1)
        self.gBox.addWidget(self.dateLabel, 4,0, 1,0)
        self.gBox.addWidget(self.sendAttendanceButton, 5,0)
        self.gBox.addWidget(self.quitButton, 5,1)
        self.vBoxTwo.addLayout(self.gBox)
        
        # X
        self.hBoxOne = QHBoxLayout()
        self.hBoxOne.addLayout(self.vBoxOne)
        self.hBoxOne.addLayout(self.vBoxTwo)
        
        self.widget = QWidget()
        self.widget.setLayout(self.hBoxOne)
        
        # Set the central widget of the Window. Widget will expand
        # to take up all the space in the window by default.
        self.setCentralWidget(self.widget)
        self.show()

        self.threadpool = QThreadPool()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())
                       
        """ Simulate temperature map running in the background """
        
        self.thread = VideoThread()
        self.thread.change_pixmap_signal.connect(self.init_video)
        self.thread.detectface_signal.connect(self.worker_function)
        self.thread.start()
        
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.recurring_timer)
        self.timer.start()
        
        self.thread_class = ClassThread()
        self.thread_class.start()
        
        """Initialise when first open application to get the current class"""
        
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        cred = ServiceAccountCredentials.from_json_keyfile_name('/home/pi/RaspiTAR_App/RaspiTAR/client_key.json', scope)
        client = gspread.authorize(cred)

        spr = client.open_by_url('https://docs.google.com/spreadsheets/d/1h8BkhqdnqTmtVdKOV13dpC3Is70OiEJ5VmvSFGQuYz4/edit#gid=0 ')
        wks = spr.worksheet('05-01')
        global sheet_all_records
        sheet_all_records = wks.get_all_records()
        global newlist
        newlist = dict()

        for ud in sheet_all_records:
            newlist[ud.pop('Start Time')] = ud
            
        ts = datetime.datetime.now()
        current_time = ts.strftime("%I:%M %p")
        current_min = ts.strftime("%M")
        current_min_int = int(current_min)

        if current_min_int < 30:
            decide_class = "00"
        else:
            decide_class = "30"
            
        decide_current_time = ts.strftime("%I:" + decide_class + " %p")
        global current_class
        global current_teacher
        global current_teacher_email
        global current_teacher_phone
        current_class = str(newlist[decide_current_time]['Class'])
        current_teacher = str(newlist[decide_current_time]['Teacher'])
        current_teacher_email = str(newlist[decide_current_time]['Email'])
        current_teacher_phone = str(newlist[decide_current_time]['Number'])
        self.classLabel.setText(current_class)
        
    def recurring_timer(self):
        self.dateDate = QDate.currentDate()
        self.timeTime = QTime.currentTime()
        self.date = self.dateDate.toString(Qt.DefaultLocaleLongDate)
        global time_now
        time_now = self.timeTime.toString(Qt.DefaultLocaleShortDate)
        self.dateLabel.setText(self.date)
        self.timeLabel.setText(time_now) #variable to be read
        self.classLabel.setText(current_class)
          
    def init_video(self, cv_img):
        """Updates the labelCam with a new opencv image, Continuous showing"""
        qt_img = self.convert_cv_qt(cv_img)
        self.cameraLabel.setPixmap(qt_img)
        
    def convert_cv_qt(self, cv_img):
        """Convert from an opencv image to QPixmap"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        p = convert_to_Qt_format.scaled(431, 321, Qt.KeepAspectRatio)
        return QPixmap.fromImage(p)
                        
    def closeEvent(self, event):
        result = QMessageBox.question(self,
                      "Confirm Exit",
                      "Are you sure you want to exit?",
                      QMessageBox.Yes| QMessageBox.No)
        event.ignore()

        if result == QMessageBox.Yes:
            self.thread.stop()
            event.accept()
            
    def execute_this_fn(self, current_frame): 
        image = cv2.resize(current_frame, (500, 500))
        is_success, im_buf_arr = cv2.imencode(".jpg", image)
        byte_im = im_buf_arr.tobytes()
                
        try:
            client=boto3.client('rekognition')
            response=client.search_faces_by_image(
                CollectionId = 'collectionbmebpd',
                Image={
                    'Bytes': byte_im
                },
                MaxFaces = 1,
                FaceMatchThreshold=95.0,
                QualityFilter='AUTO'
            )
            
            FaceId = response['FaceMatches'][0]['Face']['FaceId']
            Confidence = response['SearchedFaceConfidence']
            global Name
            iniName = response['FaceMatches'][0]['Face']['ExternalImageId']
            Name = iniName.replace("_", " ")
            return current_frame
                
        except:
            return 'No match/No internet connection'
    
    def print_output(self, s):
        try:
            ts = datetime.datetime.now()
            self.nameInputLabel.setText(Name)
            snapimage = self.convert_cv_qt(s)
            self.snapLabel.setPixmap(snapimage)
            self.tempInputLabel.setText(str(cneter))
            try:
                AddItems(current_class, "S10186XXXXX", Name, cneter).start()
            except:
                pass
            
            if cneter >37.5:
                SESEmail(ts.strftime("%Y-%m-%d %H:%M"), Name, "S10186XXXXX", cneter).start()
                        
        except:
            pass

    def thread_complete(self):
        print("--> Rekognition Thread Completed")
        self.thread_class.start()

    def worker_function(self, flip):
        worker = Worker(self.execute_this_fn, flip)
        worker.signals.result.connect(self.print_output)
        worker.signals.finished.connect(self.thread_complete)
        self.threadpool.start(worker)
        
    def sendCSV(self):
        Present_Month = datetime.datetime.now().month
        Month_dict = { 1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 7: "July", 8: "August", 9: "September", 10: "October", 11:"November", 12:"December"}
        strPresent_Month = Month_dict.get(Present_Month)
        try:
            CSVEmail(strPresent_Month, current_class, current_teacher, current_teacher_email).start()
            QMessageBox.information(self,
                  "Attendance Sheet",
                  "Attendance Sheet is sent for: \nTeacher-In-Charge: "+ current_teacher + " \nEmail: "+ current_teacher_email +"\nClass: "+ current_class +"\nTime Sent:" + time_now)
            
        except:
            QMessageBox.warning(self,
                  "Error",
                  "Failed to send attendance sheet. No Entry. Please try again.")
    
################################################### Video Thread (QThread)
                 
class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    detectface_signal = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._run_flag = True
        self.flagA = False

    def run(self):
        # capture from web cam
        cascPath = "/home/pi/RaspiTAR_App/RaspiTAR/haarcascade_frontalface_default.xml"
        faceCascade = cv2.CascadeClassifier(cascPath)
        cap = cv2.VideoCapture(0)
                
        while self._run_flag:
            # flip orientation of camera 180
            ret, cv_img = cap.read()
            flip = cv2.flip(cv_img, -1)
            gray = cv2.cvtColor(flip, cv2.COLOR_BGR2GRAY)
            faces = faceCascade.detectMultiScale(
                gray,
                scaleFactor=1.2,
                minNeighbors=4,
                minSize=(100, 100),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
                
            if ret:
                self.change_pixmap_signal.emit(flip)
                
                if type(faces) == numpy.ndarray:
                    if self.flagA == True:
                        None
                    else:
                        self.flagA = True 
                        try:
                            self.detectface_signal.emit(flip)
                            
                        except:
                            print("Bounding Error")
                            pass

                else:
                    self.flagA = False
            
        cap.release()
            
    def stop(self):
        """Sets run flag to False and waits for thread to finish"""
        self._run_flag = False
        self.wait()
            
################################################### Class Thread (Qthread)
class ClassThread(QThread):
    """
        Class that reads time variable and call "read_class" function every 30min or when min shows "00" or "30"
    """
    read_class_signal = pyqtSignal(object)
    
    def __init__(self):
        super().__init__()
        self._run_flag = True
        
    def run(self):
        while self._run_flag:
            try:
                time_string = str(time_now)
                minute_long = time_string.split(":", 1)[1]
                minute = minute_long.split(" ")[0]
                str_min = str(minute)
                
                try:
                    if (str_min == "30") or (str_min == "00"):
                        ts = datetime.datetime.now()
                        decide_current_time = ts.strftime("%I:" + str_min + " %p")
                        
                        global newlist
                        global current_class
                        global current_teacher
                        global current_teacher_email
                        global current_teacher_phone
                        current_class = str(newlist[decide_current_time]['Class'])
                        current_teacher = str(newlist[decide_current_time]['Teacher'])
                        current_teacher_email = str(newlist[decide_current_time]['Email'])
                        current_teacher_phone = str(newlist[decide_current_time]['Number'])
                        
                except:
                    print("Key Error: Time Key Not Found In List\nKey Given: " + time_now)
               
            except:
                pass

    def stop(self):
        """Sets run flag to False and waits for thread to finish"""
        self._run_flag = False
        self.wait()

################################################### run (main)
            
def run():
    global minHue
    global maxHue
    global ChipType

    port = 'I2C'
    ChipType = 'MLX90641'
    minHue = 180
    maxHue = 360
    
    
    app = QApplication(sys.argv)
    GUI = MainWindow()
    view = painter(GUI)
        
    dataThread = DataReader(port,ChipType)
    dataThread.drawRequire.connect(view.draw)
    dataThread.start()
    
    GUI.show()
    sys.exit(app.exec_())   

if __name__ == "__main__":
    run()