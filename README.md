# 星芽网站自动签到

自动签到脚本，每天 00:20 (北京时间) 自动执行。

## 账号列表

脚本内置5个账号：
- 3312423979@qq.com
- rensk66@qq.com
- 3470884203@qq.com
- 3181227118@qq.com
- 2560492318@qq.com

## 工作流程

1. 每天 UTC 16:20 (北京时间 00:20) 自动执行
2. 依次登录5个账号
3. 执行签到并记录结果
4. GitHub Actions 日志中可查看签到详情

## 手动触发

在 GitHub Actions 页面点击 "Run workflow" 按钮可手动触发。

## API 接口

- 登录: `POST /api/user/login`
- 签到: `POST /api/user/checkin`
