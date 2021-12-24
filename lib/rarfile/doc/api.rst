
rarfile API documentation
=========================

.. contents:: Table Of Contents

Introduction
------------

.. automodule:: rarfile

RarFile class
-------------

.. autoclass:: RarFile
   :members:
   :special-members: __enter__, __exit__, __iter__

RarInfo class
-------------

.. autoclass:: RarInfo
   :members:

RarExtFile class
----------------

.. autoclass:: RarExtFile
   :show-inheritance:
   :members:
   :inherited-members:
   :exclude-members: truncate, flush

nsdatetime class
----------------

.. autoclass:: nsdatetime
   :show-inheritance:
   :members:

Functions
---------

.. autofunction:: is_rarfile
.. autofunction:: is_rarfile_sfx

Constants
---------

.. autodata:: RAR_M0
.. autodata:: RAR_M1
.. autodata:: RAR_M2
.. autodata:: RAR_M3
.. autodata:: RAR_M4
.. autodata:: RAR_M5

.. autodata:: RAR_OS_WIN32
.. autodata:: RAR_OS_UNIX
.. autodata:: RAR_OS_MACOS
.. autodata:: RAR_OS_BEOS
.. autodata:: RAR_OS_OS2
.. autodata:: RAR_OS_MSDOS

Warnings
--------

.. autoclass:: UnsupportedWarning

Exceptions
----------

.. autoclass:: Error
.. autoclass:: BadRarFile
.. autoclass:: NotRarFile
.. autoclass:: BadRarName
.. autoclass:: NoRarEntry
.. autoclass:: PasswordRequired
.. autoclass:: NeedFirstVolume
.. autoclass:: NoCrypto
.. autoclass:: RarExecError
.. autoclass:: RarWarning
.. autoclass:: RarFatalError
.. autoclass:: RarCRCError
.. autoclass:: RarLockedArchiveError
.. autoclass:: RarWriteError
.. autoclass:: RarOpenError
.. autoclass:: RarUserError
.. autoclass:: RarMemoryError
.. autoclass:: RarCreateError
.. autoclass:: RarNoFilesError
.. autoclass:: RarUserBreak
.. autoclass:: RarWrongPassword
.. autoclass:: RarUnknownError
.. autoclass:: RarSignalExit
.. autoclass:: RarCannotExec


