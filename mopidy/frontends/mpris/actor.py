from __future__ import unicode_literals

import logging

import pykka

from mopidy import settings
from mopidy.core import CoreListener
from mopidy.frontends.mpris import objects

logger = logging.getLogger('mopidy.frontends.mpris')

try:
    import indicate
except ImportError as import_error:
    indicate = None  # noqa
    logger.debug('Startup notification will not be sent (%s)', import_error)


class MprisFrontend(pykka.ThreadingActor, CoreListener):
    def __init__(self, core):
        super(MprisFrontend, self).__init__()
        self.core = core
        self.indicate_server = None
        self.mpris_object = None

    def on_start(self):
        try:
            self.mpris_object = objects.MprisObject(self.core)
            self._send_startup_notification()
        except Exception as e:
            logger.error('MPRIS frontend setup failed (%s)', e)
            self.stop()

    def on_stop(self):
        logger.debug('Removing MPRIS object from D-Bus connection...')
        if self.mpris_object:
            self.mpris_object.remove_from_connection()
            self.mpris_object = None
        logger.debug('Removed MPRIS object from D-Bus connection')

    def _send_startup_notification(self):
        """
        Send startup notification using libindicate to make Mopidy appear in
        e.g. `Ubunt's sound menu <https://wiki.ubuntu.com/SoundMenu>`_.

        A reference to the libindicate server is kept for as long as Mopidy is
        running. When Mopidy exits, the server will be unreferenced and Mopidy
        will automatically be unregistered from e.g. the sound menu.
        """
        if not indicate:
            return
        logger.debug('Sending startup notification...')
        self.indicate_server = indicate.Server()
        self.indicate_server.set_type('music.mopidy')
        self.indicate_server.set_desktop_file(settings.DESKTOP_FILE)
        self.indicate_server.show()
        logger.debug('Startup notification sent')

    def _emit_properties_changed(self, *changed_properties):
        if self.mpris_object is None:
            return
        props_with_new_values = [
            (p, self.mpris_object.Get(objects.PLAYER_IFACE, p))
            for p in changed_properties]
        self.mpris_object.PropertiesChanged(
            objects.PLAYER_IFACE, dict(props_with_new_values), [])

    def track_playback_paused(self, track, time_position):
        logger.debug('Received track playback paused event')
        self._emit_properties_changed('PlaybackStatus')

    def track_playback_resumed(self, track, time_position):
        logger.debug('Received track playback resumed event')
        self._emit_properties_changed('PlaybackStatus')

    def track_playback_started(self, track):
        logger.debug('Received track playback started event')
        self._emit_properties_changed('PlaybackStatus', 'Metadata')

    def track_playback_ended(self, track, time_position):
        logger.debug('Received track playback ended event')
        self._emit_properties_changed('PlaybackStatus', 'Metadata')

    def volume_changed(self):
        logger.debug('Received volume changed event')
        self._emit_properties_changed('Volume')

    def seeked(self, time_position_in_ms):
        logger.debug('Received seeked event')
        self.mpris_object.Seeked(time_position_in_ms * 1000)
