# ODDBA API DOCS

本文档用于记录 `https://sns.oddba.cn/` 的页面、接口和自动化相关观察结果。自动化脚本已在项目 `src/oddba_looter/` 中实现；本文档同时作为该脚本的接口依据。

## 文档约定

- 本文档只记录对自动化实现有帮助的信息，不追求完整站点逆向。
- 除非某个接口章节另有说明，默认请求体为普通表单数据（`Content-Type: application/x-www-form-urlencoded`）。
- 真实登录态、真实 Cookie、账号信息等敏感内容不写入仓库文档。

## 全局约定

### 请求侧

- HTTP 版本：优先使用 `HTTP/2`。
- 浏览器伪装：该网站在正常情况下主要通过浏览器访问，自动化请求应尽量模拟浏览器环境。
- 反自动化情况：暂未观察到明显反爬措施，但仍应保留基础浏览器请求头、Cookie 和合理调用频率。
- 请求来源校验：`module/action/` 下的动作接口（`sign.php`、`sign-treasure.php`、`task.php`）会校验请求来源，若缺少本站 `Referer`/`Origin` 头会返回 `{"code":0,"msg":"非法请求！ (1700001)"}` 并拒绝执行。自动化请求需带 `Referer`（如 `https://sns.oddba.cn/sign`） 与 `Origin: https://sns.oddba.cn`，否则任何动作接口都会被拒。
- 未发现 nonce 机制：页面与前端 JS（`cdn/assets/js/jinsom.js` 中的 `jinsom_sign`/`jinsom_sign_treasure`/`jinsom_task_finish`）均未携带任何 nonce / CSRF token 字段。

### 响应侧

- 响应通常分为两类：`HTML` 或 `JSON`。
- 若返回 JSON，常见字段为：
  - `code`：`1` 表示成功或正常；`0` 表示失败或错误；`2` 有时表示失败，有时表示成功，含义取决于具体接口。
  - `msg`：提示信息。
- JSON 中的文本字段常为 Unicode 转义形式，例如 `"\u5956\u52b1\u9886\u53d6\u6210\u529f\uff01"`。

## 认证与会话

### Cookie 说明

#### `wordpress_logged_in_<32位hash>`

- 作用：用户身份认证
- 生命周期：长期有效，获取一次后通常可使用较长时间（约一年）
- 使用建议：保存在本地私有配置中
- 备注：推测该 Cookie 的名称对于不同用户可能是不同的（末尾的哈希值可能不同）

#### `server_name_session`

- 作用：短期会话维持（猜测）
- 生命周期：短期有效，目前观察为 24 小时
- 现象：若缺少该 Cookie，访问任意页面/接口时服务端会重新设置
- 自动化建议：在执行每日任务前，先访问一个页面以获取最新会话
- 已验证：
  - 清空该 Cookie 后访问网站首页 `/`，签到中心 `/sign` 或每日签到API，响应头中均设置了该 Cookie
  - 携带一个已经过期的 Cookie 去访问任意页面/接口，服务端不会设置该 Cookie
- 未验证：
  - 是否所有动作请求都依赖该 Cookie
- 备注：感觉服务端并未校验该 Cookie，但保险起见，访问 API 时还是带上

#### `history-search`

- 作用：保存搜索历史记录。
- 自动化建议：忽略。

### `theme_mode`

- 作用：保存使用的主题。
- 值：`theme-light`（默认浅色主题）、`theme-dark`（深色主题）
- 自动化建议：忽略。

### `preference-bg`

- 作用：保存偏好设置。
- 值：一个 CSS 文件地址，如 `https%3A//sns.oddba.cn/wp-content/uploads/style/wcbl/style.css`。
- 自动化建议：忽略。

## 接口详情

### 获取签到中心网页

- 方法：`GET`
- URL：`https://sns.oddba.cn/sign`
- 用途：读取签到状态，并从页面中发现后续可执行动作

#### 请求

- Query：无
- Body：无

#### 响应

- 格式：`HTML`

#### 关键发现

##### 当天签到状态

如果当天还可以签到，页面中显示：

```html
<div class="jinsom-sign-page-btn opacity" onclick="jinsom_sign('','',this)">
  <i class="jinsom-icon jinsom-qiandao3"></i><span>点击签到</span>
</div>
```

如果当天已经签到，页面中显示：

```html
<div class="jinsom-sign-page-btn had opacity">今日已签到</div>
```

##### 本月签到天数和签到宝箱奖励

本月累计签到天数达标后可领取签到宝箱奖励。

示例片段：

```html
<div class="jinsom-sign-page-box month">
  <div class="jinsom-sign-page-month-days">本月签到<span>23</span>天</div>
  <div class="content">
    <li class="">
      <div class="img">
        <img
          src="https://sns.oddba.cn/wp-content/uploads/2020/06/baoxiang.png"
          onclick="jinsom_sign_treasure_form(0)"
        /><span>7天</span>
      </div>
      <div class="btn opacity had">已领取</div>
    </li>
    <li class="">
      <div class="img">
        <img
          src="https://sns.oddba.cn/wp-content/uploads/2020/06/baoxiang.png"
          onclick="jinsom_sign_treasure_form(1)"
        /><span>14天</span>
      </div>
      <div class="btn opacity had">已领取</div>
    </li>
    <li class="">
      <div class="img">
        <img
          src="https://sns.oddba.cn/wp-content/uploads/2020/06/baoxiang.png"
          onclick="jinsom_sign_treasure_form(2)"
        /><span>21天</span>
      </div>
      <div class="btn opacity had">已领取</div>
    </li>
    <li class="">
      <div class="img">
        <img
          src="https://sns.oddba.cn/wp-content/uploads/2020/06/baoxiang.png"
          onclick="jinsom_sign_treasure_form(3)"
        /><span>28天</span>
      </div>
      <div class="btn opacity" onclick="jinsom_sign_treasure(3,this)">领取</div>
    </li>
  </div>
</div>
```

其中每一项任务的 `onclick` 中的函数的第一个参数是签到宝箱奖励编号，领取奖励时会用到。

### 每日签到

- 方法：`POST`
- URL：`https://sns.oddba.cn/wp-content/themes/LightSNS/module/action/sign.php`
- 用途：执行每日签到动作

#### 请求

- Query：无
- Body：Form Data，具体格式如下
  - `sign`：固定值 `1`
  - `ticket`：空
  - `randstr`：空

#### 响应

- 格式：`JSON`

##### 响应示例

**成功**

```json
{
  "content": "<li><i class=\"jinsom-icon jinsom-zhifuchenggong\"><\/i>\u7b7e\u5230\u6210\u529f<\/li><li>\u7d2f\u8ba1\u7b7e\u5230159\u5929<\/li><fieldset class=\"layui-elem-field\"><legend>\u83b7\u5f97\u4ee5\u4e0b\u5956\u52b1<\/legend><div class=\"layui-field-box\"><li>\u91d1\u5e01 * 2<\/li><li>\u7ecf\u9a8c\u503c * 10<\/li><li>\u6210\u957f\u503c * 10<\/li><\/div><\/fieldset>",
  "code": 1,
  "sign_c": 159,
  "msg": "\u7b7e\u5230\u6210\u529f",
  "text": "\u4eca\u65e5\u5df2\u7b7e\u5230",
  "text_mobile": "\u5df2\u7b7e\u5230"
}
```

**失败（重复签到）**

```json
{
  "code": 2,
  "sign_c": 164,
  "msg": "\u4f60\u4eca\u5929\u5df2\u7ecf\u7b7e\u5230\u4e86",
  "content": "\u4eca\u65e5\u5df2\u7b7e\u5230",
  "text": "\u4eca\u65e5\u5df2\u7b7e\u5230"
}
```

注：`sign_c` 字段是总累计签到天数，不是本月累计签到天数

### 获取“做任务”弹窗

- 方法：`GET`
- URL：`https://sns.oddba.cn/wp-content/themes/LightSNS/module/stencil/task.php`
- 用途：获取“做任务”弹窗内容

#### 请求

- Query：无
- Body：无

#### 响应

- 格式：`HTML`

#### 关键发现

##### 任务ID

每日登陆任务相关片段：

```html
<li>
  <div class="info">
    <div class="left">
      <div class="name">每日登陆</div>
      <div class="desc">每日登陆社区的奖励</div>
    </div>
    <div class="right">
      <div class="number">已完成：<m>1</m>/<n>1</n></div>
      <div
        class="status opacity on"
        onclick='jinsom_task_finish("dlrw1",
"day",this)'
      >
        领取奖励
      </div>
    </div>
  </div>
  <div class="reward">
    <p class="normal">
      普通奖励：<span>经验值 * 2</span><span>成长值 * 2</span>
    </p>
    <p class="vip">VIP 奖励：<span>经验值 * 3</span><span>成长值 * 3</span></p>
  </div>
</li>
```

其中 `onclick` 中的函数 `jinsom_task_finish` 的第一个参数为任务ID。后续领取任务奖励时会用到。

### 领取任务奖励

- 方法：`POST`
- URL：`https://sns.oddba.cn/wp-content/themes/LightSNS/module/action/task.php`
- 用途：执行领取任务奖励动作

#### 请求

- Query：无
- Body：Form Data，具体格式如下
  - `task_id`：任务ID，需通过获取“做任务”弹窗得到
  - `type`：任务类型，每日任务为 `day`

#### 响应

- 格式：`JSON`

##### 响应示例

**成功**

```json
{
  "code": 1,
  "msg": "\u5956\u52b1\u9886\u53d6\u6210\u529f\uff01",
  "task": 300
}
```

### 领取签到宝箱奖励

- 方法：`POST`
- URL：`https://sns.oddba.cn/wp-content/themes/LightSNS/module/action/sign-treasure.php`
- 用途：执行领取签到宝箱奖励动作

#### 请求

- Query：无
- Body：Form Data，具体格式如下
  - `number`：签到宝箱奖励编号，需通过获取签到中心网页得到

#### 响应

- 格式：`JSON`

##### 响应示例

**成功**

```json
{
  "content": "<li><i class=\"jinsom-icon jinsom-zhifuchenggong\"></i>领取成功</li><li>请再接再厉，获取更多奖励！</li><fieldset class=\"layui-elem-field\"><legend>获得以下奖励</legend><div class=\"layui-field-box\"><li>金币 * 5</li><li>经验值 * 10</li><li>成长值 * 10</li></div></fieldset>",
  "code": 1,
  "msg": "领取成功！"
}
```

**失败（未达到领取条件）**

```json
{
  "code": 0,
  "msg": "\u4f60\u8fd8\u6ca1\u6709\u8fbe\u5230\u9886\u53d6\u6761\u4ef6\uff01"
}
```

**失败（重复领取）**

```json
{
  "code": 0,
  "msg": "\u4f60\u5df2\u7ecf\u9886\u53d6\u8fc7\u4e86\uff01"
}
```
