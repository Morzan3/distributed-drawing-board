import time
import ntplib


def calculate_ntp_offset(time_offset):
    ntp_client = ntplib.NTPClient()
    while True:
        response = ntp_client.request('europe.pool.ntp.org', version=3)
        time_offset[0] = response.offset
        time.sleep(5)
