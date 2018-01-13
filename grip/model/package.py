class Package(object):
    def __init__(self, req):
        self.req = req
        self.dependencies = []
