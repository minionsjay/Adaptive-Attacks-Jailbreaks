# 网络不通：用 git 把项目传到 V100 机器

> 两台机器网络隔离时，用你自己的 git 服务（GitHub / Gitee / 公司 GitLab）中转。
>
> **config.yaml 和 remote/models.env 是"机器本地配置"，git 不跟踪**（仓库只存
> `.example` 模板）——你在这边随便改端口/模型路径，`git pull` 永远不会冲突、
> 也永远不会覆盖你的配置。

## 场景 A：V100 机器首次克隆

```bash
git clone git@github.com:minionsjay/Adaptive-Attacks-Jailbreaks.git ~/ams-redteam
cd ~/ams-redteam
cp config.yaml.example config.yaml        # 生成本地配置（要改端口/模型名就编辑它）
cp remote/models.env.example remote/models.env   # 可选：配置模型路径/HF镜像
pip install -r requirements.txt
```

## 场景 B：老克隆（本地已改过 config.yaml / models.env）首次迁移到新结构

仓库已把这两个文件改为"不跟踪"。老克隆迁移一次，以后就和场景 C 一样省心：

```bash
cd ~/ams-redteam
# 1. 备份你改过的配置
cp config.yaml /tmp/my_config.yaml
cp remote/models.env /tmp/my_models.env

# 2. 丢弃这两个文件的本地改动（让 pull 能干净执行）
git checkout -- config.yaml remote/models.env

# 3. 拉取（上游会把这两个文件从仓库移除——磁盘上会暂时消失，正常）
git pull

# 4. 恢复你的配置；从此它们不被 git 跟踪，以后 pull 永不冲突
cp /tmp/my_config.yaml config.yaml
cp /tmp/my_models.env remote/models.env

# 5. 验证
git status        # 应显示 working tree clean（你的配置不再是"改动"）
```

## 场景 C：日常更新代码（迁移后就是这两条）

```bash
# 开发电脑:  git add -A && git commit -m "..." && git push
# V100:      cd ~/ams-redteam && git pull
```

你的 config.yaml / models.env 不受任何影响。

## 万一改了别的被跟踪的文件想临时保存

```bash
git stash        # 临时收起本地改动
git pull
git stash pop    # 放回来（若冲突会提示，手动编辑 <<<< 标记处）
```

## 注意

- 建议用**私有仓库**（安全研究代码）
- 实验产物（redteam_output*/，含攻击样本）与模型文件已在 .gitignore 排除，不会入库
- 上游更新了模板（config.yaml.example / models.env.example）而想要新默认值时：
  手动对照 `diff config.yaml config.yaml.example` 挑需要的抄进来
