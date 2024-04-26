class capTransport(object):
    def __init__(self, config):
        self.key = config['cap_code']
        self.capacity = config['transport_capacity']

        self.total_receive_cap = 0  # M
        self.receive_cap = 0  # D
        self.road_quantities = {}  # {'road_code': xx, 'road_code': xx}

    def update_receive_cap(self, quantity):
        self.total_receive_cap += quantity
        self.receive_cap += quantity
