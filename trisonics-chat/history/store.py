"""Where the history database lives.

In Azure the database is a blob (container "history", blob "history.duckdb"
in the app's own storage account). Each instance downloads it to local temp
storage on first use and checks the blob's ETag again every few minutes, so
a refresh reaches running instances without a restart. Locally, without
AzureWebJobsStorage, history/data/history.duckdb is used as is.
"""
import logging
import os
import tempfile
import threading
import time
from pathlib import Path

CONTAINER = os.environ.get('HISTORY_CONTAINER', 'history')
BLOB = 'history.duckdb'
LOCAL = Path(__file__).with_name('data') / 'history.duckdb'
CHECK_EVERY = 300

_lock = threading.Lock()
_state = {'path': None, 'etag': None, 'checked': 0.0}


def _conn():
    conn = os.environ.get('AzureWebJobsStorage', '')
    return conn if conn.startswith('DefaultEndpointsProtocol') else None


def _blob():
    from azure.storage.blob import BlobClient
    return BlobClient.from_connection_string(_conn(), CONTAINER, BLOB)


def db_path():
    """Local path of the current database, or None if there isn't one."""
    if os.environ.get('HISTORY_DB'):
        return Path(os.environ['HISTORY_DB'])
    if not _conn():
        return LOCAL if LOCAL.exists() else None
    with _lock:
        if _state['path'] and time.time() - _state['checked'] < CHECK_EVERY:
            return _state['path']
        try:
            blob = _blob()
            etag = blob.get_blob_properties().etag
            if etag != _state['etag'] or not _state['path']:
                fd, tmp = tempfile.mkstemp(prefix='history-', suffix='.duckdb')
                with os.fdopen(fd, 'wb') as f:
                    blob.download_blob(max_concurrency=4).readinto(f)
                old = _state['path']
                _state.update(path=Path(tmp), etag=etag)
                if old:
                    old.unlink(missing_ok=True)  # open readers keep their handle
                logging.info('history db downloaded (%s)', etag)
        except Exception:
            logging.exception('history db download failed')
        _state['checked'] = time.time()
        return _state['path']


def download(to: Path):
    """The current blob into [to] (for a refresh to start from)."""
    with open(to, 'wb') as f:
        _blob().download_blob(max_concurrency=4).readinto(f)


def upload(path: Path):
    from azure.storage.blob import ContainerClient
    container = ContainerClient.from_connection_string(_conn(), CONTAINER)
    if not container.exists():
        container.create_container()
    with open(path, 'rb') as f:
        container.upload_blob(BLOB, f, overwrite=True, max_concurrency=4)
