import webiopi
import datetime
import time
import urllib.request as webby

# GPIO pin using BCM numbering
GPIO = webiopi.GPIO

NumberOfPins = 18
GPIOConfig = [[0 for x in range(NumberOfPins)] for y in range(3)]

ConfigFile = open('/home/pi/ShutterBerry/python/GPIO.cfg', 'r')

i= 0
for line in ConfigFile:
    #remove new line and carriage returns
    line = line.replace("\n", "")
    line = line.replace("\r", "")
    myvars = line.split(",")
            
    GPIOConfig[0][i] = myvars[0]
    GPIOConfig[1][i] = myvars[1]
    GPIOConfig[2][i] = int(myvars[2])

    i = i + 1

ConfigFile.close()

print (GPIOConfig)



# Function reads from config file to populate the WebGUI with necessary variables
# This has to be called from index html webiopi ready function so that it's refreshed each and everytime a web page is loaded
# Also called at startup
@webiopi.macro
def getConfig(MyRoom):

    # Variables stored in Config file used in many places - so declare as global. Create a 2x2 Array with Columns = Number of Rooms and Rows = Number of Config Items +1 
    global ShutterConfig
    global NumberOfRooms
    global NumberOfConfigItems

    NumberOfRooms = 6
    NumberOfConfigItems = 10
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
            
        ShutterConfig[0][ConfigIndex] = myvars[1]
        ShutterConfig[1][ConfigIndex] = myvars[2]
        ShutterConfig[2][ConfigIndex] = myvars[3]
        ShutterConfig[3][ConfigIndex] = myvars[4]
        ShutterConfig[4][ConfigIndex] = myvars[5]
        ShutterConfig[5][ConfigIndex] = myvars[6] 

    ConfigFile.close()

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

# setup function is automatically called at WebIOPi startup
def setup():
    # set GPIO OUT and LOW
    for i in range(NumberOfPins):
        GPIO.setFunction(GPIOConfig[2][i], GPIO.OUT)
        GPIO.digitalWrite(GPIOConfig[2][i], GPIO.LOW)

    #Run get Config to set all the variables - arbitrarily pass a room in
    getConfig("Office");
                       
        
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

# Velux control sets the actual GPIOs. Retries feature mitigates less reliable RF Link
@webiopi.macro
def VeluxControl(MyRoom, MyStatus):

    Tries = 2
    ButtonPress = 0.5

    for i in range(NumberOfPins):
        if (GPIOConfig[0][i] == MyRoom) and (GPIOConfig[1][i] == MyStatus):
            for x in range(Tries):
                GPIO.digitalWrite(GPIOConfig[2][i], GPIO.HIGH)
                time.sleep(ButtonPress)
                GPIO.digitalWrite(GPIOConfig[2][i], GPIO.LOW)
                time.sleep(ButtonPress)
            i = NumberOfPins + 1

# Baier control sets the actual GPIOs for the Baier Shutters    
@webiopi.macro
def BaierControl(MyRoom, MyStatus):
    ButtonPress = 0.5

    for i in range(NumberOfPins):
        if (GPIOConfig[0][i] == MyRoom) and (GPIOConfig[1][i] == MyStatus):
            GPIO.digitalWrite(GPIOConfig[2][i], GPIO.HIGH)
            time.sleep(ButtonPress)
            GPIO.digitalWrite(GPIOConfig[2][i], GPIO.LOW)
        i = NumberOfPins + 1
        
@webiopi.macro
def setConfig(MyRoom, WeekdayUp, WeekdayDown, SaturdayUp, SaturdayDown, SundayUp, SundayDown, AutoShutter, Holidays, SunRiseSet, KackWetter):

   
    # Do the oposite of getConfig - i.e. update ShutterConfig and write it to the file.
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

    for y in range(NumberOfConfigItems + 1):
        for x in range(NumberOfRooms):
            myline[y] = myline[y] + ',' + ShutterConfig[x][y] 
    
    
    # print myline and write to a file. 
    ConfigFile = open('/home/pi/ShutterBerry/python/Shutter.cfg', 'w')
    for y in range(NumberOfConfigItems +1):
        ConfigFile.write(myline[y] + '\n')
    ConfigFile.close()

    # Once the file has been written, call getConfig which updates the globals for other functions to use
    return getConfig(MyRoom)


@webiopi.macro
def AutoShuttersOpen(MyRoom):

    # Check if this is the BedroomBathroom case and Open the Velux Shutters if necessary
    if MyRoom == 'BedroomBathroom':
        VeluxControl('Bedroom', 'Up')
        VeluxControl('Bathroom', 'Up')
        BaierControl('Bedroom', 'Open')
    if MyRoom != 'BedroomBathroom':
        BaierControl('MyRoom', 'Open')
    

@webiopi.macro
def AutoShuttersClose(MyRoom):

    # Check if this is the BedroomBathroom case and Close the Velux Shutters if necessary
    if MyRoom == 'BedroomBathroom':
        VeluxControl('Bedroom', 'Down')
        VeluxControl('Bathroom', 'Down')
        BaierControl('Bedroom', 'Close')
    if MyRoom != 'BedroomBathroom':
        BaierControl('MyRoom', 'Close')

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
            print(MyRoom + " Auto Opening" + CurrentTime)
            AutoShuttersOpen(MyRoom)
            
        #Check whether Shutters need opening...
        if ((TodayCloseTime == CurrentTime) and (AutoShutter == 'true')):
            print(MyRoom + " Auto Closing " + CurrentTime)
            AutoShuttersClose(MyRoom)
