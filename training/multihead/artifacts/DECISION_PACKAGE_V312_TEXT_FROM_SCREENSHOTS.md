# v3.1.2 Decision Package 文字版（据全量机截图整理）

**来源路径：** `training/multihead/checkpoints/state_v312/decision_package_v312/`  
**整理依据：** 全量环境屏幕截图（2026-08-07）；**Asset 13/13、Commitment 3/3、Contactability reachable→unreachable 4/4 已转录**；unreachable→reachable **5/14**（Case1–5）。  
**用途：** 供同事 Residual Audit / Task Boundary / Long-tail 决策，无需再翻整包目录。

---

## 0. 包内目录（截图已确认存在）

```text
decision_package_v312/
├── 00_DECISION_TEMPLATE.md
├── README.md
├── eval_test_v32.md / .json          # 旁路评估产物，非决策核心
├── 01_residual_audit/
│   ├── INDEX.md
│   ├── residual_cases.jsonl
│   ├── Asset__unavailable_to_available.md      # 11
│   ├── Asset__available_to_unavailable.md      # 2
│   ├── Contactability__unreachable_to_reachable.md   # 14
│   ├── Contactability__reachable_to_unreachable.md   # 4
│   └── Commitment__resistant_to_committed.md         # 3
├── 02_identity_process/
│   ├── ontology_snippet.yaml
│   ├── positive_examples.md / .jsonl
│   └── boundary_checklist.md
├── 03_longtail_distribution/
│   └── multi_state_train_test.md / .json
└── 04_ontology_heads/
    ├── Asset.yaml / Contactability.yaml / Commitment.yaml
    ├── RepaymentCapability.yaml / IdentityProcess.yaml
    └── heads_bundle.yaml
```

---

## 1. Residual Audit 索引（`01_residual_audit/INDEX.md`）

分类口径：`model_error` / `ontology_boundary` / `label_error`

| Head | gold → pred | n | 文件 |
|------|-------------|--:|------|
| Asset | unavailable → available | **11** | `Asset__unavailable_to_available.md` |
| Asset | available → unavailable | **2** | `Asset__available_to_unavailable.md` |
| Contactability | unreachable → reachable | **14** | `Contactability__unreachable_to_reachable.md` |
| Contactability | reachable → unreachable | **4** | `Contactability__reachable_to_unreachable.md` |
| Commitment | resistant → committed | **3** | `Commitment__resistant_to_committed.md` |

**Confidence 读法（包内说明）：**

- pred≈0.5 / gold≈0.5 → 边界 / 难例  
- pred≈0.99 / gold≈0.01 → 类未学到或系统性偏差  

机器可读全集：`residual_cases.jsonl`

> 说明：截图主要展开了 **Asset** 两类混淆的原文；Contactability / Commitment 文件已生成，正文未完整入镜，请直接打开对应 md。

---

## 2. Asset：`available` → `unavailable`（2 条）

### Case 1

- **sample_id:** `2368736060494402303#turn23`
- **conversation window:**
  - turn1 `[collector]`：暂时住在这儿租的是吧?
  - turn2 `[customer]`：算是以后离了，那我就不在这里了嘞，这个房子又不是我的，又不是挂名下的。
  - turn3 `[collector]`：是您——是您爱人那边的是吧?
  - turn4 `[customer]`：名下又没有这个住房。
- **gold:** `Asset=available`
- **prediction:** `Asset=unavailable`
- **confidence:** available 0.0161 / unavailable **0.9837** / none 0.0003
- **logits:** available -1.2895 / unavailable 2.8258 / none -5.3476
- **margin (pred−gold):** 0.9676
- **window_raws:** `['asset_situation']`（截图旁注）
- **fired（旁注）：** `asset_situation → Asset=available (include_raw)`
- **audit_label:** _TODO_

**读法提示：** 客户明确「房子不是我的 / 名下没有」；模型高置信判 unavailable，与字面更一致——优先怀疑 **gold=available 是否标错 / ontology 边界**，而非单纯「模型没学到」。

---

### Case 2

- **sample_id:** `2367077110282209977#turn41`
- **conversation window:**
  - turn1 `[collector]`：……如果您有招行的储蓄卡的话，那就开通的，但是您都没有招行的储蓄卡就不存在自动划扣的一个事情……
  - turn2 `[customer]`：我没有，刚注销，我是、我是、我是其他的储蓄卡，其他行的储蓄卡。
- **gold:** `Asset=available`
- **prediction:** `Asset=unavailable`
- **confidence:** available 0.0009 / unavailable **0.9988** / none 0.0003
- **logits:** available -3.2073 / unavailable 3.7777 / none -4.4488
- **margin:** 0.9979
- **window_raws:** `['other_bank_account', 'account_restriction']`
- **fired（旁注）：** `other_bank_account → Asset`；`account_restriction → BankConstraint`
- **audit_label:** _TODO_

**读法提示：** 有「其他行储蓄卡」却 gold=available、模型=unavailable；需核对 **银行卡/他行账户是否算 Asset.available**，以及 `account_restriction` 是否应进 Asset。

---

## 3. Asset：`unavailable` → `available`（11 条；截图可见部分）

### Case 1

- **sample_id:** `2353351790090454417#turn12`
- **conversation window:**
  - turn1 `[collector]`：嗯，这个应该也是您自己住的地方，是吧？
  - turn2 `[customer]`：是的。
  - turn3 `[collector]`：噢，这个是您自己的房子吗？
  - turn4 `[customer]`：嗯，不是。
- **gold:** `Asset=unavailable`
- **prediction:** `Asset=available`
- **confidence:** available **1.0** / unavailable 0.0 / none 0.0
- **logits:** available 6.7154 / unavailable -4.2629 / none -5.3409
- **margin:** 1.0
- **window_raws:** `['self_residence', 'not_own_house']`
- **fired:**
  - `self_residence → Asset=available`
  - `not_own_house → Asset=unavailable`
- **audit_label:** _TODO_

**冲突点：** 同窗同时打出 available 与 unavailable 的 include_raw → **同头冲突 / 映射优先级** 极可能是根因。

---

### Case 2

- **sample_id:** `2353351790090454417#turn14`（与 Case1 同会话后续窗）
- **conversation window:**
  - turn1 `[collector]`：噢，这个是您自己的房子吗？
  - turn2 `[customer]`：嗯，不是。
  - turn3 `[collector]`：是家里人的房子吗？
  - turn4 `[customer]`：对。
- **gold:** `Asset=unavailable`
- **prediction:** `Asset=available`
- **confidence:** available **1.0** / unavailable 0.0 / none 0.0
- **logits:** available 7.5194 / unavailable -5.0197 / none ≈ -6.73
- **audit_label:** _TODO_

**读法提示：** 「自住但非本人产权 / 家里人的房子」——典型 **available vs unavailable 边界**（使用权 vs 可变现产权）。

---

### Case 3

- **sample_id:** `2354064048518978448#turn4`
- **conversation window（客户侧摘要）：**  
  短期内还款有压力；在等甲方回款，预计 1–2 个月能进账几万到十几万；这段时间还款「没问题」但**当下立即还很难**；不想上征信。
- **gold:** `Asset=unavailable`
- **prediction:** `Asset=available`
- **confidence:** available **0.9975** / unavailable 0.0023 / none 0.0001
- **margin:** 0.9952
- **window_raws（截图）：**  
  `['income_reduction', 'income_loss', 'debt_inquiry', 'debt_overwhelm', 'savings_exhausted', 'income_delay', 'health_crisis']`
- **audit_label:** _TODO_

**读法提示：** 内容更像 **Income / FH / RC**，却标进 Asset；优先查 **label_error 或 include_raw 串头**，而非只怪模型。

---

### Case 4

- **sample_id:** `2360252780382284897#turn19`
- **conversation window:**
  - turn1 `[collector]`：您失业多久了？
  - turn2 `[customer]`：这俩月了。
  - turn3 `[collector]`：俩月？……银行这边看您家是有房子的吧？有房贷的嘛，您这个房贷现在逾期没有？
  - turn4 `[customer]`：没有。
- **gold:** `Asset=unavailable`
- **prediction:** `Asset=available`
- **confidence:** available **1.0** / unavailable 0.0 / none 0.0
- **logits（截图）：** available 7.4365 / unavailable -5.114 / none -5.3074
- **window_raws:** `['income_loss', 'no_overdue_mortgage']`
- **fired:**
  - `income_loss → Income=unavailable`
  - `no_overdue_mortgage → Asset=unavailable`
- **audit_label:** _TODO_

**冲突点：** gold/fired 倾向 unavailable，但催收话术「家里有房子」被模型强吃成 available（置信度 1.0）。

---

### Case 5

- **sample_id:** `2360252780382284897#turn21`（同会话后续）
- **conversation window:**
  - turn1 `[collector]`：……银行这边查到您家里是有房子的吧？有房贷的哪，这这个房贷现在逾期没有？
  - turn2 `[customer]`：没有。
  - turn3 `[collector]`：房贷没有？您这个房贷是在哪呢？
  - turn4 `[customer]`：啊？
- **gold:** `Asset=unavailable`
- **prediction:** `Asset=available`
- **confidence:** available **1.0** / unavailable 0.0 / none 0.0
- **logits:** available 7.5269 / unavailable -5.2446 / none -5.2248
- **margin:** 1.0
- **window_raws:** `['no_overdue_mortgage']`
- **fired:** `no_overdue_mortgage → Asset=unavailable (include_raw)`
- **audit_label:** _TODO_

**冲突点：** fired 明确指向 unavailable，模型却 available=1.0 —— **映射证据与 Softmax 预测完全反向**。

---

### Case 6

- **sample_id:** `2360841170379679925#turn11`
- **conversation window:**
  - turn1 `[collector]`：嗯嗯，就暂时是居住在这边，是一个人在居住吗？还是家里人这些一起在居住呢？
  - turn2 `[customer]`：和家人一起。
  - turn3 `[collector]`：目前名下的的话有没有房产呢？
  - turn4 `[customer]`：没有。
- **gold:** `Asset=unavailable`
- **prediction:** `Asset=available`
- **confidence:** available **1.0** / unavailable 0.0 / none 0.0
- **logits:** available 6.2321 / unavailable -4.1666 / none -5.4853
- **margin:** 1.0
- **window_raws:** `['personal_info', 'no_property']`（截图记法）
- **fired:** `no_property → Asset=unavailable`
- **audit_label:** _TODO_

**读法提示：** 客户口头明确「名下没有房产」；fired=unavailable 但 pred=available=1.0 → 强 **model_error** 候选（或训练里 available 压倒 no_property）。

---

### Case 7

- **sample_id:** `2360841170379679925#turn13`（同会话后续）
- **conversation window:**
  - turn1 `[collector]`：目前名下的还有没有房产呢？
  - turn2 `[customer]`：没有。
  - turn3 `[collector]`：所，我看一下，您之前停留了一个是在安徽淮北烈山区那边，那个地址的话是您自己之前在那边居住吗？还是说卖的房子呢，在那儿呢？
  - turn4 `[customer]`：之前是在那边上班，租的房子。
- **gold:** `Asset=unavailable`
- **prediction:** `Asset=available`
- **confidence:** available **1.0** / unavailable 0.0 / none 0.0
- **logits:** available 6.5673 / unavailable -4.1481 / none -5.0103
- **margin:** 1.0
- **window_raws:** `['no_property', 'asset_situation']`
- **fired:**
  - `no_property → Asset=unavailable`
  - `asset_situation → Asset=available`
- **audit_label:** _TODO_

**冲突点：** 再次出现 **no_property vs asset_situation 同窗对打**；催收追问历史住址/「卖的房子」可能触发 available 侧映射。

---

### Case 8

- **sample_id:** `2353956380444571755#turn31`
- **conversation window:**
  - turn1 `[collector]`：嗯...您在这找工作是吧?
  - turn2 `[customer]`：对啊。
  - turn3 `[collector]`：租好了房子是吧？
  - turn4 `[customer]`：没租啊，还没租。
- **gold:** `Asset=unavailable`
- **prediction:** `Asset=available`
- **confidence:** available **0.9969** / unavailable 0.0031 / none 0.0001
- **logits:** available 4.0286 / unavailable -1.7546 / none -5.6785
- **margin:** 0.9938
- **window_raws:** `['income_loss', 'no_rental']`
- **fired:** `income_loss` / `no_rental` → Asset=unavailable（截图）
- **audit_label:** _TODO_

**读法提示：** 「没租」应偏 unavailable；模型仍高置信 available。注意催收诱导句「租好了房子是吧」可能污染 encoder 表征。

---

### Case 9

- **sample_id:** `2353956380444571755#turn33`（同会话后续）
- **conversation window:**
  - turn1 `[collector]`：租好了房子了吧？
  - turn2 `[customer]`：没租啊，还没租。
  - turn3 `[collector]`：嗯，没租的话，那您现在的话，那您现在是租住哪里呢？
  - turn4 `[customer]`：现在住在朋友那里。
- **gold:** `Asset=unavailable`
- **prediction:** `Asset=available`
- **confidence:** available **0.7884** / unavailable 0.2112 / none 0.0004
- **logits:** available 1.7165 / unavailable 0.3995 / none -5.839
- **margin:** 0.5772
- **window_raws:** `['no_rental', 'staying_with_friend']`
- **fired:**
  - `no_rental → Asset=unavailable`
  - `staying_with_friend → Asset=available`
- **audit_label:** _TODO_

**读法提示：** 本条置信度相对不极端（0.79 vs 0.21）——典型 **ontology_boundary**：「住朋友家」算不算 available？`staying_with_friend` 映射到 available 是否合理需拍板。

---

### Case 10

- **sample_id:** `2366240120076501727#turn35`
- **conversation window:**
  - turn1 `[customer]`：我现在是属于没钱，啥也没有，现在房都退了，我一个人在外面那个情况。
- **gold:** `Asset=unavailable`
- **prediction:** `Asset=available`
- **confidence:** available **1.0** / unavailable 0.0
- **logits:** available 6.424 / unavailable -4.0587（截图）
- **margin:** 1.0
- **window_raws:** `['family_strain', 'housing_loss', 'repayment_inability']`
- **fired:** `housing_loss → Asset=unavailable`（截图）
- **audit_label:** _TODO_

**读法提示：** 字面「房都退了 / 啥也没有」极强 unavailable；fired 也对，pred 仍 available=1.0 → 优先 **model_error**（且可能与困难/还款串头混训）。

---

### Case 11

- **sample_id:** `2367077110202209977#turn39`（截图 id；与 available→unavailable Case2 同会话族）
- **conversation window:**
  - turn1 `[collector]`：可以，反正你要还到对应的卡号里面。你不要往你的储蓄卡里面存钱，你现在如果是储蓄卡里面充钱的话，这边会网络扣划的……
  - turn2 `[customer]`：喂，那个，我没有……那台商哪个，那，那个储蓄卡，我没有。你的意思是……有没有开通自动还款……你能看到吗？
- **gold:** `Asset=unavailable`
- **prediction:** `Asset=available`
- **confidence:** available **0.9968** / unavailable 0.003 / none 0.0002
- **logits:** available 3.7552 / unavailable -2.0516
- **margin:** 0.9938
- **window_raws:** `['no_bank_savings_account']`
- **fired:** `no_bank_savings_account → Asset=unavailable`
- **audit_label:** _TODO_

**读法提示：** 「没有储蓄卡」→ fired unavailable，pred available；需确认 **银行卡缺失是否应进 Asset**，还是 BankConstraint / 渠道类。

---

### Asset unavailable→available（11/11）汇总表

| Case | sample_id | 主题 | conf(avail) | fired 冲突 | 初判倾向 |
|-----:|-----------|------|------------:|------------|----------|
| 1 | …4417#turn12 | 自住非本人房 | 1.0 | self_residence↔not_own_house | ontology / 映射 |
| 2 | …4417#turn14 | 家里人的房子 | 1.0 | （同族） | ontology_boundary |
| 3 | …8448#turn4 | 等回款/当下难 | 0.9975 | 大量 Income/FH raws | 串头 / label |
| 4 | …4897#turn19 | 催收「家里有房」 | 1.0 | no_overdue_mortgage→unavail | 话术污染+model |
| 5 | …4897#turn21 | 房贷追问 | 1.0 | fired=unavail, pred=avail | model vs 映射 |
| 6 | …9925#turn11 | 名下无房产 | 1.0 | no_property→unavail | **model_error** |
| 7 | …9925#turn13 | 租房史/淮北 | 1.0 | no_property↔asset_situation | 映射对打 |
| 8 | …1755#turn31 | 没租 | 0.9969 | no_rental→unavail | model / 诱导问 |
| 9 | …1755#turn33 | 住朋友家 | **0.7884** | no_rental↔staying_with_friend | **ontology_boundary** |
| 10 | …1727#turn35 | 房都退了 | 1.0 | housing_loss→unavail | **model_error** |
| 11 | …9977#turn39 | 没有储蓄卡 | 0.9968 | no_bank_savings→unavail | ontology: 是否算 Asset |

> **Asset unavailable→available 11 条已全部据截图录入。**

---

## 4. Commitment：`resistant` → `committed`（3/3）

### Case 1

- **sample_id:** `2364446260415875725#turn71`
- **conversation window:**
  - turn1 `[collector]`：建议找工作/取现改善收入，八月再与银行协商（大意）
  - turn2 `[customer]`：嗯...噢, 不行, 我现在还不知道呀, 没办法给你答应。
- **gold:** `Commitment=resistant`
- **prediction:** `Commitment=committed`
- **confidence:** committed **1.0** / resistant 0.0 / none 0.0
- **logits:** committed 7.0405 / resistant -4.5325 / none -6.6191
- **margin:** 1.0
- **window_raws:** `['uncertain_future']`
- **fired:** `uncertain_future → Commitment=resistant`
- **audit_label:** _TODO_

**读法提示：** 「没办法给你答应」字面 resistant；fired 也对，pred=committed=1.0 → 强 **model_error** / 多数类压倒。

---

### Case 2

- **sample_id:** `2364446260415875725#turn73`（同会话）
- **conversation window:**
  - turn1 `[customer]`：嗯... 唉，不行，我现在未知数呀，没办法给你答应。
  - turn2 `[collector]`：您要相信，女士，后面这种情况可能会越来越好的。这个钱您还一次就少一分。
  - turn3 `[customer]`：现在就想... 想把那弄死，要不然越累越多，越累越多，没到上面。（抱怨/情绪）
- **gold:** `Commitment=resistant`
- **prediction:** `Commitment=committed`
- **confidence:** committed **1.0** / resistant 0.0 / none 0.0
- **logits:** committed 6.4914 / resistant -4.0141 / none -6.3235
- **margin:** 1.0
- **window_raws:** `['uncertain_future', 'collection_grievance']`
- **fired:**
  - `uncertain_future → Commitment=resistant`
  - `collection_grievance → Grievance=yes`
- **audit_label:** _TODO_

**读法提示：** 与 Case1 同模式；窗口混入 Grievance，仍不应变成 committed。

---

### Case 3

- **sample_id:** `2367947930405438891#turn68`
- **conversation window:**
  - turn1 `[collector]`：嗯，嗯嗯，了解您的意思。
  - turn2 `[customer]`：你让任何人临时去办一首事情，那肯定还是会有难度的呀。
- **gold:** `Commitment=resistant`
- **prediction:** `Commitment=committed`
- **confidence:** committed **1.0** / resistant 0.0 / none 0.0
- **logits:** committed 6.9676 / resistant -4.3939 / none -6.7973
- **margin:** 1.0
- **window_raws:** `['late_proposal', 'installment_request', 'contact_history', 'lack_of_clarity']`
- **fired:**
  - `late_proposal` / `installment_request` → NegotiationRequest
  - `lack_of_clarity → Commitment=resistant`
- **audit_label:** _TODO_

**读法提示：** 「有难度」+ `lack_of_clarity→resistant`，但同窗有 installment_request（NR）——易把「谈分期」误吃成 committed；查 **Commitment vs NR 边界**。

### Commitment 汇总

| Case | 主题 | conf(committed) | fired | 初判 |
|-----:|------|----------------:|-------|------|
| 1 | 没办法答应 | 1.0 | uncertain_future→resistant | model_error |
| 2 | 未知数/抱怨 | 1.0 | uncertain_future→resistant | model_error |
| 3 | 临时办事有难度 | 1.0 | lack_of_clarity→resistant + NR raws | model / 与 NR 串味 |

> **3/3 全是 committed=1.0，且 fired 已指向 resistant → resistant 类几乎被多数类淹没。**

---

## 5. Contactability：`reachable` → `unreachable`（4/4）

### Case 1

- **sample_id:** `2277025580033084888#turn32`
- **conversation window:**
  - turn1 `[collector]`：你说的是哪一天嘛，哪一天多少号？
  - turn2 `[customer]`：就是我还款之后，我还款之后，然后第2天他跟我说——
  - turn3 `[collector]`：你是10号还是16号还的嘛？
  - turn4 `[customer]`：多少星期几？
- **gold:** `Contactability=reachable`
- **prediction:** `Contactability=unreachable`
- **confidence:** reachable 0.0044 / unreachable **0.9924** / denied 0.0031 / none 0.0001
- **margin:** ≈0.988
- **audit_label:** _TODO_

**读法提示：** 客户在正常应答还款日期细节，联通良好；gold=reachable 更合理 → 偏 **model_error**（或把「听不清日期」误当失联）。

---

### Case 2

- **sample_id:** `2263153350494474037#turn41`（截图记法）
- **conversation window:**
  - turn1 `[collector]`：……大概在三点半左右会跟您最后一次确认……下午的时候就跳转了。
  - turn2 `[customer]`：好好好好。
- **gold:** `Contactability=reachable`
- **prediction:** `Contactability=unreachable`
- **confidence:** reachable 0.0308 / unreachable **0.9688** / denied 0.0003 / none 0.0001
- **logits:** reachable -0.2237 / unreachable 3.6789
- **margin:** ≈0.9377
- **fired（旁注）：** `communication_preference → reachable`（via legacy_bridge:third_party_involvement）
- **audit_label:** _TODO_

**读法提示：** 约定回访时间且客户应答「好好」= 可达；fired 也偏 reachable，pred 反了 → **model_error**。

---

### Case 3

- **sample_id:** `2263153350494474937#turn43`（同会话族）
- **conversation window:**
  - turn1 `[collector]`：三点半左右再确认，请接听（大意）
  - turn2 `[customer]`：好好好行。
  - turn3 `[collector]`：好嘞祝您生活愉快再见哦。
  - turn4 `[customer]`：嗯好再见。
- **gold:** `Contactability=reachable`
- **prediction:** `Contactability=unreachable`
- **confidence:** reachable 0.1022 / unreachable **0.8968** / denied 0.0008
- **logits:** reachable 0.8631 / unreachable 3.0351 / denied -3.9301 / none -5.3121
- **margin:** 0.7946
- **fired:** `communication_preference` via legacy_bridge:third_party_involvement（旁注）
- **audit_label:** _TODO_

**读法提示：** 正常道别收尾；pred=unreachable 不合理 → model_error；注意是否把「结束通话」学成 unreachable。

---

### Case 4

- **sample_id:** `2366240400617655014#turn6`
- **conversation window:**
  - turn1 `[customer]`：我只能明天上午弄完，今天下午有点事。你们不是已经打过电话了吗？我明天中午之前凑够钱先还上。（大意）
  - turn2 `[collector]`：对对对。噢，您下午忙是吧？
  - turn3 `[customer]`：……他们都已经打过一次了。
- **gold:** `Contactability=reachable`
- **prediction:** `Contactability=unreachable`
- **confidence:** reachable 0.0124 / unreachable **0.9871** / denied 0.0004 / none 0.0001
- **logits:** reachable -0.1427 / unreachable 4.232 / denied -3.6589 / none -5.2851
- **margin:** 0.9747
- **window_raws:** `['promise_to_pay_tomorrow', 'payment_tomorrow_morning', 'busy_afternoon']`
- **fired:**
  - `promise_to_pay_tomorrow → Commitment=committed`
  - `busy_afternoon → Contactability=reachable`
- **audit_label:** _TODO_

**读法提示：** 「下午忙」被正确 fired 为 reachable，模型仍判 unreachable——**busy ≠ unreachable** 边界需在 ontology/训练里钉死。

### Contactability reachable→unreachable 汇总

| Case | 主题 | conf(unreach) | 初判 |
|-----:|------|--------------:|------|
| 1 | 核对还款日期 | 0.99 | model_error |
| 2 | 约三点半确认 | 0.97 | model_error |
| 3 | 正常道别 | 0.90 | model_error |
| 4 | 下午忙/明早还 | 0.99 | busy vs unreachable |

> **4/4 已齐。** 方向与 v3.2 报告一致：模型偏把「忙/收尾」打成 unreachable。

---

## 6. Contactability：`unreachable` → `reachable`（14 条；截图已见 Case1–5）

### Case 1

- **sample_id:** `2295390960575848101#turn0`
- **conversation window:**  
  客户谈还款困难、还款日混乱、银行记录差 40 元争议等（长段陈述，在通话中）。
- **gold:** `Contactability=unreachable`
- **prediction:** `Contactability=reachable`
- **confidence:** reachable **0.9995** / unreachable 0.0003 / denied 0.0001 / none 0.0
- **logits:** reachable 5.4896 / unreachable -2.5867
- **margin:** 0.9992
- **window_raws:** `['missed_communication']`
- **fired:** `missed_communication → Contactability=unreachable`
- **audit_label:** _TODO_

**读法提示：** 客户正在通话详述 → 直觉更像 reachable；但 gold+fired=unreachable。优先怀疑 **gold/定义**：`missed_communication` 是否应标本窗 Contactability，还是历史失联记忆。

---

### Case 2

- **sample_id:** `2257962120650021284#turn30`
- **conversation window:**
  - turn1 `[customer]`：我要不要生活啊，美女？你说嘛。
  - turn2 `[collector]`：好，如果您这边确实处理不了的话，我们提醒不到您的呀，先生。……可以给您做到一个减息的。
  - turn3 `[customer]`：你现在你要求我今天要处理，我去哪里处理？现在几号啊？美女，你自己说现在几号啊？
- **gold:** `Contactability=unreachable`
- **prediction:** `Contactability=reachable`
- **confidence:** reachable **0.9464** / unreachable 0.0524 / denied 0.001 / none 0.0002
- **logits:** reachable 3.2251 / unreachable 0.3307
- **margin:** 0.894
- **window_raws:** `['time_constraint']`
- **fired:** `time_constraint → Contactability=unreachable`（via legacy_bridge:contact_difficulty）
- **audit_label:** _TODO_

**读法提示：** 人在线上争吵/谈时间约束；fired=unreachable，pred=reachable。需定：**time_constraint / 「今天处理不了」= unreachable 还是仍 reachable（仅排程难）**。

---

### Case 3

- **sample_id:** `2257962120650021284#turn32`（同会话 Case2 后续）
- **conversation window:**
  - turn1 `[customer]`：你现在在这要求找我处理，我去哪里处理？现在几号啊？美女，你自己说现在几号啊？
  - turn2 `[collector]`：没有要求您处理，您能还您就还，您还不就不算，好吧，先生。
  - turn3 `[customer]`：你们每次都是这样，每次人家主动跟你们沟通，你们这样不行，那样不行。好了，等人家彻底烂了，你们过来才跟我沟通，我才来给我方案。
- **gold:** `Contactability=unreachable`
- **prediction:** `Contactability=reachable`
- **confidence:** reachable **0.9998** / unreachable 0.0002
- **logits:** reachable 6.8575 / unreachable -2.7112
- **margin:** 0.9996
- **window_raws:** `['time_constraint']`
- **fired:** `time_constraint → Contactability=unreachable`（via legacy_bridge:contact_difficulty）
- **audit_label:** _TODO_

**读法提示：** 与 Case2 同模式——客户在线抱怨「主动沟通却没方案」；`time_constraint→unreachable` 与「人在通话」冲突，**legacy_bridge:contact_difficulty 定义过宽**嫌疑大。

---

### Case 4

- **sample_id:** `2263153358494474937#turn29`（截图 id）
- **conversation window:**  
  客户抱怨被要求极短时限内还款（如「11 点前要还」「只给一小时缓冲」等，长段施压抱怨）。
- **gold:** `Contactability=unreachable`
- **prediction:** `Contactability=reachable`
- **confidence:** reachable **0.9998** / unreachable 0.0001
- **logits:** reachable 6.1394 / unreachable -2.9396
- **margin:** 0.9997
- **window_raws:** `['time_constraint', 'payment_deadline']`
- **fired:**
  - `time_constraint → Contactability=unreachable`（legacy_bridge:contact_difficulty）
  - （旁注）另有 Commitment 侧 `future_payment_plan → committed` 类触发
- **audit_label:** _TODO_

**读法提示：** 「deadline 太紧」被标 unreachable；若 Contactability 语义是「能否联系上」，本窗人在说话应为 reachable → **ontology：time_constraint≠unreachable**。

---

### Case 5

- **sample_id:** `2291651190048678717#turn11`
- **conversation window:**
  - turn1 `[customer]`：咱们银行给找什么样的解决方案？他根本没有给我解决什么方案。我的意思，人家别的银行都给给一个解决方案，咱们银行找什么解决方案了？他们是拒绝解决方案，知道吗？我不是拒绝，他们是拒绝方案。
- **gold:** `Contactability=unreachable`
- **prediction:** `Contactability=reachable`
- **confidence:** reachable **0.9999** / unreachable 0.0 / denied 0.0 / none 0.0
- **logits:** reachable 6.822 / unreachable -3.4518 / denied -3.7732 / none -5.5699
- **margin:** 0.9999
- **window_raws:** `['location']`
- **audit_label:** _TODO_

**读法提示：** 典型协商/抱怨方案（更像 NR/Grievance），与「失联」无关；gold=unreachable 很可疑 → 优先 **label_error / 串头**。

### Case 1–5 小结（unreachable→reachable）

| Case | 主题 | conf(reach) | fired | 初判 |
|-----:|------|------------:|-------|------|
| 1 | 还款争议长谈 | 0.9995 | missed_communication→unreach | gold/定义 |
| 2 | 今天处理不了 | 0.9464 | time_constraint→unreach | ontology: 排程≠失联 |
| 3 | 抱怨沟通方案 | 0.9998 | time_constraint→unreach | 同 Case2 |
| 4 | 时限过紧抱怨 | 0.9998 | time_constraint→unreach | time≠unreachable |
| 5 | 抱怨银行无方案 | 0.9999 | location | **label/串头** |

### Case 6–14

截图未继续；请打开：

`01_residual_audit/Contactability__unreachable_to_reachable.md`

---

## 7. IdentityProcess / 分布 / Ontology（目录已生成）

| 路径 | 用途 |
|------|------|
| `02_identity_process/ontology_snippet.yaml` | 定义 + collector_action |
| `02_identity_process/positive_examples.md` | 正例原文（约 20 条） |
| `02_identity_process/boundary_checklist.md` | Event / Process / Fact 勾选 |
| `03_longtail_distribution/multi_state_train_test.md` | Asset/Contact/Commitment/RC train·test 分布 |
| `04_ontology_heads/*.yaml` | 五头 definition / action / include_raw |
| `00_DECISION_TEMPLATE.md` | 填决策表 + 业务星级 |

（上述正文截图未逐条展开，以包内原件为准。）

---

## 8. 据截图可得的初步判断（供同事拍板，非终审）

### Asset
1. 主矛盾 = **映射冲突 + Softmax 偏 available**（fired=unavailable 仍 pred≈1.0）。  
2. Case 9「住朋友家」为 ontology 边界；Case 6/10 偏 model_error。

### Commitment（3/3）
3. **全军覆没式偏向 committed**：客户明确「没办法答应 / 未知数」，fired=resistant，pred=committed=1.0 → **长尾未学会**，优先 resample / 查与 NR 串味（Case3）。

### Contactability
4. **reachable→unreachable（4/4）**：正常通话/约回访/道别/「下午忙」被打成 unreachable；busy≠unreachable 需钉死。  
5. **unreachable→reachable（已见 5/14）**：模式收敛——  
   - `time_constraint` / `missed_communication` **legacy_bridge 把「排程难/历史难联」打成窗内 unreachable**，但客户正在通话；  
   - Softmax 几乎一律 reachable≈1.0（与字面「在线」一致）；  
   - **更像 ontology/标注定义问题，不是模型学崩**（模型反而常更合理）。  
6. Case5 抱怨方案 + gold=unreachable → 串头/标错嫌疑。

### 建议动作顺序
1. Asset：include_raw 冲突 + 家人房/朋友住定义  
2. Commitment：resistant 样本审计 + 与 NR 边界  
3. Contactability：**收紧 `time_constraint`/`contact_difficulty` → unreachable 的映射**；区分「当前可联」vs「历史失联/排期难」  
4. 再谈补数/重训  

---

## 9. 建议发给同事的最小文件清单

**必给：**

1. `01_residual_audit/INDEX.md`  
2. 5 个 residual `*.md`（Asset×2 + Contactability×2 + Commitment×1）  
3. `02_identity_process/` 下 3 个主文件  
4. `03_longtail_distribution/multi_state_train_test.md`  

**选给：** `04_ontology_heads/heads_bundle.yaml`、`00_DECISION_TEMPLATE.md`、`residual_cases.jsonl`  

**可不给：** 根目录 `eval_test*.md/json`

---

## 10. 转录进度 & 一句话

| 块 | 进度 |
|----|------|
| Asset available↔unavailable | **13/13** |
| Commitment resistant→committed | **3/3** |
| Contactability reachable→unreachable | **4/4** |
| Contactability unreachable→reachable | **5/14**（Case6–14 待续） |
| Identity / 分布正文 | 未截图 |

> Contactability 双向已够定性：一边把「忙/道别」打成 unreachable（model）；另一边 gold 用 time_constraint 标 unreachable、人却在线（ontology/标注）。先收紧 Contact 定义与 legacy_bridge，再决定是否重训。
