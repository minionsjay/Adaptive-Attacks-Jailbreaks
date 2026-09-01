# 外挂词库目录（本地文件，不入库）

把你的平台词库放进来，keyword-baseline 自动加载：

- 文件名：`extra_<类别>.txt`（类别如 gambling/porn/fraud/drugs/weapons/political/…）
- 格式：每行一个词；`#` 开头为注释
- 生效：重启 serve_detector.py 即可，命中按类别权重 0.85 计分

例：`extra_political.txt`、`extra_platform_grey.txt`（自己平台积累的灰产词）
