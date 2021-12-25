# -*- coding: latin-1 -*-
#
# Copyright (C) Martin Sjögren and AB Strakt 2001, All rights reserved
# Copyright (C) Jean-Paul Calderone 2008, All rights reserved
# This file is licenced under the GNU LESSER GENERAL PUBLIC LICENSE Version 2.1 or later (aka LGPL v2.1)
# Please see LGPL2.1.txt for more information
"""
Certificate generation module.
"""

import time
from OpenSSL import crypto


TYPE_RSA = crypto.TYPE_RSA
TYPE_DSA = crypto.TYPE_DSA

serial = int(time.time())


def createKeyPair(type, bits):
    """
    Create a public/private key pair.

    Arguments: type - Key type, must be one of TYPE_RSA and TYPE_DSA
               bits - Number of bits to use in the key
    Returns:   The public/private key pair in a PKey object
    """
    pkey = crypto.PKey()
    pkey.generate_key(type, bits)
    return pkey

def createCertRequest(pkey, digest="md5", **name):
    """
    Create a certificate request.

    Arguments: pkey   - The key to associate with the request
               digest - Digestion method to use for signing, default is md5
               **name - The name of the subject of the request, possible
                        arguments are:
                          C     - Country name
                          ST    - State or province name
                          L     - Locality name
                          O     - Organization name
                          OU    - Organizational unit name
                          CN    - Common name
                          emailAddress - E-mail address
    Returns:   The certificate request in an X509Req object
    """
    req = crypto.X509Req()
    subj = req.get_subject()

    for (key,value) in name.items():
        setattr(subj, key, value)

    req.set_pubkey(pkey)
    req.sign(pkey, digest)
    return req

def createCertificate(req, iss_cert_key, serial, before_after, digest="md5"):
    """
    Generate a certificate given a certificate request.

    Arguments: req          - Certificate reqeust to use
               iss_cert_key - A tuple containing these two vars:
                              1. The certificate of the issuer
                              2. The private key of the issuer
               serial       - Serial number for the certificate
               before_after - A Tuple containing these two vars:
                              1. Timestamp (relative to now) when the certificate
                                 starts being valid
                              2. Timestamp (relative to now) when the certificate
                                 stops being valid
               digest       - Digest method to use for signing, default is md5
    Returns:   The signed certificate in an X509 object
    """
    issuerCert, issuerKey = iss_cert_key
    notBefore, notAfter = before_after
    cert = crypto.X509()
    cert.set_serial_number(serial)
    cert.gmtime_adj_notBefore(notBefore)
    cert.gmtime_adj_notAfter(notAfter)
    cert.set_issuer(issuerCert.get_subject())
    cert.set_subject(req.get_subject())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(issuerKey, digest)
    return cert
