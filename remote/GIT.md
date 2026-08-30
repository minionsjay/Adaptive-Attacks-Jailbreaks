# 网络不通：用 git 把项目传到 V100 机器

> 两台机器网络隔离时，用你自己的 git 服务（GitHub / Gitee / 公司 GitLab）中转。
> 项目仓库已初始化好（含 .gitignore，实验产物和模型文件不会入库）。

## 开发电脑（这台）：推送

```bash
cd /home/ninini/DeepSeek_Harness/最新AI安全论文相关/redteam

# 首次传（仓库已 init + commit 好，直接加远端推即可）：
git remote add origin <你的git地址>     # 例: git@github.com:你/ams-redteam.git
git push -u origin main

# 以后每次改完代码：
git add -A && git commit -m "说明" && git push
```

⚠️ 建议用**私有仓库**（安全研究代码）。
.gitignore 已排除：`redteam_output*/`（含攻击样本）、`*.gguf`、`__pycache__`。

## V100 机器：拉取 + 装依赖

```bash
git clone <你的git地址> ~/ams-redteam
cd ~/ams-redteam
pip install -r requirements.txt        # 唯一需要装的（你说环境已配好，这步补齐 runner 依赖）
```

## 更新代码

```bash
# 开发电脑: git add -A && git commit -m "..." && git push
# V100:     cd ~/ams-redteam && git pull
```
