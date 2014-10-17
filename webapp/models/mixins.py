from webapp import db

class CRUDMixin(object):
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)

    # keep a list of properties that have changed, so we know if
    # something needs to be synced to the OpenStack cluster or to
    # the pool when save is called
    _changed_properties = set()

    @classmethod
    def get(cls):
        return cls.query.first()
        
    @classmethod 
    def get_all(cls):
        return cls.query.all()
        
    @classmethod
    def get_by_id(cls, id):
        if any(
            (isinstance(id, basestring) and id.isdigit(),
             isinstance(id, (int, float))),
        ):
            return cls.query.get(int(id))
        return None

    @classmethod
    def create(cls, **kwargs):
        instance = cls(**kwargs)
        return instance.save()

    def __setattr__(self, key, value):
      # remember properties that are being changed
      self._changed_properties.add(key)
      super(CRUDMixin, self).__setattr__(key, value)

    # hooks that should be called when properties are being updated,
    # by default there are none, this is supposed to be overriden
    def _get_sync_hooks(self):
      return {}

    # check for properties that have hooks to sync on change and call hooks
    def call_property_hooks(self):
      hooks = self._get_sync_hooks()
      properties = self._changed_properties.copy()
      for prop in properties:
        if prop in hooks.keys():
          # call sync hook for changed property
          hooks[prop]()

    def update(self, commit=True, **kwargs):
      for attr, value in kwargs.iteritems():
          setattr(self, attr, value)
      return commit and self.save() or self

    def save(self, commit=True, ignore_hooks=False):
      db.session.add(self)
      if commit:
        if not ignore_hooks:
          self.call_property_hooks()
          # reset the _changed_properties if syncing has been completed
        self._changed_properties = set()
        db.session.commit()
      return self

    def delete(self, commit=True):
        db.session.delete(self)
        return commit and db.session.commit()
