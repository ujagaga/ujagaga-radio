# ujagaga radio gpio module #

I am using Orange PI Zero to play internet radio. There are three GPIO pins I use connected to push buttons to switch stations and start/stop radio

### How to start? ###

Just run setup.sh to install necessary packages. Then run gpiocmd.py. Do take a look at contents because it defines pushbutton pins at start:
BTN_NEXT = 23
BTN_PREV = 19
BTN_PAUSE = 21

BTN_PAUSE will start/stop radio if shortly pressed and turn off the whole computer if held longer than 3 seconds.


## Contact ##

* [My web page](http://www.radinaradionica.com)






