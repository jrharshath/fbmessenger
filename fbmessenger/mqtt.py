import threading
import random
import os

from . import mosquitto
from . import settings
from . import event
from . import network
from . import application

CONNECTION_CHANGED_EVENT = object()
MESSAGE_RECEIVED_EVENT = object()

MQTT_URL = "orcart.facebook.com"
MQTT_PORT = 443

is_connected = False

_subscriptions = []
_client = None
_must_reconnect = False
_backoff_count = 0
_backoff_timer = None

def init():
  global _client
  _client = mosquitto.Mosquitto()
  _client.on_connect = _on_connect
  _client.on_disconnect = _on_disconnect
  _client.on_message = _on_message

  # Find the system certs file, or fall back to our own copy.
  cert_path = "/etc/ssl/certs/ca-certificates.crt"
  if not os.path.exists(cert_path):
    cert_path = application.resource_path("ca-certificates-fallback.crt")
  _client.tls_set(cert_path)

  event.subscribe(settings.AUTH_CHANGED_EVENT, _force_reconnect)
  event.subscribe(network.NETWORK_CHANGED_EVENT, _force_reconnect)
  _BackgroundThread().start()

def subscribe(topic):
  if topic not in _subscriptions:
    _subscriptions.append(topic)
  if _client:
    _client.subscribe(topic, 0)

def publish(topic, payload):
  _client.publish(topic, payload)

class _BackgroundThread(threading.Thread):
  def __init__(self):
    threading.Thread.__init__(self)
    # don't stop the app from exiting
    self.daemon = True

  def run(self):
    _background_loop()

def _background_loop():
  global _must_reconnect
  reconnect_tries = 0
  while True:
    if not is_connected:
      uid, token = settings.get_user_info()
      _client.username_pw_set(uid, token)
      try:
        rc = _client.connect(MQTT_URL, MQTT_PORT)
      # connect can throw some inconsistent exception :(
      except Exception as e:
        print("Mqtt connect error", e)
        rc = -1
      if rc != 0:
        # connection error
        _backoff_wait()
        continue

    if _must_reconnect:
      _must_reconnect = False
      _client.disconnect()
      # We can't rely on the on_disconnect callback here to set the
      # disconnected state, since it will never be called if the network
      # isn't present.
      _set_is_connected(False)

    try:
      rc = _client.loop()
    # loop can throw some weird exceptions too
    except Exception as e:
      print("Mqtt loop error", e)
      rc = -1
    if rc != 0:
      _backoff_wait()
      continue

def _force_reconnect():
  global _must_reconnect, _backoff_count, _backoff_timer
  _must_reconnect = True
  _backoff_count = 0
  if _backoff_timer:
    # cancel any _backoff_wait that might be going on
    _backoff_timer.set()

def _backoff_wait():
  global _backoff_count, _backoff_timer
  # start with one second
  wait_time = 1
  # double it for each previous attempt
  wait_time = wait_time * (2 ** _backoff_count)
  # cap at 5 minutes
  wait_time = min(wait_time, 5 * 60)
  # adjust plus or minus 20%, to avoid thundering herds
  wait_time = (.8 + random.random() * .4) * wait_time

  _backoff_count += 1
  _backoff_timer = threading.Event()
  _backoff_timer.wait(wait_time)

def _on_connect(mosq, obj, rc):
  global is_connected, _backoff_count
  if rc == 0: # success
    # Reset the number of connection attempts when one succeeds.
    _backoff_count = 0
    _set_is_connected(True)
    for topic in _subscriptions:
      _client.subscribe(topic, 0)
  else:
    _set_is_connected(False)

def _on_disconnect(mosq, obj, rc):
  _set_is_connected(False)

def _on_message(mosq, obj, msg):
  topic = msg.topic
  payload = msg.payload.decode('utf-8')
  event.inform(MESSAGE_RECEIVED_EVENT, topic, payload)

def _set_is_connected(value):
  global is_connected
  if is_connected != value:
    is_connected = value
    event.inform(CONNECTION_CHANGED_EVENT, value)
