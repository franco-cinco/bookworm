# coding: utf-8

import sys
import wx
from multiprocessing import freeze_support
from bookworm import app as appinfo
from bookworm.paths import logs_path
from bookworm.config import setup_config
from bookworm.database import init_database
from bookworm.signals import app_started, app_shuttingdown
from bookworm.gui.book_viewer import BookViewerWindow
from bookworm.logger import logger


log = logger.getChild(__name__)


class BookwormApp(wx.App):
    def setupSubsystems(self):
        log.debug("Setting up application subsystems.")
        log.debug("Setting up the configuration subsystem.")
        setup_config()
        log.debug("Initializing the database subsystem.")
        init_database()

    def OnInit(self):
        log.debug("Starting the application.")
        log.debug(f"Debug mode is {'on' if appinfo.debug else 'off'}.")
        self.setupSubsystems()
        mainFrame = BookViewerWindow(None, appinfo.display_name)
        self.SetTopWindow(mainFrame)
        mainFrame.Show(True)
        self.Bind(wx.EVT_END_SESSION, self.onEndSession)
        app_started.send(self)
        log.debug("The application has started successfully.")
        return True

    def OnAssert(self, file, line, cond, msg):
        message = f"{file}, line {line}:\nassert {cond}: {msg}"
        log.warning(message, codepath="wx", stack_info=True)

    def onEndSession(self, event):
        app_shuttingdown.send(self)

    def OnExit(self):
        log.debug("Shutting down the application.")
        return 0


def init_app_and_run_main_loop():
    if hasattr(sys, "frozen"):
        freeze_support()
    wxlogfilename = logs_path("wx.log") if not appinfo.debug else None
    app = BookwormApp(redirect=True, useBestVisual=True, filename=wxlogfilename)
    app.MainLoop()
    app_shuttingdown.send(app)


def main():
    try:
        init_app_and_run_main_loop()
        log.debug("The application has exited grasefully.")
    except BaseException as e:
        log.exception(f"An unhandled error has occured.")
        if appinfo.debug:
            raise e
        wx.Exit()