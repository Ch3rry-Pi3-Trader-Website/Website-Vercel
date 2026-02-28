class BrokerAdapter:
    def place_order(self, *args, **kwargs):
        raise NotImplementedError

    def cancel_order(self, *args, **kwargs):
        raise NotImplementedError

    def get_positions(self):
        raise NotImplementedError
