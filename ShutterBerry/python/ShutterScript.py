import webiopi
import datetime
import time
import urllib.request as webby

# GPIO pin using BCM numbering
GPIO = webiopi.GPIO

#Velux Shutters
BedroomUp = 2 
BedroomStop = 3
BedroomDown = 4

BathroomUp = 17 
BathroomStop = 27
BathroomDown = 22

#Baier Shutters
BedroomOpen = 10
BedroomClose = 9

# Function reads from config file to populate the WebGUI with necessary variables
# This has to be called from index html webiopi ready function so that it's refreshed each and everytime a web page is loaded
# Also called at startup
@webiopi.macro
def getConfig():

    # Variables stored in Config file used in many places - so declare as globals. 
    global WeekdayUp, WeekdayDown, SaturdayUp, SaturdayDown, SundayUp, SundayDown, AutoShutter, Holidays, SunRiseSet, KackWetter
    
    BedroomBathroomFile = open('/home/pi/ShutterBerry/python/BedroomBathroom.cfg', 'r')
    for line in BedroomBathroomFile:

        #remove new line and carriage returns
        line = line.replace("\n", "")
        line = line.replace("\r", "")
        myvars = line.split(",")
        if myvars[0]=="Weekday":
            WeekdayUp = myvars[1]
            WeekdayDown = myvars[2]
        if myvars[0]=="Saturday":
            SaturdayUp = myvars[1]
            SaturdayDown = myvars[2]
        if myvars[0]=="Sunday":
            SundayUp = myvars[1]
            SundayDown = myvars[2]
        if myvars[0]=="AutoShutter":
            AutoShutter = myvars[1]
        if myvars[0]=="Holidays":
            Holidays = myvars[1]
        if myvars[0]=="SunRiseSet":
            SunRiseSet = myvars[1]
        if myvars[0]=="KackWetter":
            KackWetter = myvars[1]

    BedroomBathroomFile.close()

    return "%s;%s;%s;%s;%s;%s;%s;%s;%s;%s" % (WeekdayUp, WeekdayDown, SaturdayUp, SaturdayDown, SundayUp, SundayDown, AutoShutter, Holidays, SunRiseSet, KackWetter)

# setup function is automatically called at WebIOPi startup
def setup():
    # set GPIO OUT
    GPIO.setFunction(BedroomUp, GPIO.OUT)
    GPIO.setFunction(BedroomStop, GPIO.OUT)
    GPIO.setFunction(BedroomDown, GPIO.OUT)

    GPIO.setFunction(BathroomUp, GPIO.OUT)
    GPIO.setFunction(BathroomStop, GPIO.OUT)
    GPIO.setFunction(BathroomDown, GPIO.OUT)

    GPIO.setFunction(BedroomOpen, GPIO.OUT)
    GPIO.setFunction(BedroomClose, GPIO.OUT)

    #Set GPIO Low
    GPIO.digitalWrite(BedroomUp, GPIO.LOW)
    GPIO.digitalWrite(BedroomStop, GPIO.LOW)
    GPIO.digitalWrite(BedroomDown, GPIO.LOW)

    GPIO.digitalWrite(BathroomUp, GPIO.LOW)
    GPIO.digitalWrite(BathroomStop, GPIO.LOW)
    GPIO.digitalWrite(BathroomDown, GPIO.LOW)

    GPIO.digitalWrite(BedroomOpen, GPIO.LOW)
    GPIO.digitalWrite(BedroomClose, GPIO.LOW) 

    #Run get Config to set all the variables
    getConfig();
                 
       
        
# Function is called daily to calculate Sun Rise and Sun Set times for current location    
def DaylightHours():
    print("Checking Daylight Hours")
    
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


    
# Function is called daily to get the local weather
def CurrentWeather():
    print("Checking Current Weather")

# Velux control sets the actual GPIOs. Retries, wait etc can be easily set globally    
def VeluxControl(MyGPIO):
    Tries = 2
    ButtonPress = 0.5

    for x in range(Tries):
        GPIO.digitalWrite(MyGPIO, GPIO.HIGH)
        time.sleep(ButtonPress)
        GPIO.digitalWrite(MyGPIO, GPIO.LOW)
        time.sleep(ButtonPress)

# Baier control sets the actual GPIOs for the Baier Shutters    
def BaierControl(MyGPIO):
    ButtonPress = 1

    GPIO.digitalWrite(MyGPIO, GPIO.HIGH)
    time.sleep(ButtonPress)
    GPIO.digitalWrite(MyGPIO, GPIO.LOW)
    
@webiopi.macro
def setConfig(WeekdayUp, WeekdayDown, SaturdayUp, SaturdayDown, SundayUp, SundayDown, AutoShutter, Holidays, SunRiseSet, KackWetter):

    # Set values of myline 
    myline = [0,1,2,3,4,5,6]
    myline[0] = 'Weekday,' + WeekdayUp + ',' + WeekdayDown
    myline[1] = 'Saturday,' + SaturdayUp + ',' + SaturdayDown
    myline[2] = 'Sunday,' + SundayUp + ',' + SundayDown
    myline[3] = 'AutoShutter,' + AutoShutter
    myline[4] = 'Holidays,' + Holidays
    myline[5] = 'SunRiseSet,' + SunRiseSet
    myline[6] = 'KackWetter,' + KackWetter

    # print myline and write to a file. 
    BedroomBathroomFile = open('/home/pi/ShutterBerry/python/BedroomBathroom.cfg', 'w')
    for index in range(len(myline)):
        print (myline[index])
        BedroomBathroomFile.write(myline[index] + '\n')
    BedroomBathroomFile.close()

    # Once the file has been written, call getConfig which updates the globals for other functions to use
    return getConfig()

@webiopi.macro
def BedroomUpMacro():
    VeluxControl(BedroomUp)

@webiopi.macro
def BedroomStopMacro():
    VeluxControl(BedroomStop)

@webiopi.macro
def BedroomDownMacro():
    VeluxControl(BedroomDown)

@webiopi.macro
def BedroomOpenMacro():
    BaierControl(BedroomOpen)

@webiopi.macro
def BedroomCloseMacro():
    BaierControl(BedroomClose)

@webiopi.macro
def BathroomUpMacro():
    VeluxControl(BathroomUp)

@webiopi.macro
def BathroomStopMacro():
    VeluxControl(BathroomStop)

@webiopi.macro
def BathroomDownMacro():
    VeluxControl(BathroomDown)

@webiopi.macro
def BedBathroomUpMacro():
    BedroomUpMacro()
    time.sleep(0.5)
    BathroomUpMacro()
       
@webiopi.macro
def BedBathroomStopMacro():
    BedroomStopMacro()
    time.sleep(0.5)
    BathroomStopMacro() 
    
@webiopi.macro
def BedBathroomDownMacro():
    BedroomDownMacro()
    time.sleep(0.5)
    BathroomDownMacro() 

# Loop function is repeatedly called by WebIOPi
# Use this to check if any action needs to be taken
# 60 s sleep as we don't need super accurate opening times
# Note, run sudo raspi-config to change time zone!
def loop():
    webiopi.sleep(60)
    now = datetime.datetime.now()

    # Current Time is in format 00:00
    CurrentTime = '%0*d' % (2, now.hour) + ':' '%0*d' % (2, now.minute)
    
    # Current Weekday used to check which schedule to use
    CurrentDay = datetime.datetime.today().weekday()

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

    # Check for Weekday
    if(CurrentDay <= 4):
        TodayOpenTime = WeekdayUp
        TodayCloseTime = WeekdayDown
        
    # Check for Saturday
    if(CurrentDay == 5):
        TodayOpenTime = SaturdayUp
        TodayCloseTime = SaturdayDown

    # Check for Sunday OR Public Holiday
    if(CurrentDay == 6) or ((HolidayToday == 'true') and (Holidays == 'true')):
        TodayOpenTime = SundayUp
        TodayCloseTime = SundayDown   

    #Check whether Shutters need opening...
    if ((TodayOpenTime == CurrentTime) and (AutoShutter == 'true')):
        BedBathroomUpMacro()
        BedroomOpenMacro()

    #Check whether Shutters need opening...
    if ((TodayCloseTime == CurrentTime) and (AutoShutter == 'true')):
        BedBathroomDownMacro()
        BedroomCloseMacro()
