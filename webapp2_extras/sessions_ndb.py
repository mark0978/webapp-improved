# -*- coding: utf-8 -*-
"""
    webapp2_extras.sessions_ndb
    ===========================

    Extended sessions stored in datastore using the ndb library.

    :copyright: 2011 by tipfy.org.
    :license: Apache Sotware License, see LICENSE for details.
"""
import pickle

from google.appengine.api import datastore_errors
from google.appengine.api import memcache

from ndb import model

from webapp2_extras import sessions


class _PickledDictProperty(model.BlobProperty):
    _indexed = False

    def _validate(self, value):
        if not isinstance(value, dict):
            raise datastore_errors.BadValueError(
                'Expected dict, got %r' % value)

        return value

    def _db_set_value(self, v, p, value):
        assert isinstance(value, dict), (self._name)
        super(self.__class__, self)._db_set_value(v, p, pickle.dumps(value))

    def _db_get_value(self, v, p):
        if not v.has_stringvalue():
            return None

        return pickle.loads(v.stringvalue())


class Session(model.Model):
    """A model to store session data."""

    #: Save time.
    updated = model.DateTimeProperty(auto_now=True)
    #: Session data, pickled.
    data = _PickledDictProperty()

    @classmethod
    def get_by_sid(cls, sid):
        """Returns a ``Session`` instance by session id.

        :param sid:
            A session id.
        :returns:
            An existing ``Session`` entity.
        """
        data = memcache.get(sid)
        if not data:
            session = model.Key(cls, sid).get()
            if session:
                data = session.data
                memcache.set(sid, data)

        return data

    def _put(self):
        """Saves the session and updates the memcache entry."""
        memcache.set(self._key.id(), self.data)
        super(self.__class__, self).put()


class DatastoreSessionFactory(sessions.CustomBackendSessionFactory):
    """A session factory that stores data serialized in datastore.

    To use datastore sessions, pass this class as the `factory` keyword to
    :meth:`webapp2_extras.sessions.SessionStore.get_session`::

        from webapp2_extras import sessions_ndb

        # [...]

        session = self.session_store.get_session(
            name='db_session', factory=sessions_ndb.DatastoreSessionFactory)

    See in :meth:`webapp2_extras.sessions.SessionStore` an example of how to
    make sessions available in a :class:`webapp2.RequestHandler`.
    """

    def _get_by_sid(self, sid):
        """Returns a session given a session id."""
        if self._is_valid_sid(sid):
            data = Session.get_by_sid(sid)
            if data is not None:
                self.sid = sid
                return sessions.SessionDict(self, data=data)

        self.sid = self._get_new_sid()
        return sessions.SessionDict(self, new=True)

    def save_session(self, response):
        if self.session is None or not self.session.modified:
            return

        Session(id=self.sid, data=dict(self.session))._put()
        self.session_store.save_secure_cookie(
            response, self.name, {'_sid': self.sid}, **self.session_args)
