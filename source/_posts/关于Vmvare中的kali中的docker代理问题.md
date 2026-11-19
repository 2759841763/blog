---
title: "关于Vmvare中的kali中的docker代理问题"
date: 2026-11-19 00:00:00
categories:
  - 杂记
---

# 关于Vmvare中的kali中的docker代理问题

先要设置我们的 Kali 虚拟机使用的是**NAT 模式**（这也是 VMware 的默认推荐模式），Kali 和物理机通信，走的一定是 VMnet8 这个虚拟网卡。

- **这个 `192.168.162.1` 基本是固定不变的**

### 接下来你要做的：

1. **在 Kali 里测试连通性**：
   打开 Kali 终端，输入：

   bash

   ```
   curl -x http://192.168.162.1:7897 https://www.google.com -I
   ```

   

   如果返回 `HTTP/2 200`，说明完美连通。

2. **修改 Docker 代理配置**：

   bash

   ```
   sudo nano /etc/systemd/system/docker.service.d/http-proxy.conf
   ```

   

   把里面的 IP 全部改成 `192.168.162.1`：

   ini

   ```
   [Service]
   Environment="HTTP_PROXY=http://192.168.162.1:7897"
   Environment="HTTPS_PROXY=http://192.168.162.1:7897"
   Environment="NO_PROXY=localhost,127.0.0.1"
   ```

   保存并退出（`Ctrl+O` 回车，`Ctrl+X` 退出）。

3. **重启 Docker**：

   bash

   ```
   sudo systemctl daemon-reload
   sudo systemctl restart docker
   ```
