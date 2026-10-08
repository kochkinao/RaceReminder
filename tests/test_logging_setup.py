import io
import logging

import pytest

from utils.logging_setup import AdminAlertHandler


def test_polling_connection_reset_stays_in_logs_but_not_admin_alerts():
    stream = io.StringIO()
    console = logging.StreamHandler(stream)
    admin = AdminAlertHandler({42})
    logger = logging.getLogger('aiogram.dispatcher')
    old_handlers, old_level, old_propagate = logger.handlers[:], logger.level, logger.propagate
    try:
        logger.handlers = [console, admin]
        logger.setLevel(logging.ERROR)
        logger.propagate = False
        logger.error(
            'Failed to fetch updates - %s: %s',
            'TelegramNetworkError',
            'HTTP Client says - ClientOSError: [Errno 104] Connection reset by peer',
        )
        assert 'Connection reset by peer' in stream.getvalue()
        assert len(admin._queue) == 0
    finally:
        logger.handlers, logger.level, logger.propagate = old_handlers, old_level, old_propagate
        console.close()
        admin.close()


@pytest.mark.parametrize('name,level,message', [
    ('aiogram.dispatcher', logging.ERROR,
     'Failed to fetch updates - TelegramNetworkError: HTTP Client says - Request timeout error'),
    ('aiogram.dispatcher', logging.ERROR,
     'Failed to fetch updates - TelegramNetworkError: Cannot connect to host api.telegram.org:443 [Temporary failure in name resolution]'),
    ('aiogram.dispatcher', logging.ERROR,
     'Failed to fetch updates - TelegramConflictError: terminated by other getUpdates request'),
    ('aiogram.dispatcher', logging.ERROR,
     'Failed to fetch updates - TelegramUnauthorizedError: Unauthorized'),
    ('aiogram.dispatcher', logging.ERROR,
     'Failed to fetch updates - TelegramServerError: Bad Gateway'),
    ('scheduler', logging.ERROR, 'Connection reset by peer'),
    ('aiogram.event', logging.ERROR,
     'Failed to fetch updates - TelegramNetworkError: Connection reset by peer'),
    ('aiogram.dispatcher', logging.ERROR,
     'Message delivery failed - TelegramNetworkError: Connection reset by peer'),
    ('aiogram.dispatcher', logging.CRITICAL,
     'Failed to fetch updates - TelegramNetworkError: Connection reset by peer'),
])
def test_other_errors_still_reach_admin_alerts(name, level, message):
    admin = AdminAlertHandler({42})
    try:
        admin.handle(logging.LogRecord(name, level, __file__, 0, message, (), None))
        assert len(admin._queue) == 1
    finally:
        admin.close()


def test_connector_reset_during_polling_is_also_silent():
    admin = AdminAlertHandler({42})
    try:
        admin.handle(logging.LogRecord(
            'aiogram.dispatcher', logging.ERROR, __file__, 0,
            'Failed to fetch updates - TelegramNetworkError: HTTP Client says - ClientConnectorError: Cannot connect to host api.telegram.org:443 ssl:default [Connection reset by peer]',
            (), None,
        ))
        assert len(admin._queue) == 0
    finally:
        admin.close()
