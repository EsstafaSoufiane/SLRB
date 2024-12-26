import multiprocessing

# Worker settings
workers = 1  # Single worker to handle requests
worker_class = 'sync'  # Synchronous worker
threads = 4  # Number of threads per worker
worker_connections = 1000

# Timeouts
timeout = 300  # 5 minutes
keepalive = 2

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# SSL
keyfile = None
certfile = None

# Server socket
bind = "0.0.0.0:$PORT"
backlog = 2048

# Process naming
proc_name = None

# Default SSL options
ssl_version = None
cert_reqs = None
ca_certs = None
suppress_ragged_eofs = True
do_handshake_on_connect = False

# Debugging
reload = False
reload_engine = 'auto'
spew = False
check_config = False
