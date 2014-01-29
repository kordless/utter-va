from webapp import db
from webapp.mixins import CRUDMixin

# instances object
class Instances(CRUDMixin, db.Model):
    __tablename__ = 'instances'
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.Integer)
    updated = db.Column(db.Integer) 
    expires = db.Column(db.Integer)
    osflavorid = db.Column(db.String(100))
    osimageid = db.Column(db.String(100))
    publicip = db.Column(db.String(100))
    ssltunnel = db.Column(db.String(400))
    osinstanceid = db.Column(db.String(100))
    name = db.Column(db.String(100))
    
    state = db.Column(db.Integer) 
    # instance state is one of:
    # 0 - inactive, no payment address available
    # 1 - payment address available
    # 2 - payment observed from blockchain callback
    # 3 - instance running
    # 4 - instance halted
    # 5 - instance decommissioned
    
    token = db.Column(db.String(100))
    secret = db.Column(db.String(100))
    confirmations = db.Column(db.Integer)
    callbackurl = db.Column(db.String(400))
    feepercent =db.Column(db.Float)
    destination = db.Column(db.String(100))
    inputaddress = db.Column(db.String(100))
    transactionhash = db.Column(db.String(100))

    def __init__(self, 
        created=None,
        updated=None,
        expires=None,
        osflavorid=None,
        osimageid=None,
        publicip=None,
        ssltunnel=None,
        osinstanceid=None,
        name=None,
        state=None,
        token=None,
        secret=None,
        confirmations=None,
        callbackurl=None,
        feepercent=None,
        destination=None,
        inputaddress=None,
        transactionhash=None
    ):
        self.created = created
        self.updated = updated
        self.expires = expires
        self.osflavorid = osflavorid
        self.osimageid = osimageid
        self.publicip = publicip
        self.ssltunnel = ssltunnel
        self.osinstanceid = osinstanceid
        self.name = name
        self.state = state
        self.token = token
        self.secret = secret
        self.confirmations = confirmations
        self.callbackurl = callbackurl
        self.feepercent = feepercent
        self.destination = destination
        self.inputaddress = inputaddress
        self.transactionhash = transactionhash

    def __repr__(self):
        return '<Address %r>' % (self.name)

# images object
class Images(CRUDMixin,  db.Model):
    __tablename__ = 'images'
    id = db.Column(db.Integer, primary_key=True)
    osid = db.Column(db.String(100))
    md5 = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(100), unique=True)
    url = db.Column(db.String(400), unique=True)
    diskformat = db.Column(db.String(100))
    containerformat = db.Column(db.String(100))
    size = db.Column(db.Integer)
    flags = db.Column(db.Integer)
    active = db.Column(db.Integer) # 0 - not active, 1 - installing, 2 - active

    def __init__(self, osid=None, md5=None, name=None, url=None, size=None, diskformat=None, containerformat=None, flags=None):
        self.osid = osid
        self.md5 = md5
        self.name = name
        self.url = url
        self.size = size
        self.diskformat = diskformat
        self.containerformat = containerformat
        self.flags = flags
    
    def __repr__(self):
        return '<Image %r>' % (self.name)

    def sync(self, remoteimages=None):
        # update database for images
        for remoteimage in remoteimages['images']:
            image = db.session.query(Images).filter_by(md5=remoteimage['md5']).first()
            
            if image is None:
                # we don't have the image coming in from the server
                image = Images()

                # need help here populating db object from dict - anyone?
                image.md5 = remoteimage['md5']
                image.name = remoteimage['name']
                image.url = remoteimage['url']
                image.size = remoteimage['size']
                image.diskformat = remoteimage['diskformat']
                image.containerformat = remoteimage['containerformat']
                image.active = 0
                image.flags = remoteimage['flags']

                # add and commit
                db.session.add(image)
                db.session.commit()
            else:
                # we have the image already, so update
                
                # check if we need to delete image from local db
                if remoteimage['flags'] == 9:
                    image.delete(image)
                    db.session.commit()
                    continue

                # need help here populating db object from dict - anyone?
                image.md5 = remoteimage['md5']
                image.name = remoteimage['name']
                image.url = remoteimage['url']
                image.size = remoteimage['size']
                image.diskformat = remoteimage['diskformat']
                image.containerformat = remoteimage['containerformat']
                image.flags = remoteimage['flags']
                
                # udpate and commit
                image.update(image)
                db.session.commit()


# flavors object
class Flavors(CRUDMixin,  db.Model):
    __tablename__ = 'flavors'
    id = db.Column(db.Integer, primary_key=True)
    osid = db.Column(db.String(100))
    name = db.Column(db.String(100), unique=True)
    comment = db.Column(db.String(200), unique=True)
    vpu = db.Column(db.Integer)
    mem = db.Column(db.Integer)
    disk = db.Column(db.Integer)
    flags = db.Column(db.Integer)
    active = db.Column(db.Integer)

    def __init__(self, name=None, osid=None, comment=None, vpu=None, mem=None, disk=None, flags=None, active=None):
        self.name = name
        self.osid = osid
        self.comment = comment
        self.vpu = vpu
        self.mem = mem
        self.disk = disk
        self.flags = flags
        self.active = active

    def __repr__(self):
        return '<Flavor %r>' % (self.name)

    def sync(self, remoteflavors=None):
        # update the database with the flavors
        for remoteflavor in remoteflavors['flavors']:
            flavor = db.session.query(Flavors).filter_by(name=remoteflavor['name']).first()
            if flavor is None:
                # we don't have the flavor coming in from the server
                flavor = Flavors()

                # need help here populating db object from dict - anyone?
                flavor.name = remoteflavor['name']
                flavor.comment = remoteflavor['comment']
                flavor.vpu = remoteflavor['vpu']
                flavor.mem = remoteflavor['mem']
                flavor.disk = remoteflavor['disk']
                flavor.flags = remoteflavor['flags']
                flavor.active = 0

                # add and commit
                db.session.add(flavor)
                db.session.commit()
            else:
                # we have the flavor already, so update

                # check if we need to delete image from local db
                if remoteflavor['flags'] == 9:
                    flavor.delete(flavor)
                    db.session.commit()
                    continue

                # need help here populating db object from dict - anyone?
                flavor.name = remoteflavor['name']
                flavor.comment = remoteflavor['comment']
                flavor.vpu = remoteflavor['vpu']
                flavor.mem = remoteflavor['mem']
                flavor.disk = remoteflavor['disk']
                flavor.flags = remoteflavor['flags']
                
                # udpate and commit
                flavor.update(flavor)
                db.session.commit()