# Python2 defaults to PyQt5's API level 1, but Python3
# defaults to level 2, which is what we want. For
# compatibility, we have to explicitly ask for level 2.
import sip
for module in ("QString", "QUrl"):
  sip.setapi(module, 2)

import sys
import signal
import os.path
from PyQt5 import QtCore
from PyQt5 import QtWidgets

def init():
  print("init app")
  global _app
  _app = QtWidgets.QApplication(sys.argv)
  # Needs to be set for media below
  _app.setApplicationName("fbmessenger")

  # Handle Qt's debug output

  # Enable quitting with ctrl-c
  signal.signal(signal.SIGINT, signal.SIG_DFL)

def get_qt_application():
  return _app

def handle_qt_debug_message(level, message_bytes):
  ignored_messages = [
      # QtWebKit spams this and no one knows why :(
      "QFont::setPixelSize: Pixel size <= 0 (0)",
  ]
  message = message_bytes.decode('utf-8')
  if message not in ignored_messages:
    print("Qt debug:", message)

def main_loop():
  sys.exit(_app.exec_())

def resource_path(resource_name):
  this_module = sys.modules[__name__]
  module_dir = os.path.dirname(this_module.__file__)
  return os.path.join(module_dir, "resources", resource_name)

def play_message_sound():
  pass

def quit():
  # Don't bother with _app.exit(). Other parts of the app may still use Qt
  # objects while they're being cleaned up, which causes scary errors
  # (https://github.com/oconnor663/linuxmessenger/issues/33). Just exit the
  # process directly.
  sys.exit()
