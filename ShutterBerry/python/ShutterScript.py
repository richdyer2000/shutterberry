import webiopi
import datetime
import time
import urllib.request as webby
import sys
import spidev
import os
sys.path.append('/home/pi/ShutterBerry/python')
from lib_nrf24 import NRF24

#separate GPIO definition for RF Interface to Arduino
import RPi.GPIO as RFGPIO
RFGPIO.setmode(RFGPIO.BCM)

# GPIO pin using BCM numbering 
def GPIOConfig():

    global NumberOfPins
    global GPIOConfig
    global GPIO
    
    GPIO = webiopi.GPIO
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
            GPIO.setFunction(GPIOConfig[3][i], GPIO.OUT)
            GPIO.digitalWrite(GPIOConfig[3][i], GPIO.HIGH)
        i = i + 1
    ConfigFile.close()

############################################################################
# This function sends command to Arduino
def arduinoSend(message):
    
    pipes = [[0xE8, 0xE8, 0xF0, 0xF0, 0xE1], [0xF0, 0xF0, 0xF0, 0xF0, 0xE1]]
    
    radio = NRF24(RFGPIO, spidev.SpiDev())
    radio.begin(0,18)

    radio.setPayloadSize(1)
    radio.setChannel(0x76)
    radio.setDataRate(NRF24.BR_250KBPS)
    radio.setPALevel(NRF24.PA_MAX)
    radio.setAutoAck(True)
    radio.enableDynamicPayloads()
    radio.enableAckPayload()

    radio.openWritingPipe(pipes[0])
    radio.openReadingPipe(1, pipes[1])
    #radio.printDetails()

    radio.write(message)
    print("Commanded Arduino Digital {}".format(message))
    #Wait a short time to clear buffer
    time.sleep(1)
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


    InsideTemp = myTemps[0] #put code in here when sensor actually works!
    OutsideTemp = myTemps[1]

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

##################################################
# Macro Just reads LUT with SunRise and Set times
def SunRiseSetTimes():
    #Ultimately want to use PyEphem (see www.Rhodesmill.org) but can't get it working. Just use LUT created from www.timeanddate.com
    #Sunrise/Set times are for Darmstadt, Germany in GMT.

    # For now, just dump everything in a 3x366 array and declare that as global.
    global SunRiseSetUTC
    SunRiseSetUTC = [[0 for x in range(366)] for y in range(3)]


    ConfigFile = open('/home/pi/ShutterBerry/python/SunRiseSet.cfg', 'r')
    for line in ConfigFile:
        #remove new line and carriage returns
        line = line.replace("\w", "")
        line = line.replace("\n", "")
        line = line.replace("\r", "")
        myvars = line.split(",")
        SunRiseSetIndex = int(myvars[0]) -1 
        SunRiseSetUTC[0][SunRiseSetIndex] = myvars[0]
        SunRiseSetUTC[1][SunRiseSetIndex] = myvars[1]
        SunRiseSetUTC[2][SunRiseSetIndex] = myvars[2]
     
    ConfigFile.close()
#
###################################################    
    
############################################################
# setup function is automatically called at WebIOPi startup
def setup():
    GPIOConfig()
    readShutterConfig()
    SunRiseSetTimes()
    getSunProtectionConfig()
    getTemps()
#
#############################################################                       

######################################################################################### 
# Function is called daily to get Hessen Holidays from iCal
def getHolidays():
  
    # Create 2 lists - Holiday Dates and Holiday Descriptions
    HolidayDates = []
    HolidayDescriptions = []

    HolidaysLink = "http://www.officeholidays.com/ics/ics_region_iso.php?region_iso=HE&tbl_country=Germany"
    print("Retrieving Holidays from " + HolidaysLink)

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
   

#####################################################################################
#The following 2 macros do the actually nitty gritty work
#Separate Macros for the Baier and Velux Shutters - should sort this out at some point   
# Velux control sets the actual GPIOs. Retries feature mitigates less reliable RF Link
@webiopi.macro
def VeluxControl(MyRoom, MyStatus):

    Tries = 2
    ButtonPress = 0.5

    for i in range(NumberOfPins):
        if (GPIOConfig[0][i] == MyRoom) and (GPIOConfig[1][i] == MyStatus):
            for x in range(Tries):
                GPIO.digitalWrite(GPIOConfig[3][i], GPIO.LOW)
                time.sleep(ButtonPress)
                GPIO.digitalWrite(GPIOConfig[3][i], GPIO.HIGH)
                time.sleep(ButtonPress)
            i = NumberOfPins + 1

# Baier control sets the actual GPIOs for the Baier Shutters    
@webiopi.macro
def BaierControl(MyRoom, MyStatus):
    ButtonPress = 0.5

    
    for i in range(NumberOfPins):
        if (GPIOConfig[0][i] == MyRoom) and (GPIOConfig[1][i] == MyStatus):
            #Some Baier shutters are actually controlled via arduino Nano 
            if (GPIOConfig[2][i] == 'ARD'):
                message = list(str(GPIOConfig[3][i]))
                arduinoSend(message)
            if (GPIOConfig[2][i] == 'RPI'):   
                GPIO.digitalWrite(GPIOConfig[3][i], GPIO.LOW)
                time.sleep(ButtonPress)
                GPIO.digitalWrite(GPIOConfig[3][i], GPIO.HIGH)
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

def TimeNumeric(MyTime):
    MyTimeArray = MyTime.split(":")
    MyTimeNumeric = int(MyTimeArray[0])*60 + int(MyTimeArray[1])
    return MyTimeNumeric;

##############################################################################################    
# Loop function is repeatedly called by WebIOPi
# Use this to check if any action needs to be taken
# 60 s sleep as we don't need super accurate opening times
# Note, run sudo raspi-config to change time zone!
def loop():
    TotalTemp = InsideTemp + OutsideTemp
    
    now = datetime.datetime.now()
    UTCOffset = (-time.timezone/3600) + time.daylight
   
    # Current Time is in format 00:00
    CurrentTime = '%0*d' % (2, now.hour) + ':' '%0*d' % (2, now.minute)
    
    # Current Day of Week and Day Of Year
    CurrentDOW = int(now.strftime('%w'))
    CurrentDOY = int(now.strftime('%j'))

    SunRiseUTC = SunRiseSetUTC[1][CurrentDOY + 1].split(":")
    SunSetUTC = SunRiseSetUTC[2][CurrentDOY + 1].split(":")

    SunRiseLT = '%0*d' %(2, int(SunRiseUTC[0]) + UTCOffset) + ":" + SunRiseUTC[1] 
    SunSetLT = '%0*d' %(2, int(SunSetUTC[0]) + UTCOffset) + ":" +  SunSetUTC[1] 

    #Current date in format yyyymmdd
    iCalDate = '%0*d' % (4, now.year) + '%0*d' % (2, now.month) + '%0*d' % (2, now.day)

    # At 03:00 each day, update the holidays for the year and write to a local file
    if (CurrentTime == '03:00'):
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
        if ((SunProtection == 'true') and (TotalTemp > ProtectionTemp) and (CurrentTimeNumeric > SunProtectionStartNumeric) and (CurrentTimeNumeric <  SunProtectionStopNumeric)):
            SunProhibit = 'true'
       
        #Check whether Shutters need opening...
        if ((TodayOpenTime == CurrentTime) and (AutoShutter == 'true')):
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
        if ((TodayCloseTime == CurrentTime) and (AutoShutter == 'true')):
            print(MyRoom + " Auto Closing " + CurrentTime)
            AutoShuttersClose(MyRoom)
        #
        ################################################################

        #############################################################################
        #Check whether SunProtection Period is over and Shutters Should be Re-Opened
        #To allow manual over-ride, only try to close at start of Sun Protection Period
        #also prevent re-opening after scheduled closing time (or before scheduled opening time)

        # Determine whether Schedule should prevent re-Opening
        ScheduleProhibit = 'false'
        if (CurrentTimeNumeric < TodayOpenTimeNumeric) or (CurrentTimeNumeric > TodayCloseTimeNumeric):
            ScheduleProhibit = 'true'
        
        if ((SunProtection == 'true') and (TotalTemp > ProtectionTemp) and (CurrentTime == SunProtectionStart)):
            AutoShuttersClose(MyRoom)
            ShutterConfig[i][16] = 'Close'
            writeShutterConfig()

        if ((SunProtection == 'true') and (CurrentTime == SunProtectionStop) and (SunProtectionLastCommand == 'Close') and (ScheduleProhibit == 'false')):
            AutoShuttersOpen(MyRoom)
            ShutterConfig[i][16] = 'Open'
            writeShutterConfig()            
         #
         ###############################################################################
    webiopi.sleep(60)

    
    
