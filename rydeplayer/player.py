#    Ryde Player provides a on screen interface and video player for Longmynd compatible tuners.
#    Copyright © 2020 Tim Clark
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

import pygame, vlc, select, pydispmanx, yaml, os, pkg_resources, argparse, importlib
from . import longmynd
from . import ir
import rydeplayer.common
import rydeplayer.states.gui
import rydeplayer.states.playback

# container for the theme
class Theme(object):
    def __init__(self, displaySize):
        self.colours = type('colours', (object,), {
            'transparent': (0,0,0,0),
            'transpBack': (0,0,0,51),
            'black': (0,0,0,255),
            'white': (255,255,255,255),
            'red': (255,0,0,255),
            'backgroundMenu': (57,169,251,255),
            'backgroundSubMenu': (57,169,251,255),
            'backgroundPlayState': (255,0,0,255),
            })
        self.menuWidth = int(displaySize[0]/4)
        self.menuHeight = int(displaySize[1])
        playStateTitleFontSize=self.fontSysSizeOptimize('Not Loaded', displaySize[0]/2, 'freesans')
        menuH1FontSize=self.fontSysSizeOptimize('BATC Ryde Project', self.menuWidth*0.85, 'freesans')
        self.fonts = type('fonts', (object,), {
            'menuH1': pygame.font.SysFont('freesans', menuH1FontSize),
            'playStateTitle' :  pygame.font.SysFont('freesans', playStateTitleFontSize),
            })
        self.logofile = pkg_resources.resource_stream('rydeplayer.resources', 'logo_menu.png')

    # calculate the largest font size that you can render the given test in as still be less than width
    def fontSysSizeOptimize(self, text, width, fontname):
        fontsize = -1
        while True:
            fontCandidate = pygame.font.SysFont(fontname, fontsize+1)
            fontwidth = fontCandidate.size(text)[0]
            del(fontCandidate)
            if(fontwidth > width):
                break
            else:
                fontsize += 1
        return fontsize

# main UI state machine
class guiState(rydeplayer.states.gui.SuperStates):
    def __init__(self, theme):
        super().__init__(theme)
        self.done = False
    def startup(self, config, debugFunctions):
        # main menu states, order is important to get menus and sub menus to display in the right place
        mainMenuStates = {
            'freq-sel' : rydeplayer.states.gui.NumberSelect(self.theme, 'freq', 'KHz', config.tuner.freq, 2450000, 144000, config.tuner.setFrequency),
            'freq'     : rydeplayer.states.gui.MenuItem(self.theme, "Frequency", "port", "sr", "freq-sel"),
            'sr-sel'   : rydeplayer.states.gui.NumberSelect(self.theme, 'sr', 'KSPS', config.tuner.sr, 27500, 33, config.tuner.setSymbolRate),
            'sr'       : rydeplayer.states.gui.MenuItem(self.theme, "Symbol Rate", "freq", "pol", "sr-sel"),
            'pol-sel'  : rydeplayer.states.gui.ListSelect(self.theme, 'pol', {longmynd.PolarityEnum.NONE:'None', longmynd.PolarityEnum.HORIZONTAL:'Horizontal', longmynd.PolarityEnum.VERTICAL:'Vertical'}, config.tuner.pol, config.tuner.setPolarity),
            'pol'      : rydeplayer.states.gui.MenuItem(self.theme, "LNB Polarity", "sr", "port", "pol-sel"),
            'port-sel' : rydeplayer.states.gui.ListSelect(self.theme, 'port', {longmynd.inPortEnum.TOP:'Top', longmynd.inPortEnum.BOTTOM:'Bottom'}, config.tuner.port, config.tuner.setInputPort),
            'port'     : rydeplayer.states.gui.MenuItem(self.theme, "Input Port", "pol", "freq", "port-sel"),
#            'autoplay-sel' : rydeplayer.states.gui.ListSelect(self.theme, 'autoplay', {True:'Enabled', False:'Disabled'}, config.debug.autoplay, config.setAutoplay),
#            'autoplay' : rydeplayer.states.gui.MenuItem(self.theme, "Autoplay", "port", "vlcplay", "autoplay-sel"),
        }
        firstkey = 'freq'
        lastkey = 'port'
        for key in debugFunctions:
            menukey = key.strip().replace(" ", "").lower()
            mainMenuStates[menukey] = rydeplayer.states.gui.MenuItemFunction(self.theme, key, lastkey, firstkey, debugFunctions[key])
            mainMenuStates[lastkey].down = menukey
            mainMenuStates[firstkey].up = menukey
            lastkey = menukey

        self.state_dict = {
            'menu': rydeplayer.states.gui.Menu(self.theme, 'home', mainMenuStates, "freq"),
            'home': Home(self.theme)
        }
        self.state_name = "home"
        self.state = self.state_dict[self.state_name]
        self.state.startup()
    def get_event(self, event):
        if(event == rydeplayer.common.navEvent.POWER):
            self.state.cleanup()
            self.done = True
        else:
            self.state.get_event(event)

# GUI state for when the menu isnt showing
class Home(rydeplayer.states.gui.States):
    def __init__(self, theme):
        super().__init__(theme)
        self.next = 'menu'
    def cleanup(self):
        None
    def startup(self):
        None
    def get_event(self, event):
        #TODO: add OSD state machine
        if(event == rydeplayer.common.navEvent.SELECT):
            print('OSD')
        elif(event == rydeplayer.common.navEvent.MENU):
            self.done = True

class rydeConfig(object):
    def __init__(self):
        self.ir = ir.irConfig()
        self.tuner = longmynd.tunerConfig()
        #important longmynd path defaults
        self.longmynd = type('lmConfig', (object,), {
            'binpath': '/home/pi/longmynd/longmynd',
            'mediapath': '/home/pi/lmmedia',
            'statuspath': '/home/pi/lmstatus',
            })
        self.debug = type('debugConfig', (object,), {
            'autoplay': True,
            'disableHardwareCodec': True,
            })
        self.configRev = 1
    #setter for default values
    def setAutoplay(self, newval):
        self.debug.autoplay = newval

    # parse config dict
    def loadConfig(self, config):
        perfectConfig = True
        if isinstance(config, dict):
            # parse config revision
            if 'configRev' in config:
                if isinstance(config['configRev'], int):
                    if config['configRev'] != self.configRev:
                        print("Unmatched config revision, config load aborted")
                        return False
                else:
                    print("Config revision not an integer, config load aborted")
                    return False
            else:
                print("WARNING: no config revision present, config load my fail")
            # parse critical longmynd paths
            if 'longmynd' in config:
                if isinstance(config['longmynd'], dict):
                    if 'binpath' in config['longmynd']:
                        if isinstance(config['longmynd']['binpath'], str):
                            self.longmynd.binpath = config['longmynd']['binpath']
                            # TODO: check this path is valid
                        else:
                            print("Invalid longymnd binary path")
                            perfectConfig = False
                    if 'mediapath' in config['longmynd']:
                        if isinstance(config['longmynd']['mediapath'], str):
                            self.longmynd.mediapath = config['longmynd']['mediapath']
                        else:
                            print("Invalid longymnd media FIFO path")
                            perfectConfig = False
                    if 'statuspath' in config['longmynd']:
                        if isinstance(config['longmynd']['statuspath'], str):
                            self.longmynd.statuspath = config['longmynd']['statuspath']
                        else:
                            print("Invalid longymnd status FIFO path")
                            perfectConfig = False
                else:
                    print("Invalid longmynd config")
                    perfectConfig = False
            # pass default tuner config to be parsed by longmynd module
            if 'default' in config:
                perfectConfig = perfectConfig and self.tuner.loadConfig(config['default'])
            # pass ir config to be parsed by the ir config container
            if 'ir' in config:
                perfectConfig = perfectConfig and self.ir.loadConfig(config['ir'])
            # parse debug options
            if 'debug' in config:
                if isinstance(config['debug'], dict):
                    if 'autoplay' in config['debug']:
                        if isinstance(config['debug']['autoplay'], bool):
                            self.debug.autoplay = config['debug']['autoplay']
                        else:
                            print("Invalid debug autoplay config, skipping")
                            perfectConfig = False
                        if isinstance(config['debug']['disableHardwareCodec'], bool):
                            self.debug.disableHardwareCodec = config['debug']['disableHardwareCodec']
                        else:
                            print("Invalid debug hardware codec config, skipping")
                            perfectConfig = False
                else:
                    print("Invalid debug config, skipping")
                    perfectConfig = False

                    
        else:
            print("Invalid config, no fields")
            perfectConfig = False
        return perfectConfig

    # load yaml config file
    def loadFile(self, path):
        if os.path.exists(path) and os.path.isfile(path):
            try:
                with open("config.yaml", 'r') as ymlconfigfile:
                    self.loadConfig(yaml.load(ymlconfigfile))
            except IOError as e:
                print(e)
        else:
            print("config file not found")

class player(object):

    def __init__(self, configFile = None):
        # load config
        self.config = rydeConfig()
        if configFile != None:
            self.config.loadFile(configFile)
        print(self.config.tuner)

        # setup ui core
        pygame.init()
        self.theme = Theme(pydispmanx.getDisplaySize())
        self.playbackState = rydeplayer.states.playback.StateDisplay(self.theme)
        print(pygame.font.get_fonts())

        # setup longmynd
        self.lmMan = longmynd.lmManager(self.config.tuner, self.config.longmynd.binpath, self.config.longmynd.mediapath, self.config.longmynd.statuspath)
        self.config.tuner.setCallbackFunction(self.lmMan.reconfig)

        self.vlcStartup()

        # start ui
        self.app = guiState(self.theme)
        self.app.startup(self.config, {'Restart LongMynd':self.lmMan.restart, 'Force VLC':self.vlcStop, 'Abort VLC': self.vlcAbort})

        # setup ir
        self.irMan = ir.irManager(self.app, self.config.ir)

        # start longmynd
        self.lmMan.start()
        print("Ready")
        self.monotonicState = 0;

    def start(self):
        quit = False
        # main event loop
        while not quit:
            # need to regen every loop, lm stdout handler changes on lm restart
            fds = self.irMan.getFDs() + self.lmMan.getFDs()
            r, w, x = select.select(fds, [], [])
            for fd in r:
                quit = self.handleEvent(fd)
                self.updateState()
                if quit:
                    break

    def handleEvent(self, fd):
        quit = False
        # handle ready file descriptors
        if(fd in self.irMan.getFDs()):
            quit = self.irMan.handleFD(fd)
        elif(fd in self.lmMan.getFDs()):
            self.lmMan.handleFD(fd)
        return quit

    def updateState(self):
        # update playback state
        if(self.lmMan.isRunning()):
            if(self.lmMan.isLocked()):
                self.playbackState.setState(rydeplayer.states.playback.States.LOCKED)
                newMonoState = self.lmMan.getMonotonicState()

                if self.monotonicState != newMonoState:
                    self.monotonicState = newMonoState
                    self.vlcStop()
                    print("Param Restart")
                if self.vlcPlayer.get_state() not in [vlc.State.Playing, vlc.State.Opening] and self.config.debug.autoplay:
                    self.vlcPlay()
            else:
                self.playbackState.setState(rydeplayer.states.playback.States.NOLOCK)
                if self.config.debug.autoplay:
                    self.vlcStop()
        else:
            self.playbackState.setState(rydeplayer.states.playback.States.NOLONGMYND)
            if self.config.debug.autoplay:
                self.vlcStop()
#               print("parsed:"+str(vlcMedia.is_parsed()))
        print(self.vlcPlayer.get_state())

    # retrigger vlc to play, mostly exsists as its needed as a callback
    def vlcPlay(self):
        self.vlcPlayer.set_media(self.vlcMedia)
        self.vlcPlayer.play()
    def vlcStop(self):
        self.vlcPlayer.stop()
    def vlcAbort(self):
        del(self.vlcMedia)
        del(self.vlcPlayer)
        del(self.vlcInstance)
        importlib.reload(vlc)
        self.lmMan.remedia()
#        self.lmMan.restart()
        self.vlcStartup()

    def vlcStartup(self):
        if self.config.debug.disableHardwareCodec:
            self.vlcInstance = vlc.Instance('--codec ffmpeg')
        else:
            self.vlcInstance = vlc.Instance()
#            self.vlcInstance = vlc.Instance('--gain 4 --alsa-audio-device hw:CARD=Headphones,DEV=0')

        self.vlcPlayer = self.vlcInstance.media_player_new()
        self.vlcMedia = self.vlcInstance.media_new_fd(self.lmMan.getMediaFd().fileno())

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("Config File", help="YAML config file to try and load. Default: config.yaml", nargs='?', default='config.yaml')
    args = parser.parse_args()
    print(args)
    newplayer = player('config.yaml')
    newplayer.start()

if __name__ == '__main__':
    run()
