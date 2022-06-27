from ShutterScript import *
import xmltodict
import math
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
from dateutil.rrule import *
from dateutil.parser import *


##############################################################################
# Turns time in format HH:MM to integer minutes of day to allow comparisons
def TimeNumeric(MyTime):
    MyTimeArray = MyTime.split(":")
    MyTimeNumeric = int(MyTimeArray[0])*60 + int(MyTimeArray[1])
    return MyTimeNumeric;
#
##############################################################################

################################################################################################################
#Weather Factor is the approx. solar energy (kWh) we expect to receive at equinox, depending weather forecast from 12-6pm.
#This is also (very) approximately how much we can expect it to raise the WWTankTemp by.
#If it looks like we'll collect, we can reduce the target temp used by the burner in the morning
def setTodaysWWTargetTemps():

    db = MySQLdb.connect(host="DISKSTATION", user="shutter", passwd="berry", db="Heating")
    WWTargetTempStandard = 48 
    WWTargetTempReduced = 40
    WWTargetTempMin= 35

    try:
        file = webby.urlopen('http://www.yr.no/place/Germany/Hesse/Traisa/forecast.xml')
        data = file.read()
        file.close()
        data = xmltodict.parse(data)

        symbols = []
        times = []
        for time in data['weatherdata']['forecast']['tabular']['time']:
            times.append(time['@from'])
            symbols.append(time['symbol']['@name'])
        print(times)
        print(symbols)

        now = datetime.datetime.now() 
        OurPeriod = '%0*d' % (4, now.year) + '-' + '%0*d' % (2, now.month) + '-' + '%0*d' % (2, now.day) + 'T12:00:00'
        weather12to6 = symbols[times.index(OurPeriod)]
        print(weather12to6)
        
        
    except:
        #if it doesn't work, we have not much to lose by going for partly cloudy.
        weather12to6 = 'Partly cloudy'
        print('Cannot Find 12-18 Weather for Today')
            
        
    #All these are better than nothing. Rain doesn't make any difference over cloud and we don't care whether we have thunder.
    weather12to6 = weather12to6.replace(" and thunder", "")
    NotTheBest = ['Partly cloudy', 'Light rain showers' , 'Rain showers', 'Heavy rain showers']  
    WeatherFactor = 0
    if weather12to6 == 'Clear sky':
        WeatherFactor = 20
    if weather12to6 == 'Fair':
        WeatherFactor = 10
    if weather12to6 in NotTheBest:
        WeatherFactor = 5

    now = datetime.datetime.now()
    Today = '%0*d' % (4, now.year) + '-' + '%0*d' % (2, now.month) + '-' + '%0*d' % (2, now.day)
    print(Today)
    CurrentDOY = int(now.strftime('%j'))
    
    PredictedSolarInput = WeatherFactor * (1-math.cos(CurrentDOY*3.142/180))
    WWTarget1 = round(WWTargetTempStandard - PredictedSolarInput)
    if WWTarget1 < WWTargetTempReduced:
        WWTarget1 = WWTargetTempReduced
    WWTarget2 = round(WWTargetTempStandard - PredictedSolarInput)
    if WWTarget2 < WWTargetTempMin:
        WWTarget2 = WWTargetTempMin


    try:
        cursor = db.cursor()
        cursor.execute("DELETE FROM WarmWaterTargets WHERE Day = '%s'" % Today)
        db.commit()
        cursor.execute("INSERT INTO WarmWaterTargets (Day, WarmWaterTarget1, WarmWaterTarget2, WarmWaterTarget3) VALUES (%s, %s, %s, %s)", (Today, WWTarget1, WWTarget2, WWTargetTempStandard))
        db.commit()
        db.close()
    except:
        print('cannot write WW target Temps')
#################################################################################
        

##############################################################################
# This function handles gets Data from the Viessmann 200-W using established connection
def GetViessmannData(connection, command):

    encodedcommand = (command + ' \n').encode()
    

    data = ""
    while data != 'vctrld>':
        data = connection.recv(1024).decode()
    
    connection.send(encodedcommand) 
    data = connection.recv(1024).decode().split(" ")[0]

    if (data != 'ERR:') and (data != 'OK'):

        try:
            data=float(data)
        except:
            data=667
            
    return data

##############################################################################
# This function handles gets Data from the Viessmann 200-W using established connection
def SetViessmannData(connection, command):

    command = command + ' \n'
    command = command.encode()

    data = ""
    while data != 'vctrld>':
        data = connection.recv(1024).decode()

    connection.send(command) 

##############################################################################
# This function handles the Viessmann Vitodens 200-W
# Data are logged in a MySQL Database
# The function of the Heating is also checked as this doesn't quite work correctly
def GetAndSetHeating():

    now = datetime.datetime.now()

    DefaultTempRaumSoll = 22
    DefaultNeigung = 0.9
    DefaultNiveau = 0
    DefaultWWTargetTemp = 44
    HeatingForceOff = 22.5
    HeatingForceOn = 21
    WWTarget1Time = '07:30'
    WWTarget2Time = '16:00'

    Today = '%0*d' % (4, now.year) + '-' + '%0*d' % (2, now.month) + '-' + '%0*d' % (2, now.day)
    CurrentTime = '%0*d' % (2, now.hour) + ':' + '%0*d' % (2, now.minute)
    minutenow = now.minute
    loginterval = 10

    InsideTemp, OutsideTemp = getTemps()    
    TempInnen = InsideTemp

    TCP_IP = 'localhost'
    TCP_PORT = 3002
    BUFFER_SIZE = 1024

    #first try socket
    try:
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection.settimeout(5)
    except socket.error as e:
        print ("Error creating socket: %s", e)
        return
        
    #second try host
    try:
        connection.connect((TCP_IP, TCP_PORT))
    except socket.gaierror as e:
        print ("Address related error connecting to server: %s", e)
        return
    except socket.error as e:
        print ("Connection error: %s", e)
        return
    else:
        

        TempRaumSoll = GetViessmannData(connection, 'getTempRaumSollHK2')
        PumpHK2 = GetViessmannData(connection, 'getPumpeStatusHK2')
        ModeHK2 = GetViessmannData(connection, 'getBetriebsart')
        TempVLHK2 = GetViessmannData(connection, 'getTempVListM2')

        TempAussen = GetViessmannData(connection, 'getTempAussen')

        SolarHours=GetViessmannData(connection, 'getSolarStunden')
        SolarLeistung=GetViessmannData(connection, 'getSolarLeistung')
        SolarPump=GetViessmannData(connection, 'getSolarPumpeStatus')
        TempSolar=GetViessmannData(connection, 'getTempSolarKollektor')
        WaterTankTemp=GetViessmannData(connection, 'getTempWasserSpeicher1')
       
        BurnerStarts=GetViessmannData(connection, 'getBrennerStarts')
        BurnerHours=GetViessmannData(connection, 'getBrennerStunden')
        GasKW=GetViessmannData(connection, 'getLeistungIst') * 35/100
        BoilerTarget=GetViessmannData(connection, 'getTempKesselSoll')
        BoilerActual=GetViessmannData(connection, 'getTempKessel')
        TankPump=GetViessmannData(connection, 'getPumpeStatusSp') 


        WWTarget=GetViessmannData(connection, 'getTempWWsoll')
        WWActual=GetViessmannData(connection, 'getTempWWist')
        WWPump=GetViessmannData(connection, 'getPumpeStatusZirku')

        HolidayBegin=GetViessmannData(connection, 'getHolidayBegin')



        ######################################################
        #Part 1 - Log data in database periodically
        if minutenow/loginterval == int(minutenow/loginterval):
            try:
                db = MySQLdb.connect(host="DISKSTATION", user="shutter", passwd="berry", db="Heating")

                cursor = db.cursor()
                cursor.execute("INSERT INTO History (Timestamp, BurnerHours, BurnerStarts, GasKW, ModeHK2, PumpHK2, SolarHours, SolarLeistung, SolarPump, TempAussen, TempInnen, TempRaumSoll, TempSolar, TempVLHK2, WaterTankTemp, BoilerTarget, BoilerActual, TankPump, WWTarget, WWActual, WWPump) VALUES \
(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", \
                               (now, BurnerHours, BurnerStarts, GasKW, ModeHK2, PumpHK2, SolarHours, SolarLeistung, SolarPump, TempAussen, TempInnen, TempRaumSoll, TempSolar, TempVLHK2, WaterTankTemp, BoilerTarget, BoilerActual, TankPump, WWTarget, WWActual, WWPump))
                db.commit()
                db.close()
            except:
                print("could not write to database")
        ######################################################


        ######################################################  
        #Part 2 - Correct Heating         
        HeatIncreaseAttempts = 0
        #Use data to set heating logic
        #If it's too hot, then switch off the heating and set the RaumTempSoll etc back to 
        if ((InsideTemp > HeatingForceOff) or ((InsideTemp > HeatingForceOn) and (TempVLHK2 < InsideTemp + 4))) and (ModeHK2 == 2):
            print("Switching heating off")
            SetViessmannData(connection, 'setBetriebsartTo1')
            NiveauCommand = 'setNiveauHK2 ' + str(int(DefaultNiveau))
            NeigungCommand = 'setNeigungHK2 ' + str(DefaultNeigung)
            TempRaumSollCommand = 'setTempRaumSollHK2 ' + str(int(DefaultTempRaumSoll))
            SetViessmannData(connection, NiveauCommand)
            SetViessmannData(connection, NeigungCommand)
            SetViessmannData(connection, TempRaumSollCommand)




        #If it's too cold and we're not in Mode 2, then first try Switching to Mode 2



        if (InsideTemp < HeatingForceOn) and (ModeHK2 != 2):
            print("Switching heating on")
            SetViessmannData(connection, 'setBetriebsartTo2')
            HeatIncreaseAttempts = 1
        
        #If it's too cold and we're in Mode 2 and the pump is on and the Vorlauf Temp < Heating Force Off temp +4.... then try increasing the RaumTempSoll
        if (InsideTemp < HeatingForceOn) and (ModeHK2 == 2) and (PumpHK2 == 1) and TempVLHK2 < (HeatingForceOff +4) and HeatIncreaseAttempts == 0:
            print("Setting Target Temperature to " + str(int(TempRaumSoll+1)))
            MyCommand = 'setTempRaumSollHK2 ' + str(int(TempRaumSoll+1)) 
            SetViessmannData(connection, MyCommand)
            HeatIncreaseAttempts = 1
        ####################################################################


        ###################################################################
        #Part 3 - Set HW Target Temps according to weather
        WWTarget1 = DefaultWWTargetTemp
        WWTarget2 = DefaultWWTargetTemp
        WWTarget3 = DefaultWWTargetTemp

        try:
            db = MySQLdb.connect(host="DISKSTATION", user="shutter", passwd="berry", db="Heating")
            cursor = db.cursor()
            cursor.execute("SELECT * FROM WarmWaterTargets WHERE Day = '%s'" % Today)
            results = cursor.fetchall()
            db.close()
        
            for row in results:
              WWTarget1 = row[1]
              WWTarget2 = row[2]
              WWTarget3 = row[3]
        except:
            print('could not retrieve WW Target Temps for today')
    
        if (datetime.datetime.strptime(CurrentTime, "%H:%M") < datetime.datetime.strptime(WWTarget1Time, "%H:%M")) and (WWTarget != WWTarget1):
            print('setting WWTarget ' + str(WWTarget1))
            MyCommand = 'setTempWWsoll ' + str(int(WWTarget1)) 
            SetViessmannData(connection, MyCommand)      
        if (datetime.datetime.strptime(CurrentTime, "%H:%M") > datetime.datetime.strptime(WWTarget1Time, "%H:%M")) and (datetime.datetime.strptime(CurrentTime, "%H:%M") < datetime.datetime.strptime(WWTarget2Time, "%H:%M")) and (WWTarget != WWTarget2):
            print('setting WWTarget ' + str(WWTarget2))
            MyCommand = 'setTempWWsoll ' + str(int(WWTarget2)) 
            SetViessmannData(connection, MyCommand)  
        if (datetime.datetime.strptime(CurrentTime, "%H:%M") > datetime.datetime.strptime(WWTarget2Time, "%H:%M")) and (WWTarget != WWTarget3):
            print('setting WWTarget ' + str(WWTarget3))
            MyCommand = 'setTempWWsoll ' + str(int(WWTarget3)) 
            SetViessmannData(connection, MyCommand)
        ####################################################################
                  
        connection.close()    
#
##############################################################################



##############################################################################################    
# Loop function is repeatedly called by WebIOPi
# Use this to check if any action needs to be taken
# 60 s sleep as we don't need super accurate opening times
# Note, run sudo raspi-config to change time zone!
if __name__ == "__main__":
    

    ShutterConfig, NumberOfRooms, NumberOfConfigItems = readShutterConfig()
    NumberOfPins, GPIOConfig = GPIOConfigi()
    InsideTemp, OutsideTemp = getTemps()
    GetAndSetHeating()

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
    if ((CurrentTime == '15:35') and (CurrentDOW == 5)):
        getHolidays()

    # Every hour until 12:00, try to get weather updates from yr.no
    # This can be used to set WW Target Temps
    if (now.hour < 12) and now.minute == 0:
        setTodaysWWTargetTemps()

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

  
