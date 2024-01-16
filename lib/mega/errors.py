class ValidationError(Exception):
    """
    Error in validation stage
    """
    pass


_CODE_TO_DESCRIPTIONS = {
    -1: ('EINTERNAL',
         ('An internal error has occurred. Please submit a bug report, '
          'detailing the exact circumstances in which this error occurred')),
    -2: ('EARGS', 'You have passed invalid arguments to this command'),
    -3: ('EAGAIN',
         ('(always at the request level) A temporary congestion or server '
          'malfunction prevented your request from being processed. '
          'No data was altered. Retry. Retries must be spaced with '
          'exponential backoff')),
    -4: ('ERATELIMIT',
         ('You have exceeded your command weight per time quota. Please '
          'wait a few seconds, then try again (this should never happen '
          'in sane real-life applications)')),
    -5: ('EFAILED', 'The upload failed. Please restart it from scratch'),
    -6:
    ('ETOOMANY',
     'Too many concurrent IP addresses are accessing this upload target URL'),
    -7:
    ('ERANGE', ('The upload file packet is out of range or not starting and '
                'ending on a chunk boundary')),
    -8: ('EEXPIRED',
         ('The upload target URL you are trying to access has expired. '
          'Please request a fresh one')),
    -9: ('ENOENT', 'Object (typically, node or user) not found'),
    -10: ('ECIRCULAR', 'Circular linkage attempted'),
    -11: ('EACCESS',
          'Access violation (e.g., trying to write to a read-only share)'),
    -12: ('EEXIST', 'Trying to create an object that already exists'),
    -13: ('EINCOMPLETE', 'Trying to access an incomplete resource'),
    -14: ('EKEY', 'A decryption operation failed (never returned by the API)'),
    -15: ('ESID', 'Invalid or expired user session, please relogin'),
    -16: ('EBLOCKED', 'User blocked'),
    -17: ('EOVERQUOTA', 'Request over quota'),
    -18: ('ETEMPUNAVAIL',
          'Resource temporarily not available, please try again later'),
    -19: ('ETOOMANYCONNECTIONS', 'many connections on this resource'),
    -20: ('EWRITE', 'Write failed'),
    -21: ('EREAD', 'Read failed'),
    -22: ('EAPPKEY', 'Invalid application key; request not processed'),
}


class RequestError(Exception):
    """
    Error in API request
    """
    def __init__(self, message):
        code = message
        self.code = code
        code_desc, long_desc = _CODE_TO_DESCRIPTIONS[code]
        self.message = f'{code_desc}, {long_desc}'

    def __str__(self):
        return self.message
