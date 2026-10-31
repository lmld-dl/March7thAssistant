# 常见配置修改

配置文件是安装目录的 `config.yaml`。**每个键的含义、可选值都写在 `assets/config/config.example.yaml` 同名键的注释里**，
改之前先读那里；这里只列最常被问到的几类。只改需要改的键，保持 YAML 缩进，改完可以重新读一遍确认格式正确。

## 体力计划（清体力刷什么）

```yaml
power_plan:                      # 按顺序执行，每项为 [副本类型, 副本名称, 剩余次数]
  - ["拟造花萼（金）", "回忆之蕾", 10]
  - ["侵蚀隧洞", "睿治之径", 5]
power_plan_keep: false           # false：按剩余次数更新、完成后删除；true：每次执行后保留整份计划
```

- 副本类型：`拟造花萼（金）`、`拟造花萼（赤）`、`凝滞虚影`、`侵蚀隧洞`、`饰品提取`。
- 副本名称必须与 `assets/config/instance_names.json` 中的名称完全一致（该文件也写明了每个副本掉落什么）。
  用户说「刷角色经验」「刷 XX 的突破材料」时，先在这个文件里找到对应副本名，不确定就问。
- 计划为空时，清体力使用 `instance_type` 与 `instance_names`（每种副本类型的默认副本）；`instance_names_challenge_count` 是每次连续挑战次数。
- `power_enable: false` 会让完整运行与「日常」跳过清体力，单独运行 `power` 不受影响。

## 定时任务（由图形界面执行）

```yaml
scheduled_tasks:
  - id: "3f0c2b9e-6a8d-4f1e-9c7a-2b5d8e1f4a60"   # 唯一 ID，新增时生成一个新的 UUID
    name: "每日完整运行"
    time: "04:30"                # HH:mm，24 小时制
    weekdays: [1, 3, 5]          # 1=周一 … 7=周日；省略表示每天
    program: "self"              # self 表示运行小助手自己的任务
    args: "main"                 # 任务 ID
    timeout: 0                   # 超时秒数，0 表示不限制
    notify: false
    post_action: "None"          # 完成后操作，与 after_finish 相同；不要擅自设成关机
    kill_processes: []           # 完成后要结束的进程，例如 ["StarRail.exe"]
    enabled: true
```

- 只有图形界面运行时（包括最小化到托盘）定时任务才会触发；提醒用户保持图形界面运行，或开启开机自启（图形界面「设置 → 杂项」）。
- 新增时保留已有项与它们的 `id`；`scheduled_on_conflict` 决定触发时已有任务在运行怎么办（`skip` 跳过 / `stop` 停止正在运行的任务）。
## 完成后操作

`after_finish`：`None`、`Exit`、`Loop`（循环运行，按 `loop_mode` 等待下一轮）、`Shutdown`、`Sleep`、`Hibernate`、`Restart`、`Logoff`、`TurnOffDisplay`、`RunScript`。
只是本次运行不想关机时，用命令行参数 `--after-finish None`，不要改配置。

## 消息推送

- 精简客户端只保留 Windows 原生通知：总开关 `notification_enable`，开关 `notify_winotify_enable`。
- 图形界面「设置 → 推送」里可以发送一条测试通知。

## 日常与周常

- 每日实训、奖励领取、活动等开关分别在「日常任务设置」「奖励领取设置」「活动设置」几段（`daily_*`、`reward_*`、`activity_*`）。
- 差分宇宙 `weekly_divergent_*` / `divergent_*`，货币战争 `currencywars_*`，历战余响 `echo_of_war_*`。
- 游戏本体更新用任务 `game_update` / `game_pre_download`（通过启动器），不是小助手自更新。
