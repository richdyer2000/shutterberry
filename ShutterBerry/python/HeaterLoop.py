from ShutterScript import *
import math
import datetime
import time
import urllib3
import sys
import spidev
import os
import numpy
import socket
import telnetlib
import json
import MySQLdb
sys.path.append('/home/pi/ShutterBerry/python')
from dateutil.rrule import *
from dateutil.parser import *


HeatingDB = MySQLdb.connect(host="192.168.178.29", user="shutter", passwd="berry", db="Heating")

Today = '%0*d' % (4, datetime.datetime.now().year) + '-' + '%0*d' % (2, datetime.datetime.now().month) + '-' + '%0*d' % (2, datetime.datetime.now().day)



################################################################################################################
#Weather Factor is the approx. solar energy (kWh) we expect to receive at equinox, depending weather forecast from 12-6pm.
#This is also (very) approximately how much we can expect it to raise the WWTankTemp by.
#If it looks like we'll collect, we can reduce the target temp used by the burner in the morning
def setTodaysWWTargetTemps():
    
    

    WWTargetTempStandard = 48 
    WWTargetTempReduced = 40
    WWTargetTempMin= 35

    try:
        http = urllib3.PoolManager()
        response = http.request('GET', 'https://api.met.no/weatherapi/locationforecast/2.0/classic?lat=49.8059&lon=8.6918')
        soup = BeautifulSoup(response.data.decode('utf-8'))
        print(soup)

        symbols = []
        times = []
        for time in data['weatherdata']['forecast']['tabular']['time']:
            times.append(time['@from'])
            symbols.append(time['symbol']['@name'])
        Logger(times)
        Logger(symbols)

        now = datetime.datetime.now() 
        OurPeriod = '%0*d' % (4, now.year) + '-' + '%0*d' % (2, now.month) + '-' + '%0*d' % (2, now.day) + 'T12:00:00'
        weather12to6 = symbols[times.index(OurPeriod)]
        Logger(weather12to6)
        
        
    except:
        #if it doesn't work, we have not much to lose by going for partly cloudy.
        weather12to6 = 'Partly cloudy'
        Logger('Cannot Find 12-18 Weather for Today', 'Warning')
            
        
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
    CurrentDOY = int(now.strftime('%j'))
    
    PredictedSolarInput = WeatherFactor * (1-math.cos(CurrentDOY*3.142/180))
    WWTarget1 = round(WWTargetTempStandard - PredictedSolarInput)
    if WWTarget1 < WWTargetTempReduced:
        WWTarget1 = WWTargetTempReduced
    WWTarget2 = round(WWTargetTempStandard - PredictedSolarInput)
    if WWTarget2 < WWTargetTempMin:
        WWTarget2 = WWTargetTempMin


    HeatingDBWrite("DELETE FROM WarmWaterTargets WHERE Day = '%s'", Today)
    HeatingDBWrite("INSERT INTO WarmWaterTargets (Day, WarmWaterTarget1, WarmWaterTarget2, WarmWaterTarget3) VALUES (%s, %s, %s, %s)", (Today, WWTarget1, WWTarget2, WWTargetTempStandard))

#################################################################################
        

##############################################################################
# This function  gets Data from the Viessmann 200-W using established connection
def GetViessmannData(parameter):
    
    connection = ViessmannConnect()
    command = ('get' + parameter + ' \n').encode()
    
    data = ""
    while data != 'vctrld>':
        data = connection.recv(1024).decode()
    
    connection.send(command) 
    data = connection.recv(1024).decode().split(" ")[0]

    if (data != 'ERR:') and (data != 'OK'):

        try:
            data=float(data)
        except:
            data=667

    connection.close()                
    return data



##############################################################################
# This function sets Viessmann 200-W using established connection
def SetViessmannData(parameter):

    connection = ViessmannConnect()
    command = ('set' + parameter + ' \n').encode()
 
    data = ""
    while data != 'vctrld>':
        data = connection.recv(1024).decode()

    connection.send(command)
    connection.close()    




##############################################################################
# This function establishes Connection to the Viessmann
def ViessmannConnect():
    TCP_IP = 'localhost'
    TCP_PORT = 3002
    BUFFER_SIZE = 1024

    #first try socket
    try:
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection.settimeout(5)
    except socket.error as e:
        Logger("Error creating socket: %s", e)
        return
        
    #second try host
    try:
        connection.connect((TCP_IP, TCP_PORT))
    except socket.gaierror as e:
        Logger("Address related error connecting to server: %s", e)
        return
    except socket.error as e:
        Logger("Connection error: %s", e)
        return
    else:
        return connection

##############################################################################
# This function establishes Connection to the Viessmann
def HeatingDBWrite(Instruction, ParameterList):
    try:
        cursor = HeatingDB.cursor()
        cursor.execute(Instruction, ParameterList)
        HeatingDB.commit()
        HeatingDB.close()
    except:
        Logger('Could Not Execute ' + Instruction, 'Warning')
        
##############################################################################################    
# Loop function is repeatedly called by WebIOPi
# Use this to check if any action needs to be taken
# 60 s sleep as we don't need super accurate opening times
# Note, run sudo raspi-config to change time zone!
if __name__ == "__main__":
    
    now = datetime.datetime.now()
 
    DefaultTempRaumSoll = 22
    DefaultNeigung = 0.9
    DefaultNiveau = 0
    DefaultWWTargetTemp = 44
    HeatingForceOff = 22.5
    HeatingForceOn = 21
    WWTarget1Time = '07:30'
    WWTarget2Time = '16:00'

    #Before Midday, try to set WW Target Temps hourly
    if (now.hour < 12) and now.minute == 0:
        setTodaysWWTargetTemps()
    
    CurrentTime = '%0*d' % (2, now.hour) + ':' + '%0*d' % (2, now.minute)
    
    InsideTemp, OutsideTemp = getTemps()    
    TempInnen = InsideTemp
     
    TempRaumSoll = GetViessmannData('TempRaumSollHK2')
    PumpHK2 = GetViessmannData('PumpeStatusHK2')
    ModeHK2 = GetViessmannData('Betriebsart')
    TempVLHK2 = GetViessmannData('TempVListM2')

    TempAussen = GetViessmannData('TempAussen')
    SolarHours=GetViessmannData('SolarStunden')
    SolarLeistung=GetViessmannData('SolarLeistung')
    SolarPump=GetViessmannData('SolarPumpeStatus')
    TempSolar=GetViessmannData('TempSolarKollektor')
    WaterTankTemp=GetViessmannData('TempWasserSpeicher1')
       
    BurnerStarts=GetViessmannData('BrennerStarts')
    BurnerHours=GetViessmannData('BrennerStunden')
    GasKW=GetViessmannData('LeistungIst') * 35/100
    BoilerTarget=GetViessmannData('TempKesselSoll')
    BoilerActual=GetViessmannData('TempKessel')
    TankPump=GetViessmannData('PumpeStatusSp') 

    WWTarget=GetViessmannData('TempWWsoll')
    WWActual=GetViessmannData('TempWWist')
    WWPump=GetViessmannData('PumpeStatusZirku')

    HolidayBegin=GetViessmannData('HolidayBegin')



    ######################################################
    #Part 1 - Log data in database periodically
    HeatingDBWrite("INSERT INTO History (Timestamp, BurnerHours, BurnerStarts, GasKW, ModeHK2, PumpHK2, SolarHours, SolarLeistung, SolarPump, TempAussen, TempInnen, TempRaumSoll, TempSolar, TempVLHK2, WaterTankTemp, BoilerTarget, BoilerActual, TankPump, WWTarget, WWActual, WWPump) VALUES \
(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (now, BurnerHours, BurnerStarts, GasKW, ModeHK2, PumpHK2, SolarHours, SolarLeistung, SolarPump, TempAussen, TempInnen, TempRaumSoll, TempSolar, TempVLHK2, WaterTankTemp, BoilerTarget, BoilerActual, TankPump, WWTarget, WWActual, WWPump))
        
    
    ######################################################


    ######################################################  
    #Part 2 - Correct Heating         
    HeatIncreaseAttempts = 0
    #Use data to set heating logic
    #If it's too hot, then switch off the heating and set the RaumTempSoll etc back to default
    if ((InsideTemp > HeatingForceOff) or ((InsideTemp > HeatingForceOn) and (TempVLHK2 < InsideTemp + 4))) and (ModeHK2 == 2):
        Logger("Switching heating off", "Info")
        SetViessmannData('setBetriebsartTo1')
        SetViessmannData('NiveauHK2 ' + str(int(DefaultNiveau)))
        SetViessmannData('NeigungHK2 ' + str(DefaultNeigung))
        SetViessmannData('TempRaumSollHK2 ' + str(int(DefaultTempRaumSoll)))

    #If it's too cold and we're not in Mode 2, then first try Switching to Mode 2
    if (InsideTemp < HeatingForceOn) and (ModeHK2 != 2):
        Logger("Switching heating on", "Info")
        SetViessmannData('BetriebsartTo2')
        HeatIncreaseAttempts = 1
    
    #If it's too cold and we're in Mode 2 and the pump is on and the Vorlauf Temp < Heating Force Off temp +4.... then try increasing the RaumTempSoll
    if (InsideTemp < HeatingForceOn) and (ModeHK2 == 2) and (PumpHK2 == 1) and TempVLHK2 < (HeatingForceOff +4) and HeatIncreaseAttempts == 0:
        strTargetTemp = str(int(TempRaumSoll+1))
        Logger("Setting Target Temperature to " + strTargetTemp, "Info")
        SetViessmannData('TempRaumSollHK2 ' + strTargetTemp) 
        HeatIncreaseAttempts = 1
    ####################################################################


    ###################################################################
    #Part 3 - Set HW Target Temps according to weather
    WWTarget1 = DefaultWWTargetTemp
    WWTarget2 = DefaultWWTargetTemp
    WWTarget3 = DefaultWWTargetTemp

    try:
        cursor = HeatingDB.cursor()
        cursor.execute("SELECT * FROM WarmWaterTargets WHERE Day = '%s'" % Today)
        results = cursor.fetchall()
        db.close()
    
        for row in results:
          WWTarget1 = row[1]
          WWTarget2 = row[2]
          WWTarget3 = row[3]
    except:
        Logger('Could not retrieve WW Target Temps for today', 'Warning')

    if (datetime.datetime.strptime(CurrentTime, "%H:%M") < datetime.datetime.strptime(WWTarget1Time, "%H:%M")) and (WWTarget != WWTarget1):
        Logger('setting WWTarget ' + str(WWTarget1), 'Info')
        SetViessmannData('TempWWsoll ' + str(int(WWTarget1)))    
    if (datetime.datetime.strptime(CurrentTime, "%H:%M") > datetime.datetime.strptime(WWTarget1Time, "%H:%M")) and (datetime.datetime.strptime(CurrentTime, "%H:%M") < datetime.datetime.strptime(WWTarget2Time, "%H:%M")) and (WWTarget != WWTarget2):
        Logger('setting WWTarget ' + str(WWTarget2), 'Info')
        SetViessmannData('TempWWsoll ' + str(int(WWTarget2))) 
    if (datetime.datetime.strptime(CurrentTime, "%H:%M") > datetime.datetime.strptime(WWTarget2Time, "%H:%M")) and (WWTarget != WWTarget3):
        Logger('setting WWTarget ' + str(WWTarget3), 'Info')
        SetViessmannData('TempWWsoll ' + str(int(WWTarget3)))
     
    ####################################################################
                  






           
            
            
 


  
