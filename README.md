# Quake3-server-monitoring
Provides simple GUI to monitor Quake3 servers

Installation:
1) Install Python3 or higher
2) Install required 
3) Unzip q3monitor.7z and run q3mon.pyw

Settings:

All settings including server list are done via settings.ini file

[Servers]
server1=q3msk.ru:27977
server2=meat.q3msk.ru:7777
server3=ca.q3msk.ru:27960
server4=ctf.q3msk.ru:27960

[Settings]
;hex packet for udp getstatus of Q3 server. do not change
Message=ffffffff67657473746174757300
;app interface refresh frequency, ms
refreshrate=300
;Send packets frequency, ms. if update rate is too high server may consider you as a flooder and ignore your requests
updaterate=1500 
;play sound on first map change or on free slot after app start on full server. set empty to disable or write filename to enable
map_change_sound=tada.wav
;start minimized
minimized=1
;default server number (1 is server1)
default_srv=1
;Quake 3: Arena window name to focus it to press enter if map_change_sound=1
app_name=Quake 3: Arena
