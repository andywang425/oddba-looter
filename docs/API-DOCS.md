# ODDBA API DOCS

本文档用于记录 `https://sns.oddba.cn/` 的页面、接口和自动化相关观察结果。自动化脚本已在项目 `src/oddba_looter/` 中实现；本文档同时作为该脚本的接口依据。

## 文档约定

- 本文档只记录对自动化实现有帮助的信息，不追求完整站点逆向。对脚本重要的接口写在前面，不重要的放后面。可搜索 `以下是相对来说没那么重要的接口` 找到分割线。
- 除非某个接口章节另有说明，默认请求体为普通表单数据（`application/x-www-form-urlencoded;charset=UTF-8`）。
- 真实登录态、Cookie、账号信息等敏感内容不写入仓库文档。
- 章节示例里的 `request_id` 和 `timestamp` 默认使用占位值 `0123456789abcdef` 和 `1790269261`；样例中的用户 id、昵称、头像等也一律替换为虚构值。允许有例外情况，但也不使用实际抓包得到的值。构造虚构值时需确保其符合逻辑。
- 如果响应示例很长（格式化后超过 100 行），将其放入 `response` 目录中，在文档中使用 `[接口名称](response/接口名称.json)` 的方式引用。

## 全局约定

### 请求侧

- 请求重试：仅页头、签到中心初始化、任务中心初始化这三个查询接口在网络异常、HTTP 408 或 5xx 时自动重试。登录、签到和领奖不盲目重发；签到或领奖结果不确定时查询当前状态，已生效则继续，未确认则记为失败，留待下一轮执行，不在本轮再次提交。
- HTTP 429：立即结束本轮执行（退出码 `2`），不重试、不继续调用其他接口，也不为核验状态额外发送请求。
- HTTP 版本：优先使用 `HTTP/2`。
- 浏览器伪装：该网站在正常情况下主要通过浏览器访问，自动化请求应尽量模拟浏览器环境。
- 反自动化情况：站点有验证码守卫接口，前端在执行部分动作前先询问本次是否需要验证码。目前观察到的所有登录和签到均返回 `need=false`，但以后网站也许会实装验证码功能。目前脚本为了省请求刻意跳过守卫查询，直接发送空 `captcha_token`；未来实际遇到验证码问题时再调整实现。

### 响应侧

- 响应分为两类：`HTML` 或 `JSON`。本文档涉及的业务接口全部为 JSON，`content-type: application/json; charset=utf-8`。
- 业务接口响应头中的 `x-request-id` 与响应体 JSON 的 `request_id` 字段完全一致。
- JSON 信封固定为：

  | 字段         | 说明                                                  |
  | ------------ | ----------------------------------------------------- |
  | `code`       | `1` = 成功；`0` = 业务失败；`401` = 未登录/会话过期   |
  | `msg`        | 提示文案，成功时可能为空串，失败时可直接展示给用户    |
  | `data`       | 业务数据；失败时为 `null`                             |
  | `timestamp`  | 秒级时间戳                                            |
  | `request_id` | 16 位小写十六进制字符串，与响应头 `x-request-id` 一致 |
  | `error_code` | **仅失败时出现**，字符串                              |

- `HTTP 200` 不代表业务成功：业务失败、未登录都仍可能返回 `HTTP 200`，必须看 `code`。脚本先检查 HTTP 状态，再检查 JSON 信封；非 2xx 响应作为 HTTP 错误处理。
- 宝箱、每日任务条目或分组结构异常时，保留可正常解析的条目继续处理，同时累计失败，最终退出码为 `1`，不将跳过的异常条目视为成功。
- 失败响应示例：

  ```json
  {
    "code": 0,
    "msg": "今天已签到",
    "data": null,
    "timestamp": 1790269261,
    "request_id": "0123456789abcdef",
    "error_code": "business_failed"
  }
  ```

  ```json
  {
    "code": 401,
    "msg": "请先登录",
    "data": null,
    "timestamp": 1790269261,
    "request_id": "0123456789abcdef",
    "error_code": "unauthorized"
  }
  ```

## 认证与会话

### Cookie 说明

#### `lightsns_token`

- 作用：用户身份认证
- 生命周期：签发后 30 天（`exp - iat == 2592000` 秒）
- 值格式：`<base64url 编码的 JSON payload>.<64 位小写十六进制签名>`。payload 解码后为 JSON，字段为 `{"userId":123456, "iat":1790264166, "exp":1792856166, "sid":7300}`，即用户 id、签发时间、过期时间、会话 id。脚本不依赖或解码这些身份字段。
- 实现将 token 视为不透明的 Cookie 值，不限定长度、分段或签名编码；真实有效性由页头接口的 `data.is_login` 确认。
- 已验证：
  - 删除该 Cookie 后访问任意页面，登录状态失效，需重新登录
  - 删除后调用动作类接口（如 `/api/user/checkin`）返回 `code = 401`、`error_code = "unauthorized"`
- 自动化建议：可以在本地持久化存储，但不要让用户直接填写（有效期仅一个月，手动更新太麻烦），缺失或过期后应通过登录接口获取。

#### `lightsns_visitor_id`

- 作用：不清楚
- 生命周期：目前观察为一年
- 值格式：32 位数字 + 小写字母组成的 hash
- 已验证：
  - 删除该 Cookie 后，访问下一个页面时服务端会重新设置，Cookie 值与先前的不同
- 自动化建议：无需在本地持久化存储，访问第一个接口拿到该 Cookie 后，后续请求带上即可

#### `server_session_<8位数字+小写字母组成的hash>`

- 作用：不清楚
- 生命周期：目前观察为 10 天
- 值格式：32 位数字 + 小写字母组成的 hash
- 已验证：
  - 删除该 Cookie 后访问任意页面，服务端会重新设置该 Cookie，Cookie 名称和值与先前的均相同
- 自动化建议：无需在本地持久化存储，访问第一个接口拿到该 Cookie 后，后续请求带上即可

## 接口详情

网站接口可分为两类：

- `/api/*`：全站业务接口
- `/module/<平台>/<类型>/<模块名>/<动作>`：页面模块接口

### 登录

- 方法：`POST`
- URL：`https://sns.oddba.cn/api/user/login`
- 用途：登录网站

#### 请求

- Query：无
- Body：Form Data，具体格式如下
  - `account`：用户名
  - `password`：密码
  - `captcha_token`：验证码令牌，无验证码时为空
- Referer：`https://sns.oddba.cn/`

#### 响应

- 格式：`JSON`
- 会通过 `set-cookie` 响应头设置 `lightsns_token` Cookie。

#### 响应示例

**成功**

```json
{
  "code": 1,
  "msg": "欢迎回来",
  "data": {
    "user_info": {
      "user_id": 123456,
      "nickname": "示例用户",
      "avatar_url": "https://ods3.oddba.cn/user_files/123456/avatar/0000000_1700000000.png"
    },
    "token": "..."
  },
  "timestamp": 1790269261,
  "request_id": "0123456789abcdef"
}
```

**失败（密码错误）**

```json
{
  "code": 0,
  "msg": "账号或密码错误",
  "data": null,
  "timestamp": 1790269261,
  "request_id": "0123456789abcdef",
  "error_code": "business_failed"
}
```

##### 重要字段说明

- `token`：Cookie 中的 `lightsns_token`。与 `set-cookie` 响应头中的 Cookie 值一致。

### 获取页头

- 方法：`POST`
- URL：`https://sns.oddba.cn/api/pc/header/index`
- 用途：获取页头数据，可用于确认 Cookie 登录态是否有效

#### 请求

- Query：无
- Body：无

#### 响应

- 格式：`JSON`

#### 响应示例

[获取页头](response/获取页头.json)

##### 重要字段说明

- `data.is_login`：是否已登录
- `data.nickname`：被 `<font>` 标签包裹的用户昵称
- `data.quick_assets`：快捷资产列表，目前仅发现一项（金币）
- `data.exp` 和 `data.exp_next`：当前经验值与达到下一级所需的经验值

### 签到中心初始化

- 方法：`POST`
- URL：`https://sns.oddba.cn/module/pc/page/jinsom-pc-page-default-sign/init`
- 用途：获取签到中心的全部业务数据（签到状态、本月日历、累签宝箱、心情墙、排行、今日签到人数）

#### 请求

- Query：无
- Body：无
- Referer：`https://sns.oddba.cn/sign`

#### 响应

- 格式：`JSON`

##### 响应示例

[签到中心初始化](response/签到中心初始化.json)

##### 重要字段说明

- `data.user`：未登录时为 `null`
  - `signed`：今日是否已签到
  - `total_days`：累计签到天数（不是本月累计）
  - `streak_days`：连续签到天数（补签会改变它）
  - `sign_card`：补签卡数量
  - `rank`：今日签到排行名次，今日未签到时为 `0`
  - `mark`：今日已发布的心情文本，未发布为 `""`；非空时签到中心不再显示心情输入框
- `data.calendar.count`：当前日历月份的签到天数；累签宝箱按本月签到天数解锁，不能用 `user.total_days` 判断资格。页面宝箱旁的「已签 N 天」却取总累计天数，容易误解。
- `data.chests`：累签宝箱列表，目前配置为 4 档（`day` 为 `7`、`14`、`21`、`28`）；应以服务端返回为准，不写死档位
  - `claimed`：已领取（`true` 时前端显示对勾）
  - `active`：是否可领取（`true` 时前端显示「领取」按钮；`claimed=true` 时必为 `false`）
  - `remain`：距该档位还差的天数；`claimed=true` 时为 `0`。未登录时等于档位本身（即从 0 天起算）

签到后应重新初始化：当前前端只局部更新日历和统计，不重新计算宝箱按钮。`checkin` 的 `continuous_days` 与初始化的 `user.streak_days` 口径不同，实测并不相等，不能互相替代或据此推算宝箱资格。

脚本在收到明确的签到成功响应时沿用签到前宝箱的 `remain == 1` 判断本次新解锁档位；若签到请求因网络异常或 HTTP 408/5xx 无法确定结果，则重新初始化签到中心。此时直接使用刷新后的 `user.signed` 和宝箱状态，不再给 `remain` 推算增加一天。

### 每日签到

- 方法：`POST`
- URL：`https://sns.oddba.cn/api/user/checkin`
- 用途：执行每日签到动作；已签到后再带 `mark` 调用则是「发布今日签到心情」

#### 请求

- Query：无
- Body：Form Data，具体格式如下
  - `mark`：签到心情文本，可为空
  - `captcha_token`：验证码令牌，无验证码时为空
- Referer：`https://sns.oddba.cn/sign`

#### 响应

- 格式：`JSON`

##### 响应示例

**成功（首次签到）**

```json
{
  "code": 1,
  "msg": "签到成功",
  "data": {
    "rewards": [
      {
        "type": "credit",
        "number": 2,
        "text": "金币",
        "icon": "ri-copper-coin-line",
        "icon_url": "",
        "title": ""
      },
      {
        "type": "exp",
        "number": 10,
        "text": "经验",
        "icon": "ri-flashlight-fill",
        "icon_url": "",
        "title": ""
      },
      {
        "type": "vip_number",
        "number": 10,
        "text": "成长值",
        "icon": "ri-vip-diamond-fill",
        "icon_url": "",
        "title": ""
      }
    ],
    "granted": [
      {
        "type": "currency",
        "key": "credit",
        "name": "金币",
        "amount": "2",
        "balance": "714"
      },
      {
        "type": "currency",
        "key": "exp",
        "name": "经验",
        "amount": "10",
        "balance": "3721"
      },
      {
        "type": "currency",
        "key": "vip_number",
        "name": "VIP 数值",
        "amount": "10",
        "balance": "7147"
      }
    ],
    "signed": true,
    "today_count": 223,
    "rank_item": {
      "uid": 123456,
      "rank": 223,
      "info": {
        "user_id": 123456,
        "nickname": "<font class=\"nickname nickname-123456\">某用户</font>",
        "avatar_url": "https://ods3.oddba.cn/user_files/123456/avatar/0000000_1700000000.png",
        "link": "/users/AbCdEfGhIjK"
      },
      "time": "00:47",
      "days": 245
    },
    "continuous_days": 2
  },
  "timestamp": 1790269261,
  "request_id": "0123456789abcdef"
}
```

- `data.granted`：拿到的奖励和该奖励的余额
- `data.signed`：本次签到是否真的生效。前端签到组件（`module/pc/widget/YXYH-pc-widget-sign/`）除了 `code == 1`，还要 `payload.signed` 为真才把按钮切成「今日已签到」并更新连续天数，所以它是比 `code` 更严的一档判据。已签到的失败响应 `data` 为 `null`，此时没有这个字段。
- `data.rank_item.days`：总签到天数
- `data.continuous_days`：真实连续签到天数（补签不算）

**失败：今天已签到**

```json
{
  "code": 0,
  "msg": "今天已签到",
  "data": null,
  "timestamp": 1790269261,
  "request_id": "0123456789abcdef",
  "error_code": "business_failed"
}
```

**已签到后再带 `mark` 调用（发布签到心情）**

```json
{
  "code": 1,
  "msg": "心情已发布",
  "data": {
    "rewards": [
      {
        "type": "credit",
        "number": 2,
        "text": "金币",
        "icon": "ri-copper-coin-line",
        "icon_url": "",
        "title": ""
      },
      {
        "type": "exp",
        "number": 10,
        "text": "经验",
        "icon": "ri-flashlight-fill",
        "icon_url": "",
        "title": ""
      },
      {
        "type": "vip_number",
        "number": 10,
        "text": "成长值",
        "icon": "ri-vip-diamond-fill",
        "icon_url": "",
        "title": ""
      }
    ],
    "granted": [],
    "signed": false,
    "today_count": 226,
    "rank_item": null,
    "continuous_days": 2
  },
  "timestamp": 1790269261,
  "request_id": "0123456789abcdef"
}
```

目前发布签到心情不会得到任何奖励。

### 领取累签宝箱奖励

- 方法：`POST`
- URL：`https://sns.oddba.cn/api/user/checkin-treasure`
- 用途：领取本月累计签到（累签）宝箱奖励

#### 请求

- Query：无
- Body：Form Data，具体格式如下
  - `day`：宝箱档位（`7`、`14`、`21`、`28`），取自签到中心初始化的 `data.chests[].day`
- Referer：`https://sns.oddba.cn/sign`

#### 响应

- 格式：`JSON`

**成功（领取28天档位的累签宝箱）**

```json
{
  "code": 1,
  "msg": "领取成功",
  "data": {
    "reward_list": [
      {
        "reward_number": 38,
        "reward_text": "金币"
      },
      {
        "reward_number": 20,
        "reward_text": "经验值"
      },
      {
        "reward_number": 20,
        "reward_text": "VIP成长值"
      },
      {
        "reward_number": 1,
        "reward_text": "补签卡"
      }
    ],
    "rewards": [
      {
        "type": "currency",
        "key": "credit",
        "name": "金币",
        "amount": "38",
        "balance": "705"
      },
      {
        "type": "currency",
        "key": "exp",
        "name": "经验",
        "amount": "20",
        "balance": "3799"
      },
      {
        "type": "currency",
        "key": "vip_number",
        "name": "VIP 数值",
        "amount": "20",
        "balance": "7245"
      },
      {
        "type": "prop",
        "key": "sign_card",
        "name": "补签卡",
        "icon": "ri-calendar-check-line",
        "amount": 1,
        "left": 5
      }
    ]
  },
  "timestamp": 1790269261,
  "request_id": "0123456789abcdef"
}
```

##### 重要字段说明

- `data.rewards`：本次实际发放的奖励，结构同签到 `data.granted` 与任务中心 `data.rewards`，全站六个发奖入口（卡密兑换、全站公告领奖、任务中心领奖、每日签到、累签宝箱、模块 `reward.grant`）回的都是同一形状。前端 `pc/bundle/base__*.js` 的 `LS.grant` 弹窗按 `type` 分流，共支持五类：
  - `type = currency`：货币类，带 `key`、`name`、`amount`、`balance`（发放后余额），如金币、经验、VIP 数值
  - `type = prop`：道具类，带 `key`、`name`、`icon`、`amount`、`left`（发放后剩余数量，没有 `balance`），如补签卡
  - `type = vip_days`：会员天数，带 `amount`；另有 `forever`（为真表示永久，此时不再给到期时间）与 `until`（到期时间），前端文案为 `永久` 或 `+N 天`
  - `type = invite_code`：邀请码，带 `amount` 与 `codes`（可复制的一串码）
  - `type = user_title`：头衔，**没有 `name`**，内容在 `title` 里，前端显示为 `头衔「<title>」`；没有数量
- 后三类截至 2026-09-28 未在本站实际观察到，字段依据是前端消费逻辑（`pc/bundle/base__*.js` 的 `TYPES` / `titleOf` / `valueOf` / `subOf`）。
- `data.reward_list`：该档位宝箱的奖励配置展示（`reward_number` 数值 + `reward_text` 文案），不是到账记录，脚本不读取它。
- 脚本以 `data.rewards` 作为实际到账依据，按 `type` 分流拼成一行明细「名字 数量（补充说明）」，与前端 `LS.grant` 的行结构对齐但文案从简：
  - 名字：`user_title` 用它自己的 `title`，拼成 `头衔「<title>」`；`vip_days` / `invite_code` 是站点固定叫法，分别写死为 `VIP 会员`、`邀请码`（不读 `name`）；其余读 `name`。头衔没有 `title` 才算解析失败。
  - 数量：货币是 `+amount`，`vip_days` 优先判断 `forever`，为真时即使缺少 `amount` 也显示 `永久`，否则显示 `+amount 天`；道具、邀请码与未知类型统一按数量处理，出 `×amount`（没用 `+`，避免与货币的"增量"语义混淆）。头衔不出数量。
  - 补充说明：货币出 `现有 X`（余额 0 也出），道具出 `剩余 X`（剩余 0 也出），`vip_days` 永久出 `不再过期`、否则出 `有效期至 <日期>`。
  - 遇到未知 `type` 时降级为「名称 + ×数量」，名称取不到 `name` 时出 `未知奖励（<type>）`，不再丢弃整批明细。

**失败（重复领取）**

```json
{
  "code": 0,
  "msg": "本月已领取该宝箱",
  "data": null,
  "timestamp": 1790269261,
  "request_id": "0123456789abcdef",
  "error_code": "business_failed"
}
```

**其它失败响应**

```json
{ "code": 0, "msg": "需要本月签到 28 天", "data": null, "error_code": "business_failed" }
{ "code": 0, "msg": "宝箱配置不存在", "data": null, "error_code": "business_failed" }
```

### 任务中心初始化

- 方法：`POST`
- URL：`https://sns.oddba.cn/api/task-center/init`
- 用途：获取任务中心（`/task-center`）的全部业务数据（概览、本周签到、任务分组、宝箱任务、今日收获、道具卡）

#### 请求

- Query：无
- Body：无
- Referer：`https://sns.oddba.cn/task-center`

#### 响应

- 格式：`JSON`

##### 响应示例

[任务中心初始化](response/任务中心初始化.json)，[任务中心初始化\_2](response/任务中心初始化_2.json)

##### 字段说明

- `data.overview`：
  - `done`：已完成的任务数，即页面上「今日完成 3/9」的分子；实测包含以前已领取的成长任务，不代表今天完成的每日任务数
  - `claimable`：服务端提供的可领取条数；当前前端自行统计每日和成长任务中 `status === "claimable"` 的条目，用于「待领取」与顶部「一键领取 N 项」，不直接读取本字段
  - `task_total`：历史累计领取次数
- `data.sections`：任务分组数组，子项的 `key` 为 `daily`（每日任务，每天 0 点刷新）或 `base`（成长任务，长期有效）。脚本关注每日任务即可。
- `data.treasures.items`：按累计领取任务次数解锁的宝箱任务，与签到中心按月解锁的累签宝箱不同；实测可为空数组。当前网页一键领取不包含它，脚本也不处理。
- `data.week_sign`：本周签到展示；`configured=false` 不等于禁止签到，应看 `signed_today` 判断今日状态。

##### 任务条目（`sections[].items[]`）重要字段说明

| 字段            | 说明                                                                      |
| --------------- | ------------------------------------------------------------------------- |
| `id` / `group`  | 任务标识与所属分组，领取时原样回传                                        |
| `name` / `desc` | 任务名与说明                                                              |
| `claimed`       | 是否已领取                                                                |
| `claimed_at`    | 今天领取时为 `HH:mm:ss`；历史已领取的成长任务可为空，不能据空值判断未领取 |
| `status`        | `claimable`（可领取）/ `doing`（进行中）/ `claimed`（已领取）             |
| `status_text`   | 状态文案：`可领取` / `进行中` / `已领取`                                  |
| `action_text`   | 按钮文案：`领取奖励` / `去完成` / `已领取`                                |
| `reward_text`   | 奖励摘要文案（展示用）                                                    |

### 领取任务奖励

- 方法：`POST`
- URL：`https://sns.oddba.cn/api/task-center/claim`
- 用途：领取一条任务（或一个宝箱）的奖励

#### 请求

- Query：无
- Body：Form Data，具体格式如下
  - `group`：任务所属分组，取自条目自身的 `group` 字段
  - `task_id`：任务 id，取自条目自身的 `id` 字段
- Referer：`https://sns.oddba.cn/task-center`

页面上「一键领取 N 项」= 把此刻 `sections[].items[]` 中所有 `status === 'claimable'` 的条目串行逐条调用本接口（包含成长任务，不含 `treasures.items`）。脚本仅领取 `daily` 分组。该接口不需要验证码。

#### 响应

- 格式：`JSON`

##### 响应示例

[领取任务奖励\_点赞一条评论](response/领取任务奖励_点赞一条评论.json)，[领取任务奖励\_每日签到](response/领取任务奖励_每日签到.json)

##### 重要字段说明

- `data.payload`：领取后的完整任务中心数据，结构对应任务中心初始化接口的 `data`
- `data.rewards`：本次实际发放的奖励数组
- **成功判据只有 `code=1`**。前端 `pc/bundle/task_center__*.js` 的 `claim()` 与 `claimAll()` 都是 `if (res.code === 1)` 即认定领取成功，不校验条目的 `status` / `claimed`，失败计数也只数「响应 `code !== 1`」。2026-09-27 实测领取「每日登陆」「每日签到」返回 `code=1`、`msg="领取成功"`，对应条目在 `payload` 中变为 `status="claimed"`、`claimed=true`。
- `data.payload` 的用途是**刷新页面状态**，不是核验凭据。前端 `claim()` 成功后就 `render(data.payload)`，`claimAll()` 的注释写明「整页以最后一次成功领取时服务端回的那份为准；一条都没成的话重拉一次」。脚本沿用同一口径：`code=1` 即报告领取成功，整轮只以开始时的清单为准，与前端一键领取一样中途不重读、不回头补领本轮未列入清单的条目。
- 上述正常流程之外，领奖请求因网络异常或 HTTP 408/5xx 无法确定结果时，脚本重新初始化任务中心，只核验本次 `group` / `id` 对应条目的 `claimed`。已领取则不重发，也不根据刷新结果追加本轮任务；未确认则记为失败。宝箱领奖同理，通过签到中心对应 `day` 的 `claimed` 核验。
- 前端对「今天已领」的判据是 `claimed && claimed_at`（`isClaimedToday()`），**不是** `status`。注释明确说明不能只看 `claimed` —— 成长任务是一次性的，上个月领过的条目同样是 `claimed`。脚本只处理 `daily` 分组且以 `status == "claimable"` 为主判据，不受此影响。
- 两项任务各发放 2 经验、2 成长值，与签到动作本身的奖励分开发放。以上为当前配置，实际入账应读取 `data.rewards` 的 `name`、`amount`、`balance`，不能把条目的展示字段 `rewards` / `reward_text` 当成到账依据。
- 未完成任务的 `link` 可以为空；此时网页「去完成」不会跳转，也不代表点击即可完成任务。打赏任务涉及资产消耗，不属于本脚本的自动执行范围。

### 验证码守卫

- 方法：`POST`
- URL：`https://sns.oddba.cn/api/captcha/guard`
- 用途：动作执行前查询本次是否需要验证码

#### 请求

- Query：无
- Body：Form Data，具体格式如下
  - `scene`：场景名，签到场景为 `sign`，登录场景为 `login`
- Referer：使用动作所在页面；签到为 `https://sns.oddba.cn/sign`，从任务中心签到也可为 `/task-center`，登录为站点首页

#### 响应

- 格式：`JSON`

##### 响应示例

```json
{
  "code": 1,
  "msg": "",
  "data": { "need": false },
  "timestamp": 1790269261,
  "request_id": "0123456789abcdef"
}
```

##### 关键发现

- `data.need` 为 `false` 时不需要验证码，直接以空的 `captcha_token` 调用签到或登录接口即可（多次实测均为该情况）
- 前端流程（`/pc/bundle/base.js` 的 `LS.captcha.guard`）：
  1. 调 `/api/captcha/guard`
  2. `data.need=false` → 直接用空 token 继续；`data.need=true` → 优先直接渲染 `data.captcha` 携带的拼图数据，缺少预加载数据或用户点击刷新时才调 `/api/captcha/generate`
  3. 用户拖动滑块，前端调 `/api/captcha/verify`，body 为 `challenge_id`、`slide_x`、`slide_time`、`track`（拖动轨迹 JSON，反机器人用）
  4. `code=1` 时 `data.token` 即为要传给动作接口的 `captcha_token`

### 验证码拼图接口（未实际触发）

已观察的签到和登录请求未要求验证码，故这两个接口**未实际触发**，仅从 `/pc/bundle/base.js` 的 `LS.captcha` 读出请求形状，将来遇到 `need=true` 时需要再抓包进行验证：

- `POST /api/captcha/generate`
  - Body：无
  - 响应 `data`：`{challenge_id, bg, piece, y, bg_width, bg_height, piece_width, piece_height, piece_offset_x, piece_offset_y, knob_radius}`
  - `bg` / `piece` 是 `data:image/png;base64,...` 形式的图片（背景约 300×150，拼图块 60×60）
  - `y` 是拼图块的目标纵坐标，`knob_radius` 用于定位偏移
- `POST /api/captcha/verify`
  - Body：`challenge_id`、`slide_x`（拖动距离）、`slide_time`（耗时）、`track`（拖动轨迹 `JSON.stringify` 后的字符串，含各采样点时间与偏移，后端据此判人机）
  - 响应 `code=1` 时 `data.token` 即为动作接口的 `captcha_token`

---

以下是相对来说没那么重要的接口：

---

### 签到日历（切换月份）

- 方法：`POST`
- URL：`https://sns.oddba.cn/api/user/checkin-calendar`
- 用途：切换签到日历的月份

#### 请求

- Query：无
- Body：Form Data，具体格式如下
  - `year`
  - `month`

实测空 body 时服务端返回当前月份，即两个参数都可由服务端兜底。

#### 响应

- 格式：`JSON`，业务数据在 `data.calendar`

##### 响应示例

```json
{
  "code": 1,
  "msg": "",
  "data": {
    "calendar": {
      "year": 2026,
      "month": 8,
      "month_name": "2026年8月",
      "days": 31,
      "today": 25,
      "first_day": 6,
      "signed": ["2026-08-01", "2026-08-02", "..."],
      "count": 31,
      "is_current_month": false
    }
  },
  "timestamp": 1790269261,
  "request_id": "0123456789abcdef"
}
```

### 补签

- 方法：`POST`
- URL：`https://sns.oddba.cn/api/props/use`
- 用途：消耗补签卡（道具）补签指定日期

#### 请求

- Query：无
- Body：Form Data，具体格式如下
  - `prop_key`：固定值 `sign_card`
  - `scene`：固定值 `makeup_checkin`
  - `date`：补签目标日期，格式 `YYYY-MM-DD`

#### 响应

- 格式：`JSON`

##### 响应示例

**成功**

```json
{
  "code": 1,
  "msg": "补签成功",
  "data": { "sign_card": 1, "date": "2026-09-22" },
  "timestamp": 1790269261,
  "request_id": "0123456789abcdef"
}
```

`data.sign_card` 是补签后剩余的补签卡数量（此例补签前为 2，故返回 1），`data.date` 回显补签日期。

**失败**

```json
{ "code": 0, "msg": "该日期已签到",     "data": null, "error_code": "business_failed" }
{ "code": 0, "msg": "只能补签过去日期", "data": null, "error_code": "business_failed" }
{ "code": 0, "msg": "只能补签当日前30日", "data": null, "error_code": "business_failed" }
{ "code": 0, "msg": "请选择补签日期",   "data": null, "error_code": "business_failed" }
{ "code": 0, "msg": "请在对应功能入口使用该道具", "data": null, "error_code": "business_failed" }
```

### 道具商店 / 道具库存

- 方法：`POST`
- URL：`https://sns.oddba.cn/api/props/shop`
- 用途：获取道具商店列表与本人道具库存

#### 请求

- Query：无
- Body：无

#### 响应

- 格式：`JSON`

##### 响应示例

```json
{
  "code": 1,
  "msg": "",
  "data": {
    "items": [
      {
        "id": 1,
        "prop_key": "sign_card",
        "name": "补签卡",
        "description": "补回当日前30日漏签",
        "icon": "ri-calendar-check-line",
        "price_text": "20金币",
        "origin_text": "",
        "discount_label": "",
        "stock_left": -1,
        "buy_limit": 0,
        "buy_limit_days": 0,
        "bought_quantity": 0,
        "buy_limit_reached": 0,
        "active": 1,
        "limit_start_at": "",
        "limit_end_at": ""
      },
      {
        "id": 2,
        "prop_key": "reload_card",
        "name": "刷新卡",
        "description": "刷新自己的内容排序",
        "icon": "ri-refresh-line",
        "price_text": "10金币",
        "origin_text": "100金币",
        "discount_label": "1折",
        "stock_left": -1,
        "buy_limit": 0,
        "buy_limit_days": 0,
        "bought_quantity": 0,
        "buy_limit_reached": 0,
        "active": 1,
        "limit_start_at": "",
        "limit_end_at": ""
      },
      {
        "id": 3,
        "prop_key": "nickname_card",
        "name": "改名卡",
        "description": "修改昵称时抵扣",
        "icon": "ri-id-card-line",
        "price_text": "100金币",
        "origin_text": "",
        "discount_label": "",
        "stock_left": -1,
        "buy_limit": 0,
        "buy_limit_days": 0,
        "bought_quantity": 0,
        "buy_limit_reached": 0,
        "active": 1,
        "limit_start_at": "",
        "limit_end_at": ""
      }
    ],
    "inventory": {
      "sign_card": {
        "prop_key": "sign_card",
        "name": "补签卡",
        "icon": "ri-calendar-check-line",
        "quantity": 2
      },
      "reload_card": {
        "prop_key": "reload_card",
        "name": "刷新卡",
        "icon": "ri-refresh-line",
        "quantity": 0
      },
      "nickname_card": {
        "prop_key": "nickname_card",
        "name": "改名卡",
        "icon": "ri-id-card-line",
        "quantity": 2
      }
    }
  },
  "timestamp": 1790269261,
  "request_id": "0123456789abcdef"
}
```

##### 关键发现

- `stock_left = -1` 表示不限量；`active = 1` 表示上架；`buy_limit = 0` 表示不限购

### 购买道具

- 方法：`POST`
- URL：`https://sns.oddba.cn/api/props/buy`
- 用途：用金币购买道具

#### 请求

- Query：无
- Body：Form Data，具体格式如下
  - `item_id`：道具 id，取自 `/api/props/shop` 的 `items[].id`
  - `quantity`：数量，可省略

#### 响应

- 格式：`JSON`

##### 响应示例（买 1 张补签卡）

```json
{
  "code": 1,
  "msg": "购买成功",
  "data": {
    "order_no": "PROP2026090100000000000000",
    "item": {
      "id": 1,
      "prop_key": "sign_card",
      "name": "补签卡",
      "description": "补回当日前30日漏签",
      "icon": "ri-calendar-check-line",
      "price_text": "20金币",
      "origin_text": "",
      "discount_label": "",
      "stock_left": -1,
      "buy_limit": 0,
      "buy_limit_days": 0,
      "bought_quantity": 0,
      "buy_limit_reached": 0,
      "active": 1,
      "limit_start_at": "",
      "limit_end_at": ""
    },
    "inventory": {
      "sign_card": {
        "prop_key": "sign_card",
        "name": "补签卡",
        "icon": "ri-calendar-check-line",
        "quantity": 2
      },
      "reload_card": {
        "prop_key": "reload_card",
        "name": "刷新卡",
        "icon": "ri-refresh-line",
        "quantity": 0
      },
      "nickname_card": {
        "prop_key": "nickname_card",
        "name": "改名卡",
        "icon": "ri-id-card-line",
        "quantity": 1
      }
    }
  },
  "timestamp": 1790269261,
  "request_id": "0123456789abcdef"
}
```
