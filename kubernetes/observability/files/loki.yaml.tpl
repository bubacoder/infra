auth_enabled: false
server:
  http_listen_port: 3100
  grpc_listen_port: 9095
common:
  instance_addr: 127.0.0.1
  path_prefix: /data
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory
  storage:
    filesystem:
      chunks_directory: /data/chunks
      rules_directory: /data/rules
schema_config:
  configs:
    - from: "2026-01-01"
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h
storage_config:
  tsdb_shipper:
    active_index_directory: /data/index
    cache_location: /data/index-cache
ingester:
  wal:
    enabled: true
    dir: /data/wal
  chunk_idle_period: 5m
compactor:
  working_directory: /data/compactor
  compaction_interval: 10m
  retention_enabled: true
  retention_delete_delay: 2h
  retention_delete_worker_count: 10
  delete_request_store: filesystem
limits_config:
  retention_period: {{ .Values.loki.retention }}
  allow_structured_metadata: true
  volume_enabled: true
  ingestion_rate_mb: 2
  ingestion_burst_size_mb: 4
  max_query_parallelism: 2
  max_query_length: 24h
  max_entries_limit_per_query: 500
  query_timeout: 30s
query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: false
analytics:
  reporting_enabled: false
