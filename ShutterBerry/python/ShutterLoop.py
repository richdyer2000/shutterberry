from ShutterScript import *
import math
import datetime
import time
import sys
import spidev
import os
import numpy
import socket
from astral import Astral
sys.path.append('/home/pi/ShutterBerry/python')
from dateutil.rrule import *
from dateutil.parser import *



##############################################################################################    
# Loop function is repeatedly called by cron tab (once per minute
if __name__ == "__main__":
 

    ShutterConfig, NumberOfRooms, NumberOfConfigItems = readShutterConfig()
    NumberOfPins, GPIOConfig = GPIOConfigi()
    InsideTemp, OutsideTemp = getTemps()

    TotalTemp = InsideTemp + OutsideTemp
    
    now = datetime.datetime.now()
    UTCOffset = (-time.timezone/3600) + time.localtime().tm_isdst
       
    # Current Time is in format 00:00
    CurrentTime = '%0*d' % (2, now.hour) + ':' '%0*d' % (2, now.minute)
    
    # Current Day of Week and Day Of Year
    CurrentDOW = int(now.strftime('%w'))
    CurrentDOY = int(now.strftime('%j'))


    # Get Sun Rise and Sun set Times from Astral module.   
    SunRiseLT, SunSetLT = GetSunRiseSunSet() 

    #Current date in format yyyymmdd
    iCalDate = '%0*d' % (4, now.year) + '%0*d' % (2, now.month) + '%0*d' % (2, now.day)
    iCalTime = '%0*d' % (4, now.year) + '%0*d' % (2, now.month) + '%0*d' % (2, now.day) + 'T' + '%0*d' % (2, now.hour) + '%0*d' % (2, now.minute) + '%0*d' % (2, now.second)
   
    # At 03:00 each Sunday, update the holidays for the year and write to a local file
    if ((CurrentTime == '15:35') and (CurrentDOW == 5)):
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
            Logger('today is ' + myvars[1], 'Info')
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
                Logger(MyRoom + " Auto Opening " + CurrentTime, 'Info')
                AutoShuttersOpen(MyRoom)
            # ...If they Should but are prohibited, leave them but set the last command to 'Close' to allow re-opening function to work
            if (SunProhibit == 'true'):
                Logger(MyRoom + " Prohibited from Opening Due to Sun Protection " + CurrentTime, 'Info')
                ShutterConfig[i][16] = 'Close'
                writeShutterConfig()
            
            
        #Check whether Shutters need closing...
        if ((TodayCloseTimeNumeric == CurrentTimeNumeric) and (AutoShutter == 'true')):
            Logger(MyRoom + " Auto Closing " + CurrentTime, 'Info')
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
            Logger(MyRoom + " Sun Protection Close" + CurrentTime, 'Info')
        #Opening at the end - but only if Sun Protection has closed shutters
        if ((SunProtection == 'true') and (CurrentTimeNumeric == SunProtectionStopNumeric) and (SunProtectionLastCommand == 'Close')):
            # whether opening is allowed or not by schedule, the last command sent needs to be set
            ShutterConfig[i][16] = 'Open'
            writeShutterConfig()
            # ..if Opening is allowed by schedule, then open it
            if (ScheduleProhibit == 'false'):
                AutoShuttersOpen(MyRoom)
                Logger(MyRoom + " Sun Protection Re-Open" + CurrentTime, 'Info')

            
         #
         ###############################################################################


  
