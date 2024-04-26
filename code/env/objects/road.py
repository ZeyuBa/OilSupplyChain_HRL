class Road(object):
    def __init__(self, config, cap_transports):
        self.key = config['from_code']+'-'+config['to_code']
        self.start = config['from_code']
        self.end = config['to_code']
        self.cap_transports = cap_transports
        self.material = config['material_code']
        self.mode = config['mode_code']
        self.cost = config['cost']
