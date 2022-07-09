#!/usr/bin/env python3
import math
import webiopi
import datetime
import time
import urllib.request as webby
import sys
import spidev
import os
import numpy
import socket
import telnetlib
import MySQLdb
from astral import Astral
sys.path.append('/home/pi/ShutterBerry/python')
from lib_nrf24 import NRF24
from dateutil.rrule import *
from dateutil.parser import *

#Just use the normal GPIO definition
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

##############################################################################
# Turns time in format HH:MM to integer minutes of day to allow comparisons
def TimeNumeric(MyTime):
    MyTimeArray = MyTime.split(":")
    MyTimeNumeric = int(MyTimeArray[0])*60 + int(MyTimeArray[1])
    return MyTimeNumeric;


##############################################################################
# This function establishes today's Sun Rise and Sun Set Times
def GetSunRiseSunSet():
    UTCOffset = (-time.timezone/3600) + time.localtime().tm_isdst
    a=Astral()
    MyLat = 49.878
    MyLong = 8.64
    MyElevation = -3
    SunRiseUTC = a.time_at_elevation_utc(MyElevation, 1, datetime.datetime.today(), MyLat, MyLong).strftime('%H:%M').split(":")
    SunSetUTC = a.time_at_elevation_utc(MyElevation, -1, datetime.datetime.today(), MyLat, MyLong).strftime('%H:%M').split(":")
    SunRiseLT = '%0*d' %(2, int(SunRiseUTC[0]) + UTCOffset) + ":" + SunRiseUTC[1] 
    SunSetLT = '%0*d' %(2, int(SunSetUTC[0]) + UTCOffset) + ":" +  SunSetUTC[1]
    return SunRiseLT, SunSetLT


##############################################################################
# This function logs any messages with appropriate timestamp
def Logger(message, criticality):
    
    timestamp = datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")
    print(timestamp + " : " + criticality + ": " + message)

#####################################
# GPIO pin using BCM numbering 
def GPIOConfigi():

    global NumberOfPins
    global GPIOConfig

    


    NumberOfPins = 18
    GPIOConfig = [[0 for x in range(NumberOfPins)] for y in range(4)]

    # Config file defines PIN numbers and their use. RPI means shutter is controlled RPI, ARD via arduino Nano
    ConfigFile = open('/home/pi/ShutterBerry/python/GPIO.cfg', 'r')
    i= 0
    for line in ConfigFile:
        #remove new line and carriage returns
        line = line.replace("\n", "")
        line = line.replace("\r", "")
        myvars = line.split(",")
            
        GPIOConfig[0][i] = myvars[0]
        GPIOConfig[1][i] = myvars[1]
        GPIOConfig[2][i] = myvars[2]
        GPIOConfig[3][i] = int(myvars[3])
        #if it's a shutter controlled by the RPI, set the GPIO pins
        if (GPIOConfig[2][i] == 'RPI'):
            GPIO.setup(GPIOConfig[3][i], GPIO.OUT)
            GPIO.output(GPIOConfig[3][i], GPIO.HIGH)
        i = i + 1
    ConfigFile.close()

    return (NumberOfPins, GPIOConfig)
#
############################################################################

#######################################################
#Smart Switch Setup
def smartswitchSetup():
    global mySwitches
    mySwitches = ["Switch1", "Switch2", "Switch3", "Switch4"]


                   
############################################################################
# This function sends command to Arduino Shutters
def ShutterSlaveSend(message):

    Logger("Sending Shutter Slave: " + message, 'Info')
    TCP_IP = '192.168.178.40' # Let router resolve address of ShutterBerrySlave
    TCP_PORT = 5015
    BUFFER_SIZE = 1024

    #first try socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
    except socket.error as e:
        Logger ("Error creating socket: %s" % e, "Warning")
        Logger ("Cannot create socket, " + message + " not sent", "Warning")
        return
        
    #second try host
    try:
        s.connect((TCP_IP, TCP_PORT))
    except socket.gaierror as e:
        Logger ("Address related error connecting to server: %s" % e, "Warning")
        Logger ("Cannot connect to Shutter Slave, " + message + " not sent", "Warning")
        return
    except socket.error as e:
        Logger ("Connection error: %s" % e, "Warning")
        Logger ("Cannot connect to Shutter Slave, " + message + " not sent", "Warning")
        return

    #third try send data
    try:
        s.send(str(message).encode())
    except socket.error as e:
        Logger ("Cannot send to server: %s" % e, "Warning")
        Logger ("Cannot send to Shutter Slave, " + message + " not sent", "Warning")
        s.close()
        return

    try:
        data = s.recv(BUFFER_SIZE)
        Logger ("Shutter Slave Acknowledged:" + data, "Warning")
        s.close()
    except socket.error as e:
        Logger ("Error Receiving Data: %s" % e, "Warning")
        Logger("Shutter Slave Failed to Acknowledge:" + data, "Warning")
        s.close()
        return


 
#
##############################################################################

###########################################################################################
#This function gets ths DS18B20 Temperature sensor readings and returns them to the webpage   
@webiopi.macro
def getTemps():
    global InsideTemp
    global OutsideTemp

    myTemps = [0, 0]
    devices = ['28-0316446faeff', '28-041643ac1bff']
    base_dir = '/sys/bus/w1/devices/'

    for y in range(2):
        device_file =  base_dir + devices[y] +  '/w1_slave'

        if (os.path.exists(device_file) == True):
            f = open(device_file, 'r')
            lines = f.readlines()
            f.close()

            while lines[0].strip()[-3:] != 'YES':
                time.sleep(0.2)
                lines = read_temp_raw()
            equals_pos = lines[1].find('t=')
            if equals_pos != -1:
                temp_string = lines[1][equals_pos+2:]
                temp_c = float(temp_string) / 1000.0
            myTemps[y-1] = temp_c

    #Outside Temp sensor is very sheltered in a false ceiling outside, the entire building is keeping it warm (or cool).
    #From trial and error the following fudge works.
    InsideTemp = myTemps[0] 
    OutsideTemp = myTemps[1]

    return (InsideTemp, OutsideTemp) 
#
##################################################################################################

    
####################################################################################################       
# Function to Read the Shutter Config from file
# Plus another 2 macros to
#   a. Return ShutterConfig for a specific Room to WebGUI
#   b. Return SunProtection part to WebGUI
# Current design is that SunProtection, ReOpen and Temp for Sun Protection work globally, but it's much
# easier to asign these per room...also makes it more future proof incase GUI design changes
@webiopi.macro
def readShutterConfig():

# Variables stored in Config file used in many places - so declare as global. Create a 2x2 Array with Columns = Number of Rooms and Rows = Number of Config Items +1 
    global ShutterConfig
    global NumberOfRooms
    global NumberOfConfigItems

    NumberOfRooms = 6
    NumberOfConfigItems = 16
    ShutterConfig = [[0 for x in range(NumberOfConfigItems + 1)] for y in range(NumberOfRooms)]

    
    ConfigFile = open('/home/pi/ShutterBerry/python/Shutter.cfg', 'r')
    for line in ConfigFile:
        #remove new line and carriage returns
        line = line.replace("\n", "")
        line = line.replace("\r", "")
        myvars = line.split(",")
        if myvars[0]=="Room":
            ConfigIndex = 0
        if myvars[0]=="WeekdayUp":
            ConfigIndex = 1
        if myvars[0]=="WeekdayDown":
            ConfigIndex = 2
        if myvars[0]=="SaturdayUp":
            ConfigIndex = 3
        if myvars[0]=="SaturdayDown":
            ConfigIndex = 4
        if myvars[0]=="SundayUp":
            ConfigIndex = 5
        if myvars[0]=="SundayDown":
            ConfigIndex = 6
        if myvars[0]=="AutoShutter":
            ConfigIndex = 7
        if myvars[0]=="Holidays":
            ConfigIndex = 8
        if myvars[0]=="SunRiseSet":
            ConfigIndex = 9
        if myvars[0]=="KackWetter":
            ConfigIndex = 10
        if myvars[0]=="SunProtection":
            ConfigIndex = 11
        if myvars[0]=="ReOpen":
            ConfigIndex = 12
        if myvars[0]=="ProtectionTemp":
            ConfigIndex = 13
        if myvars[0]=="SunProtectionStart":
            ConfigIndex = 14            
        if myvars[0]=="SunProtectionStop":
            ConfigIndex = 15
        if myvars[0]=="SunProtectionLastCommand":
            ConfigIndex = 16
            
        ShutterConfig[0][ConfigIndex] = myvars[1]
        ShutterConfig[1][ConfigIndex] = myvars[2]
        ShutterConfig[2][ConfigIndex] = myvars[3]
        ShutterConfig[3][ConfigIndex] = myvars[4]
        ShutterConfig[4][ConfigIndex] = myvars[5]
        ShutterConfig[5][ConfigIndex] = myvars[6] 

    ConfigFile.close()

    return (ShutterConfig, NumberOfRooms, NumberOfConfigItems)

@webiopi.macro
def getShutterConfig(MyRoom):

   for i in range(NumberOfRooms):
        if (ShutterConfig[i][0] == MyRoom):
            WeekdayUp = ShutterConfig[i][1]
            WeekdayDown = ShutterConfig[i][2]
            SaturdayUp = ShutterConfig[i][3]
            SaturdayDown = ShutterConfig[i][4]
            SundayUp = ShutterConfig[i][5]
            SundayDown = ShutterConfig[i][6]
            AutoShutter = ShutterConfig[i][7]
            Holidays = ShutterConfig[i][8]
            SunRiseSet = ShutterConfig[i][9]
            KackWetter = ShutterConfig[i][10]

            return "%s;%s;%s;%s;%s;%s;%s;%s;%s;%s" % (WeekdayUp, WeekdayDown, SaturdayUp, SaturdayDown, SundayUp, SundayDown, AutoShutter, Holidays, SunRiseSet, KackWetter)

@webiopi.macro
def getSunProtectionConfig():   
    return "%s;%s" % (ShutterConfig[1][11], ShutterConfig[1][12])
#
########################################################################

#####################################################
#v.Quick Macro to get SwitchStatus
@webiopi.macro
def getSwitchMode(Target):

    message = 'status'
    SwitchStatus = arduinoSwitchSend(message, Target)
    if (len(SwitchStatus) == 0): SwitchStatus = "NA"
    Logger(Target + ' ' + SwitchStatus, "Info")
    return "%s;%s" % (Target, SwitchStatus)
#
#####################################################

    
###############################################################################################
# Macro Accesses Google Calendar for Switching entries
# Calendar might be quite dynamic, so should get called by loop on each iteration
# To simplify the main loop, it just returns the expected status of each switch
def ReadSwitchCalendar():

    #Straight from iCal
    CalEntries = -1
    CalEvents = []
    #Expanded after recursive rules
    CalExpEntries = -1
    CalExpEvents = []

    #Targets will return all the distinct switches found in the iCal and their expected status
    Results = []
    for i in range(len(mySwitches)):
        Results.append([mySwitches[i], "OFF"])
    
    #In case there is an on-going entry, we need to add an UNTIL clause to prevent endless recurrence.
    #Only get entries upto 1 week in future which is more than enough
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=7)
 
    UNTIL = ";UNTIL=" + '%0*d' % (4, tomorrow.year) + '%0*d' % (2, tomorrow.month) + '%0*d' % (2, tomorrow.day) + "T000000"

    #Calendar links stored in file so code can be put somewhere public
    SwitchCalendarLinkFile = open('/home/pi/ShutterBerry/python/SwitchCalendarLink.cfg', 'r')
    SwitchCalendarLink = SwitchCalendarLinkFile.readline() 
        
    #Read the Calendar and build a list of CalEvents
    if (tryLink(SwitchCalendarLink) == True):
        for line in webby.urlopen(SwitchCalendarLink):
            line = line.decode("utf-8")
            line = line.replace("\n", "")
            line = line.replace("\r", "")
            myvars = line.split(":")
        
            if (line == "BEGIN:VEVENT"):
                CalEntries = CalEntries +1
                CalEvents.append(["NA", "NA", "NA", "NA"])
            if ((CalEntries >= 0) and (myvars[0] == "SUMMARY")):
                CalEvents[CalEntries][0] = myvars[1]
            if ((CalEntries >= 0) and (myvars[0] == "RRULE")):
                # Google Calendar uses BYDAY, dateutil expects BYWEEKDAY. Add 'UNTIL' as well
                line = line.replace("BYDAY", "BYWEEKDAY") 
                CalEvents[CalEntries][1] = line + UNTIL
            if ((CalEntries >= 0) and ((myvars[0])[:7] == "DTSTART")):
                CalEvents[CalEntries][2] = myvars[1]
            if ((CalEntries >= 0) and ((myvars[0])[:5] == "DTEND")):
                CalEvents[CalEntries][3] = myvars[1]

    #If the Calendar has Events, then expand them using rrules
    if (len(CalEvents[:]) != 0):
        for i in range(len(CalEvents[:])):
            Event = CalEvents[i][0]
            Rule = CalEvents[i][1]
            Start = parse(CalEvents[i][2], ignoretz=True)
            Stop = parse(CalEvents[i][3], ignoretz=True)
            Duration = Stop - Start
        
            #Only append to the Expanded Events if the Switch is defined
            if Event in mySwitches:
            
                if (Rule == "NA"):
                    CalExpEvents.append([Event, Start, Start+Duration])
                
                if (Rule != "NA"):
                    StartList = (list(rrulestr(Rule,dtstart=Start)))
                    for j in range(len(StartList)):
                        CalExpEvents.append([Event, StartList[j], StartList[j]+Duration])

        #Now go through the CalExpEvents - if there's a switch meant to be on, then update the Results
        for i in range(len(CalExpEvents)):
            if CalExpEvents[i][1] <= datetime.datetime.now() and CalExpEvents[i][2] >= datetime.datetime.now():
                Results[(mySwitches.index(CalExpEvents[i][0]))][1] = "ON"
    

   
    return(Results)
    

##########################################
# Function to test a web link for iCal etc 
def tryLink(myLink):
    try:
        webby.urlopen(myLink)
        return True
    except:
        Logger(myLink + " page not found, check link or internet connection", "Warning")
        return False

        
############################################################################################################## 
# Function to get Hessen Holidays from iCal and write to a file. By writing to a file,
# the system can still run even if the oCal is unavailable for some reason - the holidays are not very dynamic!
def getHolidays():
  

    HolidaysLink = "https://www.officeholidays.com/ics/germany/hesse"

    #First try link, then only continue if it's accessible
    if (tryLink(HolidaysLink) == True):
        Logger("Retrieving Holidays from " + HolidaysLink, "Info")

        HolidayDates = []
        HolidayDescriptions = []
        
        for line in webby.urlopen(HolidaysLink):
            line = line.decode("utf-8")
            line = line.replace("\n", "")
            line = line.replace("\r", "")
            myvars = line.split(":")

            if (myvars[0] == "DTSTART;VALUE=DATE") :
                HolidayDates.append(myvars[1])

            if (myvars[0] == "SUMMARY;LANGUAGE=en-us") :
                HolidayDescriptions.append(myvars[2])

        Logger ('%s' % len(HolidayDates) + ' Holidays Found')
                
        # Print date to file if Holiday Description does not contain "[Not a public holiday]"
        iCalHolidaysFile = open('/home/pi/ShutterBerry/python/iCalHolidays.txt', 'w')
        for index in range(len(HolidayDates)):
            if ("[Not a public holiday]" not in HolidayDescriptions[index]) :
                iCalHolidaysFile.write(HolidayDates[index] + ':' + HolidayDescriptions[index] + '\n')
        iCalHolidaysFile.close()          
#
#########################################################################################
   
############################################################
# setup function is automatically called at WebIOPi startup
def setup():
    GPIOConfigi()
    smartswitchSetup()
    readShutterConfig()
    getSunProtectionConfig()
    getTemps()
#
#############################################################              

#####################################################################################
#The following 2 macros do the actually nitty gritty work
#Separate Macros for the Baier and Velux Shutters - should sort this out at some point   
# Velux control sets the actual GPIOs. Retries feature mitigates less reliable RF Link
@webiopi.macro
def VeluxControl(MyRoom, MyStatus):
    ButtonPress = 0.5
    if (OutsideTemp >= -2):
        for i in range(NumberOfPins):
            if (GPIOConfig[0][i] == MyRoom) and (GPIOConfig[1][i] == MyStatus):
                GPIO.output(GPIOConfig[3][i], GPIO.LOW)
                time.sleep(ButtonPress)
                GPIO.output(GPIOConfig[3][i], GPIO.HIGH)
                time.sleep(ButtonPress)
                GPIO.output(GPIOConfig[3][i], GPIO.LOW)
                time.sleep(ButtonPress)
                GPIO.output(GPIOConfig[3][i], GPIO.HIGH)
            i = NumberOfPins + 1
    if (OutsideTemp < -2):
        Logger("Too cold for the Velux rollers", "Info")
        
# Baier control sets the actual GPIOs for the Baier Shutters    
@webiopi.macro
def BaierControl(MyRoom, MyStatus):
    ButtonPress = 0.25
        
    for i in range(NumberOfPins):
        if (GPIOConfig[0][i] == MyRoom) and (GPIOConfig[1][i] == MyStatus):
            #Some Baier shutters are controlled via Slave Pi (formerly and arduino Nano) 
            if (GPIOConfig[2][i] == 'ARD'):
                message = GPIOConfig[3][i]
                ShutterSlaveSend(message)
                time.sleep(ButtonPress)
            if (GPIOConfig[2][i] == 'RPI'):   
                GPIO.output(GPIOConfig[3][i], GPIO.LOW)
                time.sleep(ButtonPress)
                GPIO.output(GPIOConfig[3][i], GPIO.HIGH)
        i = NumberOfPins + 1

#
######################################################################################

###########################################################################
# This Macro writes the Array ShutterConfig to the File.
# The following 2 macros are triggered by the Web UI and respectively set
#   a. ShutterConfig for each room
#   b. The SunProtection Settings
@webiopi.macro
def writeShutterConfig():

    # First BuildUp each Line.
    myline = [0 for x in range(NumberOfConfigItems + 1)]
    myline[0] = 'Room'
    myline[1] = 'WeekdayUp'
    myline[2] = 'WeekdayDown'
    myline[3] = 'SaturdayUp'
    myline[4] = 'SaturdayDown'
    myline[5] = 'SundayUp'
    myline[6] = 'SundayDown'
    myline[7] = 'AutoShutter'
    myline[8] = 'Holidays'
    myline[9] = 'SunRiseSet'
    myline[10] = 'KackWetter'
    myline[11] = 'SunProtection'
    myline[12] = 'ReOpen'
    myline[13] = 'ProtectionTemp'
    myline[14] = 'SunProtectionStart'
    myline[15] = 'SunProtectionStop'
    myline[16] = 'SunProtectionLastCommand'
    
    for y in range(NumberOfConfigItems + 1):
        for x in range(NumberOfRooms):
            myline[y] = myline[y] + ',' + ShutterConfig[x][y] 
        
    # print myline and write to a file. 
    ConfigFile = open('/home/pi/ShutterBerry/python/Shutter.cfg', 'w')
    for y in range(NumberOfConfigItems +1):
        ConfigFile.write(myline[y] + '\n')
    ConfigFile.close()

@webiopi.macro
def setShutterConfig(MyRoom, WeekdayUp, WeekdayDown, SaturdayUp, SaturdayDown, SundayUp, SundayDown, AutoShutter, Holidays, SunRiseSet, KackWetter):
   
    # Do the oposite of getShutterConfig - i.e. update ShutterConfig write it to the file.
    for i in range(NumberOfRooms):
        if (ShutterConfig[i][0] == MyRoom):
            ShutterConfig[i][1] = WeekdayUp
            ShutterConfig[i][2] = WeekdayDown
            ShutterConfig[i][3] = SaturdayUp
            ShutterConfig[i][4] = SaturdayDown
            ShutterConfig[i][5] = SundayUp
            ShutterConfig[i][6] = SundayDown
            ShutterConfig[i][7] = AutoShutter
            ShutterConfig[i][8] = Holidays
            ShutterConfig[i][9] = SunRiseSet
            ShutterConfig[i][10] = KackWetter

    writeShutterConfig()

@webiopi.macro
def setSunProtectionFlags(SunProtectionStatus, ReOpenStatus):
    for i in range(NumberOfRooms):
        ShutterConfig[i][11] = SunProtectionStatus     
        ShutterConfig[i][12] = ReOpenStatus

    writeShutterConfig()
#
##########################################################################################


##########################################################################################
# The next 2 macros handle the AutoOpen and Close - Only needed due to BadroomBathroom
# Being handled as a single room and separate functions for Velux and Baier Shutters
@webiopi.macro
def AutoShuttersOpen(MyRoom):
    if MyRoom == 'BedroomBathroom':
        VeluxControl('Bedroom', 'Up')
        VeluxControl('Bathroom', 'Up')
        BaierControl('Bedroom', 'Open')
    if MyRoom != 'BedroomBathroom':
        BaierControl(MyRoom, 'Open')

@webiopi.macro
def AutoShuttersClose(MyRoom):
    if MyRoom == 'BedroomBathroom':
        VeluxControl('Bedroom', 'Down')
        VeluxControl('Bathroom', 'Down')
        BaierControl('Bedroom', 'Close')
    if MyRoom != 'BedroomBathroom':
        BaierControl(MyRoom, 'Close')
#
##############################################################################################

##########################################################################################
# 
@webiopi.macro
def SwitchMode(MySwitch):
    message = 'mode'
    arduinoSwitchSend(message, MySwitch)

#
##############################################################################################









    
    
    
