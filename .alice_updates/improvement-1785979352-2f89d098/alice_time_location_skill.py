import datetime
import pytz
class TimeAndLocation:
    def __init__(self):
        self.timezone = pytz.timezone('UTC')

    def get_current_time(self):
        return datetime.datetime.now(self.timezone)

    def get_current_location(self, provider=None):
        if provider is None:
            return {'status': 'unavailable'}
        else:
            # Assuming provider is a string or object with location info
            return {'location': provider}

if __name__ == '__main__':
    time_and_location = TimeAndLocation()
    print(time_and_location.get_current_time())
    print(time_and_location.get_current_location('New York'))