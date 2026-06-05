# cron-service

Cron and scheduling service package for the Kairon monorepo.

It provides packaged service metadata for scheduled task execution and runtime integration.

## Runtime entrypoints

- CLI / MCP entrypoint: `cron-service`
- Local start script: [`scripts/start-cron-service.sh`](/Users/xiamingxing/Workspace/projects/kairon/packages/cron-service/scripts/start-cron-service.sh)

## Runtime state

- Config SSOT: `~/.cron-service/config.yaml`
- Logs / ephemeral state: `~/.cron-service/`

Package-local runtime output should not be committed back into the repo.
