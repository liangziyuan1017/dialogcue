# 催收话术推荐系统 — 接口调用说明

## 接口一：创建会话，绑定用户画像

```
POST http://127.0.0.1:8000/api/v1/session/start
```

**作用**：通话开始时调用一次，将客户画像信息绑定到本次会话，后续推荐接口无需再传。

```json
{
  "call_id": "2346430930132135291",
  "call_info": {
    "dial_date": "20260608183813",
    "connect_date": "20260608183852",
    "dial_type": "1",
    "ring_time": "37",
    "channel": "X",
    "mob_type": "M1"
  },
  "agent": {
    "coll_user_id": "AA11100",
    "coll_id": "A0BW9",
    "coll_area": "2",
    "coll_group_id": "CK002"
  },
  "customer": {
    "cust_no": "0000000221241219",
    "ac_no": "0221241219001001",
    "called_no": "13383023270"
  },
  "cust_tags": [
    {"tag": "经营贷款余额", "value": "0.0"},
    {"tag": "理财时点值", "value": "0.0"},
    {"tag": "其他贷款余额", "value": "0.0"},
    {"tag": "学历", "value": "大专"},
    {"tag": "商业房贷余额", "value": "0.0"},
    {"tag": "持卡用户是否疑似高风险代理投诉", "value": "否"},
    {"tag": "持卡用户是否疑似代理中介投诉", "value": "否"},
    {"tag": "持卡人当前是否缴纳社保", "value": ""},
    {"tag": "目前余额", "value": "7129.18"},
    {"tag": "ct标签", "value": ",667,040,"},
    {"tag": "（掌生APP操作）近7天-还款操作", "value": "N"},
    {"tag": "持卡用户名下历史车辆数", "value": "0"},
    {"tag": "近7日接通次数", "value": "19"},
    {"tag": "客户风险标识等级", "value": "3级"}
  ]
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `call_id` | string | 是 | 业务系统呼叫流水号，同时作为会话唯一标识，后续推荐接口用同一个 call_id 关联 |
| `call_info` | object | 否 | 呼叫上下文信息 |
| `call_info.dial_date` | string | 否 | 拨号时间，格式 `YYYYMMDDHHmmss` |
| `call_info.connect_date` | string | 否 | 接通时间 |
| `call_info.dial_type` | string | 否 | 拨号类型：1=自动外呼，2=手动外呼 |
| `call_info.ring_time` | string | 否 | 振铃时长（秒） |
| `call_info.channel` | string | 否 | 呼叫渠道：X=外呼，I=内呼 |
| `call_info.mob_type` | string | 否 | 逾期分档：M1/M2/M3/M4/M5+ |
| `agent` | object | 否 | 催收坐席信息 |
| `agent.coll_user_id` | string | 否 | 坐席工号 |
| `agent.coll_id` | string | 否 | 催收员系统ID |
| `agent.coll_area` | string | 否 | 催收区域：1=电催 / 2=外访 / 3=法催 |
| `agent.coll_group_id` | string | 否 | 催收组别 |
| `customer` | object | 否 | 客户标识信息 |
| `customer.cust_no` | string | 否 | 客户编号 |
| `customer.ac_no` | string | 否 | 账户编号 |
| `customer.called_no` | string | 否 | 被叫号码 |
| `cust_tags` | array | 否 | 客户画像标签，直接透传业务系统 custInfo 的 `[{tagName, tagValue}]` |
| `cust_tags[].tag` | string | 是 | 标签名，与业务系统 tagName 一致 |
| `cust_tags[].value` | string | 否 | 标签值，空值传空字符串 |

---

## 接口二：实时话术推荐

```
POST http://127.0.0.1:8000/api/v1/recommend
```

**作用**：输入客户说的话，返回系统推荐的催收员话术。每轮对话调用一次。

```json
{
  "call_id": "2346430930132135291",
  "current_text": "我失业了，没钱还",
  "history_context": []
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `call_id` | string | 是 | 呼叫流水号，与接口一保持一致 |
| `current_text` | string | 是 | 客户当前轮说的话 |
| `history_context` | string[] | 否 | 最近几轮对话内容，用于上下文理解，默认空数组 |

**返回示例**：

```json
{
  "recommendation": "理解您目前确实遇到了困难，我们可以帮您申请缓冲方案。",
  "state_tags": ["失业", "资金困难"],
  "confidence": 0.7,
  "rec_id": "rec_2346430930132135291_001",
  "info": ""
}
```

| 返回字段 | 类型 | 说明 |
|---------|------|------|
| `recommendation` | string | 推荐的催收员话术。为 null 时表示无推荐（语气词跳过或无匹配话术） |
| `state_tags` | string[] | 识别出的状态标签，如 ["失业", "资金困难", "焦虑"] |
|                  |          |                                                              |
| `confidence` | float | 状态识别置信度，0~1，越高越确定 |
| `rec_id` | string | 推荐记录ID |
| `info` | string | 附加说明 |

---

## 接口三：结束会话

```
DELETE http://127.0.0.1:8000/api/v1/session/end?call_id=2346430930132135291
```

**作用**：通话结束时调用，释放服务端会话资源。不调用则会话在 TTL（默认2小时）后自动过期。

**返回示例**：

```json
{
  "code": 0,
  "message": "session closed",
  "call_id": "2346430930132135291"
}
```

| 返回字段 | 类型 | 说明 |
|---------|------|------|
| `code` | int | 0=成功 |
| `message` | string | 处理结果描述 |
| `call_id` | string | 回传呼叫流水号 |
|           |        |                |
|           |        |                |

---

## 完整调用流程

```
步骤①：通话开始 → 调 session/start 绑定画像（只调1次）

步骤②：客户说话 → 调 recommend 获取推荐话术（每轮调1次）

步骤③：客户继续说话 → 再调 recommend（循环，直到通话结束）

步骤④：通话结束 → 调 session/end 关闭会话（可选）
```

```bash
# ① 会话开始：绑定画像
curl -X POST http://127.0.0.1:8000/api/v1/session/start \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "2346430930132135291",
    "call_info": {"dial_date":"20260608183813","connect_date":"20260608183852","dial_type":"1","ring_time":"37","channel":"X","mob_type":"M1"},
    "agent": {"coll_user_id":"AA11100","coll_id":"A0BW9","coll_area":"2","coll_group_id":"CK002"},
    "customer": {"cust_no":"0000000221241219","ac_no":"0221241219001001","called_no":"13383023270"},
    "cust_tags": [
      {"tag":"经营贷款余额","value":"0.0"},
      {"tag":"理财时点值","value":"0.0"},
      {"tag":"其他贷款余额","value":"0.0"},
      {"tag":"学历","value":"大专"},
      {"tag":"商业房贷余额","value":"0.0"},
      {"tag":"持卡用户是否疑似高风险代理投诉","value":"否"},
      {"tag":"持卡用户是否疑似代理中介投诉","value":"否"},
      {"tag":"持卡人当前是否缴纳社保","value":""},
      {"tag":"目前余额","value":"7129.18"},
      {"tag":"ct标签","value":",667,040,"},
      {"tag":"（掌生APP操作）近7天-还款操作","value":"N"},
      {"tag":"持卡用户名下历史车辆数","value":"0"},
      {"tag":"近7日接通次数","value":"19"},
      {"tag":"客户风险标识等级","value":"3级"}
    ]
  }'

# ② 客户第1轮发言
curl -X POST http://127.0.0.1:8000/api/v1/recommend \
  -H "Content-Type: application/json" \
  -d '{"call_id":"2346430930132135291","current_text":"我失业了，没钱还"}'

# ③ 客户第2轮发言
curl -X POST http://127.0.0.1:8000/api/v1/recommend \
  -H "Content-Type: application/json" \
  -d '{"call_id":"2346430930132135291","current_text":"能不能分期？"}'

# ④ 通话结束，关闭会话
curl -X DELETE "http://127.0.0.1:8000/api/v1/session/end?call_id=2346430930132135291"
```
