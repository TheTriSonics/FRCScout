"""Where the history database lives.

In Azure the database is a blob (container "history", blob "history.duckdb"
in the app's own storage account). Each instance downloads it to local temp
storage on first use and checks the blob's ETag again every few minutes, so
a refresh reaches running instances without a restart. Locally, without
AzureWebJobsStorage, history/data/history.duckdb is used as is. The data the
database is built from is kept in SOURCE_CONTAINER.
"""
import logging
import os
import tempfile
import threading
import time
from pathlib import Path

CONTAINER = os.environ.get('HISTORY_CONTAINER', 'history')
# The lake's source, so a rebuild never needs one machine's cache:
# raw/<source>/<kind>/<year>/<file>.json.gz (sync.py's cached responses, same paths as
# history/data/raw/, see sync.name) and lake/<table>.parquet.
SOURCE_CONTAINER = os.environ.get('HISTORY_SOURCE_CONTAINER', 'history-source')
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


def get_lake(to: Path):
    """history-source lake/*.parquet into the folder [to] (for a refresh to start from)."""
    from azure.storage.blob import ContainerClient
    container = ContainerClient.from_connection_string(_conn(), SOURCE_CONTAINER)
    to.mkdir(parents=True, exist_ok=True)
    for b in container.list_blobs(name_starts_with='lake/'):
        if b.name.endswith('.parquet'):
            with open(to / Path(b.name).name, 'wb') as f:
                container.download_blob(b.name, max_concurrency=4).readinto(f)
    return to


def upload(path: Path):
    from azure.storage.blob import ContainerClient
    container = ContainerClient.from_connection_string(_conn(), CONTAINER)
    if not container.exists():
        container.create_container()
    with open(path, 'rb') as f:
        container.upload_blob(BLOB, f, overwrite=True, max_concurrency=4)


def put_source(items):
    """Upload (blob name, bytes or local Path) pairs to the source container."""
    from azure.storage.blob import ContainerClient
    container = ContainerClient.from_connection_string(_conn(), SOURCE_CONTAINER)
    if not container.exists():
        container.create_container()
    n = 0
    for blob, data in items:
        if isinstance(data, Path):
            with open(data, 'rb') as f:
                container.upload_blob(blob, f, overwrite=True, max_concurrency=4)
        else:
            container.upload_blob(blob, data, overwrite=True)
        n += 1
    return n

