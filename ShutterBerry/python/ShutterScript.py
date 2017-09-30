#!/usr/bin/env python3
import webiopi
import datetime
import time
import urllib.request as webby
import sys
import spidev
import os
import numpy
from astral import Astral
sys.path.append('/home/pi/ShutterBerry/python')
from lib_nrf24 import NRF24
from dateutil.rrule import *
from dateutil.parser import *

#Just use the normal GPIO definition
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)


#####################################
# GPIO pin using BCM numbering 
def GPIOConfig():

    global NumberOfPins
    global GPIOConfig
    global GPIO
    


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
#
############################################################################

#######################################################
#Smart Switch Setup
def smartswitchSetup():
    global mySwitches
    mySwitches = ["Switch1", "Switch2", "Switch3", "Switch4"]


############################################################################
# Basic Radio Setup
def radioSetup(target):
    
    time.sleep(0.3)
    
    radio = NRF24(GPIO, spidev.SpiDev())
    radio.begin(0,18)
    radio.setChannel(0x76)
    radio.setDataRate(NRF24.BR_250KBPS)
    radio.setPALevel(NRF24.PA_MAX)
    radio.setAutoAck(True)
    radio.enableDynamicPayloads()
    radio.enableAckPayload()

    if (target == 'Shutters'): pipes = [[0xE8, 0xE8, 0xF0, 0xF0, 0xE1], [0xF0, 0xF0, 0xF0, 0xF0, 0xE1]]    

    for i in range(len(mySwitches)):
        if (target == mySwitches[i]):
            pipes = [[0xE8, 0xE8, 0xF0, 0xF0, 0xE2 + i], [0xF0, 0xF0, 0xF0, 0xF0, 0xE2 + i]]
    radio.openWritingPipe(pipes[0])
    radio.openReadingPipe(1, pipes[1])
    return(radio)

    
#
############################################################################


############################################################################
# This function sends command to Arduino Switches  
def arduinoSwitchSend(message, target):

    radio = radioSetup(target)

    receivedString = ""
    
    messagesend = list(message)
    while len(messagesend) < 8:
        messagesend.append(0)


    start = time.time()
    radio.write(messagesend)
    #print("Commanded " + target + " " + message

    radio.startListening()
    while not radio.available(0):
        time.sleep(0.001)
        if (time.time() - start) > 0.5:
            #print ("Response from " + target + " Timed Out")
            radio.stopListening()
            break

    receivedMessage = []
    radio.read(receivedMessage, radio.getDynamicPayloadSize())
    radio.stopListening()
        
    #print("Received: {}".format(receivedMessage))
    for n in receivedMessage:
        if (n >= 32 and n <= 126):
            receivedString += chr(n)           

    return(receivedString)
#
############################################################################

                   
############################################################################
# This function sends command to Arduino Shutters
def arduinoShutterSend(message):

    radio = radioSetup('Shutters')

    start = time.time()
    radio.write(message)
    print("Commanded Arduino Digital {}".format(message))
 
    time.sleep(0.5)  
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
    OutsideTemp = InsideTemp + ((myTemps[1] - InsideTemp)*1.15)

    return "%.1f;%.1f" % (InsideTemp, OutsideTemp) 
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
    print(Target + ' ' + SwitchStatus)
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
        print(myLink + " page not found, check link or internet connection")
        return False

        
############################################################################################################## 
# Function to get Hessen Holidays from iCal and write to a file. By writing to a file,
# the system can still run even if the oCal is unavailable for some reason - the holidays are not very dynamic!
def getHolidays():
  

    HolidaysLink = "http://www.officeholidays.com/ics/ics_region_iso.php?region_iso=HE&tbl_country=Germany"

    #First try link, then only continue if it's accessible
    if (tryLink(HolidaysLink) == True):
        print("Retrieving Holidays from " + HolidaysLink)

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

        print ('%s' % len(HolidayDates) + ' Holidays Found')
                
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
    GPIOConfig()
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

    Tries = 2
    ButtonPress = 0.5
    if (OutsideTemp >= 0):
        for i in range(NumberOfPins):
            if (GPIOConfig[0][i] == MyRoom) and (GPIOConfig[1][i] == MyStatus):
                for x in range(Tries):
                    GPIO.output(GPIOConfig[3][i], GPIO.LOW)
                    time.sleep(ButtonPress)
                    GPIO.output(GPIOConfig[3][i], GPIO.HIGH)
                    time.sleep(ButtonPress)
                i = NumberOfPins + 1
    if (OutsideTemp < 0):
        print("too cold for the Velux rollers")
# Baier control sets the actual GPIOs for the Baier Shutters    
@webiopi.macro
def BaierControl(MyRoom, MyStatus):
    ButtonPress = 0.5
        
    for i in range(NumberOfPins):
        if (GPIOConfig[0][i] == MyRoom) and (GPIOConfig[1][i] == MyStatus):
            #Some Baier shutters are actually controlled via arduino Nano 
            if (GPIOConfig[2][i] == 'ARD'):
                message = list(str(GPIOConfig[3][i]))
                arduinoShutterSend(message)
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


##############################################################################
# Turns time in format HH:MM to integer minutes of day to allow comparisons
def TimeNumeric(MyTime):
    MyTimeArray = MyTime.split(":")
    MyTimeNumeric = int(MyTimeArray[0])*60 + int(MyTimeArray[1])
    return MyTimeNumeric;
#
##############################################################################

##############################################################################################    
# Loop function is repeatedly called by WebIOPi
# Use this to check if any action needs to be taken
# 60 s sleep as we don't need super accurate opening times
# Note, run sudo raspi-config to change time zone!
def loop():
    TotalTemp = InsideTemp + OutsideTemp
    
    now = datetime.datetime.now()
    UTCOffset = (-time.timezone/3600) + time.localtime().tm_isdst
    
   
    # Current Time is in format 00:00
    CurrentTime = '%0*d' % (2, now.hour) + ':' '%0*d' % (2, now.minute)
    
    # Current Day of Week and Day Of Year
    CurrentDOW = int(now.strftime('%w'))
    CurrentDOY = int(now.strftime('%j'))


    # Get Sun Rise and Sun set Times from Astral module.   
    a=Astral()
    MyLat = 49.878
    MyLong = 8.64
    MyElevation = -3
    SunRiseUTC = a.time_at_elevation_utc(MyElevation, 1, datetime.datetime.today(), MyLat, MyLong).strftime('%H:%M').split(":")
    SunSetUTC = a.time_at_elevation_utc(MyElevation, -1, datetime.datetime.today(), MyLat, MyLong).strftime('%H:%M').split(":")
    SunRiseLT = '%0*d' %(2, int(SunRiseUTC[0]) + UTCOffset) + ":" + SunRiseUTC[1] 
    SunSetLT = '%0*d' %(2, int(SunSetUTC[0]) + UTCOffset) + ":" +  SunSetUTC[1]

    #Current date in format yyyymmdd
    iCalDate = '%0*d' % (4, now.year) + '%0*d' % (2, now.month) + '%0*d' % (2, now.day)
    iCalTime = '%0*d' % (4, now.year) + '%0*d' % (2, now.month) + '%0*d' % (2, now.day) + 'T' + '%0*d' % (2, now.hour) + '%0*d' % (2, now.minute) + '%0*d' % (2, now.second)
   
    # At 03:00 each Sunday, update the holidays for the year and write to a local file
    if ((CurrentTime == '03:00') and (CurrentDOW == 0)):
        getHolidays()

    # Check for Holiday
    HolidayToday = 'false'
    iCalHolidaysFile = open('/home/pi/ShutterBerry/python/iCalHolidays.txt', 'r')
    for line in iCalHolidaysFile:
        #remove new line and carriage returns
        line = line.replace("\n", "")
        line = line.replace("\r", "")
        myvars = line.split(":")
        if (myvars[0] == iCalDate):
            HolidayToday = 'true'
            print('today is ' + myvars[1])
    iCalHolidaysFile.close()        


    ################################
    #Shutters
    for i in range(NumberOfRooms):
        MyRoom = ShutterConfig[i][0]
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
        SunProtection = ShutterConfig[i][11]
        ReOpen = ShutterConfig[i][12]
        ProtectionTemp = int(ShutterConfig[i][13])
        SunProtectionStart = ShutterConfig[i][14]
        SunProtectionStop = ShutterConfig[i][15]
        SunProtectionLastCommand = ShutterConfig[i][16]
      

        ######################################################################################################
        # The following Logic Looks after the "Standard" Schedule
        # for each room.
        # BUT, we shouldn't Open during Sun Protection Period if that's enabled and necessary.
        # Also, if Sun Protection stops a shutter opening, the last command must also be set to closed
        # so that the 'reopen' function works (N.B. will do that later)
      
        # Check for Weekday
        if(CurrentDOW <= 5):
            TodayOpenTime = WeekdayUp
            TodayCloseTime = WeekdayDown
        
        # Check for Saturday
        if(CurrentDOW == 6):
            TodayOpenTime = SaturdayUp
            TodayCloseTime = SaturdayDown

        # Check for Sunday OR Public Holiday
        if(CurrentDOW == 0) or ((HolidayToday == 'true') and (Holidays == 'true')):
            TodayOpenTime = SundayUp
            TodayCloseTime = SundayDown

        # Now Check for SunRiseSet Flag and times
        if (SunRiseSet == 'true') and (datetime.datetime.strptime(SunSetLT, "%H:%M") < datetime.datetime.strptime(TodayCloseTime, "%H:%M")):
            TodayCloseTime = SunSetLT
        if (SunRiseSet == 'true') and (datetime.datetime.strptime(SunRiseLT, "%H:%M") > datetime.datetime.strptime(TodayOpenTime, "%H:%M")):
            TodayOpenTime = SunRiseLT            


        TodayOpenTimeNumeric = TimeNumeric(TodayOpenTime)
        TodayCloseTimeNumeric = TimeNumeric(TodayCloseTime)
        SunProtectionStartNumeric = TimeNumeric(SunProtectionStart)
        SunProtectionStopNumeric = TimeNumeric(SunProtectionStop)    
        CurrentTimeNumeric = TimeNumeric(CurrentTime)

        # Determine whether Sun Protection Should Prohibit Opening
        SunProhibit = 'false'
        if ((SunProtection == 'true') and (TotalTemp >= ProtectionTemp) and (CurrentTimeNumeric >= SunProtectionStartNumeric) and (CurrentTimeNumeric <  SunProtectionStopNumeric)):
            SunProhibit = 'true'
       
        #Check whether Shutters need opening...
        if ((TodayOpenTimeNumeric == CurrentTimeNumeric) and (AutoShutter == 'true')):
            # ..If they should and are allowed, open them
            if (SunProhibit == 'false'):
                print(MyRoom + " Auto Opening " + CurrentTime)
                AutoShuttersOpen(MyRoom)
            # ...If they Should but are prohibited, leave them but set the last command to 'Close' to allow re-opening function to work
            if (SunProhibit == 'true'):
                print(MyRoom + " Prohibited from Opening Due to Sun Protection " + CurrentTime)
                ShutterConfig[i][16] = 'Close'
                writeShutterConfig()
            
            
        #Check whether Shutters need closing...
        if ((TodayCloseTimeNumeric == CurrentTimeNumeric) and (AutoShutter == 'true')):
            print(MyRoom + " Auto Closing " + CurrentTime)
            AutoShuttersClose(MyRoom)
        #
        ################################################################

        #############################################################################
        #Check whether SunProtection Period is over and Shutters Should be Re-Opened
        #To allow manual over-ride, only try to close if last Sun Protection Command was Open
        #also prevent re-opening after scheduled closing time (or before scheduled opening time)

        # Determine whether Schedule should prevent re-Opening
        ScheduleProhibit = 'false'
        if (CurrentTimeNumeric < TodayOpenTimeNumeric) or (CurrentTimeNumeric > TodayCloseTimeNumeric):
            ScheduleProhibit = 'true'
        
        #Closing should be at any time during the Sun Protection Period
        if ((SunProtection == 'true') and (TotalTemp >= ProtectionTemp) and (CurrentTimeNumeric >= SunProtectionStartNumeric) and (CurrentTimeNumeric < SunProtectionStopNumeric) and (SunProtectionLastCommand == 'Open')):
            AutoShuttersClose(MyRoom)
            ShutterConfig[i][16] = 'Close'
            writeShutterConfig()
            print(MyRoom + " Sun Protection Close" + CurrentTime)
        #Opening at the end - but only if Sun Protection has closed shutters
        if ((SunProtection == 'true') and (CurrentTimeNumeric == SunProtectionStopNumeric) and (SunProtectionLastCommand == 'Close')):
            # whether opening is allowed or not by schedule, the last command sent needs to be set
            ShutterConfig[i][16] = 'Open'
            writeShutterConfig()
            # ..if Opening is allowed by schedule, then open it
            if (ScheduleProhibit == 'false'):
                AutoShuttersOpen(MyRoom)
                print(MyRoom + " Sun Protection Re-Open" + CurrentTime)

            
         #
         ###############################################################################

    #End of Shutters
    ###############################

    ##########################################################################################################################
    #For the switches, we ignore the mode - it may have been change at the switch itself, so we would have to ask for it here
    #It's easier just to send the status as scheduled each minute and each switch can decide what to do with i
##
##    print (CurrentTime)
##    SwitchCommands = ReadSwitchCalendar()
##    print (SwitchCommands)
##    if (len(SwitchCommands) != 0):
##        for i in range(len(SwitchCommands)):
##            arduinoSwitchSend(SwitchCommands[i][1], SwitchCommands[i][0])
    
    #######################################

    #sleep until start of the next minute
    time.sleep(-time.time() %60)     

    
    
    
