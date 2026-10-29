# 局域网服务器 Docker 定时运行

适用于支持 host 网络的 Linux Docker Engine：Horizon 与 Ollama 同在服务器上，
宿主机用户只需 Docker 和项目目录的使用权限，不需要安装 Python、uv 或宿主机定时服务。

## 迁移

将当前项目目录复制到服务器，包含未提交的源代码、`profiles/`、
`data/config.icar.json`、`data/vmc_whitelist.json`、`data/subscribers.json` 和 `.env`。
排除 `.venv/`，运行环境在镜像中重新安装。仅克隆远程仓库不会带上未提交代码或被 Git 忽略的配置和订阅者。

服务器需要可用的 `docker compose`。以下命令均在服务器项目根目录运行。

## 配置

将 `data/config.icar.json` 的 `ai.base_url` 设置为
`http://127.0.0.1:11434/v1`，模型名称保持与 Ollama 已安装模型一致。
本配置使用 `network_mode: host`，所以此地址指向服务器上的 Ollama。
Horizon 不加载模型到自身进程，不需要给容器分配 GPU。

检查 Ollama：

```bash
curl --noproxy '*' http://127.0.0.1:11434/api/tags
```

在 `.env` 中增加 `HORIZON_UID`、`HORIZON_GID`，值分别为服务器运行用户的
`id -u`、`id -g` 输出。例如：

```dotenv
HORIZON_UID=1000
HORIZON_GID=1000
```

容器以该 UID/GID 写入挂载目录，避免生成当前用户无法管理的文件。
`.env` 通过只读文件挂载，由应用加载，密钥不会写入镜像。
Compose 的 `NO_PROXY` 配置保证本机 Ollama 不经过代理。
如果需要外网代理，在 `.env` 中设置服务器实际可用的代理地址，不能沿用仅在原电脑运行的代理。
HTTP 或混合代理端口可用 `http://`，SOCKS5 端口用 `socks5://`，不要使用不受支持的 `socks://`。

## 构建和检查

```bash
mkdir -p data/summaries data/diagnostics docs/_posts
docker compose -f docker-compose.scheduler.yml config --quiet
docker compose -f docker-compose.scheduler.yml build
docker compose -f docker-compose.scheduler.yml run --rm horizon-scheduler -test /app/horizon.crontab
```

手动完整运行一次（启用邮件时会发送邮件，应在启动调度容器之前进行）：

```bash
docker compose -f docker-compose.scheduler.yml run --rm --entrypoint /app/.venv/bin/horizon horizon-scheduler -c /app/data/config.icar.json --hours 24
```

## 启动和运维

```bash
docker compose -f docker-compose.scheduler.yml up -d
docker compose -f docker-compose.scheduler.yml ps
docker compose -f docker-compose.scheduler.yml logs -f --tail=100
```

容器启动后等待每天北京时间 07:00，不会立即运行日报。
`restart: unless-stopped` 会在 Docker 重启后恢复未手动停止的容器；
服务器启动后 Docker 自身也需要自动运行。关闭 SSH 不影响容器。
调度器在上轮任务仍运行时不会启动同一任务的并行副本，手工另起容器不受此保护。
任务失败会记入日志，调度器继续等待下次计划，不自动重试发送邮件。
容器停止或服务器关机期间错过的任务不会在恢复后补跑，可按需手动执行。
07:00 是开始时间，邮件在本轮处理完成后发出。
当前应用使用 UTC 日期命名日报，北京时间 07:00 对应前一天 23:00 UTC，
因此文件名和日报标题日期可能为前一天；设置容器时区不会改变应用中显式使用的 UTC 日期。

输出保存在宿主机 `data/summaries/`、`data/diagnostics/` 和 `docs/_posts/`。
修改 `.env` 或提示词后，下一轮应用启动时会重新读取；
修改 JSON 配置可能同时修改了模型、订阅等行为，应先验证配置。
修改调度时间时编辑 `docker/horizon.crontab`（例如 `0 8 * * *` 为早上 8 点），然后运行：

```bash
docker compose -f docker-compose.scheduler.yml restart
```

更新源代码后重新构建：

```bash
docker compose -f docker-compose.scheduler.yml up -d --build
```

停止容器和定时任务（挂载的数据保留）：

```bash
docker compose -f docker-compose.scheduler.yml down
```

原来的 `docker-compose.yml` 继续用于单次运行，本方案使用单独的 Compose 文件。

参考：[Supercronic](https://github.com/aptible/supercronic)、
[Docker Compose services](https://docs.docker.com/reference/compose-file/services/)。
