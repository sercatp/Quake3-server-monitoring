from PyQt5.QtCore import QTime, QTimer
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QAction, QTableWidget,QTableWidgetItem,QVBoxLayout, QLabel, QGridLayout, QCheckBox
from PyQt5.QtGui import QIcon, QPainter, QBrush, QPen, QColor, QFont
from PyQt5.QtCore import pyqtSlot
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QCoreApplication, Qt,QBasicTimer, QPoint, QEvent
from playsound import playsound

import threading
import sys
import socket
import time
import tempfile #for transparent icon?
import base64, zlib #for transparent icon
import select
import os #for os path to get app icon
import configparser #ini reader?

#import this section to run q3
import win32ui
import pygetwindow  as gw
import keyboard

class Q3Mon(QLabel):
    def __init__(self, parent=None):
        #UDP port  to listen
        self.UDPR_IP = "127.0.0.1"
        self.UDPR_PORT = 7001

        self.UDP_IP=[]
        self.UDP_PORT=[]
        self.app_name=""

        self.ReadIni()

        self.globalserverstatus='' #used in win title
        self.MonitoredServers=[] #if server is monitored then  =1, if not then =0
        self.IsSending=[] #trigger that is switched after packet sent in the thread for each server
        self.milli_time1=[]
        self.milli_time2=[]
        self.ping_ms=[]
        self.thread=[]
        self.data=[]
        self.addr=[]
        self.dataDecoded=[]
        self.server_status=[]
        self.pl_list=[] #one string (with all the players) per server
        self.players_count=[]
        self.old_mapname=""
        self.prev_players_count=0

        self.old_servno= len(self.UDP_IP)+1

        for i in range(len(self.UDP_IP)):
            self.milli_time1.append(0)
            self.milli_time2.append(0)
            self.MonitoredServers.append(1)
            self.IsSending.append(0)
            self.pl_list.append("")
            self.players_count.append(0)
            #self.pl_list.append(0)
            #self.pl_list.append(0)
            self.ping_ms.append(999)
            self.data.append('unreachable')
            self.server_status.append('unreachable - - -')
            self.addr.append('')
            self.dataDecoded.append('')

        if len(sys.argv)>1: self.server_no = int(sys.argv[1])

        super(QLabel, self).__init__(parent)

        self.left = 1300
        self.top = 300
        self.width = 500
        self.height = 500
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.showTime)
        self.timer.start(self.refreshrate)

        # Add box layout, add table to box layout and add box layout to widget
        self.tableWidget = []
        self.layout = QGridLayout()

        self.serverWidget = QTableWidget()
        self.layout.addWidget(self.serverWidget)
        self.tableWidget= QTableWidget()
        self.layout.addWidget(self.tableWidget)

        self.setWindowFlags(Qt.Window|Qt.FramelessWindowHint|Qt.WindowMinMaxButtonsHint) #windows with no borders, but available to minimize
        #translate tableWidget mouse events to window events
        for TableNo in range (0, 1, 1): #range(len(self.UDP_IP)):
            self.tableWidget.mousePressEvent = self.mousePressEvent
            self.tableWidget.mouseMoveEvent = self.mouseMoveEvent
            self.tableWidget.mouseReleaseEvent = self.mouseReleaseEvent
            self.tableWidget.changeEvent = self.changeEvent

        self.serverWidget.itemClicked.connect(self.selRow)
        self.serverWidget.move(0,0)
        self.setLayout(self.layout)

        self.StartListening()
        time.sleep(0.2)
        self.showTime()
        if (self.minimized==1): self.showMinimized ()

    def ReadIni(self):
        config = configparser.ConfigParser()
        config.read('settings.ini')

        for section in config.sections():
           for option, value in config.items(section):
                if "server" in option:
                   temp=value.split(":")
                   self.UDP_IP.append(temp[0])
                   self.UDP_PORT.append(int(temp[1]))
                   print (self.UDP_IP, self.UDP_PORT)
                if "message" in option: self.MESSAGE = bytes.fromhex(value)
                if "map_change_sound" in option: self.map_change_sound = str(value)
                if "refreshrate" in option: self.refreshrate = int(value)
                if "updaterate" in option: self.updaterate = int(value)
                if "minimized" in option: self.minimized = int(value)
                if "default_srv" in option: self.server_no = int(value)-1 #server_no can also be set in init section by sys.argv[1]
                if "app_name" in option: self.app_name = str(value)
                print (option,value)

    def StartListening(self):
        self.sock=[]
        portCounter=0
        for serverN in range(len(self.UDP_IP)):
            #register network listeners
            sockTemp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.append (sockTemp)
            self.sock[serverN].bind((self.UDPR_IP, self.UDPR_PORT+serverN))
            print ("listening port: ",self.UDPR_IP, self.UDPR_PORT+serverN)
            #SO_REUSEADDR prevents busy port exception
            self.sock[serverN].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock[serverN] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP

            #now for each monitored server starting threads that will send UDP packets
            tempThread = threading.Thread(target = self.SendUDP, args = [serverN])
            self.thread.append(tempThread)
            print ("=== THREAD STARTED === for server",self.UDP_IP[serverN],":", self.UDP_PORT[serverN], self.thread[serverN])
            self.thread[serverN].daemon = True #to terminate program faster
            self.thread[serverN].start()

    def SendUDP(self, serverN):
        #send packets only if the flag for serverN server is on (app is not minimized)
        while (self.MonitoredServers[serverN]==1):
            print ("---new packet sent---" ,self.UDP_IP[serverN],":", self.UDP_PORT[serverN])
            self.IsSending[serverN]=1 #trigger to catch packet timeouts
            try:
                self.milli_time1[serverN] = int(round(time.time() * 1000)) #to check ping between send and recieve
                self.sock[serverN].sendto(bytes(self.MESSAGE), (self.UDP_IP[serverN], self.UDP_PORT[serverN]))
                self.sock[serverN].setblocking(0) # set the socket to non-blocking mode to guarantee that recv() will never block indefinitely.
                self.sock[serverN].settimeout(1)
                self.data[serverN], self.addr[serverN] = self.sock[serverN].recvfrom(4096) # buffer size is 4096 bytes
                self.milli_time2[serverN] = int(round(time.time() * 1000)) #to check ping between send and recieve
                self.ping_ms[serverN] = self.milli_time2[serverN]-self.milli_time1[serverN]
                self.IsSending[serverN]=0
            except socket.error:
                print ("network error")

            if not self.data[serverN]: print ("---------------------------self.data-",[serverN])
            else:
                self.dataDecoded[serverN] = self.data[serverN].decode('utf-8', errors='ignore') #convert the string encoding from bytes to str
                self.analyze_response(self.dataDecoded[serverN], serverN)
                print ("--------------------------------- data was sent", self.data[serverN])
            time.sleep(self.updaterate/1000)

    def showTime(self): #main routine function
        #print ("showTime")
        icon_path = 'icons\\' + str(self.server_no+1) + '.png'
        scriptDir = os.path.dirname(os.path.realpath(__file__))
        self.setWindowIcon(QtGui.QIcon(icon_path))
        #for serverN in range(len(self.UDP_IP)):
            #print ("xxxxx:",self.UDP_IP[serverN],":", self.UDP_PORT[serverN],self.dataDecoded[serverN])
            #print ("self.MonitoredServers", self.MonitoredServers[serverN])

        self.ServListTable()
        self.setWindowTitle(self.globalserverstatus)
        #print ("=================================",self.globalserverstatus)

        self.FillTable(self.server_no)

        self.setFixedSize(max(self.tableWidget.width,self.serverWidget.width), self.tableWidget.height+self.serverWidget.height)
        self.setLayout(self.layout)

        self.layout.removeWidget(self.tableWidget) #destroys previous widget to update table
        self.layout.removeWidget(self.serverWidget) #destroys previous widget to update table

        self.CheckThreads() #restart thread if it is dead by timeout

    def CheckThreads(self):
        for serverN in range(len(self.UDP_IP)):
            #print (":::thread checkup:", self.thread[serverN])
            if not self.thread[serverN].isAlive(): #restart thread if it is dead by timeout
                tempThread = threading.Thread(target = self.SendUDP, args = [serverN])
                self.thread[serverN]=tempThread
                #print ("!!!!!!!!!!!!!!!!!!!!!! THREAD STARTED AGAIN === for server",self.UDP_IP[serverN],":", self.UDP_PORT[serverN])
                self.thread[serverN].daemon = True #to terminate program faster without waiting for threads to terminate
                self.thread[serverN].start()

    def analyze_response(self, string1, serverN):
        string2 = []
        string3 = []
        string4 = []
        string5 = []
        string6 = []
        scorex = -1
        score_blue = -1
        score_red = -1
        players_blue= ""
        players_red= ""
        self.pl_team=[]

        try:
           string2 = string1.split('\\') #split response packet parameters by \\
        except AttributeError as error:
           string2 = ['unreachable', 'unreachable', 'unreachable', 'unreachable']
           print ("xxxxxxxxxx AttributeError xxxxxxxxxxx ",string1, serverN)

        #get the map name
        for i in range(len(string2)-2, 0, -1):
            if string2[i] == 'mapname':
                mapname = string2[i+1]
            if string2[i] == 'score_blue':
                score_blue = int(string2[i+1])
            if string2[i] == 'score_red':
                score_red = int(string2[i+1])
            if string2[i].casefold() == 'players_blue'.casefold(): #compare case-insensitive
                players_blue = string2[i+1]
            if string2[i].casefold() == 'players_red'.casefold():
                players_red = string2[i+1]

        players_blue = players_blue.split(' ')
        players_red = players_red.split(' ')

        print ("    - - - - - players_red, players_blue:", players_red, players_blue)

        mapname=mapname.replace('tourney', 't')
        mapname=mapname.replace('pro-', '')
        mapname=mapname.replace('q3', '')

        if score_blue > -1: scorex=max(score_blue, score_red)
        print (scorex)

        string3 = string2[len(string2)-1] # assign the list of players to str3
        string4 = string3.split('\n') #split the list of players by \n
        #print (string4)

        #gets the highest score
        highestscore = 0
        string6 = [None] * (len(string4)-2) #create the list with the size of number of players
        for i in range(1, len(string4)-1, 1): #loop player list
            string5=string4[i].split(' ', 2) #split each player stats
            #print ("string5::: ", string5)
            #if string5[0].isdigit():
            #print ('current name ', string5[2]) #print the score of current player
            if int(string5[0])>highestscore: highestscore=int(string5[0])
            string6[i-1] = string5[0] + ' ' + string5[1] + ' ' +  string5[2]

        if scorex > -1: highestscore = scorex #return round score if teamplay server, or just player's highestscore if ffa

        #get the max player count
        sv_maxclients=""
        for i in range(len(string2)-2, 0, -1):
            if string2[i] == 'sv_maxclients':
                sv_maxclients = string2[i+1]

        #assign team to each player
        for i in range (len(players_blue)-1): string6[int(players_blue[i])-1] += " b"
        for i in range (len(players_red)-1): string6[int(players_red[i])-1] += " r"
        if (len(players_blue)<2):
            for i in range (len(string6)): string6[i] += " ffa" #if the mode is not teamplay

        #get the no-zero-ping-players count
        no_bot_players_count=0
        for i in range(len(string6)):
            temp1=string6[i].split()
            print (i, temp1)
            if temp1[1] != '0': #if players' ping==0 then it's a bot and dont counts in total player amount
                no_bot_players_count += 1

        #if app is minimized, fill the list of servers with 0 to prevent errors
        self.pl_list[serverN] = string6
        #print ("zzzzzzzzzz", self.pl_list)
        self.players_count[serverN] = (len(string4)-2)
        self.server_status[serverN] = (str(no_bot_players_count)+'-'+sv_maxclients+' '
                                       +str(highestscore)+' '+mapname+' '+str(self.ping_ms[serverN]))
        if serverN== self.server_no:
            self.globalserverstatus = self.server_status[serverN]
            # put point in the end if the sound on map change will be played.
            if  len(self.map_change_sound) > 1: self.globalserverstatus = self.globalserverstatus + '.' #'•'
            print (mapname, self.players_count[0], sv_maxclients)
            self.PlaySound(mapname, self.players_count, sv_maxclients)
        print (serverN, ': ' , self.globalserverstatus)

    def Process_exists(self, process_name):
        try:
            win32ui.FindWindow(process_name, None)
        except win32ui.error:
            return False
        else:
            return True

    #playsound on map change or players=max_pl-1
    def PlaySound (self, mapname, players_count, sv_maxclients):
        if (self.old_servno==len(self.UDP_IP)+1): self.old_servno=self.server_no #if first run then assign old_servno current value
        elif (self.old_servno!=self.server_no): # in case if user switched the server manually
            self.old_mapname=mapname
            self.prev_players_count=0
            self.old_servno=self.server_no
        if len(self.map_change_sound) > 1:
            playnow=0
            if (int(sv_maxclients)==int(players_count[0])): self.prev_players_count=1 #if number of players got max for this server
            if (self.prev_players_count==1) and (int(sv_maxclients)!=int(players_count[0])): playnow=1
            if (self.old_mapname==""): self.old_mapname=mapname
            if (self.old_mapname != mapname): playnow=1
            print ("sv_maxclients, players_count:", sv_maxclients, players_count[0])

            if playnow==1:
                #now focus q3arena to send \reconnect in console
                if len(self.app_name)>1: #if app_name is set in .ini file
                    if self.Process_exists(self.app_name):
                       app_handle=win32ui.FindWindow(self.app_name, None)
                       app_handle.SetFocus()
                       win = gw.getWindowsWithTitle(self.app_name)[0]
                       win.activate()
                       time.sleep (0.1)
                       #keyboard.press_and_release('`')
                       #time.sleep (0.1)
                       #keyboard.write('\\reconnect')
                       keyboard.press_and_release('enter')
                       print ("App is running")
                    else:
                       print ("App NOT running")
                try: 
                    playsound(self.map_change_sound)
                except Exception as e:
                    print ("playsound exception:",self.map_change_sound,":::",e)
                self.map_change_sound = ""
    def clean_playername (self, plname):
        #removes '^' from player's names
        plname=plname.replace('"', '')
        #print(plname)
        modifiedname=""
        i=0 #internal cycle index
        while i < len(plname):
            if (plname[i] == '^') and (i < (len(plname)-1)):
                if (plname[i+1] == 'X') or (plname[i+1] == 'x'): i += 7
                elif (plname[i+1] == '^'): #if two ^ in row, leave just one of them
                    modifiedname += plname[i]
                    i += 2
                else: i += 1
            else:
                modifiedname += plname[i]
                #print (plname[i])
            i += 1
        return modifiedname

    def ServListTable(self):
        if self.minimized==0:
            self.serverWidget.move(0,0)
            self.setLayout(self.layout)
            self.serverWidget.setRowCount(len(self.UDP_IP))
            self.serverWidget.setColumnCount(5)

            for i in range(len(self.UDP_IP)):

                #if self.IsSending[i]==0: #if the server is not timed out
                    ttt1 = self.server_status[i]
                    temp=ttt1.split(' ')

                    self.serverWidget.removeCellWidget(i,0)
                    self.serverWidget.removeCellWidget(i,1)
                    self.serverWidget.removeCellWidget(i,2)
                    self.serverWidget.removeCellWidget(i,3)
                    self.serverWidget.removeCellWidget(i,4)

                    item0 = QTableWidgetItem(self.UDP_IP[i] + ':' + str(self.UDP_PORT[i]))
                    item1 = QTableWidgetItem(temp[0])
                    item2 = QTableWidgetItem(temp[1])
                    item3 = QTableWidgetItem(temp[2])
                    item4 = QTableWidgetItem(temp[3])

                    #if server is selected then show it in color
                    if i==self.server_no:
                        item0.setBackground(QtGui.QColor(100,100,150))
                        item1.setBackground(QtGui.QColor(100,100,150))
                        item2.setBackground(QtGui.QColor(100,100,150))
                        item3.setBackground(QtGui.QColor(100,100,150))
                        item4.setBackground(QtGui.QColor(100,100,150))
                        #print ('active server is ', i)

                    self.serverWidget.setItem(i, 0, item0)
                    self.serverWidget.setItem(i, 1, item1)
                    self.serverWidget.setItem(i, 2, item2)
                    self.serverWidget.setItem(i, 3, item3)
                    self.serverWidget.setItem(i, 4, item4)

                    self.serverWidget.setRowHeight(i,10)

        self.serverWidget.resizeColumnToContents(0)
        self.serverWidget.resizeColumnToContents(1)
        self.serverWidget.resizeColumnToContents(2)
        self.serverWidget.resizeColumnToContents(3)
        self.serverWidget.resizeColumnToContents(4)

        self.serverWidget.width = 3 + self.serverWidget.columnWidth(0) + self.serverWidget.columnWidth(1) + self.serverWidget.columnWidth(2) + self.serverWidget.columnWidth(3) + self.serverWidget.columnWidth(4)
        self.serverWidget.height = len(self.UDP_IP) * self.serverWidget.rowHeight(1) + 3
        #self.resize(self.width, self.height)
        self.serverWidget.setFixedSize(self.serverWidget.width, self.serverWidget.height)

        self.serverWidget.verticalHeader().setVisible(False)
        self.serverWidget.horizontalHeader().setVisible(False)

        self.serverWidget.verticalHeader().setVisible(False)
        self.serverWidget.horizontalHeader().setVisible(False)
        self.serverWidget.setShowGrid(0)
        self.serverWidget.reset()
        self.setLayout(self.layout)

    def FillTable(self, serverN):

         if self.MonitoredServers[serverN]==1 :

            self.tableWidget.move(0,self.serverWidget.height)
            self.tableWidget.setRowCount(self.players_count[serverN])
            self.tableWidget.setColumnCount(3)
            for i in range(len(self.pl_list[serverN])):
                tt = self.pl_list[serverN]
                temp=tt[i].split(' ', 2)
                temp[0] = int(temp[0])
                temp[1] = int(temp[1])
                pl_nickname_team = temp[2].split('"') #get nickname and team name of the player
                temp[2] = self.clean_playername(pl_nickname_team[1]) #removes ^ from playernames
                #print (i, " pl_nickname ",len(pl_nickname_team))

                self.tableWidget.removeCellWidget(i,0)
                self.tableWidget.removeCellWidget(i,1)
                self.tableWidget.removeCellWidget(i,2)

                #set scores field as integer
                item = QTableWidgetItem()
                item.setData(Qt.EditRole, temp[0])
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignCenter)
                self.tableWidget.setItem(i, 0, item)
                #item.setForeground(0,QtGui.QBrush(QtGui.QColor("#123456")))

                #set playname field
                item2 = QTableWidgetItem()
                item2.setData(Qt.EditRole, temp[2])
                #self.tableWidget.setItem(i, 1, QTableWidgetItem(temp[2]))
                self.tableWidget.setItem(i, 1, item2)

                #set ping field
                item1 = QTableWidgetItem()
                item1.setFlags(item1.flags() ^ Qt.ItemIsEditable)
                item1.setData(Qt.EditRole, temp[1])
                item1.setTextAlignment(Qt.AlignCenter)
                self.tableWidget.setItem(i, 2, item1)

                #self.tableWidget.resizeRowToContents(i)
                self.tableWidget.setRowHeight(i,10)

                #colorify bot players rows
                if (temp[1] == 0) or (pl_nickname_team[2]==''): #if ping==0 (player is bot) or if player has no team (is spec): then gray
                    item.setForeground(QBrush(QColor(150, 150, 150)))
                    item1.setForeground(QBrush(QColor(150, 150, 150)))
                    item2.setForeground(QBrush(QColor(150, 150, 150)))

            self.tableWidget.setColumnWidth(0,10)
            self.tableWidget.resizeColumnToContents(1)
            self.tableWidget.setColumnWidth(2,10)
            self.tableWidget.sortByColumn(0, 1) #sort by first(0) column in descending(1) order
            self.tableWidget.width = self.tableWidget.columnWidth(1) + 64
            self.tableWidget.height = self.players_count[serverN] * 23 + 7
            #self.resize(self.width, self.height)
            self.tableWidget.setFixedSize(self.tableWidget.width, self.tableWidget.height)

            self.tableWidget.verticalHeader().setVisible(False)
            self.tableWidget.horizontalHeader().setVisible(False)
            self.tableWidget.setShowGrid(0)
            self.tableWidget.reset()

    def closeEvent(self, event):
        sys.exit()

    def selRow(self, item):
        self.server_no=item.row()
        print (":::::selRow is ", self.server_no, " row number")
        self.showTime()

    def changeEvent(self, event):
        print ("changeEvent")
        if event.type() == QEvent.WindowStateChange:
            if event.oldState() and Qt.WindowMinimized:
                self.minimized=0
                print("WindowMaximized", self.minimized)
                for ServerN in range(len(self.UDP_IP)): #start monitoring all the servers
                    self.MonitoredServers[ServerN]=1
            elif event.oldState() == Qt.WindowNoState or self.windowState() == Qt.WindowMaximized:
                self.minimized=1
                print("WindowMinimized", self.minimized)
                for ServerN in range(len(self.UDP_IP)): #disable monitoring for all servers except current
                    self.MonitoredServers[ServerN]=0
                    if ServerN==self.server_no: self.MonitoredServers[ServerN]=1
                    #print ("self.MonitoredServers", self.MonitoredServers[ServerN])

    def mousePressEvent(self, event):
        #print ("clicked")
        #print (event.globalPos())
        self.timer.stop()
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QPoint (event.globalPos() - self.oldPos)
        #print(delta)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()

    def mouseReleaseEvent(self, event):
        #self.setDisabled(false)
        #self.timer.timeout.connect(self.showTime)
        self.timer.start(self.refreshrate)
        return


if __name__ == '__main__':
    app = QApplication(sys.argv)
    clock = Q3Mon()
    clock.show()

    sys.exit(app.exec_())
